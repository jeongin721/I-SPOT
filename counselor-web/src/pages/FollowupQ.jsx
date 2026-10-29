// 4 · 추가 확인 · 질문
// 원본: 10/27 디자인 counselor-design/screens/FollowupQ.dc.html (frontend261021 브랜치).
//
// 서버 연결: 화면 주소 ?case=…&session=…. 다음 상담 전 확인할 사항은 AI 분석 결과의 followup_check_points(AI 확인 메모,
// useSessionAnalysis)이고, 근거 위치는 useRiskSignals 가 원문에서 찾는다. 머리는 useSessionDetail · useCaseDetail 이 부르고,
// 화면에 쓸 값은 src/data/screens/followupQ.ts 가 만든다(디자인 칸 → 서버 값 대응도 그 파일 머리에 있다).
// 이 파일은 훅을 부르고 배치만 한다. 확인 사항 수정 · 직접 추가 · 브리핑에 넣기는 서버에 없어 준비 중이다.
// 추가 질문은 승인 목록(useFollowupQuestions, 18절)에 저장한다 — 카드 · 승인 · 수정 · 직접 추가는 디자인 마크업 그대로.
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import StepNav from '../components/StepNav';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useFollowupQuestions } from '../data/useFollowupQuestions';
import { useRiskSignals } from '../data/useRiskSignals';
import { useSessionAnalysis } from '../data/useSessionAnalysis';
import { useSessionDetail } from '../data/useSessionDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { followupQValues } from '../data/screens/followupQ';
import { initialQuestionState, questionsNeedEvidence } from '../data/screens/followupQuestions';
import { readScreenIds } from '../data/screens/links';
import { useScreenGo } from '../data/screens/useScreenGo';
import { sessionCaseId } from '../data/screens/sessionDetail';
import './FollowupQ.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialQuestionState();
  }
  renderVals() {
    return followupQValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function FollowupQ(props) {
  const session = useAuthSession();
  const ids = readScreenIds(useSearchParams()[0]);
  // 회차 · 로그인 계정이 바뀌면 처음부터 다시 그린다. 승인 전 질문 · 고치던 문장(화면 상태)이 다른 회차로 넘어가
  // 그 회차에 저장되지 않게 한다(민규 #113 R1 — 녹취 올리기 창과 같은 방법).
  return <FollowupQScreen key={`${ids.sessionId ?? ''}|${session.me?.id ?? ''}`} {...props} session={session} ids={ids} />;
}

function FollowupQScreen(props) {
  const { session, ids } = props;
  const go = useScreenGo(useNavigate());
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const analysis = useSessionAnalysis(ids.sessionId, { enabled });
  const questions = useFollowupQuestions(ids.sessionId, { enabled });
  // 추가 질문(초안 · 승인 목록)에만 근거가 있어도 원문을 받아 근거 위치를 찾는다(민규 #113 R4).
  const needEvidence = questionsNeedEvidence(analysis.analysis, questions.questions);
  const signals = useRiskSignals(ids.sessionId, analysis.analysis, { enabled, needEvidence });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, analysis, signals, questions, go });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-FollowupQ">
      <div
        className={theme.cls}
        style={{
          minHeight: '1550px',
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
            <NotiBell />
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › <A to={v.caseHref}>{v.caseLabel}</A> › <A to={v.historyHref}>상담 이력</A>{' '}
            › <A to={v.sessionHref}>{v.sessionLabel}</A>
          </nav>
          <Notice value={v.notice} />
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 280px' }}>
              <div className="sub">{v.sub}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '2px' }}>
                <A
                  className="btn btn-sm btn-s"
                  to={v.caseHref}
                  aria-label="내담자 정보로 돌아가기"
                  title="내담자 정보로 돌아가기"
                >
                  ←
                </A>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
              </div>
            </div>
          </header>
          <StepNav steps={v.steps} />

          <section
            className="card"
            aria-label="다음 상담 전 확인할 사항"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">다음 상담 전 확인할 사항</h2>
              <span className="chip c-ai">{v.chip}</span>
            </div>
            <span className="note">{v.checkNote}</span>
            {v.checksEmpty ? <span className="note">{v.checksEmpty}</span> : null}
            {(v.checks || []).map((c) => (
              <div key={c.key} className="qcard" style={{ flexDirection: 'row', alignItems: 'flex-start', gap: '12px' }}>
                <div style={{ flex: '1', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ fontSize: '15px' }}>{c.text}</span>
                  {c.href ? (
                    <A className="note" to={c.href}>
                      근거 · {c.why}
                    </A>
                  ) : (
                    <span className="note">근거 · {c.why}</span>
                  )}
                </div>
              </div>
            ))}
            {v.error ? (
              <div className="note" role="alert" style={{ color: '#A33B2E' }}>
                {v.error}
              </div>
            ) : null}
            {v.signalError ? (
              <div className="note" role="alert" style={{ color: '#A33B2E' }}>
                {v.signalError}
              </div>
            ) : null}
            <span className="note" style={{ alignSelf: 'flex-end' }}>
              {v.checkEditNote}
            </span>
          </section>

          <section
            className="card"
            aria-label="추가 질문"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px' }}>
              <h2 className="h2">추가 질문</h2>
              <div role="tablist" className="seg" style={{ marginLeft: 'auto' }}>
                <button type="button" role="tab" className={v.meetCls} onClick={v.showMeet}>
                  다음 상담에서 직접
                </button>
                <button type="button" role="tab" className={v.appCls} onClick={v.showApp}>
                  아이 앱으로 먼저
                </button>
              </div>
            </div>
            {v.qNote ? <span className="note">{v.qNote}</span> : null}
            {v.qs.map((q) => (
              <div key={q.key} className="qcard">
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                  <span className="chip c-sky">{q.id}</span>
                  {q.aiDraft ? <span className="chip c-ai">AI 초안</span> : null}
                  {q.ok ? <span className="chip c-sel">{q.st}</span> : null}
                  {q.edited ? <span className="chip c-sand">상담사 수정</span> : null}
                  {q.whyHref ? (
                    <A className="note" to={q.whyHref} style={{ marginLeft: 'auto' }}>
                      근거 · {q.why}
                    </A>
                  ) : (
                    <span className="note" style={{ marginLeft: 'auto' }}>
                      근거 · {q.why}
                    </span>
                  )}
                </div>
                {v.qNotEdit ? (
                  <>
                    <div style={{ fontSize: '16px', fontWeight: '500' }}>"{q.text}"</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', gap: '8px' }}>
                      <button type="button" className={`btn btn-sm ${q.okCls}`} onClick={q.approve}>
                        {q.okLabel}
                      </button>
                    </div>
                  </>
                ) : (
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="note">질문 문장</span>
                    <textarea
                      className="edit-in"
                      rows={2}
                      aria-label="질문 문장 수정"
                      value={q.draftText}
                      onChange={(e) => q.setText(e.target.value)}
                    />
                  </label>
                )}
              </div>
            ))}
            {v.qNewRows.map((r) => (
              <div key={r.key} className="qcard" style={{ boxShadow: 'inset 0 0 0 2px #2B2A26' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                  <span className="chip c-sky">직접 작성</span>
                </div>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span className="note">질문 문장</span>
                  <textarea
                    className="edit-in"
                    rows={2}
                    aria-label="새 질문 문장"
                    placeholder="아이에게 물어볼 질문을 적어 주세요"
                    value={r.text}
                    onChange={(e) => r.setText(e.target.value)}
                  />
                </label>
              </div>
            ))}
            {v.qError ? (
              <div className="note" role="alert" style={{ color: '#A33B2E' }}>
                {v.qError}
              </div>
            ) : null}
            {v.qActions ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', gap: '8px' }}>
                <button type="button" className="btn btn-sm btn-s" onClick={v.addQ}>
                  + 질문 직접 추가
                </button>
                {v.qNotEdit ? (
                  <button type="button" className="btn btn-sm btn-s" onClick={v.startQ}>
                    수정
                  </button>
                ) : null}
                {v.qIsEdit ? (
                  <>
                    <button type="button" className="btn btn-sm btn-p" onClick={v.qOk}>
                      확인
                    </button>
                    <button type="button" className="btn btn-sm btn-s" onClick={v.qCancel}>
                      취소
                    </button>
                  </>
                ) : null}
              </div>
            ) : null}
          </section>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <A className="btn btn-s" to={v.backHref}>
              ← 상담일지 작성
            </A>
            <A className="btn btn-p" to={v.doneHref} style={{ marginLeft: 'auto' }}>
              {v.doneLabel}
            </A>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
