// AdminApp 화면 마크업 — tools/dc2jsx.py 가 디자인(AdminApp.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AdminApp.css';

export default function View({ v }) {
  return (
    <div className="pg-AdminApp">
      <div className={v.themeCls} style={{ minHeight: "1500px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
              온
            </span>
            <b style={{ fontSize: "17px" }}>
              온담
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
            <a className="on" href="#/AdminApp">
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
              안부 연계 앱 관리
            </h1>
          </header>
          {v.msg ? <p className="note" role="status" style={{ margin: "0", color: "#1F3A56" }}>{v.msg}</p> : null}
          <section aria-label="앱 · 가족 연결 요약" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }}>
            <div className="card kpi">
              <span className="sub">
                전체 어르신
              </span>
              <b>
                {v.totalElders}
              </b>
              <span className="note">
                {v.totalNote}
              </span>
            </div>
            <div className="card kpi">
              <span className="sub">
                어르신 안부 앱 연결됨
              </span>
              <b>
                {v.onCnt}
              </b>
              <span className="note">
                {v.onNote}
              </span>
            </div>
            <div className="card kpi">
              <span className="sub">
                미연결 · 초대 대기
              </span>
              <b>
                {v.offCnt}
              </b>
              <span className="note">
                {v.offNote}
              </span>
            </div>
            <a className="card kpi" href="#silent">
              <span className="sub acc" style={{ fontWeight: "700" }}>
                장기 무응답 (48시간 이상)
              </span>
              <b className="acc">
                {v.silentCnt}
              </b>
              <span className="note">
                {"안부 전화 · 방문 확인 미처리 "}{v.silentOpen}명
              </span>
            </a>
          </section>
          <section className="card" aria-label="앱 · 가족 연결 현황" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                앱 · 가족 연결 현황
              </h2>
              <div style={{ marginLeft: "auto" }}>
                <div role="group" aria-label="연결 상태" className="seg">
                  {(v.cFilters || []).map((f, i_f) => (
                    <Fragment key={i_f}>
                      <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                        {f.label}
                      </button>
                    </Fragment>
                  ))}
                </div>
              </div>
            </div>
            <div style={{ padding: "18px 22px 4px", display: "flex", flexDirection: "column", gap: "10px" }}>
              <div className="stack" role="img" aria-label={v.stackAria}>
                <span style={{ width: v.wOn, background: "#5FA4D6" }} />
                <span style={{ width: v.wWait, background: "#C5D4DE" }} />
                <span style={{ width: v.wOff, background: "#66788A" }} />
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 18px" }}>
                <span className="lg">
                  <i style={{ background: "#5FA4D6" }} />
                  {v.lgOn}
                </span>
                <span className="lg">
                  <i style={{ background: "#C5D4DE" }} />
                  {v.lgWait}
                </span>
                <span className="lg">
                  <i style={{ background: "#66788A" }} />
                  {v.lgOff}
                </span>
              </div>
            </div>
            <div style={{ overflowX: "auto", marginTop: "10px" }}>
              <table className="tbl" style={{ minWidth: "980px" }}>
                <thead>
                  <tr>
                    <th scope="col">
                      어르신
                    </th>
                    <th scope="col">
                      담당 상담사
                    </th>
                    <th scope="col">
                      앱 연결 상태
                    </th>
                    <th scope="col">
                      연결일
                    </th>
                    <th scope="col">
                      최근 응답
                    </th>
                    <th scope="col">
                      가족 연결 · 공유 동의
                    </th>
                    <th scope="col">
                      <span style={{ position: "absolute", left: "-9999px" }}>
                        작업
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.conn || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td>
                          <b style={{ fontWeight: "500" }}>
                            {r.sr}
                          </b>
                          <span className="note" style={{ display: "block" }}>
                            {r.cid}
                          </span>
                        </td>
                        <td>
                          {r.who}
                        </td>
                        <td>
                          <span className={r.stCls}>
                            {r.st}
                          </span>
                        </td>
                        <td>
                          {r.since}
                        </td>
                        <td>
                          {r.last}
                        </td>
                        <td>
                          <span className={r.famCls}>
                            {r.fam}
                          </span>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {r.canInvite ? (
                            <>
                              <button type="button" className="btn btn-sm btn-s" onClick={r.invite}>
                                {r.invLabel}
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
          <section id="silent" className="card" aria-label="장기 무응답 어르신" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                장기 무응답 어르신
              </h2>
              <span className="note">
                마지막 응답 후 48시간 이상 · 안부 전화 → 연락 안 되면 생활지원사·가족 방문 확인 (고독사 예방)
              </span>
              <div style={{ marginLeft: "auto" }}>
                <div role="group" aria-label="안부 연락 처리" className="seg">
                  {(v.sFilters || []).map((f, i_f) => (
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
              <table className="tbl" style={{ minWidth: "900px" }}>
                <thead>
                  <tr>
                    <th scope="col">
                      어르신
                    </th>
                    <th scope="col">
                      담당 상담사
                    </th>
                    <th scope="col">
                      마지막 응답
                    </th>
                    <th scope="col">
                      무응답
                    </th>
                    <th scope="col">
                      안부 확인
                    </th>
                    <th scope="col">
                      처리 내용
                    </th>
                    <th scope="col">
                      <span style={{ position: "absolute", left: "-9999px" }}>
                        작업
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.silent || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td>
                          <b style={{ fontWeight: "500" }}>
                            {r.sr}
                          </b>
                          <span className="note" style={{ display: "block" }}>
                            {r.cid}
                          </span>
                        </td>
                        <td>
                          {r.who}
                        </td>
                        <td>
                          {r.last}
                        </td>
                        <td>
                          <span className={r.dCls}>
                            {r.days}일
                          </span>
                        </td>
                        <td>
                          <span className={r.stCls}>
                            {r.st}
                          </span>
                        </td>
                        <td className="note" style={{ color: "#1F3A56" }}>
                          {r.memo}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <button type="button" className={`btn btn-sm ${r.btnCls}`} onClick={r.toggle}>
                            {r.btnLabel}
                          </button>
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
