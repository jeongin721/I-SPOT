// AdminStats 화면 마크업 — tools/dc2jsx.py 가 디자인(AdminStats.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AdminStats.css';

export default function View({ v }) {
  return (
    <div className="pg-AdminStats">
      <div className={v.themeCls} style={{ minHeight: "2400px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
          <a className="logo" href="#/AdminHome">
            <span className="mk">
              온담
            </span>
            <b style={{ fontSize: "17px" }}>
              ONDAM
            </b>
            <span className="chip c-normal" style={{ marginLeft: "2px" }}>
              관리자
            </span>
          </a>
          <input type="checkbox" id="mnav" className="mnav-tg" aria-label="메뉴 열기" />
          <label htmlFor="mnav" className="mnav-btn">
            <i aria-hidden="true" />
            메뉴
          </label>
          <nav className="nav" aria-label="관리자 메뉴">
            <a href="#/AdminHome">
              홈
            </a>
            <a href="#/AdminCases">
              대상자 목록
            </a>
            <a href="#/AdminApp">
              안부 연계 앱 관리
              <span className="cnt">
                {v.navAppCnt}
              </span>
            </a>
            <a href="#/AdminAccounts">
              상담사 계정 관리
            </a>
            <a href="#/AdminAccess">
              열람 기록
            </a>
            <a href="#/AdminSecurity">
              접속 기록 · 보안 이벤트
              <span className="cnt">
                {v.navSecCnt}
              </span>
            </a>
            <a className="on" href="#/AdminStats">
              통계 · 보고
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 300px" }}>
              <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                통계 · 보고
              </h1>
              <p className="sub" style={{ margin: "4px 0 0" }}>
                {"기관 전체 · "}{v.periodLabel}
              </p>
            </div>
            <button type="button" className="btn btn-s" onClick={v.exportXls}>
              엑셀로 내려받기
            </button>
            <button type="button" className="btn btn-p" onClick={v.exportPdf}>
              보고서 PDF 만들기
            </button>
          </header>
          {v.hasMsg ? (
            <>
              <p className="note" style={{ margin: "-8px 0 0", color: "#1F3A56" }}>
                {v.msg}
              </p>
            </>
          ) : null}
          <section className="card" aria-label="기간 선택" style={{ padding: "14px 18px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 14px" }}>
            <div role="group" aria-label="기간" className="seg">
              {(v.periods || []).map((f, i_f) => (
                <Fragment key={i_f}>
                  <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <span className="note" style={{ marginLeft: "auto" }}>
              {v.rangeLabel}
            </span>
          </section>
          <section aria-label="핵심 지표" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(136px, 1fr))", gap: "12px" }}>
            {(v.kpis || []).map((k, i_k) => (
              <Fragment key={i_k}>
                <div className="card kpi sm-k">
                  <span className="sub">
                    {k.label}
                  </span>
                  <b>
                    {k.v}
                  </b>
                  <span className="note">
                    {k.sub}
                  </span>
                </div>
              </Fragment>
            ))}
          </section>
          <section className="card" aria-label="신규 접수와 종결 추이" style={{ padding: "20px 22px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px 16px" }}>
              <h2 className="h2">
                신규 접수 · 종결 추이
              </h2>
              <span className="lg">
                <i style={{ background: "#5FA4D6" }} />
                신규 접수
              </span>
              <span className="lg">
                <i style={{ background: "#1F3A56" }} />
                종결
              </span>
            </div>
            <div className="vb" style={{ marginTop: "16px" }} role="img" aria-label={v.trendAria}>
              {(v.trend || []).map((t, i_t) => (
                <Fragment key={i_t}>
                  <div className="col" title={t.tip}>
                    <div className="bx">
                      <span>
                        {t.a}
                      </span>
                      <span className="b" style={{ height: t.ha, background: "#5FA4D6" }} />
                    </div>
                    <div className="bx">
                      <span>
                        {t.b}
                      </span>
                      <span className="b" style={{ height: t.hb, background: "#1F3A56" }} />
                    </div>
                  </div>
                </Fragment>
              ))}
            </div>
            <div style={{ display: "flex", gap: "10px", padding: "6px 4px 0" }}>
              {(v.trend || []).map((t, i_t) => (
                <Fragment key={i_t}>
                  <span className="note" style={{ flex: "1", minWidth: "0", textAlign: "center", whiteSpace: "nowrap", overflow: "hidden" }}>
                    {t.label}
                  </span>
                </Fragment>
              ))}
            </div>
          </section>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "18px" }}>
            <section className="card" aria-label="주호소 유형별" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  주호소 유형별
                </h2>
                <span className="note">
                  사례별 주 상담 영역 기준
                </span>
              </div>
              {(v.types || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{" · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
            <section className="card" aria-label="위기도별" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "14px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  위기도별
                </h2>
                <span className="note">
                  초기 사정 시점 기준
                </span>
              </div>
              <div className="stack" role="img" aria-label={v.riskAria}>
                {(v.risk || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <span style={{ width: r.w, background: r.c }} title={r.tip} />
                  </Fragment>
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: "10px" }}>
                {(v.risk || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <div className="box" style={{ padding: "12px 14px", borderRadius: "12px" }}>
                      <span className="lg">
                        <i style={{ background: r.c }} />
                        {"위기도 "}{r.name}
                      </span>
                      <div style={{ fontSize: "22px", fontWeight: "700", lineHeight: "1.3" }}>
                        {r.v}건
                      </div>
                      <span className="note">
                        {r.p}
                      </span>
                    </div>
                  </Fragment>
                ))}
              </div>
            </section>
          </div>
          <section className="card" aria-label="상담사별" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                상담사별
              </h2>
              <span className="note">
                {v.periodLabel}
              </span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl" style={{ minWidth: "860px" }}>
                <thead>
                  <tr>
                    <th scope="col">
                      상담사
                    </th>
                    <th scope="col">
                      현재 담당 사례
                    </th>
                    <th scope="col" style={{ width: "24%" }}>
                      상담 회차
                    </th>
                    <th scope="col">
                      일지 기한 내 작성률
                    </th>
                    <th scope="col">
                      종결
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.staff || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td>
                          <b style={{ fontWeight: "500" }}>
                            {r.name}
                          </b>
                          <span className="note" style={{ display: "block" }}>
                            {r.rank}
                          </span>
                        </td>
                        <td>
                          {r.cases}건
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            <span className="mini" style={{ flex: "1" }}>
                              <span style={{ width: r.w }} />
                            </span>
                            <b style={{ width: "40px" }}>
                              {r.ses}
                            </b>
                          </div>
                        </td>
                        <td>
                          <span className={r.rCls}>
                            {r.rate}
                          </span>
                        </td>
                        <td>
                          {r.closed}건
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <div className="g3">
            <section className="card" aria-label="내담 어르신 연령대별" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  내담 어르신 연령대별
                </h2>
              </div>
              {(v.ages || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb sm" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{" · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
            <section className="card" aria-label="가구형태별" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  가구형태별
                </h2>
              </div>
              {(v.actors || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb sm" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{" · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
            <section className="card" aria-label="의뢰 경로별" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  의뢰 경로별
                </h2>
                <span className="note">
                  {v.mandatoryNote}
                </span>
              </div>
              {(v.reporters || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb sm" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{" · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
            <section className="card" aria-label="연계 기관별" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  연계 기관별
                </h2>
                <span className="note">
                  연계 의뢰 건 기준
                </span>
              </div>
              {(v.measures || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb sm" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{" · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
            <section className="card" aria-label="서비스 제공 (회)" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  서비스 제공 (회)
                </h2>
              </div>
              {(v.services || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb sm" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{" · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
            <section className="card" aria-label="종결 사유" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                <h2 className="h2">
                  종결 사유
                </h2>
                <span className="note">
                  종결 사례 기준
                </span>
              </div>
              {(v.closures || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb sm" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{" · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
          </div>
          <p className="note" style={{ margin: "0" }}>
            통계는 기관 운영 보고 양식 항목(상담 접수 · 사례관리 개시 · 주호소 · 내담 어르신 특성 · 위기도 · 연계 · 서비스 제공 · 종결)에 맞춰 정리돼 있어요. 개인을 알아볼 수 없는 집계 값만 보여요.
          </p>
        </main>
      </div>
    </div>
  );
}
