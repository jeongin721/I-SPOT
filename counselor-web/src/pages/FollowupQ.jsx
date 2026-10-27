// 4 · 추가 확인 · 질문
// 원본: 10/27 디자인 counselor-design/screens/FollowupQ.dc.html (frontend261021 브랜치).
//
// 서버 연결: 화면 주소 ?case=…&session=…. 다음 상담 전 확인할 사항은 AI 분석 결과의 followup_check_points(AI 확인 메모,
// useSessionAnalysis)이고, 근거 위치는 useRiskSignals 가 원문에서 찾는다. 머리는 useSessionDetail · useCaseDetail 이 부르고,
// 화면에 쓸 값은 src/data/screens/followupQ.ts 가 만든다(디자인 칸 → 서버 값 대응도 그 파일 머리에 있다).
// 이 파일은 훅을 부르고 배치만 한다. 확인 사항 수정 · 직접 추가 · 브리핑에 넣기와 추가 질문은 서버에 없어 준비 중이다.
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useRiskSignals } from '../data/useRiskSignals';
import { useSessionAnalysis } from '../data/useSessionAnalysis';
import { useSessionDetail } from '../data/useSessionDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { followupQValues } from '../data/screens/followupQ';
import { readScreenIds } from '../data/screens/links';
import { useScreenGo } from '../data/screens/useScreenGo';
import { sessionCaseId } from '../data/screens/sessionDetail';
import './FollowupQ.css';

class Logic extends DCLogic {
  renderVals() {
    return followupQValues(this.props);
  }
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
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, analysis, signals, go });
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
          <nav className="steps" aria-label="회차 처리 단계">
            {(v.steps || []).map((t, tIndex) => (
              <A key={tIndex} className={t.cls} to={t.href} aria-current={t.current}>
                <span className="sn">{t.mark}</span>
                <b style={{ fontWeight: t.weight }}>{t.label}</b>
              </A>
            ))}
          </nav>

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
            </div>
            <span className="note">{v.questionNote}</span>
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
