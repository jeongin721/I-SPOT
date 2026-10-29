// 2 · 유형별 위험도 (AI 제안 · 심각도 1~5 · 상담원 판단)
// 원본: 10/27 디자인 counselor-design/screens/SignalReview.dc.html (frontend261021 브랜치). 예전 '위험 신호 검토' 와
// '유형별 위험도'(RiskProfile) 두 화면이 디자인에서 이 화면 하나가 됐다. #/RiskProfile 주소는 여기로 넘긴다.
//
// 서버 연결: 화면 주소 ?case=…&session=…(&ask=1 이면 판단 팝업을 연 채 시작). AI 분석 상태 · 심각도(severity_ratings) ·
// 보호요인(protective_factors)은 useSessionAnalysis, 유형별 관련 신호 · 근거 발화는 useRiskSignals(근거 위치는 원문에서),
// 상담원 판단(회차 전체 상 · 중 · 하 하나, 2026-10-29)은 useOverallRiskAssessment, 머리는 useSessionDetail · useCaseDetail 이 부르고,
// 화면에 쓸 값은 src/data/screens/signalReview.ts 가 만든다(디자인 칸 → 서버 값 대응도 그 파일 머리에 있다).
// 이 파일은 훅을 부르고 배치만 한다. 판단 없이 다음 단계로 가려 하면(nextBlocked) 옮기지 않고 팝업 "위험도를 선택해주세요." 를 띄운다.
// 서버에 없는 것(회차 전체 AI 위험도 · 안전 플래그 · 재학대 요인 · 위험요인 · 회차별 추이 · 심각도 상담사 수정)은 준비 중이다.
import { Fragment, useEffect, useRef } from 'react';
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
import { useOverallRiskAssessment } from '../data/useOverallRiskAssessment';
import { useRiskSignals } from '../data/useRiskSignals';
import { useSessionAnalysis } from '../data/useSessionAnalysis';
import { useSessionDetail } from '../data/useSessionDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds, screenHref } from '../data/screens/links';
import { useScreenGo } from '../data/screens/useScreenGo';
import { sessionCaseId } from '../data/screens/sessionDetail';
import { readAskLevel, signalReviewValues } from '../data/screens/signalReview';
import './SignalReview.css';

/** 팝업의 '닫기' · '확인' 단추와 상담원 판단 첫 단추(팝업을 닫으면 여기로 초점을 옮긴다). */
const ASK_X_ID = 'sr-ask-x';
const ASK_OK_ID = 'sr-ask-ok';
const LEVEL_FIRST_ID = 'sr-level-first';

/** 팝업 안에서 Tab 이 덮개 뒤 화면으로 나가지 않게 '닫기' 와 '확인' 사이를 돈다(aria-modal). */
function trapTab(event) {
  if (event.key !== 'Tab') return;
  const first = document.getElementById(ASK_X_ID);
  const last = document.getElementById(ASK_OK_ID);
  if (!first || !last) return;
  const active = document.activeElement;
  const next = active === first ? last : active === last ? first : event.shiftKey ? last : first;
  event.preventDefault();
  next.focus();
}

/** 상 · 중 · 하 묶음(radiogroup)에서 화살표로 이웃 단추에 초점을 옮긴다. 고르는 것은 단추 누름(Enter · Space)이다. */
function moveLevelFocus(event) {
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
  if (!step) return;
  const buttons = Array.from(event.currentTarget.querySelectorAll('[role="radio"]'));
  const index = buttons.indexOf(document.activeElement);
  if (index < 0) return;
  event.preventDefault();
  buttons[(index + step + buttons.length) % buttons.length].focus();
}

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    // 기준 보기(단계 설명 · 근거 발화 전체) 펼침과 판단 팝업(ask)은 화면 상태다. ask 는 주소의 ?ask=1 로도 켜진다.
    this.state = { open: {}, ask: !!props.askInitially };
    // 팝업이 실제로 그려져 있는가(ask 이고 막을 이유가 있을 때). Esc 는 보이는 팝업만 닫는다.
    this.shown = false;
    this.onKey = (event) => {
      if (event.key === 'Escape' && this.shown) this.closeAsk();
    };
  }
  componentDidMount() {
    window.addEventListener('keydown', this.onKey);
  }
  componentWillUnmount() {
    window.removeEventListener('keydown', this.onKey);
  }
  openAsk() {
    this.setState({ ask: true });
  }
  closeAsk() {
    this.setState({ ask: false });
    // ?ask=1 로 왔으면 주소에서 떼어 새로고침 · 뒤로 가기에 팝업이 다시 뜨지 않게 한다.
    // 닫은 뒤 초점은 화면 쪽 effect 가 상담원 판단 첫 단추로 옮긴다.
    if (this.props.askInitially) this.props.clearAsk();
  }
  renderVals() {
    const v = signalReviewValues(this.props, this.state.open);
    const ask = () => this.openAsk();
    // 팝업은 막을 이유가 있을 때만 보인다 — ?ask=1 로 왔어도 판단이 있거나 승인 완료면 띄우지 않는다.
    this.shown = this.state.ask && v.nextBlocked;
    return {
      ...v,
      // 판단이 없으면(nextBlocked) 단계 표시의 뒤 단계 링크(3 · 요약 · 일지 작성)도 옮기지 않고 팝업을 띄운다.
      steps: (v.steps || []).map((s, i) => (v.nextBlocked && s.href && i > 1 ? { ...s, block: ask } : s)),
      ask: this.shown,
      askLevel: ask,
      closeAsk: () => this.closeAsk(),
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
  const search = useSearchParams()[0];
  const ids = readScreenIds(search);
  const askInitially = readAskLevel(search);
  const navigate = useNavigate();
  const go = useScreenGo(navigate);
  // ?ask=1 로 열린 팝업을 닫으면 주소에서 ask 를 뗀다(새로고침 · 뒤로 가기에 다시 뜨지 않게). 같은 사례 · 회차 주소로 바꿔 끼운다.
  const clearAsk = () => navigate(screenHref('/SignalReview', ids), { replace: true });
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const analysis = useSessionAnalysis(ids.sessionId, { enabled });
  const signals = useRiskSignals(ids.sessionId, analysis.analysis, { enabled });
  const overall = useOverallRiskAssessment(ids.sessionId, { enabled });
  const theme = useTheme();
  const v = useDC(Logic, {
    ...props,
    session,
    ids,
    detail,
    caseDetail,
    analysis,
    signals,
    overall,
    go,
    askInitially,
    clearAsk,
  });
  // 팝업이 보이게 되는 모든 경우(아래 단추 · 단계 표시 · ?ask=1 로 돌려보내짐)에 '확인' 단추로 초점을 옮기고(aria-modal),
  // 닫히면 고를 곳인 상담원 판단 첫 단추로 옮긴다. 그린 뒤에 옮기려고 effect 에서 한다(requestAnimationFrame 은 숨은 탭에서 돌지 않는다).
  const askWasShown = useRef(false);
  useEffect(() => {
    if (v.ask) document.getElementById(ASK_OK_ID)?.focus();
    else if (askWasShown.current) document.getElementById(LEVEL_FIRST_ID)?.focus();
    askWasShown.current = v.ask;
  }, [v.ask]);
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
          <StepNav steps={v.steps} />

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
            <div style={{ flex: '0 1 340px', minWidth: '0', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span className="note">상담원 판단</span>
              <div
                style={{ display: 'flex', gap: '6px' }}
                role="radiogroup"
                aria-label="상담원 위험도"
                onKeyDown={moveLevelFocus}
              >
                {(v.levels || []).map((l, lIndex) => (
                  <button
                    key={l.key}
                    id={lIndex === 0 ? LEVEL_FIRST_ID : undefined}
                    type="button"
                    role="radio"
                    className="lvbtn"
                    data-level={l.key}
                    aria-checked={l.on ? 'true' : 'false'}
                    disabled={l.disabled}
                    onClick={l.pick}
                    style={{ background: l.bg, borderColor: l.bd, color: l.fg }}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
              <span className="sub2" aria-live="polite">
                {v.assessSaving ? '저장 중…' : v.assessNote}
              </span>
              <span className="sub2">{v.assessHint}</span>
              {v.assessLoadError ? (
                <button type="button" className="btn btn-sm btn-s" style={{ alignSelf: 'flex-start' }} onClick={v.reloadAssess}>
                  판단 다시 불러오기
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
            {v.canNext && !v.nextBlocked ? (
              <A className="btn btn-p" to={v.nextHref} style={{ marginLeft: 'auto' }}>
                {v.nextLabel}
              </A>
            ) : v.canNext ? (
              // 판단이 없으면 옮기지 않고 팝업을 띄운다(단추는 눌리는 채로 둔다 — 왜 못 가는지 팝업이 알려 준다).
              <button
                type="button"
                className="btn btn-p"
                style={{ marginLeft: 'auto' }}
                aria-haspopup="dialog"
                onClick={v.askLevel}
              >
                {v.nextLabel}
              </button>
            ) : (
              <button type="button" className="btn btn-p" disabled style={{ marginLeft: 'auto' }}>
                {v.nextLabel}
              </button>
            )}
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
        {v.ask ? (
          <div className="lv-ov" onClick={v.closeAsk}>
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="sr-ask-title"
              aria-describedby="sr-ask-hint"
              className="lv-dlg"
              onClick={(event) => event.stopPropagation()}
              onKeyDown={trapTab}
            >
              <div className="lv-hd">
                <h2 id="sr-ask-title">{v.askText}</h2>
                <button id={ASK_X_ID} type="button" className="lv-x" aria-label="닫기" onClick={v.closeAsk}>
                  ×
                </button>
              </div>
              <div className="lv-bd">
                <p id="sr-ask-hint" className="sub" style={{ margin: 0 }}>
                  {v.askHint}
                </p>
                <button id={ASK_OK_ID} type="button" className="btn btn-p" onClick={v.closeAsk}>
                  확인
                </button>
              </div>
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}
