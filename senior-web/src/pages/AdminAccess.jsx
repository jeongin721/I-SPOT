// 관리자 · 열람 기록 — 디자인 AdminAccess.dc.html(v2). 관리자 전용 화면.
//  - 목록 = 최근 7일 감사 기록(GET /auth/audit-logs) 가운데 실명 열람 둘:
//    CASE_PERSONAL_INFO_VIEWED(한 대상자 정보 화면 · entity_id = 사례) · CASE_LIST_PERSONAL_INFO_VIEWED(목록 · detail.case_ids).
//    고령자 대상자(cases.list SENIOR)에 걸린 것만 남긴다. 목록 열람은 고령자 대상자만 골라 한 줄로 묶는다.
//  - 대상 사례 칸에는 이름 대신 별칭 · 사례 번호만(실명 child_name 은 쓰지 않는다). 기록의 상세에도 값은 없다(서버가 막음).
//  - 담당 여부: 열람자가 관리자면 '관리 권한', 그 대상자 담당 상담사면 '담당', 아니면 '담당 외'.
//  - 녹취 재생 · 내려받기는 서버가 열람 기록을 남기지 않아 '—' · 준비 중. 외부 IP 구분도 없다(외부 표시 안 함).
//  - 관리자가 아니면 서버를 부르지 않고 안내만 보인다.
import { useDC } from '../dc';
import DesignLogic from '../design/AdminAccess.logic';
import { auth, cases } from '@cw/api/endpoints';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { DASH } from '../data/format';
import { errText } from './Step3Summary.basis';
import { utc, stamp, isAdmin, DENIED, ROLE, auditAll, sideVals } from './AdminSecurity';
import View from './AdminAccess.view';

const NOTE = '녹취 재생 · 내려받기 기록은 준비 중이에요. 지금은 고령자 대상자 실명 열람(최근 7일)만 보여요.';
const KIND = { one: ['실명 열람', 'chip c-normal', '대상자 정보'], list: ['목록 실명 열람', 'chip c-check', '대상자 목록'] };
const OWN = { own: ['담당', 'chip c-ok'], other: ['담당 외', 'chip c-urgent'], admin: ['관리 권한', 'chip c-normal'] };

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, q: '' };
  }

  renderValsBase() {
    const s = this.state;
    const { shell, data } = this.props;
    const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
    const base = {
      ...sideVals(shell),
      rows: [], total: DASH, whoNote: DASH, recCnt: DASH, dlCnt: DASH, otherCnt: DASH,
      onlyOther: s.other, tgBg: s.other ? '#1F3A56' : '#C5D4DE', tgX: s.other ? '16px' : '2px', toggleOther: () => this.setState({ other: !s.other }),
      kFilters: segOf('k', s.k, [['all', '전체'], ['one', '실명 열람'], ['list', '목록 실명 열람']]),
      q: s.q, setQ: (e) => this.setState({ q: e.target.value }), msg: NOTE,
    };
    if (shell.ready && !isAdmin(shell)) return { ...base, msg: DENIED };
    if (data.error) return { ...base, msg: errText(data.error, '열람 기록을 불러오지 못했어요.') };
    const d = data.data;
    if (!d) return { ...base, msg: data.loading ? '불러오는 중…' : NOTE };

    const byId = new Map(d.cases.map((c) => [c.id, c]));
    const roles = new Map(d.users.map((u) => [u.id, u.role]));
    const all = d.logs
      .map((r) => {
        const kind = r.action === 'CASE_PERSONAL_INFO_VIEWED' ? 'one' : 'list';
        const ids = kind === 'one' ? [r.entity_id] : ((r.detail && r.detail.case_ids) || []);
        const hit = ids.map((id) => byId.get(id)).filter(Boolean);
        if (!hit.length) return null; // 고령자 대상자가 아닌 열람
        const role = roles.get(r.actor_id);
        const own = role === 'ADMIN' ? 'admin' : hit.every((c) => c.counselor_id === r.actor_id) ? 'own' : 'other';
        const more = hit.length > 1 ? ` 외 ${hit.length - 1}명` : '';
        return {
          kind, own, at: utc(r.created_at), actor: r.actor_id,
          t: stamp(r.created_at), who: r.actor_name || DASH, rank: ROLE[role] || DASH,
          elder: `${hit[0].child_alias || hit[0].title || DASH}${more}`,
          cid: hit.slice(0, 3).map((c) => c.case_number).join(', ') + (hit.length > 3 ? ' …' : ''),
          kind0: KIND[kind], ip: r.ip_address || DASH, ext: false,
        };
      })
      .filter(Boolean)
      .sort((a, b) => b.at - a.at);

    const q = s.q.trim().toLowerCase();
    const rows = all
      .filter((r) => (s.k === 'all' || r.kind === s.k) && (!s.other || r.own === 'other'))
      .filter((r) => !q || [r.who, r.elder, r.cid].some((x) => String(x).toLowerCase().includes(q)))
      .map((r) => ({
        t: r.t, who: r.who, rank: r.rank, elder: r.elder, cid: r.cid,
        kind: r.kind0[0], kCls: r.kind0[1], screen: r.kind0[2], ip: r.ip, ext: r.ext,
        own: OWN[r.own][0], oCls: OWN[r.own][1],
      }));

    return {
      ...base, rows,
      total: all.length,
      whoNote: `열람자 ${new Set(all.map((r) => r.actor)).size}명`,
      otherCnt: all.filter((r) => r.own === 'other').length,
      msg: rows.length ? NOTE : `${NOTE} 해당하는 열람 기록이 없어요.`,
    };
  }
}

export default function AdminAccess(props) {
  const shell = useShell();
  const admin = isAdmin(shell);
  const data = useAsync(async () => {
    if (!shell.ready || !admin) return null;
    const since = new Date(Date.now() - 7 * 864e5).toISOString();
    const list = [];
    for (let page = 1; page <= 50; page++) {
      const res = await cases.list({ subject_type: 'SENIOR', page, page_size: 100 });
      list.push(...res.items);
      if (page >= (res.meta.total_pages || 1)) break;
    }
    const [one, many, users] = await Promise.all([
      auditAll({ action: 'CASE_PERSONAL_INFO_VIEWED', since }, 5),
      auditAll({ action: 'CASE_LIST_PERSONAL_INFO_VIEWED', since }, 5),
      auth.listUsers(),
    ]);
    return { cases: list, logs: [...one, ...many], users };
  }, [shell.ready, admin]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
