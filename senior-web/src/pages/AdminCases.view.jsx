// AdminCases 화면 마크업 — tools/dc2jsx.py 가 디자인(AdminCases.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AdminCases.css';

export default function View({ v }) {
  return (
    <div className="pg-AdminCases">
      <div className={v.themeCls} style={{ minHeight: "1100px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            <a className="on" href="#/AdminCases">
              대상자 목록
            </a>
            <a href="#/AdminApp">
              안부 연계 앱 관리
              <span className="cnt">
                {v.cntApp}
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
                {v.cntSec}
              </span>
            </a>
            <a href="#/AdminStats">
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 260px" }}>
              <div className="sub">
                상담사별 담당 사례 전체
              </div>
              <h1 style={{ margin: "2px 0 0", fontSize: "28px", fontWeight: "700" }}>
                대상자 목록
              </h1>
            </div>
          </header>
          {v.msg ? (
            <p role="alert" className="note" style={{ margin: "0", color: "#A33B2E" }}>
              {v.msg}
            </p>
          ) : null}
          <section aria-label="사례 요약" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }}>
            {(v.kpis || []).map((k, i_k) => (
              <Fragment key={i_k}>
                <div className="card kpi" style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: "2px", boxShadow: k.bar }}>
                  <span className="sub">
                    {k.label}
                  </span>
                  <b style={{ fontSize: "28px", lineHeight: "1.2", color: k.fg }}>
                    {k.v}
                  </b>
                  <span className="note">
                    {k.note}
                  </span>
                </div>
              </Fragment>
            ))}
          </section>
          <section style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 12px" }}>
              <input className="inp" type="search" aria-label="어르신 성함 또는 사례 ID 검색" placeholder="어르신 성함 · 사례 ID 검색" value={v.q} onChange={v.setQ} style={{ flex: "1 1 240px" }} />
              <div role="group" aria-label="위기도" className="seg">
                {(v.riskF || []).map((f, i_f) => (
                  <Fragment key={i_f}>
                    <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                      {f.label}
                    </button>
                  </Fragment>
                ))}
              </div>
              <div role="group" aria-label="정렬" className="seg">
                <span className="ac-lb">
                  정렬
                </span>
                {(v.sortF || []).map((f, i_f) => (
                  <Fragment key={i_f}>
                    <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                      {f.label}
                    </button>
                  </Fragment>
                ))}
              </div>
            </div>
            <div role="group" aria-label="담당 상담사" className="seg" style={{ alignSelf: "flex-start" }}>
              {(v.staffF || []).map((f, i_f) => (
                <Fragment key={i_f}>
                  <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
          </section>
          <section className="card" aria-label="대상자 목록" style={{ overflowX: "auto" }}>
            <table className="tbl" style={{ minWidth: "980px" }}>
              <thead>
                <tr>
                  <th scope="col">
                    사례 ID
                  </th>
                  <th scope="col">
                    어르신
                  </th>
                  <th scope="col">
                    담당 상담사
                  </th>
                  <th scope="col">
                    위기도
                  </th>
                  <th scope="col">
                    접수일
                  </th>
                  <th scope="col">
                    관리 기간
                  </th>
                  <th scope="col">
                    최근 상담
                  </th>
                  <th scope="col">
                    진행 단계
                  </th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <tr>
                      <td className="note">
                        {r.id}
                      </td>
                      <td>
                        <span className="nm" style={{ cursor: "default" }}>
                          <span>
                            {r.name}{" "}
                            <span className="note">
                              {r.age}
                            </span>
                          </span>
                        </span>
                      </td>
                      <td>
                        <a href={r.whoHref} onClick={r.pick}>
                          {r.who}
                        </a>
                      </td>
                      <td>
                        <span className={r.rCls}>
                          {r.risk}
                        </span>
                      </td>
                      <td>
                        {r.date}
                      </td>
                      <td>
                        {r.period}
                      </td>
                      <td>
                        {r.last}
                      </td>
                      <td>
                        <span className={r.stCls}>
                          {r.stage}
                        </span>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
            {v.empty ? (
              <>
                <p className="note" style={{ margin: "0", padding: "22px", textAlign: "center" }}>
                  조건에 맞는 사례가 없어요.
                </p>
              </>
            ) : null}
          </section>
          <p className="note" style={{ margin: "-8px 0 0" }}>
            {v.countLabel}
          </p>
        </main>
      </div>
    </div>
  );
}
