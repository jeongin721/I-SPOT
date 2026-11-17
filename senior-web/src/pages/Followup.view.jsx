// Followup 화면 마크업 — tools/dc2jsx.py 가 디자인(Followup.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './Followup.css';

export default function View({ v }) {
  return (
    <div className="pg-Followup">
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
            <a className="on" href="#/Followup">
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
          <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
            후속관리
          </h1>
          <p className="sub" style={{ margin: "-8px 0 0" }}>
            {"상담 후 남은 조치사항 · 재방문 일정 · 전문기관 연계를 어르신별로 확인하고 처리합니다. 기준일 "}{v.todayLabel}{" · 담당 "}{v.counselorLine}
          </p>
          {v.msg ? (
            <p role="alert" className="note" style={{ margin: "0", color: "#A33B2E" }}>
              {v.msg}
            </p>
          ) : null}
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 12px" }}>
            <div role="group" aria-label="돌봄 상태" className="seg">
              {(v.filters || []).map((f, i_f) => (
                <Fragment key={i_f}>
                  <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
          </section>
          <section className="card" style={{ overflowX: "auto" }} aria-label="어르신 목록">
            <table className="tbl" style={{ minWidth: "640px" }}>
              <thead>
                <tr>
                  <th scope="col">
                    어르신
                  </th>
                  <th scope="col">
                    상태
                  </th>
                  <th scope="col">
                    미처리 조치
                  </th>
                  <th scope="col">
                    다음 일정
                  </th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <tr style={{ cursor: "pointer", background: r.bg }}>
                      <td style={{ background: r.bg }}>
                        <a className="nm" href={r.href} onClick={r.go}>
                          <span>
                            <b style={{ fontWeight: "700" }}>
                              {r.name}
                            </b>
                            <span className="note">
                              {r.age}
                            </span>
                          </span>
                        </a>
                      </td>
                      <td style={{ background: r.bg }}>
                        <a href={r.href} onClick={r.go} style={{ color: "inherit", textDecoration: "none", display: "block" }}>
                          <span className={r.stCls}>
                            {r.status}
                          </span>
                        </a>
                      </td>
                      <td style={{ background: r.bg }}>
                        <a href={r.href} onClick={r.go} style={{ color: "inherit", textDecoration: "none", display: "block" }}>
                          {r.open}
                          <span className="note" style={{ marginLeft: "4px" }}>
                            {r.more}
                          </span>
                        </a>
                      </td>
                      <td style={{ background: r.bg, whiteSpace: "nowrap" }}>
                        <a href={r.href} onClick={r.go} style={{ color: "inherit", textDecoration: "none", display: "block" }}>
                          {r.next}
                        </a>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
            {v.noRows ? (
              <>
                <p className="note" style={{ margin: "0", padding: "28px 18px", textAlign: "center", fontSize: "14px" }}>
                  해당 상태의 어르신이 없어요
                </p>
              </>
            ) : null}
          </section>
          <p className="ainote">
            조치사항 · 일정 · 연계 기록은 담당자가 직접 입력한 값입니다.
          </p>
          {v.hasToast ? (
            <>
              <div className="toast" role="status" aria-live="polite">
                {v.toast}
              </div>
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
