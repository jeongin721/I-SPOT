// 관리자 · 접속 기록 · 보안 이벤트 — 디자인 AdminSecurity.dc.html(v2). 관리자 전용 화면.
//  - 목록 = 감사 기록(GET /auth/audit-logs) 가운데 로그인(LOGIN, 성공 · 실패는 status 칸) · 계정 잠금(ACCOUNT_LOCKED) ·
//    잠금 해제(ACCOUNT_UNLOCKED). 최근 것부터 로그인 100줄 · 잠금/해제 각 50줄.
//  - 로그인 실패(24시간) = LOGIN · FAILURE 를 24시간 안으로 센 수(서버 total). 아래 줄은 가장 많이 실패한 IP.
//  - 잠긴 계정 = GET /auth/users 의 is_locked. 잠금 기록 줄의 '잠금 해제' 는 POST /auth/users/{id}/unlock(지금 잠긴 계정만).
//  - 계정 칸 아래 글은 그 계정의 로그인 이메일(직원 계정). 없는 계정으로 실패한 줄은 '알 수 없음'.
//  - 외부 IP(기관 내부망 구분) · OTP · IP 차단은 서버에 없어 '—' · 준비 중.
//  - 관리자가 아니면 서버를 부르지 않고 안내만 보인다.
import { useDC } from '../dc';
import DesignLogic from '../design/AdminSecurity.logic';
import { auth } from '@cw/api/endpoints';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { DASH } from '../data/format';
import { errText } from './Step3Summary.basis';
import View from './AdminSecurity.view';

// ---- 관리자 화면 넷(AdminSecurity · AdminAccess · AdminStats · AdminApp)이 같이 쓰는 작은 도우미 ----
/** 서버 시각은 시간대 표시가 없으면 UTC 다. */
export const utc = (s) => new Date(/[zZ]$|[+-]\d\d:?\d\d$/.test(s) ? s : `${s}Z`);
const p2 = (n) => String(n).padStart(2, '0');
/** '11/17 09:14'(이 컴퓨터 시각). */
export const stamp = (s) => {
  const d = utc(s);
  return `${d.getMonth() + 1}/${d.getDate()} ${p2(d.getHours())}:${p2(d.getMinutes())}`;
};
export const isAdmin = (shell) => !!(shell.session.me && shell.session.me.role === 'ADMIN');
export const DENIED = '이 화면은 관리자 계정으로만 볼 수 있어요.';
export const ROLE = { ADMIN: '관리자', COUNSELOR: '상담사' };
/** 감사 기록을 쪽마다 모은다(최대 pages 쪽). */
export async function auditAll(params, pages = 1) {
  const out = [];
  for (let page = 1; page <= pages; page++) {
    const res = await auth.auditLogs({ ...params, page, page_size: 100 });
    out.push(...res.items);
    if (page >= (res.meta.total_pages || 1)) break;
  }
  return out;
}
/** 사이드바 공통 값. 배지 숫자는 서버가 주지 않아 비운다. */
export const sideVals = (shell) => ({ ...shell, navAppCnt: '', navSecCnt: '' });

const REASON = {
  ACCOUNT_LOCKED: '차단 · 잠긴 계정',
  INACTIVE_USER: '차단 · 비활성 계정',
  ACCOUNT_DORMANT: '차단 · 휴면 계정',
  TEMP_PASSWORD_EXPIRED: '차단 · 임시 비밀번호 만료',
};

function kindOf(r) {
  if (r.action === 'ACCOUNT_LOCKED') return 'lock';
  if (r.action === 'ACCOUNT_UNLOCKED') return 'unlock';
  return r.status === 'SUCCESS' ? 'ok' : 'fail';
}

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, q: '', busy: '', note: '' };
  }

  async unlock(userId) {
    this.setState({ busy: userId, note: '' });
    try {
      await auth.unlockUser(userId);
      this.setState({ busy: '', note: '잠금을 풀었어요.' });
      this.props.data.reload();
    } catch (e) {
      this.setState({ busy: '', note: errText(e, '잠금을 풀지 못했어요. 잠시 뒤 다시 해 주세요.') });
    }
  }

  renderValsBase() {
    const s = this.state;
    const { shell, data } = this.props;
    const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
    const kb = (v) => ({ cls: s.f === v ? 'on' : '', pressed: s.f === v ? 'true' : 'false', pick: () => this.setState({ f: s.f === v ? 'all' : v }) });
    const base = {
      ...sideVals(shell),
      rows: [], failCnt: DASH, failNote: DASH, extCnt: DASH, otpCnt: DASH, lockCnt: DASH,
      kfail: kb('fail'), kout: kb('out'), kotp: kb('otp'), klock: kb('lock'),
      filters: segOf('f', s.f, [['all', '전체 접속 기록'], ['fail', '로그인 실패'], ['out', '외부 IP 접속'], ['otp', 'OTP 실패']]),
      q: s.q, setQ: (e) => this.setState({ q: e.target.value }), msg: '',
    };
    if (shell.ready && !isAdmin(shell)) return { ...base, msg: DENIED };
    if (data.error) return { ...base, msg: errText(data.error, '접속 기록을 불러오지 못했어요.') };
    const d = data.data;
    if (!d) return { ...base, msg: data.loading ? '불러오는 중…' : '' };

    const users = new Map(d.users.map((u) => [u.id, u]));
    const all = [...d.logins, ...d.locks]
      .sort((a, b) => utc(b.created_at) - utc(a.created_at))
      .map((r) => {
        const kind = kindOf(r);
        // 잠금 해제 줄은 행동한 사람이 관리자, 대상 계정은 entity_id 다.
        const who = kind === 'unlock' ? users.get(r.entity_id) : r.actor_id ? users.get(r.actor_id) : null;
        const name = kind === 'unlock' ? (who ? who.name : DASH) : r.actor_name || (who ? who.name : '알 수 없음');
        const n = r.detail && r.detail.failed_login_count;
        const ev = {
          ok: ['로그인 성공', 'chip c-ok'],
          fail: ['로그인 실패', 'chip c-urgent'],
          lock: [n ? `로그인 실패 ${n}회` : '계정 잠금', 'chip c-urgent'],
          unlock: ['잠금 해제', 'chip c-ok'],
        }[kind];
        const res = {
          ok: '허용',
          fail: REASON[r.error_code] || (r.actor_id ? '차단 · 비밀번호 틀림' : '차단 · 없는 계정'),
          lock: n ? `계정 잠금 · ${n}회 실패` : '계정 잠금',
          unlock: `잠금 해제 · ${r.actor_name || '관리자'}`,
        }[kind];
        const target = kind === 'lock' ? users.get(r.entity_id) : null;
        const canUnlock = !!(target && target.is_locked);
        return {
          kind, t: stamp(r.created_at), name, uid: who ? who.email : DASH, ev: ev[0], evCls: ev[1],
          ip: r.ip_address || DASH, net: DASH, netCls: 'note', res,
          hasAct: canUnlock, actLabel: s.busy === r.entity_id ? '푸는 중…' : '잠금 해제',
          act: () => { if (!s.busy) this.unlock(r.entity_id); },
        };
      });

    const q = s.q.trim().toLowerCase();
    const pass = (r) => s.f === 'all' || (s.f === 'fail' && (r.kind === 'fail' || r.kind === 'lock')) || (s.f === 'lock' && r.kind === 'lock');
    const rows = all.filter(pass).filter((r) => !q || [r.name, r.uid, r.ip].some((x) => String(x).toLowerCase().includes(q)));

    const ipCnt = {};
    d.fail24.forEach((r) => { if (r.ip_address) ipCnt[r.ip_address] = (ipCnt[r.ip_address] || 0) + 1; });
    const top = Object.entries(ipCnt).sort((a, b) => b[1] - a[1])[0];
    const failNote = d.fail24Total === 0 ? '24시간 안 실패 없음' : top && top[1] > 1 ? `IP ${top[0]} 반복 시도 ${top[1]}회` : '반복 시도 없음';

    let msg = s.note;
    if (s.f === 'out') msg = '외부 IP 접속 구분은 준비 중이에요(기관 내부망 정보가 아직 서버에 없어요).';
    else if (s.f === 'otp') msg = 'OTP 는 아직 쓰지 않아요 · 준비 중.';
    else if (!rows.length) msg = msg || '해당하는 접속 기록이 없어요.';

    return {
      ...base, rows, msg,
      failCnt: d.fail24Total, failNote,
      lockCnt: d.users.filter((u) => u.is_locked).length,
    };
  }
}

export default function AdminSecurity(props) {
  const shell = useShell();
  const admin = isAdmin(shell);
  const data = useAsync(async () => {
    if (!shell.ready || !admin) return null;
    const since = new Date(Date.now() - 864e5).toISOString();
    const [logins, locked, unlocked, fail, users] = await Promise.all([
      auth.auditLogs({ action: 'LOGIN', page: 1, page_size: 100 }),
      auth.auditLogs({ action: 'ACCOUNT_LOCKED', page: 1, page_size: 50 }),
      auth.auditLogs({ action: 'ACCOUNT_UNLOCKED', page: 1, page_size: 50 }),
      auth.auditLogs({ action: 'LOGIN', status: 'FAILURE', since, page: 1, page_size: 100 }),
      auth.listUsers(),
    ]);
    return {
      logins: logins.items, locks: [...locked.items, ...unlocked.items],
      fail24: fail.items, fail24Total: fail.meta.total, users,
    };
  }, [shell.ready, admin]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
