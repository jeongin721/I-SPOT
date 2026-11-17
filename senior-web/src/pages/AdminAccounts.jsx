// 관리자 · 상담사 계정 관리 — 디자인 AdminAccounts.dc.html(v2). 관리자 전용(상담사로 열면 403 → 안내만).
//  - 목록 = GET /auth/users(관리자 포함 전체). 담당 사례 = senior-overview 가운데 그 계정의 진행 중 고령자 사례 수(아동 사례는 세지 않는다).
//    최근 접속 = last_login_at, 접속 IP = 최근 로그인 성공 기록(GET /auth/audit-logs). 기관 내부망 구분은 서버에 없어 '외부' 표시는 하지 않는다.
//  - 기관 ID 칸 = 로그인 이메일(서버 계정은 이메일로 로그인한다). 표에는 이메일 앞부분을 보인다.
//  - 계정 생성: 아무도 모르는 임의 비밀번호로 POST /auth/users → 곧바로 POST …/password-reset 으로 임시 비밀번호 발급
//    (첫 로그인 때 변경 강제 · 만료). 임시 비밀번호는 이 화면에 한 번만 보이고 저장하지 않는다. 역할은 상담사.
//  - 이름 · 상세를 누르면 상담사 상세(?user=). 디자인의 브라우저 저장소(ispot-staff)는 쓰지 않는다.
import { useDC } from '../dc';
import DesignLogic from '../design/AdminAccounts.logic';
import { auth } from '@cw/api/endpoints';
import { ApiError } from '@cw/api/client';
import { generateInitialPassword } from '@cw/data/initialPassword';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { DASH } from '../data/format';
import { SIDE, errMsg, staffHref, loginId, userState, isOpenCase, loadLoginIps, toDateTime } from './AdminHome.parts';
import View from './AdminAccounts.view';

async function createAccount(name, email) {
  let user = null;
  for (let attempt = 1; !user; attempt += 1) {
    try {
      user = await auth.createUser({ email, name, role: 'COUNSELOR', password: generateInitialPassword() });
    } catch (e) {
      // 임의 비밀번호에 이메일 아이디 · 이름 조각이 우연히 들어가면 WEAK_PASSWORD — 새로 만들어 다시 보낸다.
      if (e instanceof ApiError && e.code === 'WEAK_PASSWORD' && attempt < 3) continue;
      throw e;
    }
  }
  try {
    return { user, temp: await auth.resetPassword(user.id) };
  } catch (e) {
    return { user, temp: null };
  }
}

class Logic extends DesignLogic {
  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { shell, data } = this.props;
    const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
    const create = async () => {
      if (s.busy) return;
      const n = s.name.trim();
      const email = s.uid.trim();
      if (!n || !email) { this.setState({ fe: true, err: '' }); return; }
      if (!/^[^\s@]+@[^\s@]+$/.test(email)) { this.setState({ fe: false, err: '기관 ID 칸에는 로그인에 쓸 이메일을 넣어 주세요.' }); return; }
      this.setState({ busy: true, fe: false, err: '', msg: '' });
      try {
        const { user, temp } = await createAccount(n, email);
        this.setState({
          busy: false, show: false, name: '', uid: '',
          msg: temp
            ? `${user.name} (${loginId(user.email)}) 계정을 만들었어요 · 임시 비밀번호 ${temp.temporary_password} · ${toDateTime(temp.expires_at)}까지 · 지금 한 번만 보여요`
            : `${user.name} (${loginId(user.email)}) 계정은 만들었지만 임시 비밀번호를 발급하지 못했어요. 상세에서 '임시 비밀번호 발급'을 눌러 주세요.`,
        });
        data.reload();
      } catch (e) {
        this.setState({ busy: false, err: errMsg(e, '계정을 만들지 못했어요. 잠시 후 다시 시도해 주세요.') });
      }
    };
    const toggleForm = () => this.setState({ show: !s.show, fe: false, err: '' });
    const empty = {
      ...base, ...shell, ...SIDE, rows: [], filters: [], create, toggleForm, formErr: !!s.fe,
      created: !!s.msg, createdMsg: s.msg, err: s.err || '', q: s.q || '', setQ: (e) => this.setState({ q: e.target.value }),
    };
    if (data.error) return { ...empty, err: errMsg(data.error, '계정 목록을 불러오지 못했어요.') };
    const d = data.data;
    if (!d) return empty;

    const q = (s.q || '').trim().toLowerCase();
    const all = d.users.map((u) => {
      const st = userState(u);
      const n = d.ov.rows.filter((r) => r.counselor_id === u.id && isOpenCase(r)).length;
      return { u, st, n };
    });
    const onCnt = all.filter((x) => x.st.on).length;
    const rows = all
      .filter((x) => s.f === 'all' || (s.f === 'on' ? x.st.on : !x.st.on))
      .filter((x) => !q || (x.u.name || '').toLowerCase().includes(q) || (x.u.email || '').toLowerCase().includes(q))
      .map(({ u, st, n }) => ({
        name: u.name, ini: (u.name || '?').slice(0, 1), uid: loginId(u.email),
        cases: u.role === 'ADMIN' && !n ? DASH : `${n}${!u.is_active && n ? ' · 재배정 필요' : ''}`,
        last: u.last_login_at ? toDateTime(u.last_login_at) : '접속 기록 없음',
        ip: (d.ips && d.ips.get(u.id)) || DASH, ext: false,
        st: st.st, stCls: st.stCls, op: st.op, href: staffHref(u.id), pick: undefined,
      }));
    return {
      ...empty, rows,
      filters: segOf('f', s.f, [['all', `전체 ${all.length}`], ['on', `활성 ${onCnt}`], ['off', `비활성 ${all.length - onCnt}`]]),
    };
  }
}

export default function AdminAccounts(props) {
  const shell = useShell();
  const data = useAsync(async () => {
    if (!shell.ready) return null;
    const users = await auth.listUsers(); // 관리자가 아니면 403 — 여기서 멈춘다
    const [ov, ips] = await Promise.all([senior.overview(), loadLoginIps().catch(() => null)]);
    return { users, ov, ips };
  }, [shell.ready]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
