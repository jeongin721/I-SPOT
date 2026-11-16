// Home 화면 마크업 — tools/dc2jsx.py 가 디자인(Home.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './Home.css';

export default function View({ v }) {
  return (
    <div className="pg-Home">
      <div className={v.themeCls} style={{ minHeight: "1060px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
        {v.jobShow ? (
          <>
            <div className={`job-toast ${v.jobCls}`} role="status" aria-live="polite">
              {v.jobRun ? (
                <>
                  <span className="job-spin" aria-hidden="true" />
                  <span>
                    분석 중입니다...
                  </span>
                  <span className="job-file">
                    {v.jobName}
                  </span>
                </>
              ) : null}
              {v.jobDone ? (
                <>
                  <span className="job-ok" aria-hidden="true">
                    ✓
                  </span>
                  <span>
                    분석 완료
                  </span>
                  <a className="job-go" href="#/Step1Record" onClick={v.jobGo}>
                    검수
                  </a>
                </>
              ) : null}
            </div>
          </>
        ) : null}
        <aside className="side" aria-label="주 메뉴">
          <a className="logo" href="#/Home">
            <span className="mk">
              온
            </span>
            <b style={{ fontSize: "17px" }}>
              온담
            </b>
          </a>
          <input type="checkbox" id="mnav" className="mnav-tg" aria-label="메뉴 열기" />
          <label htmlFor="mnav" className="mnav-btn">
            <i aria-hidden="true" />
            메뉴
          </label>
          <a className="cta" href="#/Upload" onClick={v.markBack}>
            ↑ 녹취 · 자료 올리기
          </a>
          <a className="cta2" href="#/CaseRegister" onClick={v.markBack}>
            + 새 사례 등록
          </a>
          <nav className="nav" aria-label="메뉴">
            <a className="on" href="#/Home">
              홈
            </a>
            <a href="#/CaseList">
              사례 관리
            </a>
            <a href="#/Schedule">
              일정
            </a>
            <a href="#/Soon?name=ChildLink">
              안부 연계
              <span className="cnt">
                4
              </span>
            </a>
            <a href="#/Soon?name=Closure">
              종결 검토
              <span className="cnt">
                2
              </span>
            </a>
            <a href="#/Soon?name=DocBox">
              문서함
            </a>
            <a href="#/Soon?name=LawGuide">
              법령 · 매뉴얼
            </a>
            <a href="#/Soon?name=Stats">
              통계
            </a>
            <a href="#/Soon?name=Settings">
              설정
            </a>
          </nav>
          <div className="me">
            <span className="av">
              {v.meInitial}
            </span>
            <b style={{ fontWeight: "500" }}>
              {v.meName} {v.meRole}
            </b>
            <a href="#/Login" className="note" style={{ marginLeft: "auto" }} onClick={v.logout}>
              로그아웃
            </a>
          </div>
        </aside>
        <main style={{ flex: "999 1 640px", minWidth: "0", padding: "30px 36px 56px", display: "flex", flexDirection: "column", gap: "20px" }}>
          <div className="thm-bar">
            <div className="nt-wrap">
              <button type="button" className="nt-btn" aria-label={v.ntLabel} aria-expanded={v.ntExp} aria-haspopup="true" onClick={v.ntToggle}>
                <svg viewBox={"0 0 24 24"} width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M6 9.5a6 6 0 0 1 12 0c0 4.2 1.4 6 2.2 6.9a.6.6 0 0 1-.45 1H4.25a.6.6 0 0 1-.45-1C4.6 15.5 6 13.7 6 9.5z" />
                  <path d="M10 20.2a2.2 2.2 0 0 0 4 0" />
                </svg>
                {v.ntHasBadge ? (
                  <>
                    <span className="nt-badge">
                      {v.ntBadge}
                    </span>
                  </>
                ) : null}
              </button>
              {v.ntOpen ? (
                <>
                  <div className="nt-pop" role="region" aria-label="알림 목록">
                    <div className="nt-hd">
                      <b style={{ fontSize: "15px" }}>
                        알림
                      </b>
                      <span className="nt-sub">
                        {v.ntSub}
                      </span>
                      <button type="button" className="nt-all" onClick={v.ntReadAll}>
                        모두 읽음
                      </button>
                    </div>
                    <div className="nt-list">
                      {(v.ntItems || []).map((n, i_n) => (
                        <Fragment key={i_n}>
                          <a className={`nt-item ${n.cls}`} href="#/Schedule" onClick={n.go}>
                            <span className="nt-dot" aria-hidden="true" />
                            <span className="nt-main">
                              <b className="nt-t">
                                {n.title}
                              </b>
                              <span className="nt-s">
                                {n.sub}
                              </span>
                            </span>
                            <span className={`nt-dd ${n.ddCls}`}>
                              {n.dd}
                            </span>
                          </a>
                        </Fragment>
                      ))}
                      {v.ntEmpty ? (
                        <>
                          <p className="nt-empty">
                            새 알림이 없습니다.
                          </p>
                        </>
                      ) : null}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
            <button type="button" className="thm-tg" aria-pressed={v.themePressed} aria-label={v.themeLabel} onClick={v.toggleTheme}>
              <span className="thm-knob">
                <svg className="i-sun" viewBox={"0 0 24 24"} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
                </svg>
                <svg className="i-moon" viewBox={"0 0 24 24"} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
                </svg>
              </span>
            </button>
          </div>
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 300px" }}>
              <div className="sub brn" style={{ fontWeight: "500" }}>
                {v.dateLabel}
              </div>
              <h1 style={{ margin: "2px 0 0", fontSize: "28px", fontWeight: "700" }}>
                안녕하세요, 이서연 상담사님
              </h1>
            </div>
          </header>
          <section aria-label="오늘 요약" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "14px", alignItems: "stretch" }}>
            <div className="card stat">
              <a className="stat-hd" href="#/CaseList">
                <span className="sub">
                  진행 중 내담자
                </span>
                <span className="stat-more">
                  전체 보기 ›
                </span>
              </a>
              <b className="n brn">
                10
              </b>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "6px" }}>
                <a className="todo" href="#/CaseInfo">
                  <span className="chip c-hi">
                    위기도 집중
                  </span>
                  <span style={{ flex: "1" }}>
                    김순자 님 · 오늘 16:00 상담
                  </span>
                  <b className="brn">
                    ›
                  </b>
                </a>
                <a className="todo" href="#/CaseInfo">
                  <span className="chip c-hi">
                    위기도 집중
                  </span>
                  <span style={{ flex: "1" }}>
                    오금자 님 · 상담일지 작성 전
                  </span>
                  <b className="brn">
                    ›
                  </b>
                </a>
                <a className="todo" href="#/CaseInfo">
                  <span className="chip c-mid">
                    위기도 관심
                  </span>
                  <span style={{ flex: "1" }}>
                    서복례 님 · 10/30 정기상담
                  </span>
                  <b className="brn">
                    ›
                  </b>
                </a>
              </div>
            </div>
            <div className="card stat">
              <span className="sub">
                미처리 업무
              </span>
              <b className="n brn">
                7
              </b>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "6px" }}>
                <a className="todo" href="#/Step1Record">
                  <span className="chip c-sand">
                    기록 확인
                  </span>
                  <span style={{ flex: "1" }}>
                    김순자 님 8회차
                  </span>
                  <b className="brn">
                    1
                  </b>
                </a>
                <a className="todo" href="#/Step3Summary">
                  <span className="chip c-sky">
                    상담 일지 작성
                  </span>
                  <span style={{ flex: "1" }}>
                    김순자 님 8회차 외
                  </span>
                  <b className="brn">
                    2
                  </b>
                </a>
                <a className="todo" href="#/Soon?name=ChildLink">
                  <span className="chip c-check">
                    안부 답변 확인
                  </span>
                  <span style={{ flex: "1" }}>
                    오늘 09:00 안부 묶음
                  </span>
                  <b className="brn">
                    4
                  </b>
                </a>
              </div>
            </div>
            <div className="card stat" style={{ boxShadow: "inset 0 4px 0 #A33B2E" }}>
              <a className="stat-hd" href="#/Soon?name=ChildLink">
                <span className="sub acc" style={{ fontWeight: "700" }}>
                  긴급 업무
                </span>
                <span className="stat-more">
                  안부 연계 ›
                </span>
              </a>
              <b className="n acc">
                2
              </b>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "6px" }}>
                <a className="todo todo-urg" href="#/Soon?name=ChildDetail">
                  <span className="chip c-urgent">
                    위기 신호
                  </span>
                  <span style={{ flex: "1" }}>
                    박영수 님 · 오늘 08:12 자살 생각 표현 감지
                  </span>
                  <b className="acc">
                    ›
                  </b>
                </a>
                <a className="todo todo-urg" href="#/Soon?name=ChildDetail">
                  <span className="chip c-urgent">
                    안부 무응답
                  </span>
                  <span style={{ flex: "1" }}>
                    최만석 님 · 48시간 무응답 · 방문 확인 권고
                  </span>
                  <b className="acc">
                    ›
                  </b>
                </a>
              </div>
            </div>
          </section>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "20px", alignItems: "flex-start" }}>
            <section className="card" aria-label="오늘 일정" style={{ flex: "3 1 520px", minWidth: "0", overflow: "hidden" }}>
              <div className="hd">
                <h2 className="h2">
                  오늘 일정
                </h2>
                <a href="#/Schedule" style={{ marginLeft: "auto", fontSize: "13px" }}>
                  달력 보기
                </a>
              </div>
              {(v.hours || []).map((h, i_h) => (
                <Fragment key={i_h}>
                  <div className="hr" style={{ background: h.bg, opacity: h.op }}>
                    <span style={{ paddingTop: "8px", fontSize: "13px", color: h.labelFg, fontWeight: h.labelFw }}>
                      {h.label}
                    </span>
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px", justifyContent: "center" }}>
                      {h.isNowHour ? (
                        <>
                          <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <b style={{ fontSize: "12px", color: "#1F3A56" }}>
                              {"지금 "}{v.clock}
                            </b>
                            <span style={{ flex: "1", height: "2px", background: "#1F3A56" }} />
                          </span>
                        </>
                      ) : null}
                      {(h.events || []).map((e, i_e) => (
                        <Fragment key={i_e}>
                          <a className="ev" href={e.href} style={{ background: e.bg }}>
                            <span style={{ width: "10px", height: "10px", flex: "none", borderRadius: e.radius, background: e.dot }} />
                            <b style={{ fontWeight: "500", fontSize: "13px", width: "44px", flex: "none" }}>
                              {e.time}
                            </b>
                            <span style={{ flex: "1", minWidth: "0" }}>
                              <b style={{ fontWeight: "500" }}>
                                {e.title}
                              </b>
                              <span className="note" style={{ marginLeft: "8px" }}>
                                {e.sub}
                              </span>
                            </span>
                          </a>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                </Fragment>
              ))}
            </section>
            <div style={{ flex: "2 1 320px", minWidth: "0", display: "flex", flexDirection: "column", gap: "20px" }}>
              <section className="card" aria-label="현재 시간" style={{ padding: "22px 24px", background: "linear-gradient(135deg, #E8F4FC 0%, #F0F8FD 60%, #F5FAFE 100%)", borderColor: "#B9DDF4" }}>
                <div className="note" style={{ color: "#1F3A56" }}>
                  지금
                </div>
                <div style={{ color: "#235E8C", fontSize: "44px", fontWeight: "700", lineHeight: "1.1", letterSpacing: "1px" }}>
                  {v.clock}
                </div>
                <div style={{ marginTop: "14px", padding: "14px 16px", borderRadius: "14px", background: "#FFFFFF", border: "1px solid #B9DDF4", borderLeft: "4px solid #5FA4D6" }}>
                  <div className="note">
                    다음 상담까지
                  </div>
                  <b style={{ fontSize: "24px", color: "#A33B2E" }}>
                    {v.remain}
                  </b>
                  <div style={{ marginTop: "2px", fontSize: "14px" }}>
                    {v.nextTitle}
                  </div>
                  <a className="btn btn-p" href="#/CaseInfo?sec=brief" style={{ width: "100%", marginTop: "12px" }}>
                    상담 전 브리핑 보기
                  </a>
                </div>
              </section>
              <section className="card" aria-label="빠른 실행" style={{ padding: "20px 22px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                  <h2 className="h2">
                    빠른 실행
                  </h2>
                  <button type="button" className="btn btn-sm btn-s" style={{ marginLeft: "auto" }} onClick={v.toggleEdit}>
                    {v.editLabel}
                  </button>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" }}>
                  {(v.quick || []).map((q, i_q) => (
                    <Fragment key={i_q}>
                      <a className="qa" href={q.href} onClick={v.markBack}>
                        <span className="qi">
                          {q.icon}
                        </span>
                        <b style={{ fontWeight: "500" }}>
                          {q.label}
                        </b>
                        {v.editing ? (
                          <>
                            <button type="button" className="rm" aria-label={q.rmLabel} onClick={q.remove}>
                              ×
                            </button>
                          </>
                        ) : null}
                      </a>
                    </Fragment>
                  ))}
                </div>
                {v.editing ? (
                  <>
                    <div style={{ marginTop: "14px", paddingTop: "12px", borderTop: "1px solid #DDE6EC" }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                        {(v.addable || []).map((o, i_o) => (
                          <Fragment key={i_o}>
                            <button type="button" className="addq" onClick={o.add}>
                              {"+ "}{o.label}
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
