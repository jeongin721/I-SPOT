// 탭 1 · 내담자 정보 + 기관 서식 + 종결 검토 등록
// 원본: 다솔 님 디자인 counselor-web-design/CaseDetail.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 사례 정보 · 회차는 useCaseDetail 이 부르고, 화면에 쓸 값은
// src/data/screens/caseDetail.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다(디자인이 바뀌면 JSX 만 바꾼다).
// 서버에 없는 값(사례관리대상자 · 신고접수일 · 서비스 · 일정 등)은 '—', 종결 검토 등록은 준비 중.
// 위험도 · 학대 유형 · 주요 키워드는 분석이 끝난 가장 최근 회차(useCaseSignals)의 상담원 판단 · AI 결과로 채운다(caseDetail.ts 머리 주석).
// 11/05 탭1 디자인(2)에 맞춰 디자인에 없던 '초기면접 내용' 카드와 '기본 정보' 의 '수정' 단추를 뺐다 — 같은 칸은
// 문서함 › 초기면접지(CaseIntake)에서 고친다. '확인할 사항' 은 줄마다 체크(이 브라우저에 회차별로 기억),
// 진행 단계의 지난 '상담 녹음' 칸 아래 날짜를 보인다.
// 11/04 탭1 디자인: 사례 상세 탭은 내담자 정보 · 상담 이력 · 문서함 셋이고, 아이 연계는 기본 정보 머리의 '아이 연계 →' 단추로 들어간다.
// 10/21 디자인(counselor-design/screens/CaseDetail.dc.html): '녹음하기' 창(마이크 녹음 → 녹취 올리기와 같은 업로드 · 원문 변환,
// components/RecordDialog.jsx), '아이 연계 →' 단추(탭에서 빠짐 — 11/03 다시 탭 줄로), 진행 단계 칸 링크, 사정결과 · 서비스 · 다음 일정 상자 삭제.
// 10/29 디자인: 상담 전 브리핑이 탭에서 빠지고 이 화면 '현재 진행 상황' 아래(#brief)로 들어왔다. 값은 예전 브리핑 화면과
// 같은 preBriefingValues(분석이 끝난 가장 최근 회차). 주소에 view=brief 가 있으면 그 자리로 스크롤한다. '인쇄 · PDF' 는
// 이름 표시 방식(실명 그대로 / 이름 가리기)을 고르는 창을 띄우고 브리핑만 인쇄한다(가리기는 등록된 이름 전부와 별칭 — maskNames).
// 녹음 중이거나 올리지 않은 녹음이 있으면 화면을 떠날 때 묻는다(초기면접 수정과 같은 useLeaveGuard).
// '종결 검토 등록'(10/30): 등록 · 취소를 서버에 저장하고 등록됨 · 등록일 · '종결 검토 보기' 를 보인다(디자인의 '초안 생성 중' 은
// 종결 요약 AI 가 아직 없어 쓰지 않는다).
// 녹음하기 창의 주인 · 버리기 규칙은 data/useRecordFlow.ts(상담 이력 · 문서함과 같이 쓴다).
// '기관 서식' 카드(11/02): 칩은 사례관리 점검표 작성 기록(useCaseForms), '기관 서식 작성' 은 점검표(CaseForm ?form=B)로 간다.
import { Fragment, useEffect, useRef, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import CaseOverviewCard from '../components/CaseOverviewCard';
import Notice from '../components/Notice';
import PrintNameDialog, { printMasked } from '../components/PrintNameDialog';
import RecordDialog from '../components/RecordDialog';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseForms } from '../data/useCaseForms';
import { usePersonalInfo } from '../data/usePersonalInfo';
import { latestAnalyzedSession, useCaseSignals } from '../data/useCaseSignals';
import { useFollowupChecklist } from '../data/useFollowupChecklist';
import { useFollowupChecks } from '../data/useFollowupChecks';
import { useFollowupQuestions } from '../data/useFollowupQuestions';
import { useSignalHistory } from '../data/useSignalHistory';
import { INITIAL_CASE_DETAIL_STATE, caseDetailValues } from '../data/screens/caseDetail';
import { formsCardValues } from '../data/screens/caseForm';
import { needsLogin, signedIn } from '../data/screens/common';
import { checklistNeedsEvidence } from '../data/screens/followupQ';
import { readScreenIds } from '../data/screens/links';
import { caseOverviewValues } from '../data/screens/caseOverview';
import { preBriefingValues } from '../data/screens/preBriefing';
import { useLeaveGuard } from '../data/screens/useLeaveGuard';
import { useRecordFlow } from '../data/useRecordFlow';
import { cases, childApp } from '../api/endpoints';
import { errorMessage, useRemote } from '../data/useRemote';
import './CaseDetail.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_CASE_DETAIL_STATE;
  }
  renderVals() {
    return caseDetailValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function CaseDetail(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const detail = useCaseDetail(caseId, { enabled: signedIn(session) });
  // 브리핑 회차(분석이 끝난 가장 최근 회차)는 useCaseSignals 와 같은 함수로 먼저 정한다 — 저장한 확인 사항 · 체크리스트에만
  // 발화 근거가 있어도 원문을 받아 '근거 · 00:02 아동' 으로 보이게(#125 재검증).
  const briefSessionId = latestAnalyzedSession(detail.sessions)?.id ?? null;
  const briefChecks = useFollowupChecks(briefSessionId, { enabled: signedIn(session) });
  // 브리핑의 확인할 사항 초안은 4 · 다음 상담 준비 화면과 같은 목록(AI 확인 메모 + 다음 상담 체크리스트, 19절)이다.
  const briefChecklist = useFollowupChecklist(briefSessionId, { enabled: signedIn(session) });
  const needEvidence =
    briefChecks.items.some((item) => item.in_briefing && Array.isArray(item.segment_ids) && item.segment_ids.length > 0) ||
    checklistNeedsEvidence(briefChecklist.checklist, briefSessionId);
  const signals = useCaseSignals(detail, { enabled: signedIn(session), needEvidence });
  const theme = useTheme();
  const questions = useFollowupQuestions(detail.sessions[0]?.id ?? null, { enabled: signedIn(session) });
  const personal = usePersonalInfo(caseId, { enabled: signedIn(session) });
  // 기본 정보 '아이 앱' 칸(11/10): 콩콩 연결 상태. 아이 앱이 꺼져 있으면 오류라 '—' 로 둔다.
  const appKey = signedIn(session) && caseId ? `case-child-app:${caseId}` : null;
  const childAppInfo = useRemote(appKey, () => childApp.get(caseId), '아이 앱 정보를 불러오지 못했습니다.', () => false);
  const v = useDC(Logic, { ...props, session, detail, signals, questions, personal, caseId, childApp: childAppInfo.data });
  const formsCard = formsCardValues(useCaseForms(caseId, { enabled: signedIn(session) }), caseId);
  const [params] = useSearchParams();
  const briefQuestions = useFollowupQuestions(signals.session?.id ?? null, { enabled: signedIn(session) });
  const history = useSignalHistory(caseId, { enabled: signedIn(session) });
  const brief = preBriefingValues({
    childApp: childAppInfo.data,
    session,
    detail,
    signals,
    questions: briefQuestions,
    caseId,
    history,
    checks: briefChecks,
    checklist: briefChecklist,
  });
  // 사례 한눈에 보기(2026-11-13, 담당자가 바뀌어도 사례를 한 번에 — 저장된 값만 모음, components/CaseOverviewCard).
  const overview = caseOverviewValues({
    detail,
    history,
    signals,
    childApp: childAppInfo.data,
    checksCount: (brief.checks || []).length,
    caseId,
  });
  const briefRef = useRef(null);
  // 11/04 탭1 디자인: '확인할 사항' 줄 앞 체크(상담 중 확인한 것 표시). 서버 칸이 없어 이 브라우저에만 회차별로 기억한다.
  const tickKey = signals.session?.id ? `ispot-brief-ticks:${signals.session.id}` : null;
  const [ticks, setTicks] = useState(() => new Set());
  useEffect(() => {
    let saved = [];
    try {
      saved = tickKey ? JSON.parse(window.localStorage.getItem(tickKey) || '[]') : [];
    } catch {
      saved = [];
    }
    setTicks(new Set(Array.isArray(saved) ? saved : []));
  }, [tickKey]);
  const toggleTick = (text) => {
    setTicks((prev) => {
      const next = new Set(prev);
      if (next.has(text)) next.delete(text);
      else next.add(text);
      try {
        if (tickKey) window.localStorage.setItem(tickKey, JSON.stringify([...next]));
      } catch {
        /* 저장 못 해도 화면 표시는 그대로 */
      }
      return next;
    });
  };
  const [outOpen, setOutOpen] = useState(false);
  const wantBrief = params.get('view') === 'brief';
  const briefReady = Boolean(detail.caseInfo);
  useEffect(() => {
    if (wantBrief && briefReady && briefRef.current) briefRef.current.scrollIntoView({ block: 'start' });
  }, [wantBrief, briefReady]);
  const rec = useRecordFlow(session, caseId, v.canRecord);
  // 종결 검토 등록 · 취소(10/30 디자인 · POST/DELETE /cases/{id}/closure-review). 끝나면 사례를 다시 부른다.
  const [closureBusy, setClosureBusy] = useState(false);
  const [closureError, setClosureError] = useState(null);
  const closureDate = detail.caseInfo?.closureReviewDate || '';
  const setClosure = async (register) => {
    if (!caseId || closureBusy) return;
    setClosureBusy(true);
    setClosureError(null);
    try {
      await (register ? cases.registerClosureReview(caseId) : cases.cancelClosureReview(caseId));
      detail.reload();
    } catch (caught) {
      setClosureError(errorMessage(caught, '종결 검토 등록을 바꾸지 못했습니다. 잠시 후 다시 시도해 주세요.'));
    } finally {
      setClosureBusy(false);
    }
  };
  useLeaveGuard(v.unsaved || rec.unsaved);
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-CaseDetail">
      <div
        className={theme.cls}
        style={{
          minHeight: '1350px',
          background: '#E9E7E1',
          color: '#2B2A26',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <Sidebar active="CaseList" session={session} />
        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          <div className="thm-bar">
            <NotiBell session={session} />
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › {v.crumb}
          </nav>
          <Notice value={v.notice} />
          <Notice value={v.personalNote} />
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <A className="btn btn-sm btn-s" to="/CaseList">
              ← 목록
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 className="h1-sans" style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>
                  {v.title}
                </h1>
                <span className="sub">{v.sub}</span>
                <span className={`chip ${v.riskCls}`}>{v.riskChip}</span>
              </div>
              <div className="note">{v.meta}</div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-s"
                onClick={rec.start}
                disabled={!rec.canOpen}
              >
                <span className="rec-dot" aria-hidden="true"></span> 녹음하기
              </button>
              <A className="btn btn-s" to={v.uploadHref}>
                ↑ 녹취 올리기
              </A>
            </div>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A className="on" aria-current="page" to={v.tabs.detail}>
              내담자 정보
            </A>
            <A to={v.tabs.history}>상담 이력</A>
            <A to={v.tabs.docs}>문서함</A>
          </nav>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '18px' }}>
            <section className="card basics" aria-label="기본 정보" style={{ padding: '22px 24px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">기본 정보</h2>
                {/* 11/04 탭1 디자인: 아이 연계는 탭이 아니라 기본 정보 머리의 '아이 연계 →' 단추로 들어간다. */}
                <A className="btn btn-sm btn-s" to={v.tabs.app} style={{ marginLeft: 'auto' }}>
                  아이 연계 →
                </A>
              </div>
              <dl className="kv" style={{ gridTemplateColumns: '120px 1fr' }}>
                {(v.basics || []).map((b, bIndex) => (
                  <Fragment key={bIndex}>
                    <dt>{b.label}</dt>
                    <dd style={b.strong ? { fontWeight: '700' } : undefined}>{b.value}</dd>
                  </Fragment>
                ))}
              </dl>
            </section>
            <section className="card" aria-label="주요 위험 요인" style={{ padding: '22px 24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">주요 위험 요인</h2>
                <span className={`chip ${v.riskCls}`} style={{ marginLeft: 'auto' }}>
                  {v.riskChip}
                </span>
              </div>
              <div className="note" style={{ marginTop: '4px', textAlign: 'right' }}>
                상담사 지정 · {v.riskBy}
              </div>
              {v.riskNote ? (
                <div className="note" role="alert" style={{ marginTop: '4px', color: '#A33B2E' }}>
                  {v.riskNote}
                </div>
              ) : null}
              <div className="note" style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                학대 유형
                {v.typesAi ? (
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안
                  </span>
                ) : null}
              </div>
              <div style={{ margin: '6px 0 16px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {(v.abuseTypes || []).map((t, tIndex) => (
                  <span key={tIndex} className="chip c-normal">
                    {t}
                  </span>
                ))}
              </div>
              <div className="note" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                주요 키워드
                {v.keywordsAi ? (
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안
                  </span>
                ) : null}
              </div>
              <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {(v.keywords || []).map((k, kIndex) =>
                  k.href ? (
                    <A key={kIndex} className="chip c-normal" to={k.href} title={`근거 · ${k.where}`}>
                      {k.text}
                      <span style={{ marginLeft: '6px', fontSize: '11px', opacity: 0.75 }}>{k.where}</span>
                    </A>
                  ) : (
                    <span key={kIndex} className="chip c-normal">
                      {k.text}
                    </span>
                  ),
                )}
              </div>
              {v.typesAi || v.keywordsAi ? (
                <div className="note" style={{ marginTop: '10px' }}>
                  {v.aiNote}
                </div>
              ) : null}
            </section>
          </div>

          <section className="card" aria-label="현재 진행 상황" style={{ padding: '22px 24px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <h2 className="h2">현재 진행 상황</h2>
              <span className="note">{v.latestLabel}</span>
              <A className="btn btn-p btn-sm" to={v.continueHref} style={{ marginLeft: 'auto' }}>
                {v.continueLabel}
              </A>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <div
                style={{
                  minWidth: '660px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: '10%',
                    right: '10%',
                    top: '17px',
                    height: '2px',
                    background: '#E7E4DC',
                  }}
                />
                {(v.progress || []).map((p, pIndex) => {
                  const inner = (
                    <>
                      <span className="sd" style={p.dot}>
                        {p.mark}
                      </span>
                      {p.done ? <span>{p.label}</span> : null}
                      {p.note ? <span className="note">{p.note}</span> : null}
                      {p.current ? <b style={{ fontWeight: '700', color: '#2B2A26' }}>{p.label}</b> : null}
                      {p.pending ? <span style={{ color: '#7A776F' }}>{p.label}</span> : null}
                      {p.chip ? <span className="chip c-check">{p.chip}</span> : null}
                    </>
                  );
                  return p.href ? (
                    <A key={pIndex} className="st stl" to={p.href}>
                      {inner}
                    </A>
                  ) : (
                    <div key={pIndex} className="st">
                      {inner}
                    </div>
                  );
                })}
              </div>
            </div>
          </section>

          <CaseOverviewCard value={overview} />

          <div className="brief-wrap" id="brief" ref={briefRef} aria-label="상담 전 브리핑" role="region">
            <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 20px' }}>
              <div style={{ flex: '1 1 380px' }}>
                <div className="sub">{brief.lead}</div>
                <h2 style={{ margin: '2px 0 0', fontSize: '22px', fontWeight: '700' }}>상담 전 브리핑</h2>
              </div>
              <button type="button" className="btn btn-s" aria-haspopup="dialog" onClick={() => setOutOpen(true)}>
                인쇄 · PDF
              </button>
              {outOpen ? (
                <PrintNameDialog
                  title="인쇄 · PDF"
                  goLabel="인쇄"
                  name={v.title}
                  maskReady={v.namesReady}
                  onClose={() => setOutOpen(false)}
                  onRun={(mask) => {
                    setOutOpen(false);
                    printMasked({ root: briefRef.current, names: v.maskNames, mask, bodyClass: 'print-brief' });
                  }}
                />
              ) : null}
            </section>
            <section aria-label="먼저 볼 것" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <h2 className="h2">먼저 볼 것</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '18px' }}>
                {(brief.firstCards || []).map((c) => (
                  <div key={c.key} className="card lead">
                    <span className="lead-tag">{c.title}</span>
                    {c.q ? <span className="lead-q">{c.q}</span> : null}
                    {c.main ? <b className="lead-main">{c.main}</b> : null}
                    <span className="src">{c.src || c.note}</span>
                  </div>
                ))}
              </div>
            </section>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '18px' }}>
              <section
                className="card"
                style={{ padding: '26px 28px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h2 className="h2">확인할 사항</h2>
                </div>
                {brief.checksNote ? <span className="note">{brief.checksNote}</span> : null}
                {(brief.checks || []).map((c) => (
                  <label key={c.key} className="rq">
                    <input type="checkbox" checked={ticks.has(c.text)} onChange={() => toggleTick(c.text)} />
                    <span>
                      {c.text}
                      {c.href ? (
                        <A className="src" to={c.href}>
                          근거 · {c.why}
                        </A>
                      ) : (
                        <span className="src">근거 · {c.why}</span>
                      )}
                    </span>
                  </label>
                ))}
                {brief.checksError ? (
                  <span className="note" role="alert" style={{ color: '#A33B2E' }}>
                    {brief.checksError}
                  </span>
                ) : null}
              </section>
              <section
                className="card"
                style={{ padding: '26px 28px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h2 className="h2">추가 질문</h2>
                  <span className="chip c-ai">AI 초안</span>
                  {brief.questionHref ? (
                    <A to={brief.questionHref} style={{ marginLeft: 'auto', fontSize: '13px' }}>
                      질문 수정
                    </A>
                  ) : null}
                </div>
                {brief.questions.map((q) => (
                  <div key={q.key} className="rq">
                    <span className="chip c-normal">{q.chip}</span>
                    <span>"{q.text}"</span>
                  </div>
                ))}
                {brief.questionNote ? <span className="note">{brief.questionNote}</span> : null}
              </section>
            </div>
          </div>

          <section
            className="card"
            aria-label="기관 서식"
            style={{ padding: '20px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px' }}
          >
            <b style={{ flex: '1 1 200px' }}>기관 서식</b>
            <span className="chip c-check">{formsCard.chip}</span>
            <A className="btn btn-p" to={formsCard.href}>
              기관 서식 작성
            </A>
          </section>

          <section
            className="card"
            aria-label="종결 검토 등록"
            style={{ padding: '20px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px' }}
          >
            <b style={{ flex: '1 1 200px' }}>종결 검토</b>
            {closureDate ? (
              <>
                <span className="chip c-ok">등록됨 · {closureDate}</span>
                <A className="btn btn-s" to="/Closure">
                  종결 검토 보기
                </A>
                <button type="button" className="btn btn-sm btn-s" onClick={() => setClosure(false)} disabled={closureBusy}>
                  등록 취소
                </button>
              </>
            ) : (
              <button
                type="button"
                className="btn btn-y"
                onClick={() => setClosure(true)}
                disabled={closureBusy || !detail.caseInfo || detail.caseInfo.status !== 'ACTIVE'}
                title={detail.caseInfo && detail.caseInfo.status !== 'ACTIVE' ? '진행 중인 사례만 등록할 수 있습니다.' : undefined}
              >
                종결 검토 등록
              </button>
            )}
            {closureError ? (
              <span className="note" role="alert" style={{ flexBasis: '100%', color: '#A33B2E' }}>
                {closureError}
              </span>
            ) : null}
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
          {rec.show ? (
            <RecordDialog
              caseId={caseId}
              caseName={v.recordCase}
              caseSub={v.sub}
              targets={v.recordTargets}
              recorder={rec.recorder}
              upload={rec.upload}
              onClose={rec.close}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}
