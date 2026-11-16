// CaseHistory 화면 마크업 — tools/dc2jsx.py 가 디자인(CaseHistory.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './CaseHistory.css';

export default function View({ v }) {
  return (
    <div className="pg-CaseHistory">
      <div className={v.themeCls} style={{ minHeight: "1550px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            + 새 사례 등록
          </a>
          <nav className="nav" aria-label="메뉴">
            <a href="#/Home">
              홈
            </a>
            <a className="on" href="#/CaseList">
              사례 관리
            </a>
            <a href="#/Schedule">
              일정
            </a>
            <a href="#/Soon?name=ChildLink">
              안부 연계
              <span className="cnt">
                4
              </span>
            </a>
            <a href="#/Soon?name=Closure">
              종결 검토
              <span className="cnt">
                2
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
              이
            </span>
            <b style={{ fontWeight: "500" }}>
              이서연 상담사
            </b>
            <a href="#/Login" className="note" style={{ marginLeft: "auto" }}>
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
              사례 관리
            </a>
            {" › 김순자 C-2026-0351"}
          </nav>
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px 18px" }}>
            <a className="btn btn-sm btn-s" href="#/CaseList">
              ← 목록
            </a>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  김순자
                </h1>
                <span className="sub">
                  만 82세 · 여 · 독거
                </span>
                <span className="chip c-hi">
                  위기도 집중
                </span>
              </div>
              <div className="note">
                C-2026-0351 · 다음 상담 오늘 16:00
              </div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              <button type="button" className="btn btn-s" onClick={v.recOpen}>
                <span className="rec-dot" aria-hidden="true" />
                {" 녹음하기"}
              </button>
              <button type="button" className="btn btn-s" onClick={v.nsOpen}>
                + 새 상담 등록
              </button>
            </div>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <a href="#/CaseInfo">
              내담자 정보
            </a>
            <a className="on" aria-current="page" href="#/CaseHistory">
              상담 이력
            </a>
            <a href="#/Soon?name=CaseDocs">
              문서함
            </a>
          </nav>
          <section className="card" aria-label="지금까지 상담" style={{ padding: "24px 26px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px 12px" }}>
              <span className="secno">
                1
              </span>
              <h2 className="h2">
                지금까지 상담
              </h2>
              <span className="chip c-ai">
                AI 분석 · 1~8회차
              </span>
            </div>
            <div style={{ marginTop: "16px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px" }}>
              <div className="box">
                <div className="note">
                  1~3회차
                </div>
                <b style={{ fontWeight: "500" }}>
                  관계 형성 · 일상 파악
                </b>
              </div>
              <div className="box">
                <div className="note">
                  4~6회차
                </div>
                <b style={{ fontWeight: "500" }}>
                  배우자 사별 · 애도
                </b>
                <div className="note">
                  입맛 저하 · 불면 첫 언급
                </div>
              </div>
              <div className="box">
                <div className="note">
                  7~8회차 · 최근
                </div>
                <b style={{ fontWeight: "500" }}>
                  외로움 · 아들과의 관계
                </b>
                <div className="note">
                  "짐 되기 싫어요"
                </div>
              </div>
            </div>
            <div style={{ marginTop: "18px", display: "flex", flexWrap: "wrap", gap: "20px" }}>
              <div style={{ flex: "1 1 360px", display: "flex", flexDirection: "column", gap: "10px" }}>
                <div className="note">
                  주제 비중
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "110px 1fr 40px", gap: "10px", alignItems: "center" }}>
                  <span>
                    상실 · 애도
                  </span>
                  <span className="bar">
                    <span style={{ width: "38%" }} />
                  </span>
                  <span className="note">
                    38%
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "110px 1fr 40px", gap: "10px", alignItems: "center" }}>
                  <span>
                    우울감 · 정서
                  </span>
                  <span className="bar">
                    <span style={{ width: "27%" }} />
                  </span>
                  <span className="note">
                    27%
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "110px 1fr 40px", gap: "10px", alignItems: "center" }}>
                  <span>
                    가족관계(아들)
                  </span>
                  <span className="bar">
                    <span style={{ width: "20%" }} />
                  </span>
                  <span className="note">
                    20%
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "110px 1fr 40px", gap: "10px", alignItems: "center" }}>
                  <span>
                    일상 · 외출
                  </span>
                  <span className="bar">
                    <span style={{ width: "10%" }} />
                  </span>
                  <span className="note">
                    10%
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "110px 1fr 40px", gap: "10px", alignItems: "center" }}>
                  <span>
                    식사 · 건강
                  </span>
                  <span className="bar">
                    <span style={{ width: "5%" }} />
                  </span>
                  <span className="note">
                    5%
                  </span>
                </div>
              </div>
              <div style={{ flex: "1 1 300px", display: "flex", flexDirection: "column", gap: "10px" }}>
                <div className="box">
                  <b>
                    덜 다룬 부분
                  </b>
                  <div>
                    식사 · 건강
                  </div>
                  <div className="src">
                    8회차 02:15 첫 언급
                  </div>
                </div>
                <div className="box">
                  <b>
                    안부 앱 연계
                  </b>
                  <div>
                    '외로움' ↔ 안부 앱 '기분이 별로예요' 3회 연속
                  </div>
                </div>
              </div>
            </div>
          </section>
          <section className="card" aria-label="상담 회차" style={{ padding: "22px 24px", position: "relative" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px 12px", marginBottom: "10px" }}>
              <span className="secno">
                2
              </span>
              <h2 className="h2">
                상담 회차
              </h2>
              <span className="note">
                최근 3회차
              </span>
              <button type="button" className="btn btn-sm btn-s" style={{ marginLeft: "auto" }} aria-haspopup="dialog" aria-expanded={v.openAttr} onClick={v.toggleOpen}>
                {"전 회차 보기 · "}{v.total}회
              </button>
            </div>
            <div>
              {(v.recent || []).map((s, i_s) => (
                <Fragment key={i_s}>
                  <a className="srow" href="#/SessionDetail" onClick={s.go}>
                    <b>
                      {s.no}
                    </b>
                    <span>
                      {s.date}
                    </span>
                    <span className="note">
                      {s.kind}
                    </span>
                    <span className="note">
                      {s.sig}
                    </span>
                    <span className={s.st}>
                      {s.status}
                    </span>
                  </a>
                </Fragment>
              ))}
            </div>
            {v.open ? (
              <>
                <div className="pop" role="dialog" aria-label="전 회차">
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "14px 16px 10px", borderBottom: "1px solid #DDE6EC" }}>
                    <b style={{ fontSize: "15px" }}>
                      {"전 회차 · "}{v.shownCount}
                    </b>
                    <label style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "12.5px", color: "#55687A", cursor: "pointer" }}>
                      <input type="checkbox" checked={v.sigOnly} onChange={v.toggleSig} style={{ accentColor: "#5FA4D6" }} />
                      신호 있는 회차만
                    </label>
                    <button type="button" aria-label="닫기" onClick={v.toggleOpen} style={{ border: "0", background: "transparent", fontSize: "18px", color: "#66788A", cursor: "pointer", padding: "0 2px" }}>
                      ×
                    </button>
                  </div>
                  <div style={{ maxHeight: "360px", overflowY: "auto", padding: "4px 8px 8px" }}>
                    {(v.all || []).map((s, i_s) => (
                      <Fragment key={i_s}>
                        <a className="prow" href="#/SessionDetail" onClick={s.go}>
                          <b>
                            {s.no}
                          </b>
                          <span>
                            {s.date}
                          </span>
                          <span className="note">
                            {s.kindShort}
                          </span>
                          <span className="note">
                            {s.sig}
                          </span>
                          <span className={s.st}>
                            {s.status}
                          </span>
                        </a>
                      </Fragment>
                    ))}
                  </div>
                </div>
              </>
            ) : null}
          </section>
          <section className="card" aria-label="회차별 세부 신호" style={{ padding: "22px 24px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px 12px", marginBottom: "10px" }}>
              <span className="secno">
                3
              </span>
              <h2 className="h2">
                회차별 세부 신호
              </h2>
              <span className="src">
                채택 신호 · 근거 발화 수
              </span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <div className="mx" style={{ minWidth: "640px" }}>
                <span className="rl note">
                  세부 신호
                </span>
                {(v.cols || []).map((c, i_c) => (
                  <Fragment key={i_c}>
                    <a href="#/SessionDetail" onClick={c.go} className="note" style={{ textDecoration: "none", color: "#496887" }}>
                      {c.label}
                    </a>
                  </Fragment>
                ))}
                {(v.mrows || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <span className="rl">
                      <span className="chip c-normal" style={{ height: "20px", fontSize: "11px", marginRight: "6px" }}>
                        {r.type}
                      </span>
                      {r.name}
                    </span>
                    {(r.cells || []).map((x, i_x) => (
                      <Fragment key={i_x}>
                        <span>
                          {x.pend ? (
                            <>
                              <a className="dot dot-go" href="#/Step1Record" onClick={x.go} title={`${x.tip} · 눌러서 해당 발화 확인`} aria-label={`${x.tip} · 해당 발화로 이동`} style={{ background: x.bg, color: x.fg, boxShadow: x.ring }}>
                                {x.v}
                              </a>
                            </>
                          ) : null}
                          {x.notPend ? (
                            <>
                              <span className="dot" title={x.tip} style={{ background: x.bg, color: x.fg, boxShadow: x.ring }}>
                                {x.v}
                              </span>
                            </>
                          ) : null}
                        </span>
                      </Fragment>
                    ))}
                  </Fragment>
                ))}
              </div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "14px", marginTop: "10px", fontSize: "12px", color: "#66788A" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <span className="dot" style={{ width: "18px", height: "18px", background: "#DDE6EC" }} />
                1번
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <span className="dot" style={{ width: "18px", height: "18px", background: "#66788A" }} />
                2번 이상
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <span className="dot" style={{ width: "18px", height: "18px", background: "#FFFFFF", boxShadow: "inset 0 0 0 1.5px #66788A" }} />
                보류 (화자 확인 중)
              </span>
            </div>
          </section>
          <p className="ainote">
            AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
          </p>
          {v.recShow ? (
            <>
              <div className="rec-ov">
                <section role="dialog" aria-modal="true" aria-labelledby="rec-title" className="rec-dlg">
                  <div style={{ padding: "20px 24px 16px", borderBottom: "1px solid #DDE6EC", display: "flex", alignItems: "center", gap: "12px" }} className="rec-hd">
                    <h2 id="rec-title" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                      녹음하기
                    </h2>
                    <button type="button" className="rec-x" aria-label="닫기" onClick={v.recClose}>
                      ×
                    </button>
                  </div>
                  <div style={{ padding: "20px 24px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
                    <div className="rec-case">
                      <span className="note">
                        사례
                      </span>
                      <b>
                        김순자 · C-2026-0351
                      </b>
                      <span className="sub">
                        만 82세 · 여 · 독거
                      </span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="lb2">
                          상담 회차
                        </span>
                        <select className="inp" value={v.recSes} onChange={v.recSesSet} disabled={v.recLock}>
                          <option value="new">
                            새 회차 · 9회차
                          </option>
                          <option value="8">
                            8회차 · 10/2 방문상담
                          </option>
                          <option value="7">
                            7회차 · 9/18 내방상담
                          </option>
                          <option value="6">
                            6회차 · 9/4 방문상담
                          </option>
                          <option value="5">
                            5회차 · 8/28 내방상담
                          </option>
                          <option value="4">
                            4회차 · 8/21 방문상담
                          </option>
                          <option value="3">
                            3회차 · 8/14 전화상담
                          </option>
                          <option value="2">
                            2회차 · 8/7 방문상담
                          </option>
                          <option value="1">
                            1회차 · 7/31 초기상담(방문)
                          </option>
                        </select>
                      </label>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="lb2">
                          상담 유형
                        </span>
                        <select className="inp" value={v.recKind} onChange={v.recKindSet} disabled={v.recLock}>
                          <option>
                            방문상담
                          </option>
                          <option>
                            내방상담
                          </option>
                          <option>
                            전화상담
                          </option>
                          <option>
                            가족 면담
                          </option>
                        </select>
                      </label>
                    </div>
                    <div className="rec-box">
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}>
                        <span className={`rec-dot ${v.recDotCls}`} aria-hidden="true" />
                        <span className="rec-status">
                          {v.recStatus}
                        </span>
                      </div>
                      <div className="rec-time" aria-live="polite">
                        {v.recTime}
                      </div>
                      {v.recIdle ? (
                        <>
                          <label className="rec-consent">
                            <input type="checkbox" checked={v.recConsent} onChange={v.recConsentSet} />
                            <span>
                              어르신(참석자)께 녹음 사실을 천천히 알리고 동의를 받았어요
                            </span>
                          </label>
                          {v.recErr ? (
                            <>
                              <span className="acc" style={{ fontSize: "13px" }}>
                                녹음 동의를 먼저 확인해 주세요.
                              </span>
                            </>
                          ) : null}
                          <button type="button" className="btn btn-p rec-main" onClick={v.recStart}>
                            <span className="rec-dot" aria-hidden="true" />
                            {" 녹음 시작"}
                          </button>
                        </>
                      ) : null}
                      {v.recRunning ? (
                        <>
                          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px" }}>
                            <button type="button" className="btn btn-s" onClick={v.recPause}>
                              {v.recPauseLabel}
                            </button>
                            <button type="button" className="btn btn-p" onClick={v.recStop}>
                              ■ 정지
                            </button>
                          </div>
                        </>
                      ) : null}
                      {v.recDone ? (
                        <>
                          {v.recHasUrl ? (
                            <>
                              <audio controls="" src={v.recUrl} style={{ width: "100%" }} />
                            </>
                          ) : null}
                          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px" }}>
                            <button type="button" className="btn btn-s" onClick={v.recReset}>
                              다시 녹음
                            </button>
                            <button type="button" className="btn btn-p" onClick={v.recSave}>
                              저장
                            </button>
                          </div>
                        </>
                      ) : null}
                      {v.recSaved ? (
                        <>
                          <p style={{ margin: "0", textAlign: "center" }}>
                            {"녹음을 저장했어요 · "}{v.recSummary}
                            <br />
                            <b>
                              STT 분석을 시작할까요?
                            </b>
                          </p>
                          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px" }}>
                            <button type="button" className="btn btn-s" onClick={v.recClose}>
                              나중에
                            </button>
                            <a className="btn btn-p" href="#/Step1Record" onClick={v.recClose}>
                              기록 확인으로 →
                            </a>
                          </div>
                        </>
                      ) : null}
                      {v.recSim ? (
                        <>
                          <span className="note" style={{ textAlign: "center" }}>
                            이 미리보기에서는 마이크를 쓸 수 없어 녹음 흐름만 보여 드려요. 실제 화면에서는 마이크로 바로 녹음돼요.
                          </span>
                        </>
                      ) : null}
                    </div>
                  </div>
                </section>
              </div>
            </>
          ) : null}
          {v.nsShow ? (
            <>
              <div className="rec-ov">
                <section role="dialog" aria-modal="true" aria-labelledby="ns-title" className="rec-dlg" style={{ maxWidth: "640px" }}>
                  <div style={{ padding: "22px 26px 16px", borderBottom: "1px solid #DDE6EC" }} className="rec-hd">
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <h2 id="ns-title" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                        새 상담 등록
                      </h2>
                      <button type="button" className="rec-x" aria-label="닫기" onClick={v.nsClose}>
                        ×
                      </button>
                    </div>
                    <ol aria-label="등록 단계" style={{ listStyle: "none", margin: "14px 0 0", padding: "0", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {(v.nsSteps || []).map((t, i_t) => (
                        <Fragment key={i_t}>
                          <li className={`ns-step ${t.cls}`}>
                            <span className="ns-dot">
                              {t.mark}
                            </span>
                            {t.label}
                          </li>
                        </Fragment>
                      ))}
                    </ol>
                  </div>
                  <div style={{ padding: "22px 26px", minHeight: "340px", display: "flex", flexDirection: "column", gap: "14px" }}>
                    <div className="rec-case">
                      <span className="note">
                        사례
                      </span>
                      <b>
                        김순자 · C-2026-0351
                      </b>
                      <span className="sub">
                        만 82세 · 여 · 독거
                      </span>
                      {v.nsS2 ? (
                        <>
                          <span className="chip c-sand" style={{ marginLeft: "auto" }}>
                            {v.nsSesLabel}
                          </span>
                        </>
                      ) : null}
                    </div>
                    {v.nsS1 ? (
                      <>
                        <p className="lb2" style={{ margin: "0" }}>
                          몇 회차 상담인가요?
                        </p>
                        <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "300px", overflowY: "auto", paddingRight: "6px" }}>
                          {(v.nsSessions || []).map((x, i_x) => (
                            <Fragment key={i_x}>
                              <button type="button" className={`ns-opt ${x.cls}`} role="radio" aria-checked={x.on} onClick={x.pick}>
                                <span className="ns-rd" aria-hidden="true" />
                                <span>
                                  <b style={{ fontWeight: "500" }}>
                                    {x.label}
                                  </b>
                                  <span className="note" style={{ display: "block" }}>
                                    {x.meta}
                                  </span>
                                </span>
                              </button>
                            </Fragment>
                          ))}
                        </div>
                      </>
                    ) : null}
                    {v.nsS2 ? (
                      <>
                        <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                          <span className="lb2">
                            {"상담 내용 "}
                            <span className="acc">
                              *
                            </span>
                          </span>
                          <textarea className="ns-ta" rows="6" placeholder="상담 일시 · 방식(내방/방문/전화), 어르신 말씀, 주요 대화 내용 등을 적어 주세요" value={v.nsBody} onChange={v.nsBodySet} style={{ borderColor: v.nsBodyBd }} />
                          {v.nsErr ? (
                            <>
                              <span className="acc" style={{ fontSize: "13px" }}>
                                상담 내용을 입력해 주세요.
                              </span>
                            </>
                          ) : null}
                        </label>
                        <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                          <span className="lb2">
                            상담사 소견
                          </span>
                          <textarea className="ns-ta" rows="4" placeholder="어르신의 정서 · 생활 상태, 정서 · 위기 신호, 연계 · 향후 계획 등을 적어 주세요" value={v.nsNote} onChange={v.nsNoteSet} />
                        </label>
                      </>
                    ) : null}
                  </div>
                  <div style={{ padding: "16px 26px 22px", display: "flex", alignItems: "center", gap: "10px", borderTop: "1px solid #DDE6EC" }} className="rec-hd">
                    {v.nsS1 ? (
                      <>
                        <button type="button" className="btn btn-s" onClick={v.nsClose}>
                          취소
                        </button>
                      </>
                    ) : null}
                    {v.nsS2 ? (
                      <>
                        <button type="button" className="btn btn-s" onClick={v.nsPrev}>
                          이전
                        </button>
                      </>
                    ) : null}
                    <span style={{ flex: "1" }} />
                    {v.nsS1 ? (
                      <>
                        <button type="button" className="btn btn-p" onClick={v.nsNext}>
                          다음
                        </button>
                      </>
                    ) : null}
                    {v.nsS2 ? (
                      <>
                        <button type="button" className="btn btn-p" onClick={v.nsSave}>
                          저장
                        </button>
                      </>
                    ) : null}
                  </div>
                  {v.nsDone ? (
                    <>
                      <div className="ns-cf-ov">
                        <section role="alertdialog" aria-labelledby="ns-ok" className="ns-cf">
                          <span className="ns-ok-i" aria-hidden="true">
                            ✓
                          </span>
                          <h2 id="ns-ok" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                            상담을 등록했어요
                          </h2>
                          <p style={{ margin: "0" }}>
                            {"김순자 · "}{v.nsSesLabel}
                            <br />
                            {"상담 내용 "}{v.nsBodyLen}{"자 · 상담사 소견 "}{v.nsNoteLen}자
                          </p>
                          <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: "6px" }}>
                            <button type="button" className="btn btn-p" onClick={v.nsClose}>
                              확인
                            </button>
                          </div>
                        </section>
                      </div>
                    </>
                  ) : null}
                </section>
              </div>
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
