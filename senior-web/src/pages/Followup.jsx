// 후속관리(목록) — 디자인 Followup.dc.html(v2). 내가 담당한 고령자 대상자마다 돌봄 상태 · 미처리 확인사항 · 다음 일정.
//  - GET /senior-overview(27절): 상담사는 담당 사례만, 관리자는 전부 오므로 담당자 = 나(counselor_id) 인 행만 쓴다.
//  - '미처리 조치' 첫 줄 = 열린 확인사항(next-checks status=OPEN) 가운데 기한이 가장 빠른 것, 나머지는 '외 n건'.
//  - 나이 · 성별 · 사는 형태: cases.list(subject_type SENIOR) + senior-profile(대상자가 적어 사례마다 부른다).
//  - 다음 일정 = overview 의 next_visit(오늘 이후 첫 상담 일정).
//  - 행을 누르면 후속관리 상세(?case=). 디자인의 localStorage 예시 데이터(ispot-fu)는 쓰지 않는다.
//  - 사이드바 숫자 배지(안부 연계 · 후속관리)는 공통 값이 없어 비운다.
import { useDC } from '../dc';
import DesignLogic from '../design/Followup.logic';
import { cases } from '@cw/api/endpoints';
import { senior, CARE_STATUS_LABELS, LIVING_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import { DASH, age, genderLabel } from '../data/format';
import { mdw, errText } from './Step3Summary.basis';
import View from './Followup.view';

const ORDER = ['REVISIT_NEEDED', 'FOLLOWUP_IN_PROGRESS', 'CONSULT_DONE', 'SERVICE_ENDED'];
const CLS = { REVISIT_NEEDED: 'chip c-hi', FOLLOWUP_IN_PROGRESS: 'chip c-mid', CONSULT_DONE: 'chip c-ok', SERVICE_ENDED: 'chip c-ai' };
const TYPE = { VISIT: '방문', PHONE: '전화', REGULAR: '재상담', INITIAL: '초기상담', CLOSING: '종결상담' };

export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** '82 · 여 · 독거' — 서버 값이 없는 칸은 뺀다. 하나도 없으면 '—'. */
export function ageLine(c, profile) {
  const a = c ? age(c.child_birth_year) : null;
  const g = c ? genderLabel(c.child_gender) : DASH;
  const parts = [a !== null ? String(a) : '', g !== DASH ? g : '', profile && profile.living_arrangement ? LIVING_LABELS[profile.living_arrangement] : ''].filter(Boolean);
  return parts.length ? parts.join(' · ') : DASH;
}

/** 기한 빠른 것부터(기한 없는 것은 뒤로). */
export function byDue(a, b) {
  const x = a.due_date || '9999-12-31';
  const y = b.due_date || '9999-12-31';
  return x < y ? -1 : x > y ? 1 : 0;
}

class Logic extends DesignLogic {
  renderValsBase() {
    const s = this.state;
    const { shell, data } = this.props;
    const people = (data.data && data.data.people) || [];
    const list = s.f === 'all' ? people : people.filter((p) => p.status === s.f);
    const filters = [['all', '전체']].concat(ORDER.map((k) => [k, CARE_STATUS_LABELS[k]])).map(([k, l]) => {
      const n = k === 'all' ? people.length : people.filter((p) => p.status === k).length;
      return { label: `${l} ${n}`, cls: s.f === k ? 'on' : '', pressed: s.f === k ? 'true' : 'false', pick: () => this.setState({ f: k }) };
    });
    const rows = list.map((p) => {
      const nx = p.next;
      return {
        name: p.name, age: p.age, ini: p.name.slice(0, 1),
        status: p.status ? CARE_STATUS_LABELS[p.status] : DASH, stCls: CLS[p.status] || 'chip c-normal',
        open: p.open.length ? p.open[0].text : p.openCount ? `${p.openCount}건` : '없음',
        more: p.open.length > 1 ? `외 ${p.open.length - 1}건` : '',
        next: nx ? `${mdw(nx.date)} ${TYPE[nx.consult_type] || '상담'}` : DASH,
        bg: 'transparent', pressed: 'false', href: p.href, go: () => {}, pick: () => {},
      };
    });
    let msg = '';
    if (data.error) msg = errText(data.error, '후속관리 목록을 불러오지 못했어요.');
    return {
      ...shell,
      filters, rows, noRows: !data.loading && rows.length === 0,
      todayLabel: mdw(todayIso()),
      counselorLine: shell.meName ? `${shell.meName} ${shell.meRole}` : DASH,
      cntLink: '', cntFollowup: '', msg,
      toast: s.toast || '', hasToast: !!s.toast,
    };
  }
}

export default function Followup(props) {
  const shell = useShell();
  const meId = shell.session.me ? shell.session.me.id : null;
  const data = useAsync(async () => {
    if (!shell.ready || !meId) return null;
    const [ov, list] = await Promise.all([senior.overview(), cases.list({ subject_type: 'SENIOR', page_size: 100 })]);
    const byId = new Map(((list && list.items) || []).map((c) => [c.id, c]));
    const mine = ov.rows.filter((r) => r.counselor_id === meId && r.case_status !== 'CLOSED');
    const extra = await Promise.all(
      mine.map((r) => Promise.all([senior.nextChecks(r.case_id, 'OPEN').catch(() => null), senior.profile(r.case_id).catch(() => null)])),
    );
    const people = mine.map((r, i) => {
      const [checks, profile] = extra[i];
      return {
        name: r.alias || DASH,
        age: ageLine(byId.get(r.case_id), profile),
        status: r.care_status,
        open: checks ? checks.slice().sort(byDue) : [],
        openCount: r.open_checks,
        next: r.next_visit,
        href: href('FollowupDetail', { caseId: r.case_id }),
      };
    });
    const rank = (p) => (p.status ? ORDER.indexOf(p.status) : ORDER.length);
    people.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name, 'ko'));
    return { people };
  }, [shell.ready, meId]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
