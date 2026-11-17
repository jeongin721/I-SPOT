// 2단계 — 디자인 Step2Signals.dc.html('정서·위기 신호 확인'). 고령자에는 학대 분석 · 위기도가 없으므로 이 화면은
// **생활 · 정서 영역 변화 확정**(GET/PUT /sessions/{id}/care-domains, API_CONTRACT 27절)과 분석 결과의
// result.senior.safety_mentions(자해 · 급한 건강, 'AI 표시, 판정 아님')에 맞춰 연결한다.
//  - 위기도 카드: 고령자에 없는 칸이라 '—' · 상담사 위기도 단추는 '준비 중'(눌러도 바뀌지 않음). 카드의 플래그 줄은 바로 확인할 말 개수.
//  - 신호별 줄 = 영역 다섯 줄(식사 · 수면 · 외출 · 사회활동 · 정서). 1~4 단추 = 비슷함 · 달라짐 · 처음 기록 · 이야기 없음.
//    앞 기록이 있으면 '처음 기록' 을, 없으면 '비슷함 · 달라짐' 을 고를 수 없다(서버 400 과 같은 규칙).
//    이번 기록 글은 초안(또는 확정한 기록) 그대로 쓴다 — 글 고치는 칸은 디자인에 없다(3단계 상담일지에서 고친다).
//  - 회차별 추이: 확정한 영역 기록(GET /cases/{id}/care-domains)의 앞 회차 둘 + 이번 회차(지금 고른 값).
//  - 바로 확인할 말: safety_mentions 최대 3줄(그 이상은 '외 n개'), 시각은 원문 발화 시작 시각. 위험 · 보호요인 칸은 준비 중.
//  - '변화 확인' 카드(11/17 새 디자인): 영역마다 지난 회차 확정 기록 ↔ 이번 기록(확정 또는 초안), 달라진 점(change_note),
//    근거(지난 기록 · 이번 근거 발화 원문 · 시각). '맞음' = 초안의 변화 구분을 그대로 고름, '수정 필요' = 아래 영역 줄의 선택지를 연다.
//  - '확정 · 상담일지 작성 →': 다섯 영역을 모두 고르면 PUT 하고 3단계로 간다. 실패하면 상태 줄에 이유.
//  - 분석이 아직 돌고 있으면(AI_PROCESSING) 2.5초마다 다시 읽는다.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/Step2Signals.logic';
import { analysis, cases, transcript } from '@cw/api/endpoints';
import { CONSULTATION_TYPE_LABELS } from '@cw/api/types';
import { errorMessage } from '@cw/data/useRemote';
import { parseBackendTime } from '@cw/data/time';
import { senior, CHANGE_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href, useIds } from '../data/nav';
import { DASH } from '../data/format';
import View from './Step2Signals.view';

const CHANGES = ['SIMILAR', 'CHANGED', 'NEW', 'NOT_MENTIONED'];
const CHANGE_DESC = {
  SIMILAR: '앞 기록과 비슷해요',
  CHANGED: '앞 기록과 달라졌어요',
  NEW: '견줄 앞 기록이 없어 처음 적어요',
  NOT_MENTIONED: '이번 상담에서 이야기가 없었어요',
};
const SCOPE = { MEAL: '끼니 · 식사 방식', SLEEP: '잠 · 깨는 시각', OUTING: '바깥 나들이 · 복지관', SOCIAL: '가족 · 이웃과의 연락', MOOD: '기분 · 외로움' };
const SAFETY_LABELS = { SELF_HARM: '자해 · 자살', URGENT_HEALTH: '급한 건강' };
const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
const POLL_MS = 2500;
const pad = (n) => String(n).padStart(2, '0');
const clock = (ms) => { const t = Math.max(0, Math.floor((ms || 0) / 1000)); return `${pad(Math.floor(t / 60))}:${pad(t % 60)}`; };

function md(value) {
  const d = value ? parseBackendTime(value) || new Date(value) : null;
  return d && !Number.isNaN(d.getTime()) ? `${d.getMonth() + 1}/${d.getDate()}` : DASH;
}
function sessionSub(row) {
  if (!row) return DASH;
  const d = parseBackendTime(row.consulted_at || row.created_at);
  const kind = row.consultation_type ? CONSULTATION_TYPE_LABELS[row.consultation_type] : row.title || '상담';
  return d ? `${d.getMonth() + 1}/${d.getDate()}(${DAYS[d.getDay()]}) ${kind}` : kind;
}

/** 분석 · 영역 · 원문을 함께 읽는다. 분석 중이면 되풀이해 읽는다. */
function useSessionData(sessionId, ready) {
  const [state, setState] = useState({ an: null, dom: null, tx: null, error: null, loading: true });
  const seq = useRef(0);
  const load = useCallback(() => {
    if (!ready || !sessionId) return;
    const id = ++seq.current;
    const soft = (p) => p.catch(() => null);
    Promise.all([soft(analysis.get(sessionId)), senior.sessionDomains(sessionId), soft(transcript.get(sessionId))]).then(
      ([an, dom, tx]) => {
        if (id !== seq.current) return;
        setState({ an, dom, tx, error: null, loading: false });
        if (an && an.session_status === 'AI_PROCESSING') setTimeout(() => id === seq.current && load(), POLL_MS);
      },
      (error) => id === seq.current && setState((s) => ({ ...s, error, loading: false })),
    );
  }, [sessionId, ready]);
  useEffect(() => {
    load();
    return () => { seq.current += 1; };
  }, [load]);
  return { ...state, reload: load };
}

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, pick: {}, open: {}, busy: false, err: '' };
  }

  renderVals() {
    const v = super.renderVals();
    const { ids } = this.props;
    return {
      ...v,
      markBack: () => {
        const back = href('Step2Signals', ids);
        try { window.localStorage.setItem('ispot-back', back); } catch (e) {}
        try { window.sessionStorage.setItem('ispot-back', back); } catch (e) {}
        window.__ispotBack = back;
      },
    };
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { shell, ids, caseQ, sesList, data, timeline } = this.props;
    const dom = data.dom;
    const rows = dom ? dom.domains : [];
    const segs = data.tx && data.tx.transcript ? data.tx.transcript.segments : [];
    const segAt = {};
    segs.forEach((g) => { segAt[g.segment_id] = g.start_ms; });
    const atOf = (segIds) => (segIds || []).filter((x) => segAt[x] !== undefined).map((x) => clock(segAt[x]));
    const sesRows = sesList.data ? [...sesList.data.items].sort((a, b) => a.session_number - b.session_number) : [];
    const cur = sesRows.find((r) => r.id === ids.sessionId);
    const curNo = dom ? dom.session_number : cur ? cur.session_number : null;
    const sesNo = curNo ? `${curNo}회차` : DASH;

    // 영역 줄
    const choiceOf = (r) => (s.pick[r.domain] !== undefined ? s.pick[r.domain] : r.saved ? r.saved.change : r.draft ? r.draft.change : null);
    const textOf = (r) => {
      if (r.saved && r.saved.change !== 'NOT_MENTIONED' && r.saved.text) return r.saved.text;
      return (r.draft && r.draft.text) || (r.saved && r.saved.text) || null;
    };
    const allowed = (r, k) => (k === 'NOT_MENTIONED' ? true : r.previous ? k !== 'NEW' : k === 'NEW');
    const choose = (r, k) => () => {
      if (!allowed(r, k)) {
        this.setState({ err: r.previous ? `${r.label}: 앞 기록이 있어 '처음 기록' 은 고를 수 없어요.` : `${r.label}: 견줄 앞 기록이 없어 '처음 기록' 또는 '이야기 없음' 만 고를 수 있어요.` });
        return;
      }
      if (k !== 'NOT_MENTIONED' && !textOf(r)) {
        this.setState({ err: `${r.label}: 이번 기록 글이 없어 '이야기 없음' 만 고를 수 있어요.` });
        return;
      }
      this.setState({ pick: { ...this.state.pick, [r.domain]: k }, err: '' });
    };
    const types = rows.map((r) => {
      const ch = choiceOf(r);
      const open = !!s.open[r.domain];
      const text = textOf(r);
      const evText = r.saved ? '확정' : r.draft ? (r.draft.source === 'AI' ? 'AI 초안' : '자동 초안') : '초안 없음';
      const evTone = r.saved ? ['#1F3A56', '#FFFFFF'] : r.draft ? ['#ECF5FA', '#55687A'] : ['#FFFFFF', '#8094A3'];
      const refs = [];
      refs.push(r.previous ? `앞 기록 · ${r.previous.session_number}회차(${md(r.previous.date)}) “${r.previous.text}”` : '앞 기록 없음');
      const basisIds = (r.saved && r.saved.segment_ids && r.saved.segment_ids.length ? r.saved.segment_ids : r.draft ? r.draft.segment_ids : []) || [];
      const at = atOf(basisIds);
      if (at.length) refs.push(`근거 발화 ${sesNo} ${at.join(' · ')}`);
      const note = (r.saved && r.saved.change_note) || (r.draft && r.draft.change_note);
      if (note && ch === 'CHANGED') refs.push(`달라진 점 · ${note}`);
      if (r.saved) refs.push(`확정 ${md(r.saved.confirmed_at)}`);
      return {
        label: r.label, ev: evText, evBg: evTone[0], evFg: evTone[1], flag: false, flagText: '',
        colHead: '이번 변화',
        sevText: ch ? CHANGE_LABELS[ch] : '선택 전', sevSuffix: '',
        fixed: !!(ch && r.draft && r.draft.change !== ch),
        boxes: CHANGES.map((k, i) => {
          const on = ch === k; const ok = allowed(r, k);
          return { n: i + 1, aria: `${r.label} ${CHANGE_LABELS[k]}`, bg: on ? '#5FA4D6' : '#FFFFFF', fg: on ? '#FFFFFF' : ok ? '#8094A3' : '#D9E3EA', bd: on ? 'transparent' : ok ? '#C5D4DE' : '#E6EDF2', pick: choose(r, k) };
        }),
        col3Head: '이번 기록',
        matched: ch === 'NOT_MENTIONED' ? '이번 상담에서 이야기 없음' : text ? `“${text}”` : '이번 기록 글 없음',
        refs, open, toggleLabel: open ? '선택지 닫기' : '선택지 보기',
        toggle: () => this.setState({ open: { ...this.state.open, [r.domain]: !open } }),
        anchors: CHANGES.map((k, i) => ({
          n: i + 1, text: `${CHANGE_LABELS[k]} — ${CHANGE_DESC[k]}${allowed(r, k) ? '' : ' (고를 수 없음)'}`,
          bg: ch === k ? '#E8F4FC' : 'transparent', fg: ch === k ? '#1F3A56' : allowed(r, k) ? '#66788A' : '#B5C3CD', fw: ch === k ? 700 : 400,
          pick: choose(r, k),
        })),
      };
    });

    // 변화 확인 카드
    const segText = {};
    segs.forEach((g) => { segText[g.segment_id] = g.text; });
    const curDate = cur ? md(cur.consulted_at || cur.created_at) : '';
    const curSess = curNo ? `${curNo}회차${curDate ? ` · ${curDate}` : ''}` : DASH;
    const prevOf = (r) => (r.previous ? `${r.previous.session_number}회차${r.previous.date ? ` · ${md(r.previous.date)}` : ''}` : DASH);
    const latestPrev = rows.map((r) => r.previous).filter(Boolean).sort((a, b) => b.session_number - a.session_number)[0];
    const chgItems = rows.map((r) => {
      const ch = choiceOf(r);
      const text = textOf(r);
      const note = (r.saved && r.saved.change_note) || (r.draft && r.draft.change_note);
      const ck = (s.chk || {})[r.domain] || '';
      const basisIds = (r.saved && r.saved.segment_ids && r.saved.segment_ids.length ? r.saved.segment_ids : r.draft ? r.draft.segment_ids : []) || [];
      const ev = [];
      if (r.previous) ev.push({ side: '지난', quote: r.previous.text, where: `${prevOf(r)} 확정 기록`, link: false, href: '' });
      basisIds.filter((x) => segText[x]).forEach((x) => ev.push({ side: '이번', quote: segText[x], where: `${curNo || ''}회차 녹취 ${clock(segAt[x])}`, link: true, href: href('Step1Record', ids) }));
      const changed = ch === 'CHANGED';
      return {
        name: r.label, status: ch === 'CHANGED' ? '변화' : ch === 'SIMILAR' ? '유지' : ch ? CHANGE_LABELS[ch] : '선택 전',
        tagCls: changed ? 'c-hi' : 'c-normal', scope: SCOPE[r.domain] || DASH,
        prevSess: prevOf(r), curSess, prev: r.previous ? r.previous.text : '앞 기록 없음',
        cur: ch === 'NOT_MENTIONED' ? '이번 상담에서 이야기 없음' : text || '이번 기록 글 없음', curFw: changed ? 700 : 400,
        changed, kept: !changed, diff: changed ? note || CHANGE_DESC.CHANGED : ch ? CHANGE_DESC[ch] : '아직 고르지 않았어요',
        ev,
        checks: ['맞음', '수정 필요'].map((l) => ({
          label: l, on: ck === l ? 'true' : 'false', cls: ck === l ? 'btn-p' : 'btn-s',
          pick: () => {
            const chk = { ...(this.state.chk || {}), [r.domain]: ck === l ? '' : l };
            if (l === '맞음' && ck !== l) {
              const k = r.draft ? r.draft.change : r.saved ? r.saved.change : null;
              if (!k) { this.setState({ chk, err: `${r.label}: 초안이 없어 아래 영역 줄에서 직접 골라 주세요.` }); return; }
              this.setState({ chk, pick: { ...this.state.pick, [r.domain]: k }, err: '' });
            } else if (l === '수정 필요' && ck !== l) {
              this.setState({ chk, open: { ...this.state.open, [r.domain]: true }, err: '' });
            } else this.setState({ chk });
          },
        })),
      };
    });
    const nChg = chgItems.filter((x) => x.changed).length;

    // 위기도 카드(고령자 없음)
    const levels = ['위기', '집중', '관심', '일반'].map((l) => ({ label: l, on: 'false', bg: '#FFFFFF', bd: '#C5D4DE', fg: '#B5C3CD', pick: () => this.setState({ err: '고령자 상담은 위기도를 매기지 않아요(준비 중).' }) }));
    const senior0 = data.an && data.an.analysis && data.an.analysis.result ? data.an.analysis.result.senior : null;
    const mentions = senior0 && Array.isArray(senior0.safety_mentions) ? senior0.safety_mentions : [];
    const fl = [0, 1, 2].map((i) => {
      const m = mentions[i];
      if (!m) return i === 0 && senior0 ? { chip: '—', text: ' 바로 확인할 말 없음 (AI 표시, 판정 아님)', at: '' } : { chip: '—', text: '', at: '' };
      const more = i === 2 && mentions.length > 3 ? ` · 외 ${mentions.length - 3}개` : '';
      const at = atOf(m.segment_ids);
      return { chip: SAFETY_LABELS[m.kind] || m.kind, text: ` “${m.text}” — 바로 확인해 주세요(AI 표시, 판정 아님)${more}`, at: at.length ? `${sesNo} ${at.join(' · ')}` : '' };
    });

    // 회차별 추이: 앞 회차 둘 + 이번 회차
    const cols = sesRows.filter((r) => curNo && r.session_number <= curNo).slice(-3);
    while (cols.length < 3) cols.unshift(null);
    const trH = cols.map((c) => (c ? `${c.session_number}회차` : DASH));
    const tl = timeline.data ? timeline.data.domains : [];
    const domOrder = rows.length ? rows.map((r) => r.domain) : ['MEAL', 'SLEEP', 'OUTING', 'SOCIAL', 'MOOD'];
    const trL = domOrder.map((d) => { const r = rows.find((x) => x.domain === d); return r ? r.label : DASH; });
    const trC = domOrder.map((d) => cols.map((c) => {
      if (!c) return DASH;
      if (c.id === ids.sessionId) { const r = rows.find((x) => x.domain === d); const ch = r ? choiceOf(r) : null; return ch ? CHANGE_LABELS[ch] : DASH; }
      const line = tl.find((x) => x.domain === d);
      const e = line ? line.entries.find((x) => x.session_id === c.id) : null;
      return e ? CHANGE_LABELS[e.change] : DASH;
    }));

    // 상태 줄
    const st = data.an ? data.an.session_status : null;
    let statusMsg = '';
    if (!ids.sessionId) statusMsg = '회차가 정해지지 않았어요. 사례 화면에서 회차를 골라 들어와 주세요.';
    else if (data.error) statusMsg = errorMessage(data.error, '영역 기록을 불러오지 못했습니다.');
    else if (data.loading && !dom) statusMsg = '불러오는 중…';
    else if (st === 'AI_PROCESSING') statusMsg = '통합 요약 분석 중이에요… 끝나면 초안을 채워 드려요.';
    else if (st === 'AI_FAILED') statusMsg = (data.an.error && data.an.error.message) || '분석에 실패했어요. 1단계에서 다시 시작해 주세요. 초안 없이 고를 수도 있어요.';
    else if (st && ['CREATED', 'AUDIO_UPLOADED', 'STT_PROCESSING', 'STT_REVIEW_REQUIRED', 'STT_FAILED'].includes(st)) statusMsg = '1단계 기록 확인(원문 확정)을 먼저 마쳐 주세요.';
    else if (dom && dom.confirmed && !Object.keys(s.pick).length) statusMsg = '다섯 영역 모두 확정했어요. 바꾸려면 다시 골라 확정해 주세요.';
    if (s.err) statusMsg = s.err;
    else if (s.busy) statusMsg = '저장하는 중…';

    const step3Href = href('Step3Summary', ids);
    const save = async (e) => {
      if (e && e.preventDefault) e.preventDefault();
      if (this.state.busy || !rows.length) return;
      const items = [];
      for (const r of rows) {
        const ch = choiceOf(r);
        if (!ch) { this.setState({ err: `${r.label}: 변화를 골라 주세요. 다섯 영역을 모두 골라야 확정할 수 있어요.` }); return; }
        const item = { domain: r.domain, change: ch };
        const fromDraft = !(r.saved && r.saved.change !== 'NOT_MENTIONED' && r.saved.text);
        if (ch !== 'NOT_MENTIONED') {
          const text = textOf(r);
          if (!text) { this.setState({ err: `${r.label}: 이번 기록 글이 없어 '이야기 없음' 만 고를 수 있어요.` }); return; }
          item.text = text;
          const ids0 = fromDraft ? (r.draft && r.draft.segment_ids) : r.saved.segment_ids;
          if (ids0 && ids0.length) item.segment_ids = ids0;
          const note = (r.saved && r.saved.change_note) || (r.draft && r.draft.change_note);
          if (ch === 'CHANGED' && note) item.change_note = note;
        }
        if (r.draft && fromDraft) {
          item.origin = r.draft.source === 'AI' ? 'AI' : 'RULE';
          item.edited = r.draft.change !== ch;
        } else if (r.saved) {
          item.origin = r.saved.origin;
          item.edited = r.saved.edited || (r.draft ? r.draft.change !== ch : false);
        } else item.origin = 'COUNSELOR';
        items.push(item);
      }
      this.setState({ busy: true, err: '' });
      try {
        await senior.saveSessionDomains(ids.sessionId, items);
        this.setState({ busy: false, pick: {} });
        window.location.hash = step3Href;
      } catch (caught) {
        this.setState({ busy: false, err: errorMessage(caught, '저장하지 못했습니다. 잠시 후 다시 시도해 주세요.') });
      }
    };

    const c = caseQ.data;
    const caseName = c ? c.child_alias || DASH : DASH;
    return {
      ...base, ...shell,
      chgItems, chgPrevLabel: latestPrev ? `${latestPrev.session_number}회차` : '앞 기록 없음', chgCurLabel: curNo ? `${curNo}회차` : DASH,
      chgSummary: rows.length ? `${rows.length}개 항목 중 변화 ${nChg} · 그 밖 ${rows.length - nChg}` : DASH,
      types, levels, decisionNote: '고령자 상담은 위기도를 매기지 않아요 · 준비 중', decisionShort: DASH,
      aiLevel: DASH, flagLine: senior0 ? (mentions.length ? `바로 확인할 말 ${mentions.length}개` : '바로 확인할 말 없음') : DASH, trendNote: '',
      typesTitle: '생활 · 정서 영역 변화', typesNote: '초안 · 1 비슷함 · 2 달라짐 · 3 처음 기록 · 4 이야기 없음 · 상담사가 확정',
      trH, trL, trC, trLast: [DASH, DASH, DASH],
      flTitle: '바로 확인할 말 · 위기 재발 요인', fl, rfNote: '위험요인 · 보호요인 — 준비 중', rf: [DASH, DASH, DASH],
      statusMsg, hasStatus: !!statusMsg,
      caseName, caseCrumb: c ? `${caseName} ${c.case_number || ''}`.trim() : DASH,
      sesNo, sesSub: sessionSub(cur), title: `${sesNo} 처리 · ${caseName}`,
      caseHref: href('CaseInfo', { caseId: ids.caseId }), historyHref: href('CaseHistory', { caseId: ids.caseId }), detailHref: href('SessionDetail', ids),
      step1Href: href('Step1Record', ids), step2Href: href('Step2Signals', ids), step3Href, step4Href: href('Step4Next', ids),
      save, saveLabel: s.busy ? '저장하는 중…' : '확정 · 상담일지 작성 →',
    };
  }
}

export default function Step2Signals(props) {
  const shell = useShell();
  const ids = useIds();
  const caseQ = useAsync(() => (shell.ready && ids.caseId ? cases.get(ids.caseId) : null), [shell.ready, ids.caseId]);
  const sesList = useAsync(() => (shell.ready && ids.caseId ? cases.listSessions(ids.caseId, { page: 1, page_size: 100 }) : null), [shell.ready, ids.caseId]);
  const timeline = useAsync(() => (shell.ready && ids.caseId ? senior.domainTimeline(ids.caseId) : null), [shell.ready, ids.caseId]);
  const data = useSessionData(ids.sessionId, shell.ready);
  const v = useDC(Logic, { ...props, shell, ids, caseQ, sesList, timeline, data });
  return <View v={v} />;
}
