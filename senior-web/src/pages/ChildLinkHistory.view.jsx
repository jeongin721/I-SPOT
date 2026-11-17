// ChildLinkHistory 화면 마크업 — tools/dc2jsx.py 가 디자인(ChildLinkHistory.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './ChildLinkHistory.css';

export default function View({ v }) {
  return (
    <div className="pg-ChildLinkHistory">
      <div className={v.themeCls} style={{ minHeight: "1600px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            + 새 대상자 등록
          </a>
          <nav className="nav" aria-label="메뉴">
            <a href="#/Home">
              홈
            </a>
            <a href="#/CaseList">
              대상자 관리
            </a>
            <a href="#/Schedule">
              일정
            </a>
            <a className="on" href="#/ChildLink">
              안부 연계
              <span className="cnt">
                {v.cntApp}
              </span>
            </a>
            <a href="#/Followup">
              후속관리
              <span className="cnt">
                {v.cntFollow}
              </span>
            </a>
            <a href="#/DocBox">
              문서함
            </a>
            <a href="#/LawGuide">
              법령 · 매뉴얼
            </a>
            <a href="#/Stats">
              통계
            </a>
            <a href="#/Settings">
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
          <nav aria-label="위치" className="note">
            <a href={v.k.home}>
              {v.k.homeLabel}
            </a>
            {" › "}
            <a href={v.k.back}>
              {v.k.short}
            </a>
            {" › 지난 안부 기록"}
          </nav>
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px 16px" }}>
            <a className="btn btn-sm btn-s" href={v.k.back} aria-label="이전 화면으로 돌아가기" title="이전 화면으로 돌아가기">
              ←
            </a>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  {v.k.name}{" 님 · 지난 안부 기록"}
                </h1>
              </div>
              <div className="note">
                {v.k.id}{" · "}{v.k.age}{" · 안부 응답 "}{v.answered}{" / "}{v.days}{v.daysTail}
              </div>
            </div>
          </header>
          <section className="card" style={{ padding: "16px 20px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 16px" }}>
            <span className="note">
              기간
            </span>
            <div className="seg" role="group" aria-label="기간">
              {(v.periods || []).map((p, i_p) => (
                <Fragment key={i_p}>
                  <button type="button" className={p.cls} aria-pressed={p.on} onClick={p.pick}>
                    {p.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <span className="note" style={{ marginLeft: "8px" }}>
              보기
            </span>
            <div className="seg" role="group" aria-label="보기 방식">
              {(v.views || []).map((p, i_p) => (
                <Fragment key={i_p}>
                  <button type="button" className={p.cls} aria-pressed={p.on} onClick={p.pick}>
                    {p.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <span className="note" style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: "12px" }}>
              <span>
                <span className="lg lg-c" />
                확인 필요한 답
              </span>
              <span>
                <span className="lg lg-x" />
                이전과 바뀐 답
              </span>
            </span>
          </section>
          {v.byQ ? (
            <>
              <section className="card" aria-label="문항별 안부 기록" style={{ overflow: "hidden" }}>
                <div style={{ overflowX: "auto" }}>
                  <table className="mx">
                    <thead>
                      <tr>
                        <th className="qcol">
                          문항
                        </th>
                        {(v.cols || []).map((c, i_c) => (
                          <Fragment key={i_c}>
                            <th>
                              <span style={{ display: "block" }}>
                                {c.md}
                              </span>
                              <span className="note">
                                {c.dow}
                              </span>
                            </th>
                          </Fragment>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(v.rows || []).map((r, i_r) => (
                        <Fragment key={i_r}>
                          <tr>
                            <th className="qcol">
                              <span className="note" style={{ display: "block" }}>
                                {r.id}
                              </span>
                              {r.q}
                            </th>
                            {(r.cells || []).map((c, i_c) => (
                              <Fragment key={i_c}>
                                <td className={c.cls}>
                                  {c.v}
                                </td>
                              </Fragment>
                            ))}
                          </tr>
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : null}
          {v.byD ? (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "minmax(200px, 260px) minmax(0, 1fr)", gap: "18px", alignItems: "start" }} className="bd-grid">
                <section className="card" aria-label="날짜" style={{ padding: "10px", display: "flex", flexDirection: "column", gap: "4px", maxHeight: "640px", overflowY: "auto" }}>
                  {(v.dates || []).map((d, i_d) => (
                    <Fragment key={i_d}>
                      <button type="button" className={`dbtn ${d.cls}`} aria-pressed={d.on} onClick={d.pick}>
                        <b>
                          {d.label}
                        </b>
                        <span className="note">
                          {d.meta}
                        </span>
                      </button>
                    </Fragment>
                  ))}
                </section>
                <section className="card" aria-label="선택한 날짜의 안부 답" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                    <h2 className="h2">
                      {v.day.label}{" 안부"}
                    </h2>
                    <span className="note">
                      {v.day.time}
                    </span>
                  </div>
                  {v.day.hasQuote ? (
                    <>
                      <div className="quote" style={{ padding: "16px 18px" }}>
                        <span style={{ fontSize: "12px" }}>
                          {"어르신이 남긴 말씀 · "}{v.day.quoteAt}
                        </span>
                        <div style={{ fontSize: "18px", fontWeight: "700" }}>
                          "{v.day.quote}"
                        </div>
                      </div>
                    </>
                  ) : null}
                  {v.day.none ? (
                    <>
                      <p className="note" style={{ margin: "0" }}>
                        이 날은 안부 응답이 없었어요.
                      </p>
                    </>
                  ) : null}
                  {v.day.has ? (
                    <>
                      <div className="dq dq-h note">
                        <span>
                          문항
                        </span>
                        <span>
                          질문
                        </span>
                        <span>
                          직전 답변
                        </span>
                        <span>
                          이 날 답변
                        </span>
                      </div>
                      {(v.day.items || []).map((a, i_a) => (
                        <Fragment key={i_a}>
                          <div className="dq" style={{ background: a.bg }}>
                            <span className="note">
                              {a.id}
                            </span>
                            <span>
                              {a.q}
                            </span>
                            <span className="note">
                              {a.prev}
                            </span>
                            <b style={{ fontWeight: a.fw }}>
                              {a.v}
                              {a.changed ? (
                                <>
                                  <span className="chg">
                                    바뀜
                                  </span>
                                </>
                              ) : null}
                            </b>
                          </div>
                        </Fragment>
                      ))}
                    </>
                  ) : null}
                </section>
              </div>
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
