// 관리자 · 대상자 목록 — 디자인 AdminCases.dc.html(v2). 상담사별 담당 고령자 사례 전체(관리자 전용).
//  - 목록: cases.list(subject_type SENIOR) 전체 쪽 + senior-overview(돌봄 상태) + GET /auth/users(담당자 활성 여부, 상담사면 403 → 안내만).
//  - 어르신 이름은 별칭(실명은 이 화면에서 받지 않는다). 접수일 = 신고접수일, 없으면 등록일. 관리 기간 = 접수일부터 오늘까지.
//  - 위기도: 고령자에는 위기도 판정이 없다. 서버 값(risk_level)이 있을 때만 보이고 없으면 '—'(필터 · 정렬도 그 값으로).
//  - 진행 단계: 담당자 비활성 → 재배정 필요, 종결 · 서비스 종료 → 서비스 종료, 돌봄 상태 후속조치 진행 → 후속관리,
//    회차가 없으면 초기 상담, 나머지는 사례관리 진행.
//  - 담당 상담사 이름을 누르면 상담사 상세(?user=). 디자인의 브라우저 저장소(ispot-staff)는 쓰지 않는다.
import { useDC } from '../dc';
import DesignLogic from '../design/AdminCases.logic';
import { auth } from '@cw/api/endpoints';
import { senior, CARE_STATUS_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { DASH, age, md } from '../data/format';
import { SIDE, errMsg, staffHref, todayIso, loadSeniorCases, toDateOnly } from './AdminHome.parts';
import View from './AdminCases.view';

const RISK = { HIGH: ['위기', 'chip c-hi'], MEDIUM: ['집중', 'chip c-hi'], LOW: ['관심', 'chip c-mid'], NONE: ['일반', 'chip c-lo'] };
const RK = { '위기': 0, '집중': 1, '관심': 2, '일반': 3 };
const ST = {
  ing: ['사례관리 진행', 'chip c-normal'], new: ['초기 상담', 'chip c-mid'], close: ['후속관리', 'chip c-check'],
  move: ['재배정 필요', 'chip c-urgent'], end: [CARE_STATUS_LABELS.SERVICE_ENDED, 'chip c-lo'],
};

function period(from, today) {
  const days = Math.max(0, Math.round((Date.parse(today) - Date.parse(from)) / 864e5));
  if (Number.isNaN(days)) return DASH;
  if (days < 30) return `${days}일`;
  const m = Math.max(1, Math.floor(days / 30.44));
  return m >= 12 ? `${Math.floor(m / 12)}년 ${m % 12}개월` : `${m}개월`;
}

class Logic extends DesignLogic {
  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { shell, data } = this.props;
    const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
    const today = todayIso();
    const empty = {
      ...base, ...shell, ...SIDE, rows: [], empty: false, kpis: [], staffF: [], countLabel: '', msg: '',
      riskF: base.riskF, sortF: base.sortF, q: s.q, setQ: base.setQ,
    };
    if (data.error) return { ...empty, msg: errMsg(data.error, '대상자 목록을 불러오지 못했어요.') };
    const d = data.data;
    if (!d) return { ...empty, countLabel: '불러오는 중…' };

    const { list, ov, users } = d;
    const care = new Map(ov.rows.map((r) => [r.case_id, r.care_status]));
    const byId = new Map(users.map((u) => [u.id, u]));
    const all = list.map((c) => {
      const u = byId.get(c.counselor_id);
      const cs = care.get(c.id);
      const closed = c.status === 'CLOSED' || cs === 'SERVICE_ENDED';
      const stage = closed ? 'end' : !u || !u.is_active ? 'move' : cs === 'FOLLOWUP_IN_PROGRESS' ? 'close' : !c.last_session_at ? 'new' : 'ing';
      const risk = c.risk_level ? RISK[c.risk_level] : null;
      const date = c.report_date || toDateOnly(c.created_at) || '';
      const a = age(c.child_birth_year);
      return {
        c, stage, date, risk: risk ? risk[0] : DASH, rCls: risk ? risk[1] : 'chip c-lo',
        row: {
          id: c.case_number, name: c.child_alias || DASH, ini: (c.child_alias || '?').slice(0, 1), age: a !== null ? `만 ${a}세` : '',
          who: c.counselor_name || DASH, whoHref: staffHref(c.counselor_id), pick: undefined,
          risk: risk ? risk[0] : DASH, rCls: risk ? risk[1] : 'chip c-lo',
          date: date || DASH, period: date ? period(date, today) : DASH, last: c.last_session_at ? md(c.last_session_at) : DASH,
          stage: ST[stage][0], stCls: ST[stage][1],
        },
      };
    });

    const q = (s.q || '').trim();
    let pick = all.filter((x) => (s.who === 'all' || x.c.counselor_id === s.who) && (s.risk === 'all' || x.risk === s.risk)
      && (!q || (x.c.child_alias || '').includes(q) || (x.c.case_number || '').includes(q)));
    const rk = (x) => (x.risk in RK ? RK[x.risk] : 9);
    pick = pick.slice().sort((a, b) => (s.sort === 'risk' ? rk(a) - rk(b) || b.date.localeCompare(a.date)
      : s.sort === 'long' ? a.date.localeCompare(b.date) : b.date.localeCompare(a.date)));
    const rows = pick.map((x) => x.row);

    const staffIds = [...new Set(list.map((c) => c.counselor_id).filter(Boolean))];
    const staff = staffIds.map((id) => ({ id, name: (byId.get(id) || {}).name || list.find((c) => c.counselor_id === id).counselor_name || DASH }));
    const hi = all.filter((x) => x.risk === '위기' || x.risk === '집중').length;
    const cl = all.filter((x) => x.stage === 'close').length;
    const mv = all.filter((x) => x.stage === 'move').length;
    const anyRisk = all.some((x) => x.risk !== DASH);
    return {
      ...empty,
      rows, empty: rows.length === 0,
      kpis: [
        { label: '전체 사례', v: `${all.length}건`, note: `상담사 ${staff.length}명 담당`, fg: 'inherit', bar: '' },
        { label: '위기도 위기·집중', v: anyRisk ? `${hi}건` : DASH, note: anyRisk ? `전체의 ${Math.round((hi / Math.max(1, all.length)) * 100)}%` : '고령자 사례는 위기도 판정 없음', fg: '#A33B2E', bar: 'inset 0 4px 0 #A33B2E' },
        { label: '후속관리', v: `${cl}건`, note: '돌봄 상태 후속조치 진행', fg: 'inherit', bar: '' },
        { label: '재배정 필요', v: `${mv}건`, note: '담당 상담사 비활성', fg: 'inherit', bar: '' },
      ],
      staffF: segOf('who', s.who, [['all', `전체 ${all.length}`]].concat(staff.map((x) => [x.id, `${x.name} ${list.filter((c) => c.counselor_id === x.id).length}`]))),
      countLabel: `사례 ${rows.length}건 표시 · ${today} 기준`,
    };
  }
}

export default function AdminCases(props) {
  const shell = useShell();
  const data = useAsync(async () => {
    if (!shell.ready) return null;
    const users = await auth.listUsers(); // 관리자가 아니면 403 — 여기서 멈춘다
    const [list, ov] = await Promise.all([loadSeniorCases(), senior.overview()]);
    return { users, list, ov };
  }, [shell.ready]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
