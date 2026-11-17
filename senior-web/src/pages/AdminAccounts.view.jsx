// AdminAccounts 화면 마크업 — tools/dc2jsx.py 가 디자인(AdminAccounts.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AdminAccounts.css';

export default function View({ v }) {
  return (
    <div className="pg-AdminAccounts">
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
                {v.cntApp}
              </span>
            </a>
            <a className="on" href="#/AdminAccounts">
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 14px" }}>
            <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700", flex: "1 1 260px" }}>
              상담사 계정 관리
            </h1>
            <button type="button" className={`btn ${v.formBtnCls}`} onClick={v.toggleForm}>
              {v.formBtnLabel}
            </button>
          </header>
          {v.showForm ? (
            <>
              <section className="card" aria-label="계정 생성" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
                <h2 className="h2">
                  새 계정 만들기
                </h2>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }}>
                  <label className="fl">
                    <span className="lb">
                      이름
                    </span>
                    <input className="inp" type="text" placeholder="예: 홍길동" value={v.fName} onChange={v.setName} />
                  </label>
                  <label className="fl">
                    <span className="lb">
                      기관 ID
                    </span>
                    <input className="inp" type="text" placeholder="예: hong.gildong" value={v.fId} onChange={v.setId} />
                  </label>
                </div>
                <p className="note" style={{ margin: "0" }}>
                  생성하면 임시 비밀번호가 발급되고, 첫 로그인 때 비밀번호 변경과 OTP 등록을 해야 해요.
                </p>
                {v.formErr ? (
                  <>
                    <p className="warn" style={{ margin: "0", fontSize: "13px" }}>
                      이름과 기관 ID를 입력해 주세요.
                    </p>
                  </>
                ) : null}
                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                  <button type="button" className="btn btn-s" onClick={v.toggleForm}>
                    취소
                  </button>
                  <button type="button" className="btn btn-p" onClick={v.create}>
                    계정 생성
                  </button>
                </div>
              </section>
            </>
          ) : null}
          {v.created ? (
            <>
              <p className="note" style={{ margin: "-6px 0 0", color: "#1F3A56" }}>
                {v.createdMsg}
              </p>
            </>
          ) : null}
          {v.err ? (
            <p role="alert" className="note" style={{ margin: "-6px 0 0", color: "#A33B2E" }}>
              {v.err}
            </p>
          ) : null}
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 12px" }}>
            <input className="inp" type="search" aria-label="이름 또는 기관 ID 검색" placeholder="이름 · 기관 ID 검색" value={v.q} onChange={v.setQ} style={{ flex: "1 1 240px" }} />
            <div role="group" aria-label="계정 상태" className="seg">
              {(v.filters || []).map((f, i_f) => (
                <Fragment key={i_f}>
                  <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
          </section>
          <section className="card" aria-label="계정 목록" style={{ overflowX: "auto" }}>
            <table className="tbl" style={{ minWidth: "880px" }}>
              <thead>
                <tr>
                  <th scope="col">
                    이름
                  </th>
                  <th scope="col">
                    기관 ID
                  </th>
                  <th scope="col">
                    담당 사례
                  </th>
                  <th scope="col">
                    최근 접속
                  </th>
                  <th scope="col">
                    접속 IP
                  </th>
                  <th scope="col">
                    상태
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
                    <tr style={{ opacity: r.op }}>
                      <td>
                        <a className="nm" href={r.href} onClick={r.pick}>
                          <span className="av" style={{ width: "34px", height: "34px", fontSize: "13px" }}>
                            {r.ini}
                          </span>
                          <span>
                            {r.name}
                          </span>
                        </a>
                      </td>
                      <td className="note">
                        {r.uid}
                      </td>
                      <td>
                        {r.cases}
                      </td>
                      <td>
                        {r.last}
                      </td>
                      <td>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                          {r.ip}
                          {r.ext ? (
                            <>
                              <span className="chip c-urgent">
                                외부
                              </span>
                            </>
                          ) : null}
                        </span>
                      </td>
                      <td>
                        <span className={r.stCls}>
                          {r.st}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <a href={r.href} onClick={r.pick}>
                          상세
                        </a>
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
