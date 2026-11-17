// AdminSecurity 화면 마크업 — tools/dc2jsx.py 가 디자인(AdminSecurity.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AdminSecurity.css';

export default function View({ v }) {
  return (
    <div className="pg-AdminSecurity">
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
            <a className="on" href="#/AdminSecurity">
              접속 기록 · 보안 이벤트
              <span className="cnt">
                {v.navSecCnt}
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
          <header>
            <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
              접속 기록 · 보안 이벤트
            </h1>
          </header>
          <section aria-label="보안 요약" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }}>
            <button type="button" className={`card kpi kb ${v.kfail.cls}`} aria-pressed={v.kfail.pressed} onClick={v.kfail.pick} style={{ boxShadow: "inset 0 4px 0 #A33B2E" }}>
              <span className="sub acc" style={{ fontWeight: "700" }}>
                로그인 실패 (24시간)
              </span>
              <b className="acc">
                {v.failCnt}
              </b>
              <span className="note">
                {v.failNote}
              </span>
            </button>
            <button type="button" className={`card kpi kb ${v.kout.cls}`} aria-pressed={v.kout.pressed} onClick={v.kout.pick}>
              <span className="sub">
                외부 IP 접속 (24시간)
              </span>
              <b>
                {v.extCnt}
              </b>
              <span className="note">
                기관 내부망 밖에서 접속
              </span>
            </button>
            <button type="button" className={`card kpi kb ${v.kotp.cls}`} aria-pressed={v.kotp.pressed} onClick={v.kotp.pick}>
              <span className="sub">
                OTP 실패 (24시간)
              </span>
              <b>
                {v.otpCnt}
              </b>
              <span className="note">
                재시도 후 로그인 성공 포함
              </span>
            </button>
            <button type="button" className={`card kpi kb ${v.klock.cls}`} aria-pressed={v.klock.pressed} onClick={v.klock.pick}>
              <span className="sub">
                잠긴 계정
              </span>
              <b>
                {v.lockCnt}
              </b>
              <span className="note">
                로그인 5회 실패 시 자동 잠금
              </span>
            </button>
          </section>
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 12px" }}>
            <input className="inp" type="search" aria-label="계정 또는 IP 검색" placeholder="계정 · IP 검색" style={{ flex: "1 1 240px" }} value={v.q} onChange={v.setQ} />
            <div role="group" aria-label="기록 종류" className="seg">
              {(v.filters || []).map((f, i_f) => (
                <Fragment key={i_f}>
                  <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
          </section>
          {v.msg ? <p className="note" role="status" style={{ margin: "0", color: "#1F3A56" }}>{v.msg}</p> : null}
          <section className="card" aria-label="접속 기록" style={{ overflowX: "auto" }}>
            <table className="tbl" style={{ minWidth: "1000px" }}>
              <thead>
                <tr>
                  <th scope="col">
                    일시
                  </th>
                  <th scope="col">
                    계정
                  </th>
                  <th scope="col">
                    구분
                  </th>
                  <th scope="col">
                    접속 IP
                  </th>
                  <th scope="col">
                    접속 위치
                  </th>
                  <th scope="col">
                    처리 결과
                  </th>
                  <th scope="col">
                    <span style={{ position: "absolute", left: "-9999px" }}>
                      작업
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <tr>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {r.t}
                      </td>
                      <td>
                        <b style={{ fontWeight: "500" }}>
                          {r.name}
                        </b>
                        <span className="note" style={{ display: "block" }}>
                          {r.uid}
                        </span>
                      </td>
                      <td>
                        <span className={r.evCls}>
                          {r.ev}
                        </span>
                      </td>
                      <td>
                        {r.ip}
                      </td>
                      <td>
                        <span className={r.netCls}>
                          {r.net}
                        </span>
                      </td>
                      <td>
                        {r.res}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {r.hasAct ? (
                          <>
                            <button type="button" className="btn btn-sm btn-s" onClick={r.act}>
                              {r.actLabel}
                            </button>
                          </>
                        ) : null}
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
        </main>
      </div>
    </div>
  );
}
