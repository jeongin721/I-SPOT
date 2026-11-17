// 관리자 · 상담사 상세 — 디자인 AdminCounselor.dc.html(v2). 주소 #/AdminCounselor?user=<계정 ID>(계정 목록 · 대상자 목록에서).
//  - 계정 = GET /auth/users 에서 이 계정을 찾는다(한 계정만 받는 API 는 없다). 상담사로 열면 403 → 안내만.
//  - 담당 사례 = senior-overview 가운데 이 상담사의 진행 중 고령자 사례 수. 최근 접속 = last_login_at,
//    접속 IP = 최근 로그인 성공 기록(GET /auth/audit-logs). 기관 내부망 구분은 서버에 없어 '외부' 표시는 하지 않는다.
//  - 비밀번호: 서버는 재설정 링크 대신 임시 비밀번호를 발급한다(POST …/password-reset). 한 번 묻고, 임시 비밀번호는 이 화면에 한 번만 보인다.
//  - 계정 단추: 잠김이면 잠금 해제, 휴면이면 휴면 해제(임시 비밀번호 발급), 아니면 비활성화 · 다시 활성화(PATCH …). 본인 계정은 막는다.
//  - 소속 기관 · OTP · 알림 설정 · 비밀번호 마지막 변경일은 서버에 없어 '—' · 준비 중.
import { useLocation } from 'react-router-dom';
import { useDC } from '../dc';
import DesignLogic from '../design/AdminCounselor.logic';
import { auth } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { DASH } from '../data/format';
import { SIDE, errMsg, loginId, userState, isOpenCase, loadLoginIps, toDateOnly, toDateTime } from './AdminHome.parts';
import View from './AdminCounselor.view';

class Logic extends DesignLogic {
  async run(confirmText, call, done) {
    if (this.state.busy) return;
    if (confirmText && !window.confirm(confirmText)) return;
    this.setState({ busy: true, err: '', msg: '' });
    try {
      const res = await call();
      this.setState({ busy: false, ...done(res) });
      this.props.data.reload();
    } catch (e) {
      this.setState({ busy: false, err: errMsg(e, '요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.') });
    }
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { shell, data, userId } = this.props;
    const notify = (base.notify || []).map((n) => ({ ...n, st: '준비 중', cls: 'chip c-normal' }));
    const empty = {
      ...base, ...shell, ...SIDE, name: DASH, ini: '', uid: DASH, cases: DASH, mail: DASH, created: DASH, last: DASH, ip: DASH, ext: false,
      org: DASH, otp: '준비 중', otpCls: 'chip c-normal', pwText: DASH, pwLabel: '임시 비밀번호 발급', pwCls: 'btn-s', resetPw: undefined,
      notify, batch: DASH, st: DASH, stCls: 'chip c-normal', actLabel: '계정 비활성화', actCls: 'btn-s', toggleAct: undefined,
      hasMsg: !!s.msg, msg: s.msg, err: s.err || '',
    };
    if (data.error) return { ...empty, err: errMsg(data.error, '상담사 정보를 불러오지 못했어요.') };
    const d = data.data;
    if (!d) return empty;
    const u = d.users.find((x) => x.id === userId);
    if (!u) return { ...empty, err: '상담사를 찾지 못했어요. 계정 목록에서 다시 골라 주세요.' };

    const self = shell.session.me && shell.session.me.id === u.id;
    const state = userState(u);
    const mine = d.ov.rows.filter((r) => r.counselor_id === u.id && isOpenCase(r)).length;
    const ip = (d.ips && d.ips.get(u.id)) || DASH;

    const temp = s.temp && s.tempFor === u.id ? s.temp : null;
    const pwText = temp
      ? `임시 비밀번호 ${temp.temporary_password} · ${toDateTime(temp.expires_at)}까지 · 지금 한 번만 보여요`
      : u.must_change_password ? '임시 비밀번호 사용 중 · 첫 로그인 때 변경' : `마지막 변경 ${DASH}`;
    const resetPw = () => {
      if (self) { this.setState({ err: '본인 비밀번호는 설정의 비밀번호 변경에서 바꿔 주세요.' }); return; }
      this.run(`${u.name} 계정에 임시 비밀번호를 새로 발급할까요? 지금 비밀번호로는 더 로그인할 수 없어요.`,
        () => auth.resetPassword(u.id), (t) => ({ temp: t, tempFor: u.id, msg: `${u.name} 계정에 임시 비밀번호를 발급했어요 · 첫 로그인 때 비밀번호를 바꿔야 해요` }));
    };

    let actLabel; let toggleAct;
    if (self) {
      actLabel = '본인 계정';
      toggleAct = () => this.setState({ err: '본인 계정은 여기서 바꿀 수 없어요.' });
    } else if (u.is_active && u.is_locked) {
      actLabel = '잠금 해제';
      toggleAct = () => this.run(`${u.name} 계정의 잠금을 풀까요?`, () => auth.unlockUser(u.id), () => ({ msg: `${u.name} 계정의 잠금을 풀었어요` }));
    } else if (u.is_active && u.dormant_at) {
      actLabel = '휴면 해제';
      toggleAct = () => this.run(`${u.name} 계정의 휴면을 풀고 임시 비밀번호를 발급할까요?`, () => auth.reactivateUser(u.id),
        (t) => ({ temp: t, tempFor: u.id, msg: `${u.name} 계정의 휴면을 풀었어요 · 임시 비밀번호 발급됨` }));
    } else {
      actLabel = u.is_active ? '계정 비활성화' : '계정 다시 활성화';
      toggleAct = () => this.run(
        u.is_active ? `${u.name} 계정을 비활성화할까요? 이 계정으로 로그인할 수 없게 돼요.` : `${u.name} 계정을 다시 활성화할까요?`,
        () => auth.updateUser(u.id, { is_active: !u.is_active }),
        () => ({ msg: u.is_active ? `${u.name} 계정을 비활성화했어요 · 로그인할 수 없어요` : `${u.name} 계정을 다시 활성화했어요` }),
      );
    }

    return {
      ...empty,
      name: u.name, ini: (u.name || '?').slice(0, 1), uid: loginId(u.email), mail: u.email,
      cases: `${mine}${!u.is_active && mine ? ' · 재배정 필요' : ''}`,
      created: toDateOnly(u.created_at) || DASH, last: u.last_login_at ? toDateTime(u.last_login_at) : '접속 기록 없음', ip,
      st: state.st, stCls: state.stCls, pwText, pwLabel: self ? '본인 계정' : temp ? '다시 발급' : '임시 비밀번호 발급', resetPw,
      actLabel: s.busy ? '처리 중…' : actLabel, toggleAct,
    };
  }
}

export default function AdminCounselor(props) {
  const shell = useShell();
  const userId = new URLSearchParams(useLocation().search).get('user');
  const data = useAsync(async () => {
    if (!shell.ready) return null;
    const users = await auth.listUsers(); // 관리자가 아니면 403 — 여기서 멈춘다
    const [ov, ips] = await Promise.all([senior.overview(), loadLoginIps().catch(() => null)]);
    return { users, ov, ips };
  }, [shell.ready]);
  const v = useDC(Logic, { ...props, shell, data, userId });
  return <View v={v} />;
}
