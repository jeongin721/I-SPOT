// 2 · 유형별 위험도 (AI 제안 · 심각도 1~5 · 상담원 판단)
// 원본: 10/27 디자인 counselor-design/screens/SignalReview.dc.html (frontend261021 브랜치). 예전 '위험 신호 검토' 와
// '유형별 위험도'(RiskProfile) 두 화면이 디자인에서 이 화면 하나가 됐다. #/RiskProfile 주소는 여기로 넘긴다.
//
// 서버 연결: 화면 주소 ?case=…&session=…. AI 분석 상태 · 심각도(severity_ratings) · 보호요인(protective_factors)은
// useSessionAnalysis, 유형별 관련 신호 · 근거 발화는 useRiskSignals(근거 위치는 원문에서), 상담원 판단(상 · 중 · 하)은
// useRiskAssessments, 머리는 useSessionDetail · useCaseDetail 이 부르고, 화면에 쓸 값은 src/data/screens/signalReview.ts 가
// 만든다(디자인 칸 → 서버 값 대응도 그 파일 머리에 있다). 이 파일은 훅을 부르고 배치만 한다.
// 서버에 없는 것(회차 전체 AI 위험도 · 안전 플래그 · 재학대 요인 · 위험요인 · 회차별 추이 · 심각도 상담사 수정)은 준비 중이다.
import { Fragment } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useRiskAssessments } from '../data/useRiskAssessments';
import { useRiskSignals } from '../data/useRiskSignals';
import { useSessionAnalysis } from '../data/useSessionAnalysis';
import { useSessionDetail } from '../data/useSessionDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useScreenGo } from '../data/screens/useScreenGo';
import { sessionCaseId } from '../data/screens/sessionDetail';
import { signalReviewValues } from '../data/screens/signalReview';
import './SignalReview.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    // 기준 보기(단계 설명 · 근거 발화 전체) 펼침은 화면 상태다.
    this.state = { open: {} };
  }
  renderVals() {
    const v = signalReviewValues(this.props, this.state.open);
    return {
      ...v,
      types: v.types.map((t) => ({
        ...t,
        open: !!this.state.open[t.key],
        toggleLabel: this.state.open[t.key] ? '기준 닫기' : '기준 보기',
        toggle: () => this.setState({ open: { ...this.state.open, [t.key]: !this.state.open[t.key] } }),
      })),
    };
  }
}

export default function SignalReview(props) {
  const session = useAuthSession();
  const ids = readScreenIds(useSearchParams()[0]);
  const go = useScreenGo(useNavigate());
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const analysis = useSessionAnalysis(ids.sessionId, { enabled });
  const signals = useRiskSignals(ids.sessionId, analysis.analysis, { enabled });
  const assessments = useRiskAssessments(ids.sessionId, { enabled });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, analysis, signals, assessments, go });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-SignalReview">
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
            aria-label="위험도"
            style={{ padding: '22px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '18px 28px' }}
          >
            <div style={{ flex: '1 1 280px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <span className="chip c-ai">AI 초안</span>
                {v.aiAction ? (
                  <button type="button" className="btn btn-sm btn-p" onClick={v.aiAction}>
                    {v.aiActionLabel}
                  </button>
                ) : null}
              </div>
              <div style={{ fontSize: '14px' }} aria-live="polite">
                {v.aiText}
              </div>
              <span className="sub2">{v.aiOverallNote}</span>
              {(v.aiWarnings || []).map((w, wIndex) => (
                <span key={wIndex} className="sub2">
                  AI 안내 · {w}
                </span>
              ))}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span className="note">상담원 판단</span>
              <b style={{ fontSize: '16px' }}>{v.assessSummary}</b>
              <span className="sub2">{v.assessHint}</span>
              {v.assessLoadError ? (
                <button type="button" className="btn btn-sm btn-s" style={{ alignSelf: 'flex-start' }} onClick={v.reloadAssess}>
                  판단 목록 다시 불러오기
                </button>
              ) : null}
            </div>
            {v.error ? (
              <div className="note" role="alert" style={{ color: '#A33B2E', width: '100%' }}>
                {v.error}
              </div>
            ) : null}
            {v.signalError ? (
              <div className="note" role="alert" style={{ color: '#A33B2E', width: '100%' }}>
                {v.signalError}
              </div>
            ) : null}
          </section>

          <section className="card" aria-label="유형별 심각도" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">유형별 심각도</h2>
            </div>
            {(v.types || []).map((t) => (
              <div key={t.key} className="trow">
                <div>
                  <b style={{ fontSize: '16px' }}>{t.label}</b>
                  <span style={{ display: 'block', marginTop: '4px' }}>
                    <span className="chip" style={{ background: t.evBg, color: t.evFg }}>
                      {t.ev}
                    </span>
                  </span>
                </div>
                <div>
                  <span className="note">심각도</span>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                    <b style={{ fontSize: '22px' }}>{t.sevText}</b>
                    <span className="note">{t.sevSuffix}</span>
                  </div>
                  <div className="meter" role="img" aria-label={`${t.label} AI 심각도 ${t.sevText} / 5`}>
                    {(t.boxes || []).map((b) => (
                      <span
                        key={b.n}
                        aria-hidden="true"
                        style={{ background: b.bg, color: b.fg, borderColor: b.bd, cursor: 'default' }}
                      >
                        {b.n}
                      </span>
                    ))}
                  </div>
                  <span className="note" style={{ display: 'block', marginTop: '8px' }}>
                    상담원 판단
                  </span>
                  <div style={{ display: 'flex', gap: '6px' }} role="radiogroup" aria-label={`${t.label} 상담원 위험도`}>
                    {(t.levels || []).map((l) => (
                      <button
                        key={l.key}
                        type="button"
                        role="radio"
                        className="lvbtn"
                        aria-checked={l.on ? 'true' : 'false'}
                        disabled={l.disabled}
                        onClick={l.pick}
                        style={{ background: l.bg, borderColor: l.bd, color: l.fg }}
                      >
                        {l.label}
                      </button>
                    ))}
                  </div>
                  <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                    {t.assessNote}
                  </span>
                </div>
                <div style={{ minWidth: '0' }}>
                  <span className="note">해당 기준</span>
                  <div style={{ fontSize: '14px', marginTop: '2px' }}>{t.matched}</div>
                  {t.why ? (
                    <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                      AI 이유 · {t.why}
                    </span>
                  ) : null}
                  {(t.refs || []).map((r) => (
                    <Fragment key={r.key}>
                      {r.href ? (
                        <A className="sub2" to={r.href} style={{ display: 'block', marginTop: '4px' }}>
                          {r.text}
                        </A>
                      ) : (
                        <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                          {r.text}
                        </span>
                      )}
                      {t.open ? (
                        <span className="sub2" style={{ display: 'block', paddingLeft: '10px' }}>
                          {r.detail}
                        </span>
                      ) : null}
                    </Fragment>
                  ))}
                  {t.moreRefs ? (
                    <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                      {t.moreRefs}
                    </span>
                  ) : null}
                  {t.noRef ? (
                    <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                      {t.noRef}
                    </span>
                  ) : null}
                  {t.open ? (
                    <div style={{ marginTop: '10px', padding: '8px', borderRadius: '10px', background: '#F7F6F2' }}>
                      <span className="note" style={{ display: 'block', marginBottom: '4px' }}>
                        {v.rubricNote}
                      </span>
                      {(t.anchors || []).map((a) => (
                        <div key={a.n} className="anchor" style={{ background: a.bg, color: a.fg, fontWeight: a.fw }}>
                          <span>{a.n}</span>
                          <span>{a.text}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
                <button type="button" className="btn btn-sm btn-s" onClick={t.toggle}>
                  {t.toggleLabel}
                </button>
              </div>
            ))}
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '18px' }}>
            <section className="card" aria-label="회차별 추이" style={{ overflowX: 'auto' }}>
              <div className="hd">
                <h2 className="h2">회차별 추이</h2>
              </div>
              <p className="note" style={{ margin: 0, padding: '0 22px 18px' }}>
                {v.trendNote}
              </p>
            </section>

            <section
              className="card"
              aria-label="안전 플래그와 재학대 요인"
              style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
            >
              <h2 className="h2">안전 플래그 · 재학대 요인</h2>
              <span className="note">{v.flagNote}</span>
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '6px',
                  paddingTop: '10px',
                  borderTop: '1px solid #EAE7DF',
                }}
              >
                <span className="note" style={{ width: '100%' }}>
                  {v.factorTitle}
                </span>
                {v.protectiveEmpty ? <span className="sub2">{v.protectiveEmpty}</span> : null}
                {(v.protective || []).map((p) => (
                  <div key={p.key} style={{ width: '100%' }}>
                    <span className="chip c-sky" style={{ border: '1px solid #2B2A26', background: '#FFFFFF' }}>
                      {p.code}
                      {p.category ? ` ${p.category}` : ''}
                    </span>{' '}
                    {p.text}
                    <span className="sub2" style={{ display: 'block' }}>
                      {p.where}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </div>

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
