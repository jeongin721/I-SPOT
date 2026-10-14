// 2 · 위험 신호 검토 (→ 유형별 위험도)
// 원본: I-SPOT 디자인 캔버스 보드 SignalReview.dc.html (자동 변환 후 다듬어 쓰세요)
//
// 서버 연결: 화면 주소 ?case=…&session=…. AI 분석 요청 · 진행은 useSessionAnalysis, 머리는 useSessionDetail · useCaseDetail 이
// 부르고, 화면에 쓸 값은 src/data/screens/signalReview.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 위험 신호 카드 · 채택/보류/제외는 서버(AI)가 아직 신호를 주지 않아 준비 중이다(빈 목록).
import { Fragment } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSessionAnalysis } from '../data/useSessionAnalysis';
import { useSessionDetail } from '../data/useSessionDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useScreenGo } from '../data/screens/useScreenGo';
import { sessionCaseId } from '../data/screens/sessionDetail';
import { signalReviewValues } from '../data/screens/signalReview';

class Logic extends DCLogic {
  renderVals() {
    return signalReviewValues(this.props);
  }
}

export default function SignalReview(props) {
  const session = useAuthSession();
  const ids = readScreenIds(useSearchParams()[0]);
  const go = useScreenGo(useNavigate(), ids);
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const analysis = useSessionAnalysis(ids.sessionId, { enabled });
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, analysis, go });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-SignalReview">
      <div
        style={{
          minHeight: '1350px',
          background: '#FFFEFA',
          color: '#2F3A44',
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <aside className="side" aria-label="주 메뉴">
          <A className="logo" to="/Main">
            <span className="mk">IS</span>
            <b style={{ fontSize: '17px' }}>I-SPOT</b>
          </A>
          <A className="cta" to="/UploadModal">
            ↑ 녹취 · 자료 올리기
          </A>
          <A className="cta2" to="/CaseRegister">
            + 새 사례 등록
          </A>
          <nav className="nav" aria-label="메뉴">
            <A to="/Main">홈</A>
            <A className="on" to="/CaseList">
              사례 관리
            </A>
            <A to="/Schedule">일정</A>
            <A to="/ChildLink">
              아이 연계
            </A>
            <A to="/Closure">
              종결 검토
            </A>
            <A to="/Stats">통계</A>
            <A to="/Settings">설정</A>
          </nav>
          <div className="me">
            <span className="av">{v.meInitial}</span>
            <b style={{ fontWeight: '500' }}>{v.meName}</b>
            <A to="/Login" className="note" style={{ marginLeft: 'auto' }} onClick={v.logout}>
              로그아웃
            </A>
          </div>
        </aside>
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
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › <A to={v.caseHref}>{v.caseLabel}</A> ›{' '}
            <A to={v.historyHref}>상담 이력</A> › <A to={v.sessionHref}>{v.sessionLabel}</A>
          </nav>
          <Notice value={v.notice} />
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 280px' }}>
              <div className="sub">{v.sub}</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
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
          <nav className="seg" aria-label="2단계 보기" style={{ alignSelf: 'flex-start' }}>
            <button type="button" className="on">
              위험 신호
            </button>
            <A
              to={v.riskHref}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                minHeight: '34px',
                padding: '0 13px',
                borderRadius: '9px',
                fontSize: '13px',
                color: '#55606A',
                textDecoration: 'none',
              }}
            >
              유형별 위험도
            </A>
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <span className="chip c-ai">AI 분석 · 판정 아님</span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
              <span className="chip c-ok">채택 {v.nA}</span>
              <span className="chip c-check">보류 {v.nH}</span>
              <span className="chip c-normal">제외 {v.nD}</span>
            </span>
          </section>
          <section
            className="card"
            aria-label="AI 분석"
            style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <b style={{ fontSize: '16px' }}>AI 분석</b>
              {v.aiChip ? <span className="chip c-ai">{v.aiChip}</span> : null}
              {v.aiAction ? (
                <button
                  type="button"
                  className="btn btn-sm btn-p"
                  style={{ marginLeft: 'auto' }}
                  onClick={v.aiAction}
                >
                  {v.aiActionLabel}
                </button>
              ) : null}
            </div>
            <div aria-live="polite">{v.aiText}</div>
            {v.error ? (
              <div className="note" role="alert" style={{ color: '#93452E' }}>
                {v.error}
              </div>
            ) : null}
            {(v.aiWarnings || []).map((w, wIndex) => (
              <div key={wIndex} style={{ padding: '12px 14px', borderRadius: '12px', background: '#F8F5EC' }}>
                <div className="note">AI 안내 · 추가 확인 필요</div>
                <div style={{ fontSize: '13px' }}>{w}</div>
              </div>
            ))}
            <p className="note" style={{ margin: 0 }}>
              {v.signalNote}
            </p>
          </section>
          {(v.sigs || []).map((g, gIndex) => (
            <Fragment key={gIndex}>
              <section
                className="card"
                style={{
                  padding: '18px 22px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  boxShadow: g.bar,
                }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                  <span className="chip c-normal">{g.type} 학대</span>
                  <b style={{ fontSize: '16px' }}>{g.title}</b>
                  <span className={g.stCls}>{g.st}</span>
                  <span role="group" aria-label="검토" className="seg" style={{ marginLeft: 'auto' }}>
                    <button type="button" className={g.aCls} onClick={g.adopt}>
                      채택
                    </button>
                    <button type="button" className={g.hCls} onClick={g.hold}>
                      보류
                    </button>
                    <button type="button" className={g.dCls} onClick={g.drop}>
                      제외
                    </button>
                  </span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                    gap: '10px',
                  }}
                >
                  <div style={{ padding: '12px 14px', borderRadius: '12px', background: '#F8F5EC' }}>
                    <div className="note">발화 · {g.at}</div>
                    <div style={{ fontSize: '15px' }}>"{g.quote}"</div>
                  </div>
                  <div style={{ padding: '12px 14px', borderRadius: '12px', background: '#F8F5EC' }}>
                    <div className="note">근거</div>
                    <div style={{ fontSize: '13px' }}>{g.why}</div>
                    <div className="note">{g.check}</div>
                  </div>
                </div>
              </section>
            </Fragment>
          ))}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            <A className="btn btn-s" to={v.sttHref}>
              ← STT 검수
            </A>
            {v.canNext ? (
              <A className="btn btn-p" to={v.nextHref} style={{ marginLeft: 'auto' }}>
                {v.nextLabel}
              </A>
            ) : (
              <button type="button" className="btn btn-p" disabled style={{ marginLeft: 'auto' }}>
                {v.nextLabel}
              </button>
            )}
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
