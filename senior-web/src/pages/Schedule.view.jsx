// Schedule 화면 마크업 — tools/dc2jsx.py 가 디자인(Schedule.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './Schedule.css';

export default function View({ v }) {
  return (
    <div className="pg-Schedule">
      <div className={v.themeCls} style={{ minHeight: "1200px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            <a href="#/CaseList">
              사례 관리
            </a>
            <a className="on" href="#/Schedule">
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
        <main style={{ flex: "999 1 640px", minWidth: "0", padding: "30px 36px 56px", display: "flex", flexDirection: "column", gap: "18px" }}>
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 260px" }}>
              <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                일정
              </h1>
            </div>
          </header>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "18px", alignItems: "flex-start" }}>
            <section className="card" aria-label="월간 달력" style={{ flex: "3 1 620px", minWidth: "0", overflow: "hidden" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 14px", padding: "16px 18px" }}>
                <button type="button" className="mnav" aria-label="이전 달" onClick={v.prevMonth}>
                  ‹
                </button>
                <b style={{ fontSize: "20px", minWidth: "120px", textAlign: "center" }}>
                  {v.monthLabel}
                </b>
                <button type="button" className="mnav" aria-label="다음 달" onClick={v.nextMonth}>
                  ›
                </button>
                <button type="button" className="btn btn-s" style={{ minHeight: "38px" }} onClick={v.goToday}>
                  오늘
                </button>
                <div role="group" aria-label="일정 종류 보기" className="seg" style={{ marginLeft: "auto" }}>
                  <button type="button" className={v.fAllCls} onClick={v.showAll}>
                    전체
                  </button>
                  <button type="button" className={v.fCCls} onClick={v.showC}>
                    ● 상담
                  </button>
                  <button type="button" className={v.fPCls} onClick={v.showP}>
                    ■ 개인 · 기관
                  </button>
                  <button type="button" className={v.fICls} onClick={v.showI} style={{ color: "#A33B2E" }}>
                    ! 중요
                  </button>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7, minmax(0, 1fr))", background: "#F8FBFD" }}>
                <span className="dow">
                  일
                </span>
                <span className="dow">
                  월
                </span>
                <span className="dow">
                  화
                </span>
                <span className="dow">
                  수
                </span>
                <span className="dow">
                  목
                </span>
                <span className="dow">
                  금
                </span>
                <span className="dow">
                  토
                </span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7, minmax(0, 1fr))" }}>
                {(v.cells || []).map((c, i_c) => (
                  <Fragment key={i_c}>
                    <button type="button" className="cell" onClick={c.pick} aria-label={c.aria} style={{ background: c.bg, boxShadow: c.ring }}>
                      <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ width: "26px", height: "26px", borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: "13px", fontWeight: c.fw, background: c.numBg, color: c.numFg }}>
                          {c.num}
                        </span>
                        <span style={{ fontSize: "10px", color: "#66788A" }}>
                          {c.holiday}
                        </span>
                      </span>
                      {(c.pills || []).map((p, i_p) => (
                        <Fragment key={i_p}>
                          <span className="pill" onClick={p.open} title={p.tip} style={{ background: p.bg, color: p.fg, fontWeight: p.fw }}>
                            <span style={{ width: "7px", height: "7px", flex: "none", marginTop: "4px", borderRadius: p.radius, background: p.dot }} />
                            <span className="pl-tx">
                              {p.hasHead ? (
                                <>
                                  <span className="pl-head">
                                    <span className="pl-time">
                                      {p.time}
                                    </span>
                                    <b>
                                      {p.who}
                                    </b>
                                  </span>
                                </>
                              ) : null}
                              <span className="pl-ttl">
                                {p.body}
                              </span>
                            </span>
                          </span>
                        </Fragment>
                      ))}
                      <span style={{ fontSize: "11px", color: "#496887", paddingLeft: "4px" }}>
                        {c.more}
                      </span>
                    </button>
                  </Fragment>
                ))}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 20px", padding: "14px 18px", fontSize: "12px", color: "#55687A", borderTop: "1px solid #DDE6EC" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#66788A" }} />
                  {"상담 일정 "}{v.countC}건
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "10px", height: "10px", borderRadius: "2px", background: "#A0B0BB" }} />
                  {"개인 · 기관 일정 "}{v.countP}건
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", color: "#A33B2E", fontWeight: "500" }}>
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#A33B2E" }} />
                  {"중요 "}{v.countI}건
                </span>
              </div>
            </section>
            <aside className="card" aria-label="선택한 날 일정" style={{ flex: "1 1 320px", minWidth: "0", padding: "20px 22px", display: "flex", flexDirection: "column", gap: "14px" }}>
              {v.notAdding ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <div style={{ flex: "1" }}>
                      <div className="note">
                        선택한 날
                      </div>
                      <b style={{ fontSize: "19px" }}>
                        {v.selLabel}
                      </b>
                    </div>
                    <button type="button" className="btn btn-p" onClick={v.openAdd}>
                      + 일정 추가
                    </button>
                  </div>
                  <div>
                    {(v.dayEvents || []).map((e, i_e) => (
                      <Fragment key={i_e}>
                        <div className="ev ev-clk" role="button" tabIndex="0" aria-label={e.aria} onClick={e.open} onKeyDown={e.key}>
                          <span style={{ fontSize: "13px", color: "#55687A" }}>
                            {e.time}
                          </span>
                          <span style={{ marginTop: "5px", width: "12px", height: "12px", borderRadius: e.radius, background: e.dot }} />
                          <span style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                            <b style={{ fontWeight: e.fw, color: e.titleFg }}>
                              {e.title}
                            </b>
                            <span style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px" }}>
                              <span className="chip" style={{ background: e.tagBg, color: e.tagFg }}>
                                {e.tag}
                              </span>
                              <span className="note">
                                {e.sub}
                              </span>
                            </span>
                          </span>
                          <button type="button" className="impb" aria-pressed={e.impOn} onClick={e.toggleImp} style={{ background: e.impBg, color: e.impFg, borderColor: e.impBd }}>
                            {e.impLabel}
                          </button>
                        </div>
                      </Fragment>
                    ))}
                    {v.noEvents ? (
                      <>
                        <p className="note" style={{ margin: "8px 0" }}>
                          일정 없음
                        </p>
                      </>
                    ) : null}
                  </div>
                </>
              ) : null}
              {v.viewing ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <button type="button" className="btn btn-sm btn-s" onClick={v.vBack} aria-label="일정 목록으로 돌아가기">
                      ← 목록
                    </button>
                    <span className="note" style={{ marginLeft: "auto" }}>
                      {v.v.kind}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                    <span style={{ marginTop: "8px", width: "12px", height: "12px", flex: "none", borderRadius: v.v.radius, background: v.v.dot }} />
                    <b style={{ fontSize: "20px", lineHeight: "1.4", color: v.v.titleFg }}>
                      {v.v.title}
                    </b>
                  </div>
                  <div className="vd-box">
                    {(v.v.rows || []).map((r, i_r) => (
                      <Fragment key={i_r}>
                        <div className="vd-row">
                          <span className="vd-k">
                            {r.k}
                          </span>
                          <span className="vd-v">
                            {r.v}
                          </span>
                        </div>
                      </Fragment>
                    ))}
                  </div>
                  {v.v.isDl ? (
                    <>
                      <p className="note" style={{ margin: "0" }}>
                        처리 기한 일정은 최초접수 일정에 맞춰 자동으로 만들어져요. 날짜를 바꾸거나 지우려면 최초접수 일정에서 수정 · 삭제해 주세요.
                      </p>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "flex-end" }}>
                        <button type="button" className="btn btn-s" onClick={v.v.goBase}>
                          최초접수 일정 보기
                        </button>
                        <button type="button" className={`btn ${v.v.doneCls}`} onClick={v.v.toggleDone}>
                          {v.v.doneLabel}
                        </button>
                      </div>
                    </>
                  ) : null}
                  {v.v.canEdit ? (
                    <>
                      {v.v.noAsk ? (
                        <>
                          <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                            <button type="button" className="btn btn-p" onClick={v.v.edit}>
                              수정
                            </button>
                            <button type="button" className="btn btn-s vd-del" onClick={v.v.askDel}>
                              삭제
                            </button>
                          </div>
                        </>
                      ) : null}
                      {v.v.ask ? (
                        <>
                          <div className="vd-ask" role="alertdialog" aria-label="일정 삭제 확인">
                            <b>
                              이 일정을 삭제할까요?
                            </b>
                            <span className="note">
                              {v.v.askNote}
                            </span>
                            <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                              <button type="button" className="btn btn-s" onClick={v.v.cancelDel}>
                                취소
                              </button>
                              <button type="button" className="btn vd-del-go" onClick={v.v.del}>
                                삭제
                              </button>
                            </div>
                          </div>
                        </>
                      ) : null}
                    </>
                  ) : null}
                </>
              ) : null}
              {v.adding ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <b style={{ fontSize: "19px", flex: "1" }}>
                      {v.formTitle}
                    </b>
                    <span className="note">
                      {v.formDateLabel}
                    </span>
                  </div>
                  <div role="radiogroup" aria-label="일정 종류" style={{ display: "flex", gap: "8px" }}>
                    <button type="button" role="radio" aria-checked={v.isC} className="kind" onClick={v.kindC} style={{ borderColor: v.kcBorder, background: v.kcBg }}>
                      <b style={{ fontWeight: "700" }}>
                        ● 상담 일정
                      </b>
                    </button>
                    <button type="button" role="radio" aria-checked={v.isP} className="kind" onClick={v.kindP} style={{ borderColor: v.kpBorder, background: v.kpBg }}>
                      <b style={{ fontWeight: "700" }}>
                        ■ 개인 · 기관 일정
                      </b>
                    </button>
                  </div>
                  {v.isC ? (
                    <>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="lb">
                          어르신 (사례)
                        </span>
                        <select className="in" value={v.form.child} onChange={v.setChild}>
                          <option>
                            김순자 님
                          </option>
                          <option>
                            서복례 님
                          </option>
                          <option>
                            오금자 님
                          </option>
                          <option>
                            이정희 님
                          </option>
                          <option>
                            윤기철 님
                          </option>
                          <option>
                            최만석 님
                          </option>
                          <option>
                            강덕수 님
                          </option>
                          <option>
                            한옥분 님
                          </option>
                          <option>
                            정말순 님
                          </option>
                          <option>
                            박영수 님
                          </option>
                        </select>
                      </label>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="lb">
                          상담 유형
                        </span>
                        <select className="in" value={v.form.ctype} onChange={v.setCtype}>
                          <option>
                            정기상담
                          </option>
                          <option>
                            초기상담
                          </option>
                          <option>
                            내방상담
                          </option>
                          <option>
                            방문상담
                          </option>
                          <option>
                            전화상담
                          </option>
                          <option>
                            가족 상담
                          </option>
                          <option>
                            종결 상담
                          </option>
                        </select>
                      </label>
                    </>
                  ) : null}
                  {v.isP ? (
                    <>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="lb">
                          분류
                        </span>
                        <select className="in" value={v.form.pcat} onChange={v.setPcat}>
                          <option>
                            기관 회의
                          </option>
                          <option>
                            사례회의
                          </option>
                          <option>
                            최초접수
                          </option>
                          <option>
                            슈퍼비전
                          </option>
                          <option>
                            복지관 프로그램 연계
                          </option>
                          <option>
                            교육
                          </option>
                          <option>
                            외근
                          </option>
                          <option>
                            휴가
                          </option>
                          <option>
                            기타
                          </option>
                        </select>
                      </label>
                      {v.isIntake ? (
                        <>
                          <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                            <span className="lb">
                              어르신 (사례)
                            </span>
                            <select className="in" value={v.form.child} onChange={v.setChild}>
                              <option>
                                김순자 님
                              </option>
                              <option>
                                서복례 님
                              </option>
                              <option>
                                오금자 님
                              </option>
                              <option>
                                이정희 님
                              </option>
                              <option>
                                윤기철 님
                              </option>
                              <option>
                                최만석 님
                              </option>
                              <option>
                                강덕수 님
                              </option>
                              <option>
                                한옥분 님
                              </option>
                              <option>
                                정말순 님
                              </option>
                              <option>
                                박영수 님
                              </option>
                            </select>
                          </label>
                          <div className="dl-box">
                            <b style={{ fontSize: "13px" }}>
                              의뢰 접수 후 처리 기한 · 자동 추가
                            </b>
                            {(v.dlPreview || []).map((p, i_p) => (
                              <Fragment key={i_p}>
                                <div className="dl-row">
                                  <span className="dl-n">
                                    {p.n}
                                  </span>
                                  <span style={{ flex: "1" }}>
                                    {p.task}
                                  </span>
                                  <span className="note">
                                    {p.due}까지
                                  </span>
                                </div>
                              </Fragment>
                            ))}
                            <span className="note">
                              저장하면 기한 일정이 달력에 표시되고 알림에 추가돼요.
                            </span>
                          </div>
                        </>
                      ) : null}
                      {v.notIntake ? (
                        <>
                          <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                            <span className="lb">
                              제목
                            </span>
                            <input className="in" type="text" placeholder="예) 팀 회의" value={v.form.title} onChange={v.setTitle} />
                          </label>
                        </>
                      ) : null}
                    </>
                  ) : null}
                  {v.isEdit ? (
                    <>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="lb">
                          날짜
                        </span>
                        <input className="in" type="date" value={v.form.date} onChange={v.setDate} />
                      </label>
                    </>
                  ) : null}
                  <div style={{ display: "flex", gap: "10px" }}>
                    <label style={{ flex: "1", display: "flex", flexDirection: "column", gap: "6px" }}>
                      <span className="lb">
                        시간
                      </span>
                      <input className="in" type="time" value={v.form.time} onChange={v.setTime} />
                    </label>
                    <label style={{ flex: "1.4", display: "flex", flexDirection: "column", gap: "6px" }}>
                      <span className="lb">
                        장소
                      </span>
                      <input className="in" type="text" placeholder="예) 상담실 A" value={v.form.place} onChange={v.setPlace} />
                    </label>
                  </div>
                  {v.isC ? (
                    <>
                      <div style={{ padding: "12px 14px", borderRadius: "12px", background: "#F8FBFD", fontSize: "13px", display: "flex", flexDirection: "column", gap: "6px" }}>
                        <label style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                          <input type="checkbox" defaultChecked="" style={{ width: "16px", height: "16px", accentColor: "#1F3A56" }} />
                          {"상담 전날 "}
                          <a href="#/CaseInfo?sec=brief">
                            브리핑
                          </a>
                          {" 자동 준비"}
                        </label>
                        <span className="note">
                          어르신 안부 앱에 큰 글씨로 일정 안내 · 가족 안내는 어르신 동의 범위 안에서만
                        </span>
                      </div>
                    </>
                  ) : null}
                  {v.isP ? (
                    <>
                      <div style={{ padding: "12px 14px", borderRadius: "12px", background: "#F8FBFD", fontSize: "13px" }}>
                        <label style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                          <input type="checkbox" style={{ width: "16px", height: "16px", accentColor: "#1F3A56" }} />
                          팀 일정으로 공유
                        </label>
                      </div>
                    </>
                  ) : null}
                  <button type="button" role="switch" aria-checked={v.formImpOn} onClick={v.toggleFormImp} style={{ display: "flex", alignItems: "center", gap: "10px", minHeight: "46px", padding: "0 14px", borderRadius: "12px", border: `1.5px solid ${v.formImpBd}`, background: v.formImpBg, color: v.formImpFg, font: "inherit", fontSize: "14px", fontWeight: "700", cursor: "pointer", textAlign: "left" }}>
                    <span style={{ width: "18px", height: "18px", borderRadius: "5px", border: `1.5px solid ${v.formImpBd}`, background: v.formImpBox, color: "#FFFFFF", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: "12px" }}>
                      {v.formImpMark}
                    </span>
                    중요 일정 (빨간색 표시)
                  </button>
                  <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                    <button type="button" className="btn btn-s" onClick={v.cancelAdd}>
                      취소
                    </button>
                    <button type="button" className="btn btn-p" onClick={v.save}>
                      저장
                    </button>
                  </div>
                </>
              ) : null}
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}
