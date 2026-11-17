// Step3Summary 화면 마크업 — tools/dc2jsx.py 가 디자인(Step3Summary.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './Step3Summary.css';

export default function View({ v }) {
  return (
    <div className="pg-Step3Summary">
      <div className={v.themeCls} style={{ minHeight: "2000px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
              IS
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
            <a href={v.caseHref}>
              {v.crumbCase}
            </a>
            {" › "}
            <a href={v.historyHref}>
              상담 이력
            </a>
            {" › "}
            <a href={v.sessionHref}>
              {v.crumbSession}
            </a>
          </nav>
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 280px" }}>
              <div className="sub">
                {v.sub}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "2px" }}>
                <a className="btn btn-sm btn-s" href={v.caseHref} aria-label="내담자 정보로 돌아가기" title="내담자 정보로 돌아가기">
                  ←
                </a>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  {v.title}
                </h1>
              </div>
            </div>
          </header>
          <nav className="steps" aria-label="회차 처리 단계">
            <a className="stp done" href={v.step1Href}>
              <span className="sn">
                ✓
              </span>
              <b style={{ fontWeight: "500" }}>
                기록 확인
              </b>
            </a>
            <a className="stp done" href={v.step2Href}>
              <span className="sn">
                ✓
              </span>
              <b style={{ fontWeight: "500" }}>
                정서·위기 신호 확인
              </b>
            </a>
            <a className="stp on" href={v.step3Href} aria-current="step">
              <span className="sn">
                3
              </span>
              <b style={{ fontWeight: "700" }}>
                상담일지 작성
              </b>
            </a>
            <a className="stp" href={v.step4Href}>
              <span className="sn">
                4
              </span>
              <b style={{ fontWeight: "500" }}>
                다음 상담 준비
              </b>
            </a>
          </nav>
          <section className="card" aria-label="상담 요약" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "14px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
              <h2 className="h2">
                상담 요약
              </h2>
              <span className="chip c-ai">
                {v.sumChip}
              </span>
            </div>
            {(v.sums || []).map((r, i_r) => (
              <Fragment key={i_r}>
                <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <b style={{ fontSize: "14px" }}>
                    {r.k}
                  </b>
                  <textarea className="ta2" aria-label={r.k} value={r.v} onChange={r.set} readOnly={!!r.ro} />
                  <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                    <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                      <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                    </svg>
                    <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M5 12.5l4.5 4.5L19 7.5" />
                    </svg>
                  </button>
                  <span className="cp-menu" role="menu" aria-label="복사 방식">
                    <button type="button" role="menuitem" onClick={v.copyRaw}>
                      그대로 복사
                    </button>
                    <button type="button" role="menuitem" onClick={v.copyMask}>
                      이름 가려서 복사
                      <span className="cp-ex">
                        예) 김○자
                      </span>
                    </button>
                  </span>
                </label>
              </Fragment>
            ))}
          </section>
          <section className="card" aria-label="상담 일지" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "14px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
              <h2 className="h2">
                상담일지 · S-07 기관 양식
              </h2>
              <span className="chip c-ai">
                AI 초안
              </span>
            </div>
            <div className="fhead">
              <div>
                <span className="k">
                  사례번호 · 회차
                </span>
                <span className="v">
                  {v.fNo}
                </span>
              </div>
              <div>
                <span className="k">
                  내담 어르신
                </span>
                <span className="v">
                  {v.fWho}
                </span>
              </div>
              <div>
                <span className="k">
                  상담일시
                </span>
                <span className="v">
                  {v.fWhen}
                </span>
              </div>
              <div>
                <span className="k">
                  장소 · 방식
                </span>
                <span className="v">
                  {v.fWhere}
                </span>
              </div>
              <div>
                <span className="k">
                  참석자
                </span>
                <span className="v">
                  {v.fAttend}
                </span>
              </div>
              <div>
                <span className="k">
                  담당 상담사
                </span>
                <span className="v">
                  {v.fCounselor}
                </span>
              </div>
            </div>
            <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <b style={{ fontSize: "14px" }}>
                주요 내용 (어르신 말씀)
              </b>
              <textarea className="ta2" style={{ minHeight: "104px" }} value={v.quotes} readOnly />
              <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                  <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                </svg>
                <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
              </button>
              <span className="cp-menu" role="menu" aria-label="복사 방식">
                <button type="button" role="menuitem" onClick={v.copyRaw}>
                  그대로 복사
                </button>
                <button type="button" role="menuitem" onClick={v.copyMask}>
                  이름 가려서 복사
                  <span className="cp-ex">
                    예) 김○자
                  </span>
                </button>
              </span>
            </label>
            <div className="grp">
              정서 상태 및 관찰내용
            </div>
            <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <b style={{ fontSize: "14px" }}>
                정서 상태
              </b>
              <textarea className="ta2" value={v.mood} readOnly />
              <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                  <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                </svg>
                <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
              </button>
              <span className="cp-menu" role="menu" aria-label="복사 방식">
                <button type="button" role="menuitem" onClick={v.copyRaw}>
                  그대로 복사
                </button>
                <button type="button" role="menuitem" onClick={v.copyMask}>
                  이름 가려서 복사
                  <span className="cp-ex">
                    예) 김○자
                  </span>
                </button>
              </span>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <b style={{ fontSize: "14px" }}>
                생활환경 (주거 · 식사)
              </b>
              <textarea className="ta2" placeholder="상담사 작성" />
              <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                  <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                </svg>
                <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
              </button>
              <span className="cp-menu" role="menu" aria-label="복사 방식">
                <button type="button" role="menuitem" onClick={v.copyRaw}>
                  그대로 복사
                </button>
                <button type="button" role="menuitem" onClick={v.copyMask}>
                  이름 가려서 복사
                  <span className="cp-ex">
                    예) 김○자
                  </span>
                </button>
              </span>
              <span className="note acc">
                개인정보 보호 · 기관 복귀 후 기록 (어르신 앞에서 기록 금지)
              </span>
            </label>
            <div className="grp" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              어르신 정서 · 건강 특성
              <button type="button" className={`btn btn-sm ${v.trBtnCls}`} style={{ marginLeft: "auto" }} aria-pressed={v.trEditing} onClick={v.trToggleEdit}>
                {v.trBtnLabel}
              </button>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {v.trEdit ? (
                <>
                  {(v.traits || []).map((t, i_t) => (
                    <Fragment key={i_t}>
                      <button type="button" className="chipck" aria-pressed={t.pressed} onClick={t.toggle} style={{ background: t.bg, borderColor: t.bd, color: t.fg, fontWeight: t.fw }}>
                        {t.mark}{" "}{t.label}
                      </button>
                    </Fragment>
                  ))}
                </>
              ) : null}
              {v.trView ? (
                <>
                  {(v.traitsOn || []).map((t, i_t) => (
                    <Fragment key={i_t}>
                      <span className="chipck" style={{ cursor: "default", background: "#E8F4FC", borderColor: "#1F3A56", fontWeight: "700" }}>
                        {"✓ "}{t.label}
                      </span>
                    </Fragment>
                  ))}
                  {v.trNone ? (
                    <>
                      <span className="note" style={{ alignSelf: "center" }}>
                        선택된 항목 없음
                      </span>
                    </>
                  ) : null}
                </>
              ) : null}
            </div>
            <div className="grp" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              가족 · 생활 상황
              <button type="button" className={`btn btn-sm ${v.hmBtnCls}`} style={{ marginLeft: "auto" }} aria-pressed={v.hmEditing} onClick={v.hmToggleEdit}>
                {v.hmBtnLabel}
              </button>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {v.hmEdit ? (
                <>
                  {(v.homes || []).map((t, i_t) => (
                    <Fragment key={i_t}>
                      <button type="button" className="chipck" aria-pressed={t.pressed} onClick={t.toggle} style={{ background: t.bg, borderColor: t.bd, color: t.fg, fontWeight: t.fw }}>
                        {t.mark}{" "}{t.label}
                      </button>
                    </Fragment>
                  ))}
                </>
              ) : null}
              {v.hmView ? (
                <>
                  {(v.homesOn || []).map((t, i_t) => (
                    <Fragment key={i_t}>
                      <span className="chipck" style={{ cursor: "default", background: "#E8F4FC", borderColor: "#1F3A56", fontWeight: "700" }}>
                        {"✓ "}{t.label}
                      </span>
                    </Fragment>
                  ))}
                  {v.hmNone ? (
                    <>
                      <span className="note" style={{ alignSelf: "center" }}>
                        선택된 항목 없음
                      </span>
                    </>
                  ) : null}
                </>
              ) : null}
            </div>
            <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <b style={{ fontSize: "14px" }}>
                개입 내용 · 정서·위기 신호 검토
              </b>
              <textarea className="ta2" value={v.note} onChange={v.setNote} readOnly={v.noteRo} />
              <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                  <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                </svg>
                <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
              </button>
              <span className="cp-menu" role="menu" aria-label="복사 방식">
                <button type="button" role="menuitem" onClick={v.copyRaw}>
                  그대로 복사
                </button>
                <button type="button" role="menuitem" onClick={v.copyMask}>
                  이름 가려서 복사
                  <span className="cp-ex">
                    예) 김○자
                  </span>
                </button>
              </span>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <span style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <b style={{ fontSize: "14px" }}>
                  연계 · 다음 계획
                </b>
                <span className="chip c-ai" style={{ height: "20px", fontSize: "11px" }}>
                  AI 초안
                </span>
              </span>
              <textarea className="ta2" style={{ minHeight: "96px" }} value={v.plan} readOnly />
              <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                  <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                </svg>
                <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
              </button>
              <span className="cp-menu" role="menu" aria-label="복사 방식">
                <button type="button" role="menuitem" onClick={v.copyRaw}>
                  그대로 복사
                </button>
                <button type="button" role="menuitem" onClick={v.copyMask}>
                  이름 가려서 복사
                  <span className="cp-ex">
                    예) 김○자
                  </span>
                </button>
              </span>
            </label>
          </section>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" }}>
            <a className="btn btn-s" href={v.step2Href}>
              ← 정서·위기 신호 확인
            </a>
            <a className="btn btn-p" href={v.step4Href} style={{ marginLeft: "auto" }} onClick={v.save}>
              {v.saveLabel}
            </a>
          </div>
          {v.msg ? (
            <p className="note" role="alert" style={{ margin: "0" }}>
              {v.msg}
            </p>
          ) : null}
          <p className="ainote">
            AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
          </p>
        </main>
      </div>
    </div>
  );
}
