// 4 · 추가 확인 · 질문
// 원본: 10/27 디자인 counselor-design/screens/FollowupQ.dc.html (frontend261021 브랜치).
//
// 서버 연결: 화면 주소 ?case=…&session=…. 다음 상담 전 확인할 사항 · 추가 질문은 다음 상담 체크리스트
// (GET /followup-suggestions, useFollowupSuggestions — rag 가 공식 근거를 찾아 쓴 AI 초안)이고, 없으면 AI 분석 결과의
// followup_check_points(AI 확인 메모, useSessionAnalysis)를 보인다. 메모의 근거 위치는 useRiskSignals 가 원문에서 찾는다.
// 머리는 useSessionDetail · useCaseDetail 이 부르고, 화면에 쓸 값은 src/data/screens/followupQ.ts 가 만든다(디자인 칸 → 서버 값
// 대응도 그 파일 머리에 있다). 이 파일은 훅을 부르고 배치만 한다. 승인 · 수정 · 직접 추가 · 브리핑에 넣기 · 아이 앱 발송은
// 서버에 없어 준비 중이다.
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import StepNav from '../components/StepNav';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useFollowupSuggestions } from '../data/useFollowupSuggestions';
import { useRiskSignals } from '../data/useRiskSignals';
import { useSessionAnalysis } from '../data/useSessionAnalysis';
import { useSessionDetail } from '../data/useSessionDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { INITIAL_FOLLOWUP_STATE, followupQValues } from '../data/screens/followupQ';
import { readScreenIds } from '../data/screens/links';
import { useScreenGo } from '../data/screens/useScreenGo';
import { sessionCaseId } from '../data/screens/sessionDetail';
import './FollowupQ.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_FOLLOWUP_STATE;
  }
  renderVals() {
    return followupQValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

/** 근거 칩 줄. 화면 안 주소는 링크, 국가법령정보센터는 새 창, 그 밖은 글자(발췌는 마우스를 올리면 보인다). */
function Evidence({ items }) {
  if (!items.length) return <span className="note">근거 위치 없음</span>;
  return (
    <span className="note evi-line">
      근거 ·{' '}
      {items.map((e, index) => (
        <span key={e.key}>
          {index ? ' · ' : ''}
          {e.href ? (
            <A to={e.href} title={e.excerpt || undefined}>
              {e.label}
            </A>
          ) : e.url ? (
            <a href={e.url} target="_blank" rel="noopener noreferrer" title={e.excerpt || undefined}>
              {e.label} ↗
            </a>
          ) : (
            <span title={e.excerpt || undefined}>{e.label}</span>
          )}
        </span>
      ))}
    </span>
  );
}

/** 공식 근거 칩. 법령 · 판례는 원문 링크, 매뉴얼 · 체크리스트는 누르면 발췌를 펼친다(원본 PDF 는 올리지 않는다). */
function Sources({ items }) {
  if (!items.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'flex-start' }}>
      {items.map((s) =>
        s.url ? (
          <a key={s.key} className="src" href={s.url} target="_blank" rel="noopener noreferrer" title={s.excerpt || undefined}>
            {s.label} ↗
          </a>
        ) : s.excerpt ? (
          <details key={s.key} className="src">
            <summary>{s.label}</summary>
            <p>{s.excerpt}</p>
          </details>
        ) : (
          <span key={s.key} className="src">
            {s.label}
          </span>
        ),
      )}
    </div>
  );
}

export default function FollowupQ(props) {
  const session = useAuthSession();
  const ids = readScreenIds(useSearchParams()[0]);
  const go = useScreenGo(useNavigate());
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const analysis = useSessionAnalysis(ids.sessionId, { enabled });
  const signals = useRiskSignals(ids.sessionId, analysis.analysis, { enabled });
  // AI 분석이 끝나면 Backend 가 같은 작업에서 체크리스트를 만든다. 분석 중에도 되풀이 조회해 바로 받는다.
  const followup = useFollowupSuggestions(ids.sessionId, { enabled, watch: analysis.processing });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, analysis, signals, followup, go });
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
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px 8px' }}>
                    <span style={{ fontSize: '15px' }}>{c.text}</span>
                    {c.kindLabel ? <span className="chip c-sky">{c.kindLabel}</span> : null}
                    {c.priorityHigh ? <span className="chip c-hi">우선</span> : null}
                  </div>
                  <Evidence items={c.evidence} />
                  {c.reason ? <span className="note">{c.reason}</span> : null}
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
            {v.suggestionNotice ? <span className="note">{v.suggestionNotice}</span> : null}
            {v.suggestionStatus ? (
              <span className="note" role="status">
                {v.suggestionStatus}
              </span>
            ) : null}
            {v.suggestionError ? (
              <div className="note" role="alert" style={{ color: '#A33B2E' }}>
                {v.suggestionError}
              </div>
            ) : null}
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: '8px 12px' }}>
              <span className="note">{v.checkEditNote}</span>
              <button type="button" className="btn btn-sm btn-s" disabled={!v.canRegenerate} onClick={v.regenerate}>
                {v.regenerating ? '요청 중…' : '다시 만들기'}
              </button>
            </div>
          </section>

          <section
            className="card"
            aria-label="추가 질문"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px' }}>
              <h2 className="h2">추가 질문</h2>
              <span className="chip c-ai">AI 초안 · 상담원 확인</span>
              <div role="tablist" aria-label="질문 대상" className="seg" style={{ marginLeft: 'auto' }}>
                {v.tabs.map((t) => (
                  <button key={t.key} type="button" role="tab" aria-selected={t.on} className={t.on ? 'on' : ''} onClick={t.select}>
                    {t.label} {t.count}
                  </button>
                ))}
              </div>
            </div>
            {v.questionNote ? <span className="note">{v.questionNote}</span> : null}
            {v.questionsEmpty ? <span className="note">{v.questionsEmpty}</span> : null}
            {v.questions.map((q) => (
              <div key={q.key} className="qcard">
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px 8px' }}>
                  <span className="chip c-sky">{q.typeLabel}</span>
                  {q.priorityHigh ? <span className="chip c-hi">우선</span> : null}
                  {q.reviewLabel ? <span className="chip c-ai">{q.reviewLabel}</span> : null}
                  <span style={{ marginLeft: 'auto' }}>
                    <Evidence items={q.evidence} />
                  </span>
                </div>
                <div style={{ fontSize: '16px', fontWeight: '500' }}>"{q.text}"</div>
                {q.rationale ? <span className="note">{q.rationale}</span> : null}
                <Sources items={q.sources} />
              </div>
            ))}
            <span className="note" style={{ alignSelf: 'flex-end' }}>
              {v.questionActionNote}
            </span>
          </section>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <A className="btn btn-s" to={v.backHref}>
              ← 요약 · 일지 작성
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
