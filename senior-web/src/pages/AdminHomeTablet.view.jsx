// AdminHomeTablet 화면 마크업 — tools/dc2jsx.py 가 디자인(AdminHomeTablet.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AdminHomeTablet.css';

export default function View({ v }) {
  return (
    <div className="pg-AdminHomeTablet">
      <div className={v.themeCls} style={{ minHeight: "1820px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            <a className="on" href="#/AdminHome">
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
            <div style={{ flex: "1 1 300px" }}>
              <div className="sub" style={{ fontWeight: "500" }}>
                {v.dateLabel}
              </div>
              <h1 style={{ margin: "2px 0 0", fontSize: "28px", fontWeight: "700" }}>
                기관 현황
              </h1>
            </div>
          </header>
          {v.msg ? (
            <p role="alert" className="note" style={{ margin: "0", color: "#A33B2E" }}>
              {v.msg}
            </p>
          ) : null}
          <section aria-label="오늘 요약" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }}>
            <div className="card kpi">
              <span className="sub">
                진행 중 사례
              </span>
              <b>
                {v.activeCases}
              </b>
              <span className="note">
                {v.activeNote}
              </span>
            </div>
            <a className="card kpi" href="#urgent" onClick={v.goUrgent} style={{ boxShadow: "inset 0 4px 0 #A33B2E" }}>
              <span className="sub acc" style={{ fontWeight: "700" }}>
                긴급 알림 · 확인 전
              </span>
              <b className="acc">
                {v.pendingCnt}
              </b>
              <span className="note">
                {v.urgentNote}
              </span>
            </a>
            <a className="card kpi" href="#/AdminAccounts">
              <span className="sub">
                활성 상담사
              </span>
              <b>
                {v.counselorOn}
                <span className="sub" style={{ fontSize: "15px", fontWeight: "500" }}>
                  {v.counselorTotal}
                </span>
              </b>
              <span className="note">
                {v.counselorNote}
              </span>
            </a>
          </section>
          <section id="urgent" className="card" aria-label="긴급 알림 현황" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                긴급 알림 현황
              </h2>
              <span className="note">
                안부 연계 앱에서 ‘긴급’으로 분류된 응답·무응답
              </span>
              <div style={{ marginLeft: "auto" }}>
                <div role="group" aria-label="긴급 알림 보기" className="seg">
                  {(v.uFilters || []).map((f, i_f) => (
                    <Fragment key={i_f}>
                      <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                        {f.label}
                      </button>
                    </Fragment>
                  ))}
                </div>
              </div>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl" style={{ minWidth: "860px" }}>
                <thead>
                  <tr>
                    <th scope="col">
                      발생 시각
                    </th>
                    <th scope="col">
                      어르신
                    </th>
                    <th scope="col">
                      알림 유형 · 내용
                    </th>
                    <th scope="col">
                      담당 상담사
                    </th>
                    <th scope="col">
                      상담사 확인
                    </th>
                    <th scope="col">
                      <span style={{ position: "absolute", left: "-9999px" }}>
                        작업
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.urgent || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td style={{ whiteSpace: "nowrap" }}>
                          {r.t}
                        </td>
                        <td>
                          <b style={{ fontWeight: "500" }}>
                            {r.elder}
                          </b>
                          <span className="note" style={{ display: "block" }}>
                            {r.cid}
                          </span>
                        </td>
                        <td>
                          {r.msg}
                        </td>
                        <td>
                          {r.who}
                        </td>
                        <td>
                          <span className={r.stCls}>
                            {r.st}
                          </span>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {r.pending ? (
                            <>
                              <button type="button" className={`btn btn-sm ${r.btnCls}`} onClick={r.nudge}>
                                {r.btnLabel}
                              </button>
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
          <section className="card" aria-label="최근 접속 활동" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                최근 접속 활동
              </h2>
              <a href="#/AdminSecurity" style={{ marginLeft: "auto", fontSize: "13px" }}>
                전체 접속 기록
              </a>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl" style={{ minWidth: "820px" }}>
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
                  </tr>
                </thead>
                <tbody>
                  {(v.access || []).map((r, i_r) => (
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
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card" aria-label="상담사별 업무량" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                상담사별 업무량
              </h2>
              <a href="#/AdminAccounts" style={{ marginLeft: "auto", fontSize: "13px" }}>
                계정 관리
              </a>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl" style={{ minWidth: "900px" }}>
                <thead>
                  <tr>
                    <th scope="col">
                      상담사
                    </th>
                    <th scope="col" style={{ width: "22%" }}>
                      담당 사례
                    </th>
                    <th scope="col">
                      위기도 위기·집중
                    </th>
                    <th scope="col">
                      이번 주 상담
                    </th>
                    <th scope="col">
                      기록 확인 대기
                    </th>
                    <th scope="col">
                      일지 미작성
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.load || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td>
                          <span style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            <span className="av" style={{ width: "34px", height: "34px", fontSize: "13px" }}>
                              {r.ini}
                            </span>
                            <span>
                              <b style={{ fontWeight: "500" }}>
                                {r.name}
                              </b>
                              <span className="note" style={{ display: "block" }}>
                                {r.rank}
                              </span>
                            </span>
                          </span>
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            <span className="mini" style={{ flex: "1" }}>
                              <span style={{ width: r.w }} />
                            </span>
                            <b style={{ width: "32px" }}>
                              {r.cases}
                            </b>
                          </div>
                        </td>
                        <td>
                          {r.hi}
                        </td>
                        <td>
                          {r.week}
                        </td>
                        <td>
                          {r.stt}
                        </td>
                        <td>
                          {r.note}
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
