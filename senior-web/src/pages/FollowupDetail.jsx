// 후속관리 상세 — 디자인 FollowupDetail.dc.html(v2). ?case=<사례 id> 한 대상자.
//  - 조치사항 = 이 사례의 확인 · 조치사항(GET next-checks, 27절). 열린 것(기한 순) 먼저, 처리한 것은 뒤에.
//    체크 = 완료(PATCH status DONE) / 다시 누르면 미처리(OPEN). 줄 아래 '취소'(DROPPED) · '메모'(result_note) 단추를 더했다
//    (디자인에 자리가 없어 기존 클래스 btn btn-sm · inp 만 씀).
//  - '추가' = POST next-checks(kind ACTION, origin COUNSELOR, 회차 없음).
//  - 돌봄 상태 고르기 = PUT care-status.
//  - 재방문 · 연락 일정 = 이 사례의 오늘 이후 상담 일정(GET /schedule/events). '저장' = POST followup-visits
//    (방문 · 재방문 → VISIT, 전화 → PHONE). 메모는 그 일정의 제목으로 저장한다(PATCH /schedule/events/{id}).
//  - 전문기관 연계 기록은 서버에 칸이 없어 '준비 중'.
import { useDC } from '../dc';
import DesignLogic from '../design/FollowupDetail.logic';
import { cases, schedule } from '@cw/api/endpoints';
import { senior, CARE_STATUS_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH } from '../data/format';
import { mdw, errText } from './Step3Summary.basis';
import { todayIso, ageLine, byDue } from './Followup';
import View from './FollowupDetail.view';

const CLS = { REVISIT_NEEDED: 'chip c-hi', FOLLOWUP_IN_PROGRESS: 'chip c-mid', CONSULT_DONE: 'chip c-ok', SERVICE_ENDED: 'chip c-ai' };
const BY_LABEL = Object.fromEntries(Object.entries(CARE_STATUS_LABELS).map(([k, l]) => [l, k]));
const TYPE = { VISIT: '방문', PHONE: '전화', REGULAR: '재상담', INITIAL: '초기상담', CLOSING: '종결상담' };
const SEND_TYPE = { 방문: 'VISIT', 재방문: 'VISIT', 전화: 'PHONE' };
const KIND = { CHECK: '확인할 것', ACTION: '할 조치' };

function addDays(iso, n) {
  const [y, m, d] = iso.split('-').map(Number);
  const x = new Date(y, m - 1, d + n);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
}

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    const wk = addDays(todayIso(), 7);
    this.state = { ...this.state, actText: '', actDue: wk, linkText: '', adding: false, sDate: wk, sTime: '10:00', sType: '재방문', sMemo: '', busy: false, err: '', notes: {} };
  }

  async run(work, ok, fail) {
    if (this.state.busy) return;
    this.setState({ busy: true, err: '' });
    try {
      await work();
      this.setState({ busy: false });
      if (ok) this.fuToast(ok);
      this.props.data.reload();
    } catch (e) {
      this.setState({ busy: false, err: errText(e, fail) });
    }
  }

  renderValsBase() {
    const s = this.state;
    const { shell, data, caseId } = this.props;
    const d = data.data || {};
    const c = d.c;
    const profile = d.profile;
    const status = profile ? profile.care_status : null;
    const today = todayIso();
    const checks = (d.checks || []).slice();
    const open = checks.filter((x) => x.status === 'OPEN').sort(byDue);
    const closed = checks.filter((x) => x.status !== 'OPEN').sort((a, b) => ((a.checked_at || '') < (b.checked_at || '') ? 1 : -1));
    const patch = (x, body, ok) => this.run(() => senior.updateNextCheck(caseId, x.id, body), ok, '확인사항을 바꾸지 못했어요.');
    const setNote = (id, v) => this.setState({ notes: { ...this.state.notes, [id]: v } });

    const acts = open.concat(closed).map((x) => {
      const done = x.status === 'DONE';
      const head = x.status === 'DONE' ? '처리 완료' : x.status === 'DROPPED' ? '취소함' : x.due_date ? `기한 ${mdw(x.due_date)}` : '기한 없음';
      const note = s.notes[x.id];
      return {
        text: x.text, done,
        sub: [head, KIND[x.kind], x.result_note ? `메모: ${x.result_note}` : ''].filter(Boolean).join(' · '),
        toggle: () => patch(x, { status: x.status === 'OPEN' ? 'DONE' : 'OPEN' }, x.status === 'OPEN' ? '처리 완료로 표시했어요' : '미처리로 되돌렸어요'),
        hasTools: true, canDrop: x.status === 'OPEN',
        drop: () => patch(x, { status: 'DROPPED' }, '취소로 표시했어요'),
        noteOpen: note !== undefined, note: note || '',
        openNote: () => setNote(x.id, note !== undefined ? undefined : x.result_note || ''),
        setNote: (e) => setNote(x.id, e.target.value),
        saveNote: () => this.run(async () => {
          await senior.updateNextCheck(caseId, x.id, { result_note: String(note || '').trim() || null });
          setNote(x.id, undefined);
        }, '메모를 저장했어요', '메모를 저장하지 못했어요.'),
      };
    });

    const events = ((d.events && d.events.items) || [])
      .filter((e) => e.case_id === caseId && e.kind === 'CONSULT' && e.date >= today)
      .sort((a, b) => ((a.date + (a.time || '')) < (b.date + (b.time || '')) ? -1 : 1));
    const scheds = events.map((e) => ({
      text: [`${mdw(e.date)}${e.time ? ' ' + e.time.slice(0, 5) : ''}`, TYPE[e.consult_type] || '상담', e.title || ''].filter(Boolean).join(' · '),
    }));

    const name = c ? c.child_alias || DASH : DASH;
    const a = c ? ageLine(c, profile) : DASH;
    const counselor = c ? (c.counselor ? `${c.counselor.name} ${c.counselor.role === 'ADMIN' ? '관리자' : '상담사'}` : c.counselor_name || DASH) : DASH;

    let msg = s.err;
    if (!msg && !caseId) msg = '후속관리 목록에서 어르신을 골라 주세요.';
    if (!msg && data.error) msg = errText(data.error, '불러오지 못했어요.');

    return {
      ...shell,
      cntLink: '', cntFollowup: '', msg, listHref: href('Followup'),
      todayLabel: mdw(today), counselorLine: counselor,
      toast: s.toast || '', hasToast: !!s.toast,
      selName: name, selAge: a.split(' · ').map((x, i) => (i === 0 && /^\d+$/.test(x) ? `만 ${x}세` : x)).join(' · '),
      selStatus: status ? CARE_STATUS_LABELS[status] : '', selStCls: CLS[status] || 'chip c-normal', selStatusChip: status ? CARE_STATUS_LABELS[status] : DASH,
      setStatus: (e) => {
        const v = BY_LABEL[e.target.value];
        if (!v || v === status || !caseId) return;
        this.run(() => senior.setCareStatus(caseId, v), `상태를 “${CARE_STATUS_LABELS[v]}”(으)로 바꿨어요`, '돌봄 상태를 저장하지 못했어요.');
      },
      acts, noActs: !data.loading && acts.length === 0,
      actText: s.actText, actDue: s.actDue, linkText: s.linkText,
      setActText: (e) => this.setState({ actText: e.target.value }), setActDue: (e) => this.setState({ actDue: e.target.value }),
      setLinkText: (e) => this.setState({ linkText: e.target.value }),
      addAct: () => {
        const t = String(s.actText || '').trim();
        if (!t) { this.fuToast('조치사항을 입력해 주세요'); return; }
        if (!caseId) return;
        this.run(async () => {
          await senior.saveNextChecks(caseId, [{ kind: 'ACTION', text: t, due_date: s.actDue || null, origin: 'COUNSELOR', edited: false }], null);
          this.setState({ actText: '', actDue: addDays(todayIso(), 7) });
        }, '조치사항을 추가했어요', '조치사항을 추가하지 못했어요.');
      },
      scheds, noScheds: !data.loading && scheds.length === 0,
      adding: !!s.adding, notAdding: !s.adding, sDate: s.sDate, sTime: s.sTime, sType: s.sType, sMemo: s.sMemo,
      setSDate: (e) => this.setState({ sDate: e.target.value }), setSTime: (e) => this.setState({ sTime: e.target.value }),
      setSType: (e) => this.setState({ sType: e.target.value }), setSMemo: (e) => this.setState({ sMemo: e.target.value }),
      openAdd: () => this.setState({ adding: true, sDate: addDays(todayIso(), 7), sTime: '10:00', sType: '재방문', sMemo: '' }),
      closeAdd: () => this.setState({ adding: false }),
      saveSched: () => {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(s.sDate || '')) { this.fuToast('날짜를 입력해 주세요'); return; }
        if (!caseId) return;
        const memo = String(s.sMemo || '').trim();
        this.run(async () => {
          const r = await senior.scheduleFollowup(caseId, { consult_type: SEND_TYPE[s.sType] || 'VISIT', date: s.sDate, time: s.sTime || null, check_ids: [] });
          if (memo) await schedule.update(r.visit.schedule_event_id, { title: memo });
          this.setState({ adding: false });
        }, '일정을 등록했어요 · 일정 메뉴에도 추가됐어요', '일정을 만들지 못했어요.');
      },
      links: [{ text: '전문기관 연계 기록은 준비 중입니다' }], noLinks: false,
      addLink: () => this.fuToast('전문기관 연계 기록은 준비 중이에요'),
    };
  }
}

export default function FollowupDetail(props) {
  const shell = useShell();
  const { caseId } = useIds();
  const data = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const today = todayIso();
    const [c, profile, checks, events] = await Promise.all([
      cases.get(caseId),
      senior.profile(caseId).catch(() => null),
      senior.nextChecks(caseId),
      schedule.list({ from: today, to: addDays(today, 365) }).catch(() => null),
    ]);
    return { c, profile, checks, events };
  }, [shell.ready, caseId]);
  const v = useDC(Logic, { ...props, shell, data, caseId });
  return <View v={v} />;
}
