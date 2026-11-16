// 회차 상세 — 디자인 SessionDetail.dc.html. ?case= · ?session= (회차가 없으면 그 사례의 가장 최근 회차).
//  - 머리: sessions.get(회차 번호 · 날짜 · 상담 방식 · 상태), 담당은 사례의 담당 상담사.
//  - 네 단계 카드: 1 기록 확인(녹취 상태 + 이 회차 측정) · 2 영역 변화(sessionDomains) · 3 상담일지(요약 summary) · 4 다음 상담 준비(이 회차 확인사항).
//  - 단계 위치는 회차 상태로(CaseInfo 와 같은 규칙). 이름은 별칭(실명 열람 기록은 탭1 에서만).
import { useDC } from '../dc';
import DesignLogic from '../design/SessionDetail.logic';
import { cases, sessions as sessionsApi, summary as summaryApi } from '@cw/api/endpoints';
import { senior, CHANGE_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH, md, ymd, dayName } from '../data/format';
import { caseLinks, kindLabel, measureText, statusChip, stepOf, stepLook } from './CaseInfo.parts';
import View from './SessionDetail.view';

const soft = (p) => p.catch(() => null);
const LABELS = ['기록 확인', '정서·위기 신호 확인', '상담일지 작성', '다음 상담 준비'];
// 디자인의 번호 동그라미 모양: 끝남(✓) · 지금(진한 테두리) · 남음.
const LOOK = {
  done: { nBg: '#ECF5FA', nFg: '#55687A', ring: 'none' },
  cur: { nBg: '#1F3A56', nFg: '#D6ECFA', ring: 'inset 0 0 0 2px #1F3A56' },
  todo: { nBg: '#DDE6EC', nFg: '#66788A', ring: 'none' },
};

function sttStep(d) {
  if (!d) return [DASH, 'chip c-normal'];
  if (d.transcript_confirmed) return ['검수 완료', 'chip c-ok'];
  if (d.status === 'STT_FAILED') return ['변환 실패', 'chip c-check'];
  if (d.has_transcript) return ['검수 중', 'chip c-check'];
  if (d.has_audio) return ['변환 대기', 'chip c-check'];
  return ['녹음 전', 'chip c-normal'];
}

class Logic extends DesignLogic {
  sel() {
    const { data } = this.props;
    return data || {};
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const { caseId, shell } = this.props;
    const d = this.sel();
    const c = d.c;
    const s = d.detail;
    const sid = s && s.id;
    const links = caseLinks(caseId, sid);
    const name = (c && c.child_alias) || DASH;
    const no = (c && c.case_number) || DASH;

    const domains = d.domains;
    const checks = (d.checks || []).filter((x) => x.source_session_id === sid);
    // 뒤에 회차가 더 있는 확정 회차는 다음 상담 준비까지 지나간 것으로 본다.
    const later = !!(s && (d.sessions || []).some((x) => x.session_number > s.session_number));
    const cur = stepOf(s, { domainsConfirmed: !!(domains && domains.confirmed), checksSaved: checks.length > 0 || later });

    // 1 기록 확인: 녹취 상태 + 이 회차 측정
    const [sttSt, sttCls] = sttStep(s);
    const ms = (d.measurements || []).filter((m) => m.session_id === sid);
    const mText = ms.map(measureText).filter(Boolean).join(' / ');
    // 2 영역 변화
    const rows = (domains && domains.domains) || [];
    const domText = rows
      .map((r) => {
        const sv = r.saved;
        const ch = sv ? sv.change : r.draft && r.draft.change;
        if (!sv && !r.draft) return null;
        const note = sv ? sv.change_note : r.draft.change_note;
        return `${r.label} ${ch ? CHANGE_LABELS[ch] : '확인 전'}${note ? ` (${note})` : ''}`;
      })
      .filter(Boolean)
      .join('  /  ');
    const domSt = domains && domains.confirmed ? ['확정', 'chip c-ok'] : rows.some((r) => r.draft) ? ['확인 전', 'chip c-check'] : ['대기', 'chip c-normal'];
    // 3 상담일지(요약)
    const sum = d.summary && d.summary.summary;
    const sumSt = !sum ? ['작성 전', 'chip c-normal'] : sum.status === 'APPROVED' ? ['확정', 'chip c-ok'] : ['검토 대기', 'chip c-check'];
    // 4 다음 상담 준비
    const resolved = (d.checks || []).filter((x) => x.checked_session_id === sid);
    const chkText = checks.map((x) => `${x.kind === 'ACTION' ? '[할 일] ' : ''}${x.text}${x.due_date ? ` (기한 ${md(x.due_date)})` : ''}`).join('  /  ');
    const chkSt = checks.length ? [`확인사항 ${checks.length}`, 'chip c-ok'] : later ? [DASH, 'chip c-normal'] : ['대기', 'chip c-normal'];

    const defs = [
      { st: sttSt, stCls: sttCls, preview: mText ? `이번 측정 · ${mText}` : `이번 측정 ${DASH}` },
      { st: domSt[0], stCls: domSt[1], preview: domText || DASH },
      { st: sumSt[0], stCls: sumSt[1], preview: (sum && sum.overview) || DASH },
      {
        st: chkSt[0],
        stCls: chkSt[1],
        preview: [chkText, resolved.length ? `이 회차에서 확인한 것 ${resolved.length}개` : ''].filter(Boolean).join('  /  ') || DASH,
      },
    ];
    const steps = defs.map((x, i) => {
      const look = s ? stepLook(i + 1, cur) : 'todo';
      return { ...x, href: links.stepHrefs[i], label: LABELS[i], mark: look === 'done' ? '✓' : String(i + 1), ...LOOK[look], bg: '#FFFFFF' };
    });
    const [status, st] = s ? statusChip(s.status) : [DASH, 'chip c-normal'];
    const when = s ? s.consulted_at || s.created_at : null;
    return {
      ...base,
      ...shell,
      ...links,
      steps,
      name,
      caseCrumb: `${name} ${no}`,
      cur: {
        no: s ? `${s.session_number}회차` : DASH,
        meta: s ? `${ymd(when)} · ${kindLabel(s.consultation_type)} · 담당 ${(c && c.counselor_name) || DASH}` : DASH,
        status,
        st,
      },
      loadErr: this.props.loadErr,
    };
  }

  // 회차 고르기: 이 사례의 서버 회차 목록. 고르면 ?session= 을 바꾼다.
  slVals() {
    const { caseId } = this.props;
    const d = this.sel();
    const list = d.sessions || [];
    const sid = d.detail && d.detail.id;
    const open = !!(this.state && this.state.__slOpen);
    const meta = (x) => {
      const w = x.consulted_at || x.created_at;
      return `${md(w)}(${dayName(w)}) ${kindLabel(x.consultation_type)}`;
    };
    const curS = list.find((x) => x.id === sid);
    const name = (d.c && d.c.child_alias) || DASH;
    return {
      slOpen: open,
      slExp: open ? 'true' : 'false',
      slToggle: () => this.setState({ __slOpen: !open }),
      slBtn: curS ? `${curS.session_number}회차 · ${meta(curS)}` : DASH,
      slHead: `${name} · 총 ${list.length}회`,
      slItems: [...list].sort((a, b) => b.session_number - a.session_number).map((x) => {
        const [stx, stCls] = statusChip(x.status);
        return {
          no: `${x.session_number}회차`, meta: meta(x), st: stx, stCls,
          on: x.id === sid ? 'true' : 'false', cls: x.id === sid ? 'on' : '',
          pick: () => {
            this.setState({ __slOpen: false });
            window.location.hash = href('SessionDetail', { caseId, sessionId: x.id }).slice(1);
          },
        };
      }),
    };
  }
}

export default function SessionDetail(props) {
  const shell = useShell();
  const { caseId: qCase, sessionId: qSession } = useIds();
  const main = useAsync(async () => {
    if (!shell.ready || (!qCase && !qSession)) return null;
    let detail = qSession ? await sessionsApi.get(qSession) : null;
    const caseId = qCase || (detail && detail.case_id);
    const [c, page] = await Promise.all([cases.get(caseId), soft(cases.listSessions(caseId, { page_size: 100 }))]);
    const list = page ? page.items : [];
    if (!detail && list.length) {
      const latest = [...list].sort((a, b) => b.session_number - a.session_number)[0];
      detail = await sessionsApi.get(latest.id);
    }
    if (!detail) return { c, sessions: list, caseId };
    const [summary, measurements, domains, checks] = await Promise.all([
      detail.has_summary ? soft(summaryApi.get(detail.id)) : null,
      soft(senior.measurements(caseId)),
      soft(senior.sessionDomains(detail.id)),
      soft(senior.nextChecks(caseId)),
    ]);
    return { c, sessions: list, detail, summary, measurements, domains, checks, caseId };
  }, [shell.ready, qCase, qSession]);
  const caseId = qCase || (main.data && main.data.caseId);
  let loadErr = '';
  if (!qCase && !qSession) loadErr = '회차를 고르지 않았어요. 상담 이력에서 다시 들어와 주세요.';
  else if (main.error) loadErr = main.error.message || '회차 정보를 불러오지 못했어요.';
  const v = useDC(Logic, { ...props, shell, caseId, data: main.data, loadErr });
  return <View v={v} />;
}
