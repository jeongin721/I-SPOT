// 일정 · 월간 달력 + 일정 추가
// 원본: 다솔 님 디자인 counselor-web-design/Schedule.dc.html (front_new 브랜치)
//
// 서버 연결: 사례 · 회차는 useCaseOverview(사례마다 회차 목록을 모음), 화면에 쓸 값은 src/data/screens/schedule.ts(scheduleValues).
// 회차의 상담 일시 · 장소를 달력에 '상담 회차' 로만 놓고, 누르면 회차 상세(?case=&session=)로 간다.
// 개인 · 기관 일정, 일정 추가 · 중요 표시 · 팀 공유는 준비 중(일정과 회차의 관계가 팀 결정 전).
import { Fragment } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseOverview } from '../data/useCaseOverview';
import { needsLogin } from '../data/screens/common';
import { initialScheduleState, scheduleValues } from '../data/screens/schedule';
import { useTheme } from '../theme';
import './Schedule.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialScheduleState();
  }
  renderVals() {
    return scheduleValues({ ...this.props, ui: this.state, setUi: (patch) => this.setState(patch) });
  }
}

export default function Schedule(props) {
  const session = useAuthSession();
  const overview = useCaseOverview(session, 'sessions', { withNames: true });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, overview });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-Schedule">
      <div
        className={theme.cls}
        style={{
          minHeight: '1200px',
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
        <Sidebar active="Schedule" session={session} />

        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div className="thm-bar">
            <ThemeToggle />
          </div>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 260px' }}>
              <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>일정</h1>
            </div>
          </header>
          <Notice value={v.notice} />
          <p className="note" style={{ margin: '-6px 0 0' }}>
            {v.scopeLabel}
            {(v.notes || []).map((t, tIndex) => (
              <Fragment key={tIndex}> · {t}</Fragment>
            ))}
            <br />
            {v.notReadyNote}
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px', alignItems: 'flex-start' }}>
            <section
              className="card"
              aria-label="월간 달력"
              style={{ flex: '3 1 620px', minWidth: '0', overflow: 'hidden' }}
            >
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '10px 14px',
                  padding: '16px 18px',
                }}
              >
                <button type="button" className="mnav" aria-label="이전 달" onClick={v.prevMonth}>
                  ‹
                </button>
                <b style={{ fontSize: '20px', minWidth: '120px', textAlign: 'center' }}>{v.monthLabel}</b>
                <button type="button" className="mnav" aria-label="다음 달" onClick={v.nextMonth}>
                  ›
                </button>
                <button type="button" className="btn btn-s" style={{ minHeight: '38px' }} onClick={v.goToday}>
                  오늘
                </button>
                <div role="group" aria-label="일정 종류 보기" className="seg" style={{ marginLeft: 'auto' }}>
                  <button type="button" className={v.fAllCls} onClick={v.showAll}>
                    전체
                  </button>
                  <button type="button" className={v.fCCls} onClick={v.showC}>
                    ● 상담
                  </button>
                  <button type="button" className={v.fPCls} onClick={v.showP}>
                    ■ 개인 · 기관
                  </button>
                  <button type="button" className={v.fICls} onClick={v.showI} style={{ color: '#A33B2E' }}>
                    ! 중요
                  </button>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', background: '#F7F6F2' }}>
                <span className="dow">일</span>
                <span className="dow">월</span>
                <span className="dow">화</span>
                <span className="dow">수</span>
                <span className="dow">목</span>
                <span className="dow">금</span>
                <span className="dow">토</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))' }}>
                {(v.cells || []).map((c, cIndex) => (
                  <Fragment key={cIndex}>
                    <button
                      type="button"
                      className="cell"
                      onClick={c.pick}
                      aria-label={c.aria}
                      style={{ background: c.bg, boxShadow: c.ring }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span
                          style={{
                            width: '26px',
                            height: '26px',
                            borderRadius: '50%',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '13px',
                            fontWeight: c.fw,
                            background: c.numBg,
                            color: c.numFg,
                          }}
                        >
                          {c.num}
                        </span>
                        <span style={{ fontSize: '10px', color: '#7A776F' }}>{c.holiday}</span>
                      </span>
                      {(c.pills || []).map((p, pIndex) => (
                        <Fragment key={pIndex}>
                          <span className="pill" style={{ background: p.bg, color: p.fg, fontWeight: p.fw }}>
                            <span
                              style={{
                                width: '7px',
                                height: '7px',
                                flex: 'none',
                                borderRadius: p.radius,
                                background: p.dot,
                              }}
                            ></span>
                            {p.label}
                          </span>
                        </Fragment>
                      ))}
                      <span style={{ fontSize: '11px', color: '#6E6A62', paddingLeft: '4px' }}>{c.more}</span>
                    </button>
                  </Fragment>
                ))}
              </div>
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '8px 20px',
                  padding: '14px 18px',
                  fontSize: '12px',
                  color: '#66625A',
                  borderTop: '1px solid #EAE7DF',
                }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#7A776F' }}></span>
                  상담 회차 {v.countC}
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#B9B2A2' }}></span>
                  개인 · 기관 일정 {v.countP}
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    color: '#A33B2E',
                    fontWeight: '500',
                  }}
                >
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#A33B2E' }}></span>
                  중요 {v.countI}
                </span>
              </div>
            </section>

            <aside
              className="card"
              aria-label="선택한 날 일정"
              style={{
                flex: '1 1 320px',
                minWidth: '0',
                padding: '20px 22px',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ flex: '1' }}>
                  <div className="note">선택한 날</div>
                  <b style={{ fontSize: '19px' }}>{v.selLabel}</b>
                </div>
                <button
                  type="button"
                  className="btn btn-p"
                  disabled
                  title={v.notReady}
                  style={{ opacity: 0.5, cursor: 'not-allowed' }}
                >
                  + 일정 추가
                </button>
              </div>
              <div>
                {(v.dayEvents || []).map((e, eIndex) => (
                  <Fragment key={eIndex}>
                    <div className="ev">
                      <span style={{ fontSize: '13px', color: '#66625A' }}>{e.time}</span>
                      <span
                        style={{
                          marginTop: '5px',
                          width: '12px',
                          height: '12px',
                          borderRadius: e.radius,
                          background: e.dot,
                        }}
                      ></span>
                      <span style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <A to={e.href} style={{ fontWeight: 500, color: '#2B2A26' }}>
                          {e.title}
                        </A>
                        <span style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px' }}>
                          <span className="chip" style={{ background: e.tagBg, color: e.tagFg }}>
                            {e.tag}
                          </span>
                          <span className="note">{e.sub}</span>
                        </span>
                      </span>
                      <button
                        type="button"
                        className="impb"
                        aria-pressed="false"
                        disabled
                        title={v.notReady}
                        style={{ opacity: 0.5, cursor: 'not-allowed' }}
                      >
                        중요 표시
                      </button>
                    </div>
                  </Fragment>
                ))}
                {v.noEvents ? (
                  <>
                    <p className="note" style={{ margin: '8px 0' }}>
                      {v.emptyText}
                    </p>
                  </>
                ) : null}
              </div>
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}
