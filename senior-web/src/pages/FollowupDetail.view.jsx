// FollowupDetail 화면 마크업 — tools/dc2jsx.py 가 디자인(FollowupDetail.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './FollowupDetail.css';

export default function View({ v }) {
  return (
    <div className="pg-FollowupDetail">
      <div className={v.themeCls} style={{ minHeight: "1300px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
          <nav aria-label="위치" className="note">
            <a href="#/Followup">
              후속관리
            </a>
            {" › "}{v.selName}
          </nav>
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px 18px" }}>
            <a className="btn btn-sm btn-s" href="#/Followup">
              ← 목록
            </a>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  {v.selName}
                </h1>
                <span className="sub">
                  {v.selAge}
                </span>
                <span className={v.selStCls}>
                  {v.selStatusChip}
                </span>
              </div>
              <div className="note">
                {"후속관리 상세 · 기준일 "}{v.todayLabel}{" · 담당 "}{v.counselorLine}
              </div>
            </div>
          </section>
          {v.msg ? (
            <p role="alert" className="note" style={{ margin: "0", color: "#A33B2E" }}>
              {v.msg}
            </p>
          ) : null}
          <section className="card" aria-label="선택 어르신 후속관리">
            <div className="hd">
              <h2 className="h2" style={{ flex: "1 1 200px" }}>
                {v.selName}{" 어르신 · 후속관리"}
              </h2>
              <label className="note" style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                돌봄 상태
                <select className="inp" style={{ height: "36px", padding: "0 12px" }} aria-label="돌봄 상태" value={v.selStatus} onChange={v.setStatus}>
                  <option value="재방문 필요">
                    재방문 필요
                  </option>
                  <option value="후속조치 진행">
                    후속조치 진행
                  </option>
                  <option value="상담 완료">
                    상담 완료
                  </option>
                  <option value="서비스 종료">
                    서비스 종료
                  </option>
                </select>
              </label>
            </div>
            <div style={{ padding: "18px 22px 22px", display: "flex", flexDirection: "column", gap: "20px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <b style={{ fontSize: "15px" }}>
                  조치사항
                </b>
                {(v.acts || []).map((a, i_a) => (
                  <Fragment key={i_a}>
                    <label className="box" style={{ display: "flex", alignItems: "flex-start", gap: "10px", padding: "12px 14px", borderRadius: "12px", cursor: "pointer" }}>
                      <input type="checkbox" checked={a.done} onChange={a.toggle} style={{ marginTop: "4px", width: "18px", height: "18px", flex: "none" }} />
                      <span style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: "0" }}>
                        <span style={{  }}>
                          {a.text}
                        </span>
                        <span className="note">
                          {a.sub}
                        </span>
                      </span>
                    </label>
                    {a.hasTools ? (
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px", margin: "-4px 0 0 28px" }}>
                        {a.canDrop ? (
                          <button type="button" className="btn btn-sm btn-s" onClick={a.drop}>
                            취소
                          </button>
                        ) : null}
                        <button type="button" className="btn btn-sm btn-s" onClick={a.openNote}>
                          메모
                        </button>
                        {a.noteOpen ? (
                          <>
                            <input className="inp" type="text" placeholder="처리 메모" aria-label="처리 메모" value={a.note} onChange={a.setNote} style={{ flex: "1 1 180px", minWidth: "0", height: "34px" }} />
                            <button type="button" className="btn btn-sm btn-p" onClick={a.saveNote}>
                              저장
                            </button>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                  </Fragment>
                ))}
                {v.noActs ? (
                  <>
                    <p className="note" style={{ margin: "0" }}>
                      등록된 조치사항이 없어요
                    </p>
                  </>
                ) : null}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  <input className="inp" type="text" placeholder="조치사항 추가" aria-label="조치사항 추가" value={v.actText} onChange={v.setActText} style={{ flex: "1 1 180px", minWidth: "0", height: "38px" }} />
                  <input className="inp" type="date" aria-label="기한" value={v.actDue} onChange={v.setActDue} style={{ flex: "0 0 150px", height: "38px" }} />
                  <button type="button" className="btn btn-sm btn-p" onClick={v.addAct}>
                    추가
                  </button>
                </div>
              </div>
              <div className="box" style={{ padding: "14px 16px", borderRadius: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                <b style={{ fontSize: "15px" }}>
                  재방문 · 연락 일정
                </b>
                {(v.scheds || []).map((e, i_e) => (
                  <Fragment key={i_e}>
                    <span style={{ fontSize: "14px" }}>
                      {e.text}
                    </span>
                  </Fragment>
                ))}
                {v.noScheds ? (
                  <>
                    <span className="note">
                      예정된 일정 없음
                    </span>
                  </>
                ) : null}
                {v.notAdding ? (
                  <>
                    <div>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.openAdd}>
                        + 재방문 일정 등록
                      </button>
                    </div>
                  </>
                ) : null}
                {v.adding ? (
                  <>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", paddingTop: "4px" }}>
                      <input className="inp" type="date" aria-label="일정 날짜" value={v.sDate} onChange={v.setSDate} style={{ flex: "0 0 150px", height: "36px" }} />
                      <input className="inp" type="time" aria-label="일정 시간" value={v.sTime} onChange={v.setSTime} style={{ flex: "0 0 120px", height: "36px" }} />
                      <select className="inp" aria-label="일정 유형" value={v.sType} onChange={v.setSType} style={{ flex: "0 0 110px", height: "36px", padding: "0 12px" }}>
                        <option value="방문">
                          방문
                        </option>
                        <option value="전화">
                          전화
                        </option>
                        <option value="재방문">
                          재방문
                        </option>
                      </select>
                      <input className="inp" type="text" placeholder="메모" aria-label="일정 메모" value={v.sMemo} onChange={v.setSMemo} style={{ flex: "1 1 140px", minWidth: "0", height: "36px" }} />
                      <button type="button" className="btn btn-sm btn-p" onClick={v.saveSched}>
                        저장
                      </button>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.closeAdd}>
                        취소
                      </button>
                    </div>
                  </>
                ) : null}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <b style={{ fontSize: "15px" }}>
                  전문기관 연계 기록
                </b>
                {(v.links || []).map((l, i_l) => (
                  <Fragment key={i_l}>
                    <span style={{ fontSize: "14px" }}>
                      {"· "}{l.text}
                    </span>
                  </Fragment>
                ))}
                {v.noLinks ? (
                  <>
                    <span className="note">
                      없음
                    </span>
                  </>
                ) : null}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  <input className="inp" type="text" placeholder="예: 치매안심센터 상담 의뢰 (11/18)" aria-label="전문기관 연계 기록" value={v.linkText} onChange={v.setLinkText} style={{ flex: "1 1 200px", minWidth: "0", height: "38px" }} />
                  <button type="button" className="btn btn-sm btn-s" onClick={v.addLink}>
                    기록
                  </button>
                </div>
              </div>
            </div>
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
