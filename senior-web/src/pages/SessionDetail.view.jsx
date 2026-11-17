// SessionDetail 화면 마크업 — tools/dc2jsx.py 가 디자인(SessionDetail.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './SessionDetail.css';

export default function View({ v }) {
  return (
    <div className="pg-SessionDetail">
      <div className={v.themeCls} style={{ minHeight: "950px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
          <a className="cta" href={v.uploadHref} onClick={v.markBack}>
            ↑ 녹취 · 자료 올리기
          </a>
          <a className="cta2" href="#/CaseRegister" onClick={v.markBack}>
            + 새 대상자 등록
          </a>
          <nav className="nav" aria-label="메뉴">
            <a href="#/Home">
              홈
            </a>
            <a className="on" href="#/CaseList">
              대상자 관리
            </a>
            <a href="#/Schedule">
              일정
            </a>
            <a href="#/Soon?name=ChildLink">
              안부 연계
              <span className="cnt">
                {v.navLinkCnt}
              </span>
            </a>
            <a href="#/Followup">
              후속관리
              <span className="cnt">
                {v.navFollowCnt}
              </span>
            </a>
            <a href="#/Soon?name=DocBox">
              문서함
            </a>
            <a href="#/Soon?name=LawGuide">
              법령 · 매뉴얼
            </a>
            <a href="#/Soon?name=Stats">
              통계
            </a>
            <a href="#/Soon?name=Settings">
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
            <a href="#/CaseList">
              대상자 관리
            </a>
            {" › "}
            <a href={v.infoHref}>
              {v.caseCrumb}
            </a>
            {" › "}
            <a href={v.historyHref}>
              상담 이력
            </a>
            {" › "}{v.cur.no}
          </nav>
          {v.loadErr ? (
            <p role="alert" className="note" style={{ margin: "0", color: "#A33B2E" }}>
              {v.loadErr}
            </p>
          ) : null}
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 300px" }}>
              <div className="sub">
                {v.cur.meta}
              </div>
              <h1 style={{ margin: "2px 0 0", fontSize: "30px", fontWeight: "700" }}>
                {v.cur.no}{" · "}{v.name}
              </h1>
            </div>
            <span className={v.cur.st} style={{ height: "28px" }}>
              {v.cur.status}
            </span>
          </header>
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
            <a className="btn btn-sm btn-s" href={v.historyHref}>
              ← 상담 이력
            </a>
            <span className="note" style={{ marginLeft: "6px" }}>
              다른 회차
            </span>
            <div className="sl-wrap">
              <button type="button" className="sl-btn" aria-haspopup="listbox" aria-expanded={v.slExp} onClick={v.slToggle}>
                {v.slBtn}
                <svg className="sl-car" viewBox={"0 0 24 24"} width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </button>
              {v.slOpen ? (
                <>
                  <div className="sl-pop" role="listbox" aria-label="회차 선택">
                    <div className="sl-hd">
                      {"회차 선택 "}
                      <span className="note">
                        {v.slHead}
                      </span>
                    </div>
                    <div className="sl-list">
                      {(v.slItems || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" role="option" aria-selected={o.on} className={`sl-opt ${o.cls}`} onClick={o.pick}>
                            <b className="sl-no">
                              {o.no}
                            </b>
                            <span className="sl-meta">
                              {o.meta}
                            </span>
                            <span className={o.stCls} style={{ height: "22px", fontSize: "11.5px" }}>
                              {o.st}
                            </span>
                          </button>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </section>
          <nav aria-label="회차 처리 단계" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "18px" }}>
            {(v.steps || []).map((t, i_t) => (
              <Fragment key={i_t}>
                <a className="big" href={t.href} style={{ boxShadow: t.ring, background: t.bg }}>
                  <span style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                    <span className="bn" style={{ background: t.nBg, color: t.nFg }}>
                      {t.mark}
                    </span>
                    <b style={{ flex: "1", fontSize: "20px" }}>
                      {t.label}
                    </b>
                    <span className={t.stCls}>
                      {t.st}
                    </span>
                  </span>
                  <span style={{ fontSize: "15px", lineHeight: "1.7" }}>
                    {t.preview}
                  </span>
                </a>
              </Fragment>
            ))}
          </nav>
          <p className="ainote">
            AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
          </p>
        </main>
      </div>
    </div>
  );
}
