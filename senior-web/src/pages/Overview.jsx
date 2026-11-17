// 관리자 현황 — 디자인 Overview.dc.html(v2). 관리자 전용 화면.
//  - 담당자 목록은 GET /auth/users(관리자 전용)로 받는다. 상담사로 열면 서버가 403 → 안내 문구만 보이고 값은 비운다.
//  - 대상자 · 돌봄 상태 · 열린 확인사항 수 · 기한 지남 = GET /senior-overview(27절, 관리자는 모든 고령자 사례).
//  - 이번 주(월~일) 방문 · 상담 = GET /schedule/events 가운데 고령자 사례에 붙은 상담 일정(관리자는 모든 일정이 온다).
//  - 기한 순 미처리 조치사항 = 사례마다 next-checks(status=OPEN). 행을 누르면 그 대상자의 후속관리 상세.
//  - '신규 연계 대기' · 기관 이름은 서버에 값이 없어 '—'(준비 중).
//  - 수를 세기만 하고 판정하지 않는다.
import { useDC } from '../dc';
import DesignLogic from '../design/Overview.logic';
import { auth, schedule } from '@cw/api/endpoints';
import { senior, CARE_STATUS_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import { DASH } from '../data/format';
import { mdw, errText } from './Step3Summary.basis';
import { todayIso, byDue } from './Followup';
import View from './Overview.view';

const DIST = [['REVISIT_NEEDED', '#A33B2E'], ['FOLLOWUP_IN_PROGRESS', '#5FA4D6'], ['CONSULT_DONE', '#235E8C'], ['SERVICE_ENDED', '#B5C8D5']];
const ROLE = { ADMIN: '관리자', COUNSELOR: '상담사' };

function weekRange() {
  const d = new Date();
  const mon = new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() + 6) % 7));
  const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);
  const iso = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
  return [iso(mon), iso(sun)];
}
const md0 = (iso) => { const [, m, d] = iso.split('-').map(Number); return `${m}/${d}`; };

class Logic extends DesignLogic {
  renderValsBase() {
    const { shell, data } = this.props;
    const d = data.data;
    const [wk0, wk1] = weekRange();
    const empty = {
      ...shell, cntLink: '', cntFollowup: '',
      orgLine: `${DASH} · ${md0(wk0)} 주`, weekLabel: `이번 주 ${md0(wk0)} ~ ${md0(wk1)} 기준`,
      kpis: [], staffRows: [], dist: [], totalElders: DASH, pending: [], noPending: false, msg: '',
    };
    if (data.error) {
      const denied = data.error.status === 403;
      return { ...empty, msg: denied ? '관리자 현황은 관리자 계정으로만 볼 수 있어요. 담당 대상자는 후속관리 화면에서 확인해 주세요.' : errText(data.error, '현황을 불러오지 못했어요.') };
    }
    if (!d) return empty;

    const today = todayIso();
    const { ov, users, events, checks } = d;
    const rows = ov.rows;
    const caseIds = new Set(rows.map((r) => r.case_id));
    const week = ((events && events.items) || []).filter((e) => e.kind === 'CONSULT' && e.case_id && caseIds.has(e.case_id) && e.date >= wk0 && e.date <= wk1);
    const weekLeft = week.filter((e) => e.date >= today).length;
    const ended = rows.filter((r) => r.care_status === 'SERVICE_ENDED').length;
    const open = [];
    rows.forEach((r, i) => (checks[i] || []).forEach((x) => open.push({ ...x, row: r })));
    open.sort(byDue);
    const overdue = ov.counts.overdue_checks;
    const firstDue = open.find((x) => x.due_date);
    const kpis = [
      { label: '관리 대상자', v: `${rows.length - ended}명`, note: `서비스 종료 ${ended}명 제외` },
      { label: '이번 주 방문 · 상담', v: `${week.length}건`, note: `${md0(wk0)} ~ ${md0(wk1)} · 오늘 이후 ${weekLeft}건` },
      { label: '미처리 조치', v: `${ov.counts.open_checks}건`, note: overdue ? `기한 지남 ${overdue}건` : firstDue ? `가장 빠른 기한 ${mdw(firstDue.due_date)}` : ov.counts.open_checks ? '기한 없음' : '모두 처리됨' },
      { label: '신규 연계 대기', v: DASH, note: '준비 중' },
    ];

    const roleOf = new Map(users.map((u) => [u.id, ROLE[u.role] || '상담사']));
    const staff = users.filter((u) => u.is_active && (u.role === 'COUNSELOR' || rows.some((r) => r.counselor_id === u.id)));
    const staffRows = staff.map((u) => {
      const mine = rows.filter((r) => r.counselor_id === u.id);
      const ids = new Set(mine.map((r) => r.case_id));
      const re = mine.filter((r) => r.care_status === 'REVISIT_NEEDED').length;
      const act = mine.reduce((n, r) => n + r.open_checks, 0);
      return { name: u.name, role: ROLE[u.role] || '상담사', elders: mine.length, sched: week.filter((e) => ids.has(e.case_id)).length, re, act, hasRe: re > 0, noRe: re === 0, hasAct: act > 0, noAct: act === 0 };
    });

    const tot = ov.counts.total;
    const pct = (x) => `${tot ? Math.round((x / tot) * 100) : 0}%`;
    const dist = DIST.map(([k, c]) => {
      const v = ov.counts.by_care_status[k] || 0;
      const name = CARE_STATUS_LABELS[k];
      return { name, c, v, p: pct(v), w: pct(v), tip: `${name} ${v}명` };
    });

    const pending = open.map((x) => ({
      due: x.due_date ? mdw(x.due_date) : DASH, elder: x.row.alias || DASH, t: x.text,
      who: x.row.counselor_name ? `${x.row.counselor_name} ${roleOf.get(x.row.counselor_id) || '상담사'}` : DASH,
      href: href('FollowupDetail', { caseId: x.row.case_id }),
    }));

    return { ...empty, kpis, staffRows, dist, totalElders: tot, pending, noPending: pending.length === 0 };
  }
}

export default function Overview(props) {
  const shell = useShell();
  const data = useAsync(async () => {
    if (!shell.ready) return null;
    const users = await auth.listUsers(); // 관리자가 아니면 403 — 여기서 멈춘다
    const [wk0, wk1] = weekRange();
    const [ov, events] = await Promise.all([senior.overview(), schedule.list({ from: wk0, to: wk1 }).catch(() => null)]);
    const checks = await Promise.all(ov.rows.map((r) => (r.open_checks ? senior.nextChecks(r.case_id, 'OPEN').catch(() => []) : [])));
    return { ov, users, events, checks };
  }, [shell.ready]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
