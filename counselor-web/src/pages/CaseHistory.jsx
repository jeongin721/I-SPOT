// 탭 2 · 상담 이력 (① 지금까지 상담 → ② 상담 회차 → ③ 회차별 세부 신호)
// 원본: 다솔 님 디자인 counselor-web-design/CaseHistory.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 회차 목록은 useCaseDetail 이 부르고, 화면에 쓸 값은
// src/data/screens/caseDetail.ts(caseHistoryValues)가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 누적 요약 · 주제 비중 · 회차별 세부 신호 · 상담 유형 · 신호 채택 수는 서버에 없어 준비 중 · '—'.
import { Fragment, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseSignals } from '../data/useCaseSignals';
import { caseHistoryValues } from '../data/screens/caseDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import './CaseHistory.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { open: false, sigOnly: false };
  }
  renderVals() {
    return caseHistoryValues(this.props);
  }
}

export default function CaseHistory(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const detail = useCaseDetail(caseId, { enabled: signedIn(session) });
  const signals = useCaseSignals(detail, { enabled: signedIn(session) });
  const theme = useTheme();
  // '전 회차 보기' 창이 열렸는가(화면 안에서만 쓰는 값).
  const [historyOpen, setHistoryOpen] = useState(false);
  const v = useDC(Logic, { ...props, session, detail, signals, caseId, historyOpen, setHistoryOpen });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-CaseHistory">
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
            <A to="/CaseList">사례 관리</A> › {v.crumb}
          </nav>
          <Notice value={v.notice} />
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <A className="btn btn-sm btn-s" to="/CaseList">
              ← 목록
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
                <span className="sub">{v.sub}</span>
                <span className={`chip ${v.riskCls}`}>{v.riskChip}</span>
              </div>
              <div className="note">{v.meta}</div>
            </div>
            <A className="btn btn-s" to={v.uploadHref}>
              ↑ 녹취 올리기
            </A>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A to={v.tabs.detail}>내담자 정보</A>
            <A className="on" aria-current="page" to={v.tabs.history}>
              상담 이력
            </A>
            <A to={v.tabs.briefing}>상담 전 브리핑</A>
            <A to={v.tabs.docs}>문서함</A>
          </nav>
          <section className="card" aria-label="지금까지 상담" style={{ padding: '24px 26px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px' }}>
              <span className="secno">1</span>
              <h2 className="h2">지금까지 상담</h2>
              <span className="chip c-ai">{v.overviewChip}</span>
              <span className="src" style={{ marginLeft: 'auto' }}>
                근거 · 확정 일지 · 검수본 · 체크인
              </span>
            </div>
            <div
              style={{
                marginTop: '16px',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '12px',
              }}
            >
              {(v.periods || []).map((p, pIndex) => (
                <div key={pIndex} className="box">
                  <div className="note">{p.range}</div>
                  <b style={{ fontWeight: '500' }}>{p.title}</b>
                  {p.note ? <div className="note">{p.note}</div> : null}
                </div>
              ))}
            </div>
            {v.overviewNote ? (
              <p className="note" style={{ margin: '12px 0 0' }}>
                {v.overviewNote}
              </p>
            ) : null}
            <div style={{ marginTop: '18px', display: 'flex', flexWrap: 'wrap', gap: '20px' }}>
              <div style={{ flex: '1 1 360px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div className="note">주제 비중</div>
                {(v.topics || []).map((t, tIndex) => (
                  <div
                    key={tIndex}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '110px 1fr 40px',
                      gap: '10px',
                      alignItems: 'center',
                    }}
                  >
                    <span>{t.label}</span>
                    <span className="bar">
                      <span style={{ width: t.width }} />
                    </span>
                    <span className="note">{t.pct}</span>
                  </div>
                ))}
              </div>
              <div style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {(v.insights || []).map((x, xIndex) => (
                  <div key={xIndex} className="box">
                    <b>{x.title}</b>
                    <div>{x.text}</div>
                    {x.src ? <div className="src">{x.src}</div> : null}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="card" aria-label="상담 회차" style={{ padding: '22px 24px', position: 'relative' }}>
            <div
              style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px', marginBottom: '10px' }}
            >
              <span className="secno">2</span>
              <h2 className="h2">상담 회차</h2>
              <span className="note">최근 3회차</span>
              <button
                type="button"
                className="btn btn-sm btn-s"
                style={{ marginLeft: 'auto' }}
                aria-haspopup="dialog"
                aria-expanded={v.open}
                onClick={v.toggleOpen}
              >
                전 회차 보기 · {v.total}회
              </button>
            </div>
            {v.sessionsNote ? (
              <p className="note" style={{ margin: '0 0 12px' }}>
                {v.sessionsNote}
              </p>
            ) : null}
            <div>
              {(v.recent || []).map((s, sIndex) => (
                <Fragment key={sIndex}>
                  <A className="srow" to={s.href}>
                    <b>{s.no}</b>
                    <span>{s.date}</span>
                    <span className="note">{s.kind}</span>
                    <span className="note">{s.sig}</span>
                    <span className={s.st}>{s.status}</span>
                  </A>
                </Fragment>
              ))}
            </div>
            {v.open ? (
              <>
                <div className="pop" role="dialog" aria-label="전 회차">
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '14px 16px 10px',
                      borderBottom: '1px solid #EAE7DF',
                    }}
                  >
                    <b style={{ fontSize: '15px' }}>전 회차 · {v.shownCount}</b>
                    <label
                      style={{
                        marginLeft: 'auto',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontSize: '12.5px',
                        color: '#66625A',
                        cursor: 'pointer',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={false}
                        disabled
                        title={v.notReady}
                        style={{ accentColor: '#C2A36B' }}
                      />
                      신호 있는 회차만
                    </label>
                    <button
                      type="button"
                      aria-label="닫기"
                      onClick={v.toggleOpen}
                      style={{
                        border: '0',
                        background: 'transparent',
                        fontSize: '18px',
                        color: '#7A776F',
                        cursor: 'pointer',
                        padding: '0 2px',
                      }}
                    >
                      ×
                    </button>
                  </div>
                  <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '4px 8px 8px' }}>
                    {(v.all || []).map((s, sIndex) => (
                      <Fragment key={sIndex}>
                        <A className="prow" to={s.href}>
                          <b>{s.no}</b>
                          <span>{s.date}</span>
                          <span className="note">{s.kindShort}</span>
                          <span className="note">{s.sig}</span>
                          <span className={s.st}>{s.status}</span>
                        </A>
                      </Fragment>
                    ))}
                  </div>
                </div>
              </>
            ) : null}
          </section>

          <section className="card" aria-label="회차별 세부 신호" style={{ padding: '22px 24px' }}>
            <div
              style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px', marginBottom: '10px' }}
            >
              <span className="secno">3</span>
              <h2 className="h2">회차별 세부 신호</h2>
              <span className="src">채택 신호 · 근거 발화 수</span>
            </div>
            {v.signalNote ? (
              <p className="note" style={{ margin: '0 0 10px' }}>
                {v.signalNote}
              </p>
            ) : null}
            <div style={{ overflowX: 'auto' }}>
              <div className="mx" style={{ minWidth: '640px' }}>
                <span className="rl note">세부 신호</span>
                {(v.cols || []).map((c, cIndex) => (
                  <Fragment key={cIndex}>
                    <A to={c.href} className="note" style={{ textDecoration: 'none', color: '#6E6A62' }}>
                      {c.label}
                    </A>
                  </Fragment>
                ))}
                {(v.mrows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <span className="rl">
                      <span className="chip c-normal" style={{ height: '20px', fontSize: '11px', marginRight: '6px' }}>
                        {r.type}
                      </span>
                      {r.name}
                    </span>
                    {(r.cells || []).map((x, xIndex) => (
                      <Fragment key={xIndex}>
                        <span>
                          <span
                            className="dot"
                            title={x.tip}
                            style={{ background: x.bg, color: x.fg, boxShadow: x.ring }}
                          >
                            {x.v}
                          </span>
                        </span>
                      </Fragment>
                    ))}
                  </Fragment>
                ))}
              </div>
            </div>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '14px',
                marginTop: '10px',
                fontSize: '12px',
                color: '#7A776F',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span className="dot" style={{ width: '18px', height: '18px', background: '#EAE7DF' }}></span>1번
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span className="dot" style={{ width: '18px', height: '18px', background: '#7A776F' }}></span>2번 이상
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span
                  className="dot"
                  style={{
                    width: '18px',
                    height: '18px',
                    background: '#FFFFFF',
                    boxShadow: 'inset 0 0 0 1.5px #7A776F',
                  }}
                ></span>
                보류 (화자 확인 중)
              </span>
            </div>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
