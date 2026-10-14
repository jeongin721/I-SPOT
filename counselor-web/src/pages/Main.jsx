// 홈 (대시보드)
// 원본: 다솔 님 디자인 counselor-web-design/Main.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useTheme } from '../theme';
import './Main.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { now: new Date(), editing: false, quick: ['upload', 'schedule', 'closure', 'search'] };
  }
  componentDidMount() {
    this.timer = setInterval(() => this.setState({ now: new Date() }), 20000);
  }
  componentWillUnmount() {
    clearInterval(this.timer);
  }
  renderVals() {
    const s = this.state;
    const now = s.now;
    const pad = (n) => String(n).padStart(2, '0');
    const mins = now.getHours() * 60 + now.getMinutes();
    const days = ['일', '월', '화', '수', '목', '금', '토'];
    const dateLabel = `${now.getFullYear()}년 ${now.getMonth() + 1}월 ${now.getDate()}일 ${days[now.getDay()]}요일`;
    const clock = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    const events = [
      { m: 600, t: 'p', title: '기관 사례회의', sub: '회의실 2', href: '/Schedule' },
      { m: 780, t: 'c', title: '지호 · 정기상담 4회차', sub: '면담실 A', href: '/Schedule' },
      { m: 870, t: 'c', title: '서준 · 초기면담', sub: '가정 방문', href: '/Schedule' },
      { m: 960, t: 'c', title: '서윤 · 정기상담 9회차', sub: '면담실 B · 브리핑 준비됨', href: '/PreBriefing' },
      { m: 1050, t: 'p', title: '슈퍼비전', sub: '팀장 면담 · 30분', href: '/Schedule' },
    ];
    const nowH = now.getHours();
    const hours = [];
    for (let h = 9; h <= 18; h++) {
      const evs = events
        .filter((e) => Math.floor(e.m / 60) === h)
        .map((e) => {
          const c = e.t === 'c';
          return {
            time: `${pad(Math.floor(e.m / 60))}:${pad(e.m % 60)}`,
            title: e.title,
            sub: e.sub,
            href: e.href,
            dot: c ? '#7A776F' : '#DAD5C9',
            radius: c ? '50%' : '2px',
            bg: '#F7F6F2',
          };
        });
      const isNowHour = h === nowH;
      hours.push({
        label: `${pad(h)}:00`,
        events: evs,
        isNowHour,
        bg: isNowHour ? '#F7F6F2' : '#FFFFFF',
        op: h < nowH ? 0.5 : 1,
        labelFg: isNowHour ? '#2B2A26' : '#7A776F',
        labelFw: isNowHour ? 700 : 400,
      });
    }
    const next = events.find((e) => e.t === 'c' && e.m > mins);
    let remain = '오늘 남은 상담 없음',
      nextTitle = '내일 첫 상담 10:00 · 하은 전화상담';
    if (next) {
      const d = next.m - mins;
      const hh = Math.floor(d / 60);
      const mm = d % 60;
      remain = hh > 0 ? `${hh}시간 ${mm}분 남음` : `${mm}분 남음`;
      nextTitle = `${pad(Math.floor(next.m / 60))}:${pad(next.m % 60)} ${next.title}`;
    }
    const pool = {
      upload: { label: '녹취 올리기', icon: '↑', href: '/UploadModal' },
      schedule: { label: '일정 추가', icon: '+', href: '/Schedule' },
      closure: { label: '종결 검토', icon: '✓', href: '/Closure' },
      search: { label: '사례 찾기', icon: '⌕', href: '/CaseList' },
      stats: { label: '통계', icon: '▦', href: '/Stats' },
      briefing: { label: '상담 전 브리핑', icon: '☰', href: '/PreBriefing' },
    };
    const quick = s.quick.map((k) => ({
      ...pool[k],
      rmLabel: `${pool[k].label} 빼기`,
      remove: (ev) => {
        if (ev && ev.preventDefault) ev.preventDefault();
        this.setState({ quick: s.quick.filter((x) => x !== k) });
      },
    }));
    const addable = Object.keys(pool)
      .filter((k) => !s.quick.includes(k))
      .map((k) => ({ label: pool[k].label, add: () => this.setState({ quick: [...s.quick, k] }) }));
    return {
      hours,
      clock,
      dateLabel,
      remain,
      nextTitle,
      quick,
      addable,
      editing: s.editing,
      editLabel: s.editing ? '완료' : '편집',
      toggleEdit: () => this.setState({ editing: !s.editing }),
    };
  }
}

export default function Main(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const theme = useTheme();
  const v = useDC(Logic, props);
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
            <ThemeToggle />
          </div>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <div className="sub brn" style={{ fontWeight: '500' }}>
                {v.dateLabel}
              </div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>안녕하세요, 이서연 상담원님</h1>
            </div>
          </header>

          <section
            aria-label="오늘 요약"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '14px',
              alignItems: 'stretch',
            }}
          >
            <A className="card stat" to="/CaseList">
              <span className="sub">진행 중 내담자</span>
              <b className="n brn">10</b>
            </A>
            <div className="card stat">
              <span className="sub">미처리 업무</span>
              <b className="n brn">7</b>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                <A className="todo" to="/SttReview">
                  <span className="chip c-sand">STT 검수</span>
                  <span style={{ flex: '1' }}>서윤 8회차</span>
                  <b className="brn">1</b>
                </A>
                <A className="todo" to="/NoteWrite">
                  <span className="chip c-sky">상담 일지 작성</span>
                  <span style={{ flex: '1' }}>서윤 8회차 외</span>
                  <b className="brn">2</b>
                </A>
                <A className="todo" to="/ChildLink">
                  <span className="chip c-check">앱 확인</span>
                  <span style={{ flex: '1' }}>오늘 09:00 묶음</span>
                  <b className="brn">4</b>
                </A>
              </div>
            </div>
            <A className="card stat" to="/ChildLink" style={{ boxShadow: 'inset 0 4px 0 #A33B2E' }}>
              <span className="sub acc" style={{ fontWeight: '700' }}>
                긴급 업무
              </span>
              <b className="n acc">1</b>
              <span style={{ fontSize: '14px' }}>민준 · 오늘 08:12 체크인</span>
            </A>
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
