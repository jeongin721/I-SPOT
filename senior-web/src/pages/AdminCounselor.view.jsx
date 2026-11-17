// AdminCounselor 화면 마크업 — tools/dc2jsx.py 가 디자인(AdminCounselor.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AdminCounselor.css';

export default function View({ v }) {
  return (
    <div className="pg-AdminCounselor">
      <div className={v.themeCls} style={{ minHeight: "900px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px 16px" }}>
            <a className="btn btn-sm btn-s" href="#/AdminAccounts">
              ← 목록
            </a>
            <span className="av" style={{ width: "52px", height: "52px", fontSize: "20px" }}>
              {v.ini}
            </span>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  {v.name}
                </h1>
                <span className={v.stCls}>
                  {v.st}
                </span>
              </div>
              <div className="note">
                {v.uid}{" · 담당 사례 "}{v.cases}
              </div>
            </div>
            <button type="button" className={`btn ${v.actCls}`} onClick={v.toggleAct}>
              {v.actLabel}
            </button>
          </header>
          {v.hasMsg ? (
            <>
              <p className="note" style={{ margin: "-8px 0 0", color: "#1F3A56" }}>
                {v.msg}
              </p>
            </>
          ) : null}
          {v.err ? (
            <p role="alert" className="note" style={{ margin: "-8px 0 0", color: "#A33B2E" }}>
              {v.err}
            </p>
          ) : null}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: "18px", alignItems: "start" }}>
            <section className="card" aria-label="계정" style={{ overflow: "hidden" }}>
              <div className="hd">
                <h2 className="h2">
                  계정
                </h2>
                <span className="note">
                  상담사 마이페이지 정보
                </span>
              </div>
              <div style={{ padding: "6px 22px 10px" }}>
                <div className="row">
                  <span className="lab">
                    상담사 이름
                  </span>
                  <b style={{ fontWeight: "500" }}>
                    {v.name}
                  </b>
                </div>
                <div className="row">
                  <span className="lab">
                    계정 (연결된 이메일)
                  </span>
                  <b style={{ fontWeight: "500" }}>
                    {v.mail}
                  </b>
                </div>
                <div className="row">
                  <span className="lab">
                    비밀번호
                  </span>
                  <span style={{ flex: "1" }} className="sub">
                    {v.pwText}
                  </span>
                  <button type="button" className={`btn btn-sm ${v.pwCls}`} onClick={v.resetPw}>
                    {v.pwLabel}
                  </button>
                </div>
                <div className="row">
                  <span className="lab">
                    소속 기관
                  </span>
                  <b style={{ fontWeight: "500" }}>
                    {v.org}
                  </b>
                </div>
                <div className="row" style={{ borderBottom: "0" }}>
                  <span className="lab">
                    OTP
                  </span>
                  <span className={v.otpCls}>
                    {v.otp}
                  </span>
                </div>
              </div>
            </section>
            <section className="card" aria-label="접속 정보" style={{ overflow: "hidden" }}>
              <div className="hd">
                <h2 className="h2">
                  접속 정보
                </h2>
                <a href="#/AdminSecurity" style={{ marginLeft: "auto", fontSize: "13px" }}>
                  전체 접속 기록
                </a>
              </div>
              <div style={{ padding: "6px 22px 10px" }}>
                <div className="row">
                  <span className="lab">
                    계정 생성일
                  </span>
                  <b style={{ fontWeight: "500" }}>
                    {v.created}
                  </b>
                </div>
                <div className="row">
                  <span className="lab">
                    최근 접속
                  </span>
                  <b style={{ fontWeight: "500" }}>
                    {v.last}
                  </b>
                </div>
                <div className="row" style={{ borderBottom: "0" }}>
                  <span className="lab">
                    접속 IP
                  </span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                    <b style={{ fontWeight: "500" }}>
                      {v.ip}
                    </b>
                    {v.ext ? (
                      <>
                        <span className="chip c-urgent">
                          외부
                        </span>
                      </>
                    ) : null}
                  </span>
                </div>
              </div>
            </section>
            <section className="card" aria-label="알림 설정" style={{ overflow: "hidden" }}>
              <div className="hd">
                <h2 className="h2">
                  알림 설정
                </h2>
                <span className="note">
                  상담사가 마이페이지에서 설정한 값
                </span>
              </div>
              <div style={{ padding: "6px 22px 10px" }}>
                {(v.notify || []).map((n, i_n) => (
                  <Fragment key={i_n}>
                    <div className="row">
                      <span style={{ flex: "1" }}>
                        {n.label}
                      </span>
                      <span className={n.cls}>
                        {n.st}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <div className="row" style={{ borderBottom: "0" }}>
                  <span style={{ flex: "1" }}>
                    어르신 안부 응답 묶음 시간
                  </span>
                  <b style={{ fontWeight: "500" }}>
                    {v.batch}
                  </b>
                </div>
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
