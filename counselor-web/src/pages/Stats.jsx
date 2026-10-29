// 통계 (기간 직접 선택 · 원형 · 가로/세로 막대 · 표)
// 원본: 다솔 님 디자인 counselor-web-design/Stats.dc.html (front_new 브랜치)
//
// 서버 연결: 사례 · 회차는 useCaseOverview(사례마다 회차 목록을 모음), 화면에 쓸 값은 src/data/screens/stats.ts(statsValues).
// 지금 셀 수 있는 것: 사례 수 · 진행/종결 수, 기간 안 사례 등록 수(사례 등록일 기준 — 신고접수일 아님), 기간 안 상담 회차 수(상담일 기준).
// 신고 · 학대 판단 · 재신고 · 서비스 지표와 유형 · 연령 · 행위자 · 서비스 분포, AI 요약은 준비 중.
// 10/21 디자인(counselor-design/screens/Stats.dc.html): 기간 프리셋 순서(전체 · 이번 달 · 최근 3개월 · 직접 선택),
// 시작 · 종료일을 글자 입력 + 연 → 월 → 일 팝업으로(components/StatsDateField.jsx). 치는 중인 글자는 셈에 넣지 않고
// 올바른 날짜가 되었을 때만 기간에 넣는다(stats.ts). 기존 '달력'(기간을 두 번 눌러 고르기)도 디자인대로 남겼다.
import { Fragment } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import StatsDateField from '../components/StatsDateField';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseOverview } from '../data/useCaseOverview';
import { needsLogin } from '../data/screens/common';
import { initialStatsState, statsValues } from '../data/screens/stats';
import { useTheme } from '../theme';
import './Stats.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialStatsState();
  }
  renderVals() {
    return statsValues({ ...this.props, ui: this.state, setUi: (patch) => this.setState(patch) });
  }
}

export default function Stats(props) {
  const session = useAuthSession();
  const overview = useCaseOverview(session, 'sessions');
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, overview });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-Stats">
      <div
        className={theme.cls}
        style={{
          minHeight: '1990px',
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
        <Sidebar active="Stats" session={session} />
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
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>통계</h1>
            </div>
          </header>
          <Notice value={v.notice} />
          <p className="note" style={{ margin: '-8px 0 0' }}>
            {v.scopeLabel}
            {(v.notes || []).map((t, tIndex) => (
              <Fragment key={tIndex}> · {t}</Fragment>
            ))}
          </p>

          <section
            className="card"
            aria-label="기간 선택"
            style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 14px' }}>
              <div role="group" aria-label="빠른 기간" className="seg">
                {(v.presets || []).map((p, pIndex) => (
                  <Fragment key={pIndex}>
                    <button type="button" className={p.cls} onClick={p.pick}>
                      {p.label}
                    </button>
                  </Fragment>
                ))}
              </div>
              <StatsDateField label="시작" name="시작일" field={v.fromField} />
              <span className="note">~</span>
              <StatsDateField label="종료" name="종료일" field={v.toField} align="end" />
              <button type="button" className={`btn btn-sm ${v.calCls}`} onClick={v.toggleCal}>
                달력
              </button>
              <span className="brn" style={{ marginLeft: 'auto', fontWeight: '700' }}>
                {v.rangeLabel}
              </span>
            </div>
            {v.dateHint ? (
              <p className="note" role="status" style={{ margin: '0' }}>
                {v.dateHint}
              </p>
            ) : null}
            {v.showCal ? (
              <>
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '24px',
                    paddingTop: '6px',
                    borderTop: '1px solid #EAE7DF',
                  }}
                >
                  <div style={{ flex: '0 1 320px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.calPrev} aria-label="이전 달">
                        ‹
                      </button>
                      <b style={{ flex: '1', textAlign: 'center' }}>{v.calLabel}</b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.calNext} aria-label="다음 달">
                        ›
                      </button>
                    </div>
                    <div className="cal note" style={{ textAlign: 'center', marginBottom: '2px' }}>
                      <span>일</span>
                      <span>월</span>
                      <span>화</span>
                      <span>수</span>
                      <span>목</span>
                      <span>금</span>
                      <span>토</span>
                    </div>
                    <div className="cal">
                      {(v.cal || []).map((d, dIndex) => (
                        <Fragment key={dIndex}>
                          <button
                            type="button"
                            onClick={d.pick}
                            disabled={d.off}
                            aria-label={d.aria}
                            style={{ background: d.bg, color: d.fg, fontWeight: d.fw }}
                          >
                            {d.n}
                          </button>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                  <p className="note" style={{ flex: '1 1 220px', margin: '0', alignSelf: 'center' }}>
                    {v.pickHint}
                  </p>
                </div>
              </>
            ) : null}
          </section>

          <section
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
          >
            {(v.kpis || []).map((k, kIndex) => (
              <Fragment key={kIndex}>
                <div className="card kpi">
                  <div className="sub">{k.label}</div>
                  <b className="brn">{k.value}</b>
                  <div className="note">{k.note}</div>
                </div>
              </Fragment>
            ))}
          </section>

          <section
            aria-label="준비 중인 지표"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
          >
            {(v.pendingKpis || []).map((k, kIndex) => (
              <Fragment key={kIndex}>
                <div className="card kpi">
                  <div className="sub">{k.label}</div>
                  <b className="brn">{k.value}</b>
                  <div className="note">{k.note}</div>
                </div>
              </Fragment>
            ))}
          </section>

          <section className="card" aria-label="사례 등록 추이" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
              <h2 className="h2">사례 등록 추이</h2>
              <span className="note">{v.binLabel}</span>
              <span className="note">{v.caseTrendNote}</span>
            </div>
            <div className="vb" style={{ marginTop: '14px' }} role="img" aria-label={v.caseTrendAria}>
              {(v.caseTrend || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <div className="col" title={t.tip}>
                    <span className="note" style={{ color: '#2B2A26' }}>
                      {t.v}
                    </span>
                    <span className="b" style={{ height: t.h }}></span>
                  </div>
                </Fragment>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '8px', padding: '6px 4px 0' }}>
              {(v.caseTrend || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <span
                    className="note"
                    style={{ flex: '1', minWidth: '0', textAlign: 'center', overflow: 'hidden', whiteSpace: 'nowrap' }}
                  >
                    {t.label}
                  </span>
                </Fragment>
              ))}
            </div>
          </section>

          <section className="card" aria-label="상담 회차 추이" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
              <h2 className="h2">상담 회차 추이</h2>
              <span className="note">{v.binLabel}</span>
              <span className="note">{v.sessionTrendNote}</span>
            </div>
            <div className="vb" style={{ marginTop: '14px' }} role="img" aria-label={v.sessionTrendAria}>
              {(v.sessionTrend || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <div className="col" title={t.tip}>
                    <span className="note" style={{ color: '#2B2A26' }}>
                      {t.v}
                    </span>
                    <span className="b" style={{ height: t.h }}></span>
                  </div>
                </Fragment>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '8px', padding: '6px 4px 0' }}>
              {(v.sessionTrend || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <span
                    className="note"
                    style={{ flex: '1', minWidth: '0', textAlign: 'center', overflow: 'hidden', whiteSpace: 'nowrap' }}
                  >
                    {t.label}
                  </span>
                </Fragment>
              ))}
            </div>
          </section>

          <section className="card" aria-label="신고 접수 추이" style={{ padding: '20px 22px' }}>
            <h2 className="h2">신고 접수 추이</h2>
            <p className="note" style={{ margin: '8px 0 0' }}>
              {v.notReadyNote}
            </p>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '18px' }}>
            <section className="card" aria-label="학대 유형별 사례 수" style={{ padding: '20px 22px' }}>
              <h2 className="h2">학대 유형별 사례 수</h2>
              <p className="note" style={{ margin: '8px 0 0' }}>
                {v.notReadyNote}
              </p>
            </section>
            <section className="card" aria-label="아동 연령 비율" style={{ padding: '20px 22px' }}>
              <h2 className="h2">학대 피해 아동 연령 비율</h2>
              <p className="note" style={{ margin: '8px 0 0' }}>
                {v.notReadyNote}
              </p>
            </section>
          </div>

          <section className="card" aria-label="학대 행위자 상황" style={{ padding: '20px 22px' }}>
            <h2 className="h2">학대 행위자 상황</h2>
            <p className="note" style={{ margin: '8px 0 0' }}>
              {v.notReadyNote}
            </p>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '18px' }}>
            <section className="card" aria-label="서비스 제공 현황" style={{ padding: '20px 22px' }}>
              <h2 className="h2">서비스 제공 현황</h2>
              <p className="note" style={{ margin: '8px 0 0' }}>
                {v.notReadyNote}
              </p>
            </section>
            <section className="card" aria-label="서비스 진행 표" style={{ padding: '20px 22px' }}>
              <h2 className="h2">서비스 진행 상태</h2>
              <p className="note" style={{ margin: '8px 0 0' }}>
                {v.notReadyNote}
              </p>
            </section>
          </div>

          <section
            className="card"
            aria-label="AI 분석"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">AI가 본 이 기간</h2>
              <span className="chip c-ai">AI 초안</span>
            </div>
            <p className="note" style={{ margin: '0' }}>
              {v.notReadyNote}
            </p>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
