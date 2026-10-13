// 탭 2 · 상담 이력 (① 지금까지 상담 → ② 상담 회차 → ③ 회차별 세부 신호)
// 원본: I-SPOT 디자인 캔버스 보드 CaseHistory.dc.html (자동 변환 후 다듬어 쓰세요)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 회차 목록은 useCaseDetail 이 부르고, 화면에 쓸 값은
// src/data/screens/caseDetail.ts(caseHistoryValues)가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 누적 요약 · 주제 비중 · 회차별 세부 신호 · 상담 유형 · 신호 채택 수는 서버에 없어 준비 중 · '—'.
import { Fragment } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { caseHistoryValues } from '../data/screens/caseDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import './CaseHistory.css';

class Logic extends DCLogic {
  renderVals() {
    return caseHistoryValues(this.props);
  }
}

export default function CaseHistory(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const detail = useCaseDetail(caseId, { enabled: signedIn(session) });
  const v = useDC(Logic, { ...props, session, detail, caseId });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-CaseHistory">
      <div
        style={{
          minHeight: '1550px',
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
              아이 연계<span className="cnt">4</span>
            </A>
            <A to="/Closure">
              종결 검토<span className="cnt">2</span>
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
            <A to="/CaseList">사례 관리</A> › {v.crumb}
          </nav>
          <Notice value={v.notice} />
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
                <span className="sub">{v.sub}</span>
                <span className="chip c-normal">{v.riskChip}</span>
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
            <A to={v.tabs.app}>아이 연계</A>
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
          <section className="card" aria-label="상담 회차" style={{ padding: '22px 24px' }}>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: '8px 12px',
                marginBottom: '14px',
              }}
            >
              <span className="secno">2</span>
              <h2 className="h2">상담 회차</h2>
            </div>
            {v.sessionsNote ? (
              <p className="note" style={{ margin: '0 0 12px' }}>
                {v.sessionsNote}
              </p>
            ) : null}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
              }}
            >
              {(v.sessions || []).map((s, sIndex) => (
                <Fragment key={sIndex}>
                  <A className="scard" to={s.href}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <b className="brn" style={{ fontSize: '18px' }}>
                        {s.no}
                      </b>
                      <span className={s.st} style={{ marginLeft: 'auto' }}>
                        {s.status}
                      </span>
                    </span>
                    <span style={{ fontSize: '14px' }}>{s.date}</span>
                    <span className="note">{s.kind}</span>
                    <span className="note">{s.sig}</span>
                  </A>
                </Fragment>
              ))}
            </div>
          </section>
          <section className="card" aria-label="회차별 세부 신호" style={{ padding: '22px 24px' }}>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: '8px 12px',
                marginBottom: '10px',
              }}
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
                    <A to={c.href} className="note" style={{ textDecoration: 'none', color: '#5F6A73' }}>
                      {c.label}
                    </A>
                  </Fragment>
                ))}
                {(v.mrows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <span className="rl">
                      <span
                        className="chip c-normal"
                        style={{ height: '20px', fontSize: '11px', marginRight: '6px' }}
                      >
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
                color: '#6F7880',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span className="dot" style={{ width: '18px', height: '18px', background: '#EEE8DA' }} />
                1번
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span className="dot" style={{ width: '18px', height: '18px', background: '#6F7880' }} />
                2번 이상
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span
                  className="dot"
                  style={{
                    width: '18px',
                    height: '18px',
                    background: '#FFFFFF',
                    boxShadow: 'inset 0 0 0 1.5px #6F7880',
                  }}
                />
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
