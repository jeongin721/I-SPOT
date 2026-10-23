// 2 › 유형별 위험도 (AI 제안 · 심각도 1~5 · 상담원 판단)
// 원본: 다솔 님 디자인 counselor-web-design/RiskProfile.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=…&session=…. AI 심각도(severity_ratings)는 useSessionAnalysis, 유형별 관련 신호 · 근거 발화는
// useRiskSignals, 상담원 판단(상 · 중 · 하)은 useRiskAssessments, 머리는 useSessionDetail · useCaseDetail 이 부르고,
// 화면에 쓸 값은 src/data/screens/riskProfile.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 서버에 없는 것(회차 전체 AI 위험도 · 안전 플래그 · 재학대 요인 · 회차별 추이 · 다음 상담 확인 사항)은 준비 중이다.
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
import { riskProfileValues } from '../data/screens/riskProfile';
import './RiskProfile.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    // 참고 기준(단계 설명) 펼침은 화면 상태다.
    this.state = { open: {} };
  }
  renderVals() {
    const v = riskProfileValues(this.props, this.state.open);
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

export default function RiskProfile(props) {
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
    <div className="pg-RiskProfile">
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
            <A
              to={v.signalHref}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                minHeight: '34px',
                padding: '0 13px',
                borderRadius: '9px',
                fontSize: '13px',
                color: '#66625A',
                textDecoration: 'none',
              }}
            >
              위험 신호
            </A>
            <button type="button" className="on">
              유형별 위험도
            </button>
          </nav>

          <section
            className="card"
            aria-label="위험도"
            style={{ padding: '22px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '18px 28px' }}
          >
            <div style={{ flex: '1 1 280px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="note">AI 제안 · 회차 전체</span>
                <span className="chip c-ai">AI 제안 · 판정 아님</span>
              </div>
              <div style={{ fontSize: '14px', marginTop: '4px' }}>{v.aiOverallNote}</div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: '1 1 280px' }}>
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
              <h2 className="h2">유형별 심각도 · 상담원 판단</h2>
              <span className="note">AI 단계는 제안이라 고칠 수 없고, 상담원 판단(상 · 중 · 하)은 유형마다 저장됩니다</span>
            </div>
            {(v.types || []).map((t) => (
              <Fragment key={t.key}>
                <div className="trow">
                  <div>
                    <b style={{ fontSize: '16px' }}>{t.label}</b>
                    <span style={{ display: 'block', marginTop: '4px' }}>
                      <span className="chip c-normal">{t.ev}</span>
                    </span>
                  </div>
                  <div>
                    <span className="note">AI 심각도 제안</span>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                      <b style={{ fontSize: '22px' }}>{t.sevText}</b>
                      <span className="note">{t.sevSuffix}</span>
                    </div>
                    <div className="meter" role="img" aria-label={`${t.label} AI 심각도 ${t.sevText} / 5`}>
                      {(t.boxes || []).map((b) => (
                        <Fragment key={b.n}>
                          <span
                            aria-hidden="true"
                            style={{
                              background: b.on ? '#2B2A26' : '#FFFFFF',
                              color: b.on ? '#FFFFFF' : '#98948B',
                              borderColor: b.on ? 'transparent' : '#DAD5C9',
                            }}
                          >
                            {b.n}
                          </span>
                        </Fragment>
                      ))}
                    </div>
                    <span className="note" style={{ display: 'block', marginTop: '8px' }}>
                      상담원 판단
                    </span>
                    <div style={{ display: 'flex', gap: '6px' }} role="radiogroup" aria-label={`${t.label} 상담원 위험도`}>
                      {(t.levels || []).map((l) => (
                        <Fragment key={l.key}>
                          <button
                            type="button"
                            role="radio"
                            className="lvbtn"
                            aria-checked={l.on ? 'true' : 'false'}
                            disabled={l.disabled}
                            onClick={l.pick}
                            style={{
                              background: l.on ? '#F1EADA' : '#FFFFFF',
                              borderColor: l.on ? '#2B2A26' : '#DAD5C9',
                              color: l.on ? '#2B2A26' : '#66625A',
                              fontWeight: l.on ? 700 : 400,
                            }}
                          >
                            {l.label}
                          </button>
                        </Fragment>
                      ))}
                    </div>
                    <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                      {t.assessNote}
                    </span>
                  </div>
                  <div style={{ minWidth: '0' }}>
                    <span className="note">AI 가 든 이유</span>
                    <div style={{ fontSize: '14px', marginTop: '2px' }}>{t.matched}</div>
                    {(t.refs || []).map((r, rIndex) => (
                      <Fragment key={rIndex}>
                        <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                          {r}
                        </span>
                      </Fragment>
                    ))}
                    {t.moreRefs ? (
                      <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                        {t.moreRefs}
                      </span>
                    ) : null}
                    {t.open ? (
                      <>
                        <div style={{ marginTop: '10px', padding: '8px', borderRadius: '10px', background: '#F7F6F2' }}>
                          <span className="note" style={{ display: 'block', marginBottom: '4px' }}>
                            {v.rubricNote}
                          </span>
                          {(t.rubric || []).map((a) => (
                            <Fragment key={a.n}>
                              <div
                                className="anchor"
                                style={{
                                  background: a.on ? '#F1EADA' : 'transparent',
                                  color: a.on ? '#2B2A26' : '#7A776F',
                                  fontWeight: a.on ? 700 : 400,
                                }}
                              >
                                <span>{a.n}</span>
                                <span>{a.text}</span>
                              </div>
                            </Fragment>
                          ))}
                        </div>
                      </>
                    ) : null}
                  </div>
                  <button type="button" className="btn btn-sm btn-s" onClick={t.toggle}>
                    {t.toggleLabel}
                  </button>
                </div>
              </Fragment>
            ))}
          </section>

          <section
            className="card"
            aria-label="준비 중인 항목"
            style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: '6px' }}
          >
            <h2 className="h2">준비 중</h2>
            {(v.notReady || []).map((n, nIndex) => (
              <span key={nIndex} className="note">
                {n}
              </span>
            ))}
          </section>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            <A className="btn btn-s" to={v.signalHref}>
              ← 위험 신호
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
