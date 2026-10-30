// 홈 (대시보드)
// 원본: 다솔 님 디자인 counselor-web-design/Main.dc.html (front_new 브랜치)
//
// 서버 연결: 진행 중 사례 수 · 미처리 업무(목록 · 종류별 수)는 useHomeDashboard 가 부르고, 화면에 쓸 값은
// src/data/screens/main.ts(mainValues)가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 오늘 일정 · 다음 상담까지 남은 시간 · 아이 앱 긴급 응답은 서버에 없어 준비 중 · '—'. 시계 · 빠른 실행은 화면 상태다.
import { Fragment } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useHomeDashboard } from '../data/useHomeDashboard';
import { needsLogin } from '../data/screens/common';
import { initialMainState, mainValues } from '../data/screens/main';
import { useTheme } from '../theme';
import './Main.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialMainState();
  }
  componentDidMount() {
    this.timer = setInterval(() => this.setState({ now: new Date() }), 20000);
  }
  componentWillUnmount() {
    clearInterval(this.timer);
  }
  renderVals() {
    return mainValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function Main(props) {
  const session = useAuthSession();
  const home = useHomeDashboard(session);
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, home });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-Main">
      <div
        className={theme.cls}
        style={{
          minHeight: '1060px',
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
        <Sidebar active="Main" session={session} />
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
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <div className="sub brn" style={{ fontWeight: '500' }}>
                {v.dateLabel}
              </div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>{v.greeting}</h1>
            </div>
          </header>
          <Notice value={v.notice} />

          <section
            aria-label="오늘 요약"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '14px',
              alignItems: 'stretch',
            }}
          >
            <div className="card stat">
              <A className="stat-hd" to="/CaseList">
                <span className="sub">{v.casesLabel}</span>
                <span className="stat-more">전체 보기 ›</span>
              </A>
              <b className="n brn">{v.casesCount}</b>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                {(v.caseTodos || []).map((t) => (
                  <A key={t.href} className="todo" to={t.href}>
                    <span className={t.chip}>{t.label}</span>
                    <span style={{ flex: '1' }}>{t.text}</span>
                    <b className="brn">›</b>
                  </A>
                ))}
              </div>
            </div>
            <div className="card stat">
              <span className="sub">{v.tasksLabel}</span>
              <b className="n brn">{v.tasksCount}</b>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                {(v.todos || []).map((t, tIndex) => (
                  <A key={tIndex} className="todo" to={t.href}>
                    <span className={t.chip}>{t.label}</span>
                    <span style={{ flex: '1' }}>{t.text}</span>
                    <b className="brn" title={t.waitedTitle}>
                      {t.waited}
                    </b>
                  </A>
                ))}
                {v.todoNote ? <span className="note">{v.todoNote}</span> : null}
              </div>
            </div>
            <div className="card stat" style={{ boxShadow: 'inset 0 4px 0 #A33B2E' }}>
              <A className="stat-hd" to="/ChildLink">
                <span className="sub acc" style={{ fontWeight: '700' }}>
                  긴급 업무
                </span>
                <span className="stat-more">아이 연계 ›</span>
              </A>
              <b className="n acc">{v.urgentCount}</b>
              <span className="note">{v.urgentText}</span>
            </div>
          </section>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'flex-start' }}>
            <section
              className="card"
              aria-label="오늘 일정"
              style={{ flex: '3 1 520px', minWidth: '0', overflow: 'hidden' }}
            >
              <div className="hd">
                <h2 className="h2">오늘 일정</h2>
                <A to="/Schedule" style={{ marginLeft: 'auto', fontSize: '13px' }}>
                  달력 보기
                </A>
              </div>
              <p className="note" style={{ margin: '0 24px 10px' }}>
                {v.scheduleNote}
              </p>
              {(v.hours || []).map((h, hIndex) => (
                <Fragment key={hIndex}>
                  <div className="hr" style={{ background: h.bg, opacity: h.op }}>
                    <span style={{ paddingTop: '8px', fontSize: '13px', color: h.labelFg, fontWeight: h.labelFw }}>
                      {h.label}
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', justifyContent: 'center' }}>
                      {h.isNowHour ? (
                        <>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <b style={{ fontSize: '12px', color: '#2B2A26' }}>지금 {v.clock}</b>
                            <span style={{ flex: '1', height: '2px', background: '#2B2A26' }}></span>
                          </span>
                        </>
                      ) : null}
                      {(h.events || []).map((e, eIndex) => (
                        <Fragment key={eIndex}>
                          <A className="ev" to={e.href} style={{ background: e.bg }}>
                            <span
                              style={{
                                width: '10px',
                                height: '10px',
                                flex: 'none',
                                borderRadius: e.radius,
                                background: e.dot,
                              }}
                            ></span>
                            <b style={{ fontWeight: '500', fontSize: '13px', width: '44px', flex: 'none' }}>{e.time}</b>
                            <span style={{ flex: '1', minWidth: '0' }}>
                              <b style={{ fontWeight: '500' }}>{e.title}</b>
                              <span className="note" style={{ marginLeft: '8px' }}>
                                {e.sub}
                              </span>
                            </span>
                          </A>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                </Fragment>
              ))}
            </section>

            <div style={{ flex: '2 1 320px', minWidth: '0', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <section
                className="card"
                aria-label="현재 시간"
                style={{
                  padding: '22px 24px',
                  background: 'linear-gradient(135deg, #F1EADA 0%, #F7F2E6 60%, #FAF6EC 100%)',
                  borderColor: '#DCCB9F',
                }}
              >
                <div className="note" style={{ color: '#2B2A26' }}>
                  지금
                </div>
                <div
                  style={{
                    color: '#7A5F28',
                    fontSize: '44px',
                    fontWeight: '700',
                    lineHeight: '1.1',
                    letterSpacing: '1px',
                  }}
                >
                  {v.clock}
                </div>
                <div
                  style={{
                    marginTop: '14px',
                    padding: '14px 16px',
                    borderRadius: '14px',
                    background: '#FFFFFF',
                    border: '1px solid #DCCB9F',
                    borderLeft: '4px solid #C2A36B',
                  }}
                >
                  <div className="note">다음 상담까지</div>
                  <b style={{ fontSize: '24px', color: '#A33B2E' }}>{v.remain}</b>
                  <div style={{ marginTop: '2px', fontSize: '14px' }}>{v.nextTitle}</div>
                  <A className="btn btn-p" to="/PreBriefing" style={{ width: '100%', marginTop: '12px' }}>
                    상담 전 브리핑 보기
                  </A>
                </div>
              </section>

              <section className="card" aria-label="빠른 실행" style={{ padding: '20px 22px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <h2 className="h2">빠른 실행</h2>
                  <button
                    type="button"
                    className="btn btn-sm btn-s"
                    style={{ marginLeft: 'auto' }}
                    onClick={v.toggleEdit}
                  >
                    {v.editLabel}
                  </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '10px' }}>
                  {(v.quick || []).map((q, qIndex) => (
                    <Fragment key={qIndex}>
                      <A className="qa" to={q.href}>
                        <span className="qi">{q.icon}</span>
                        <b style={{ fontWeight: '500' }}>{q.label}</b>
                        {v.editing ? (
                          <>
                            <button type="button" className="rm" aria-label={q.rmLabel} onClick={q.remove}>
                              ×
                            </button>
                          </>
                        ) : null}
                      </A>
                    </Fragment>
                  ))}
                </div>
                {v.editing ? (
                  <>
                    <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px solid #EAE7DF' }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {(v.addable || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button type="button" className="addq" onClick={o.add}>
                              + {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </div>
                    </div>
                  </>
                ) : null}
              </section>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
