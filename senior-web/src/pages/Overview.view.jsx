// Overview 화면 마크업 — tools/dc2jsx.py 가 디자인(Overview.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './Overview.css';

export default function View({ v }) {
  return (
    <div className="pg-Overview">
      <div className={v.themeCls} style={{ minHeight: "1400px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            <a href="#/ChildLink">
              안부 연계
              <span className="cnt">
                {v.cntLink}
              </span>
            </a>
            <a href="#/Followup">
              후속관리
              <span className="cnt">
                {v.cntFollowup}
              </span>
            </a>
            <a href="#/DocBox">
              문서함
            </a>
            <a href="#/LawGuide">
              법령 · 매뉴얼
            </a>
            <a href="#/Stats" style={{ fontWeight: "600" }}>
              통계
            </a>
            <a className="on" href="#/Overview" aria-current="page" style={{ minHeight: "34px", paddingLeft: "46px", fontSize: "13px" }}>
              관리자 현황
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 300px" }}>
              <p className="note" style={{ margin: "0 0 4px" }}>
                {v.orgLine}
              </p>
              <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                관리자 현황
              </h1>
            </div>
          </header>
          {v.msg ? (
            <p role="alert" className="note" style={{ margin: "0", color: "#A33B2E" }}>
              {v.msg}
            </p>
          ) : null}
          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }} aria-label="주요 지표">
            {(v.kpis || []).map((m, i_m) => (
              <Fragment key={i_m}>
                <div className="card kpi">
                  <div className="sub">
                    {m.label}
                  </div>
                  <b className="brn">
                    {m.v}
                  </b>
                  <div className="note">
                    {m.note}
                  </div>
                </div>
              </Fragment>
            ))}
          </section>
          <section className="card" aria-label="담당자별 현황" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                담당자별 현황
              </h2>
              <span className="note">
                {v.weekLabel}
              </span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl" style={{ minWidth: "720px" }}>
                <thead>
                  <tr>
                    <th>
                      담당자
                    </th>
                    <th>
                      역할
                    </th>
                    <th>
                      담당 어르신
                    </th>
                    <th>
                      이번 주 일정
                    </th>
                    <th>
                      재방문 필요
                    </th>
                    <th>
                      미처리 조치
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.staffRows || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td>
                          <b style={{ fontWeight: "500" }}>
                            {r.name}
                          </b>
                        </td>
                        <td className="note">
                          {r.role}
                        </td>
                        <td>
                          {r.elders}명
                        </td>
                        <td>
                          {r.sched}건
                        </td>
                        <td>
                          {r.hasRe ? (
                            <>
                              <span className="chip c-hi">
                                {r.re}명
                              </span>
                            </>
                          ) : null}
                          {r.noRe ? (
                            <>
                              <span className="note">
                                0
                              </span>
                            </>
                          ) : null}
                        </td>
                        <td>
                          {r.hasAct ? (
                            <>
                              <span className="chip c-mid">
                                {r.act}건
                              </span>
                            </>
                          ) : null}
                          {r.noAct ? (
                            <>
                              <span className="note">
                                0
                              </span>
                            </>
                          ) : null}
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "18px", alignItems: "start" }}>
            <section className="card" aria-label="돌봄 상태 분포" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  돌봄 상태 분포
                </h2>
                <span className="note">
                  {"전체 "}{v.totalElders}명
                </span>
              </div>
              {(v.dist || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w, background: g.c }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{"명 · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
            <section className="card" aria-label="기한 순 미처리 조치사항" style={{ overflow: "hidden" }}>
              <div className="hd">
                <h2 className="h2">
                  기한 순 미처리 조치사항
                </h2>
                <a className="note" href="#/Followup" style={{ marginLeft: "auto" }}>
                  후속관리 열기
                </a>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="tbl" style={{ minWidth: "520px" }}>
                  <thead>
                    <tr>
                      <th>
                        기한
                      </th>
                      <th>
                        어르신
                      </th>
                      <th>
                        조치
                      </th>
                      <th>
                        담당자
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {(v.pending || []).map((r, i_r) => (
                      <Fragment key={i_r}>
                        <tr>
                          <td>
                            <a href={r.href} style={{ fontWeight: "700", textDecoration: "none" }}>
                              {r.due}
                            </a>
                          </td>
                          <td>
                            <a href={r.href} style={{ textDecoration: "none" }}>
                              {r.elder}
                            </a>
                          </td>
                          <td>
                            {r.t}
                          </td>
                          <td className="note">
                            {r.who}
                          </td>
                        </tr>
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
              {v.noPending ? (
                <>
                  <p className="note" style={{ margin: "0", padding: "16px 22px" }}>
                    미처리 조치사항이 없습니다.
                  </p>
                </>
              ) : null}
            </section>
          </div>
          <p className="ainote">
            담당자가 후속관리 화면에 입력한 조치 · 일정 기준이며, 매일 갱신됩니다.
          </p>
        </main>
      </div>
    </div>
  );
}
