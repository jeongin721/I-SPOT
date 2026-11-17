// Stats 화면 마크업 — tools/dc2jsx.py 가 디자인(Stats.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './Stats.css';

export default function View({ v }) {
  return (
    <div className="pg-Stats">
      <div className={v.themeCls} style={{ minHeight: "1990px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
                {v.navLinkCnt}
              </span>
            </a>
            <a href="#/Followup">
              후속관리
              <span className="cnt">
                {v.navFollowCnt}
              </span>
            </a>
            <a href="#/DocBox">
              문서함
            </a>
            <a href="#/LawGuide">
              법령 · 매뉴얼
            </a>
            <a className="on" href="#/Stats">
              통계
            </a>
            <a href="#/Overview" style={{ minHeight: "34px", paddingLeft: "46px", fontSize: "13px" }}>
              관리자 현황
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 300px" }}>
              <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                통계
              </h1>
            </div>
          </header>
          <section className="card" aria-label="기간 선택" style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 14px" }}>
              <div role="group" aria-label="빠른 기간" className="seg">
                {(v.presets || []).map((p, i_p) => (
                  <Fragment key={i_p}>
                    <button type="button" className={p.cls} onClick={p.pick}>
                      {p.label}
                    </button>
                  </Fragment>
                ))}
              </div>
              <label style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <span className="note">
                  시작
                </span>
                <span className="dpw st">
                  <input className="inp dpi" type="text" inputMode="numeric" placeholder="YYYY-MM-DD" maxLength="10" value={v.from} onChange={v.setFrom} aria-label="시작일" />
                  <button type="button" className="dp-btn" aria-label="시작일 달력 열기" aria-expanded={v.dp.from.exp} onClick={v.dp.from.toggle}>
                    <svg viewBox={"0 0 24 24"} width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="3" y="5" width="18" height="16" rx="2" />
                      <path d="M16 3v4M8 3v4M3 10h18" />
                    </svg>
                  </button>
                  {v.dp.from.open ? (
                    <>
                      <span className="dp-bd" onClick={v.dp.from.close} />
                      <span className="dp-pop" role="dialog" aria-label="시작일 선택">
                        {v.dp.from.isY ? (
                          <>
                            <span className="dp-hd">
                              <b>
                                연도 선택
                              </b>
                            </span>
                            <span className="dp-years" id={v.dp.from.listId}>
                              {(v.dp.from.years || []).map((o, i_o) => (
                                <Fragment key={i_o}>
                                  <button type="button" className={`dp-y ${o.cls}`} id={o.id} aria-pressed={o.on} onClick={o.pick}>
                                    {o.label}
                                  </button>
                                </Fragment>
                              ))}
                            </span>
                          </>
                        ) : null}
                        {v.dp.from.isM ? (
                          <>
                            <span className="dp-hd">
                              <button type="button" className="dp-nav" aria-label="연도 선택으로" onClick={v.dp.from.toY}>
                                ←
                              </button>
                              <b>
                                {v.dp.from.yLabel}
                              </b>
                            </span>
                            <span className="dp-months">
                              {(v.dp.from.months || []).map((o, i_o) => (
                                <Fragment key={i_o}>
                                  <button type="button" className={`dp-m ${o.cls}`} disabled={o.dis} onClick={o.pick}>
                                    {o.label}
                                  </button>
                                </Fragment>
                              ))}
                            </span>
                          </>
                        ) : null}
                        {v.dp.from.isD ? (
                          <>
                            <span className="dp-hd">
                              <button type="button" className="dp-nav" aria-label="월 선택으로" onClick={v.dp.from.toM}>
                                ←
                              </button>
                              <b>
                                {v.dp.from.ymLabel}
                              </b>
                              <span style={{ marginLeft: "auto", display: "inline-flex", gap: "6px" }}>
                                <button type="button" className="dp-nav" aria-label="이전 달" disabled={v.dp.from.prevDis} onClick={v.dp.from.prev}>
                                  ‹
                                </button>
                                <button type="button" className="dp-nav" aria-label="다음 달" disabled={v.dp.from.nextDis} onClick={v.dp.from.next}>
                                  ›
                                </button>
                              </span>
                            </span>
                            <span className="dp-days">
                              {(v.dp.from.dows || []).map((w, i_w) => (
                                <Fragment key={i_w}>
                                  <span className="dp-dow">
                                    {w}
                                  </span>
                                </Fragment>
                              ))}
                              {(v.dp.from.days || []).map((o, i_o) => (
                                <Fragment key={i_o}>
                                  {o.blank ? (
                                    <>
                                      <span />
                                    </>
                                  ) : null}
                                  {o.real ? (
                                    <>
                                      <button type="button" className={`dp-d ${o.cls}`} disabled={o.dis} aria-label={o.aria} onClick={o.pick}>
                                        {o.n}
                                      </button>
                                    </>
                                  ) : null}
                                </Fragment>
                              ))}
                            </span>
                          </>
                        ) : null}
                      </span>
                    </>
                  ) : null}
                </span>
              </label>
              <span className="note">
                ~
              </span>
              <label style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <span className="note">
                  종료
                </span>
                <span className="dpw st">
                  <input className="inp dpi" type="text" inputMode="numeric" placeholder="YYYY-MM-DD" maxLength="10" value={v.to} onChange={v.setTo} aria-label="종료일" />
                  <button type="button" className="dp-btn" aria-label="종료일 달력 열기" aria-expanded={v.dp.to.exp} onClick={v.dp.to.toggle}>
                    <svg viewBox={"0 0 24 24"} width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="3" y="5" width="18" height="16" rx="2" />
                      <path d="M16 3v4M8 3v4M3 10h18" />
                    </svg>
                  </button>
                  {v.dp.to.open ? (
                    <>
                      <span className="dp-bd" onClick={v.dp.to.close} />
                      <span className="dp-pop" role="dialog" aria-label="종료일 선택">
                        {v.dp.to.isY ? (
                          <>
                            <span className="dp-hd">
                              <b>
                                연도 선택
                              </b>
                            </span>
                            <span className="dp-years" id={v.dp.to.listId}>
                              {(v.dp.to.years || []).map((o, i_o) => (
                                <Fragment key={i_o}>
                                  <button type="button" className={`dp-y ${o.cls}`} id={o.id} aria-pressed={o.on} onClick={o.pick}>
                                    {o.label}
                                  </button>
                                </Fragment>
                              ))}
                            </span>
                          </>
                        ) : null}
                        {v.dp.to.isM ? (
                          <>
                            <span className="dp-hd">
                              <button type="button" className="dp-nav" aria-label="연도 선택으로" onClick={v.dp.to.toY}>
                                ←
                              </button>
                              <b>
                                {v.dp.to.yLabel}
                              </b>
                            </span>
                            <span className="dp-months">
                              {(v.dp.to.months || []).map((o, i_o) => (
                                <Fragment key={i_o}>
                                  <button type="button" className={`dp-m ${o.cls}`} disabled={o.dis} onClick={o.pick}>
                                    {o.label}
                                  </button>
                                </Fragment>
                              ))}
                            </span>
                          </>
                        ) : null}
                        {v.dp.to.isD ? (
                          <>
                            <span className="dp-hd">
                              <button type="button" className="dp-nav" aria-label="월 선택으로" onClick={v.dp.to.toM}>
                                ←
                              </button>
                              <b>
                                {v.dp.to.ymLabel}
                              </b>
                              <span style={{ marginLeft: "auto", display: "inline-flex", gap: "6px" }}>
                                <button type="button" className="dp-nav" aria-label="이전 달" disabled={v.dp.to.prevDis} onClick={v.dp.to.prev}>
                                  ‹
                                </button>
                                <button type="button" className="dp-nav" aria-label="다음 달" disabled={v.dp.to.nextDis} onClick={v.dp.to.next}>
                                  ›
                                </button>
                              </span>
                            </span>
                            <span className="dp-days">
                              {(v.dp.to.dows || []).map((w, i_w) => (
                                <Fragment key={i_w}>
                                  <span className="dp-dow">
                                    {w}
                                  </span>
                                </Fragment>
                              ))}
                              {(v.dp.to.days || []).map((o, i_o) => (
                                <Fragment key={i_o}>
                                  {o.blank ? (
                                    <>
                                      <span />
                                    </>
                                  ) : null}
                                  {o.real ? (
                                    <>
                                      <button type="button" className={`dp-d ${o.cls}`} disabled={o.dis} aria-label={o.aria} onClick={o.pick}>
                                        {o.n}
                                      </button>
                                    </>
                                  ) : null}
                                </Fragment>
                              ))}
                            </span>
                          </>
                        ) : null}
                      </span>
                    </>
                  ) : null}
                </span>
              </label>
              <button type="button" className={`btn btn-sm ${v.calCls}`} onClick={v.toggleCal}>
                달력
              </button>
              <span className="brn" style={{ marginLeft: "auto", fontWeight: "700" }}>
                {v.rangeLabel}
              </span>
            </div>
            {v.showCal ? (
              <>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "24px", paddingTop: "6px", borderTop: "1px solid #DDE6EC" }}>
                  <div style={{ flex: "0 1 320px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.calPrev} aria-label="이전 달">
                        ‹
                      </button>
                      <b style={{ flex: "1", textAlign: "center" }}>
                        {v.calLabel}
                      </b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.calNext} aria-label="다음 달">
                        ›
                      </button>
                    </div>
                    <div className="cal note" style={{ textAlign: "center", marginBottom: "2px" }}>
                      <span>
                        일
                      </span>
                      <span>
                        월
                      </span>
                      <span>
                        화
                      </span>
                      <span>
                        수
                      </span>
                      <span>
                        목
                      </span>
                      <span>
                        금
                      </span>
                      <span>
                        토
                      </span>
                    </div>
                    <div className="cal">
                      {(v.cal || []).map((d, i_d) => (
                        <Fragment key={i_d}>
                          <button type="button" onClick={d.pick} disabled={d.off} aria-label={d.aria} style={{ background: d.bg, color: d.fg, fontWeight: d.fw }}>
                            {d.n}
                          </button>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                  <p className="note" style={{ flex: "1 1 220px", margin: "0", alignSelf: "center" }}>
                    {v.pickHint}
                  </p>
                </div>
              </>
            ) : null}
          </section>
          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }}>
            <div className="card kpi">
              <div className="sub">
                상담 접수
              </div>
              <b className="brn">
                {v.k.total}건
              </b>
              <div className="note">
                {"하루 평균 "}{v.k.perDay}건
              </div>
            </div>
            <div className="card kpi">
              <div className="sub">
                사례관리 진행
              </div>
              <b className="brn">
                {v.k.judged}건
              </b>
              <div className="note">
                {"접수 중 "}{v.k.judgedPct}
              </div>
            </div>
            <div className="card kpi">
              <div className="sub">
                재의뢰 사례
              </div>
              <b className="brn">
                {v.k.repeat}건
              </b>
            </div>
            <div className="card kpi">
              <div className="sub">
                연계 · 서비스
              </div>
              <b className="brn">
                {v.k.services}회
              </b>
              <div className="note">
                {"완료율 "}{v.k.donePct}
              </div>
            </div>
          </section>
          <section className="card" aria-label="상담 접수" style={{ padding: "20px 22px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
              <h2 className="h2">
                상담 접수 추이
              </h2>
              <span className="note">
                {v.binLabel}
              </span>
            </div>
            <div className="vb" style={{ marginTop: "14px" }} role="img" aria-label={v.trendAria}>
              {(v.trend || []).map((t, i_t) => (
                <Fragment key={i_t}>
                  <div className="col" title={t.tip}>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {t.v}
                    </span>
                    <span className="b" style={{ height: t.h }} />
                  </div>
                </Fragment>
              ))}
            </div>
            <div style={{ display: "flex", gap: "8px", padding: "6px 4px 0" }}>
              {(v.trend || []).map((t, i_t) => (
                <Fragment key={i_t}>
                  <span className="note" style={{ flex: "1", minWidth: "0", textAlign: "center", overflow: "hidden", whiteSpace: "nowrap" }}>
                    {t.label}
                  </span>
                </Fragment>
              ))}
            </div>
          </section>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "18px" }}>
            <section className="card" aria-label="주호소 유형별 사례 수" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <h2 className="h2">
                주호소 유형별 사례 수
              </h2>
              {(v.types || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{"건 · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
              <h2 className="h2" style={{ marginTop: "8px" }}>
                위기도별 사례 수
              </h2>
              {(v.risks || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb" title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{"건 · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>
            <section className="card" aria-label="어르신 연령대 비율" style={{ padding: "20px 22px" }}>
              <h2 className="h2">
                내담 어르신 연령대 비율
              </h2>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "22px", marginTop: "12px" }}>
                <svg viewBox={"0 0 200 200"} width="190" height="190" role="img" aria-label={v.ageAria}>
                  {(v.ages || []).map((a, i_a) => (
                    <Fragment key={i_a}>
                      <path d={a.d} fill={a.c} stroke="#FFFFFF" strokeWidth="2">
                        <title>
                          {a.tip}
                        </title>
                      </path>
                    </Fragment>
                  ))}
                  <circle cx="100" cy="100" r="52" fill="#FFFFFF" />
                  <text x="100" y="96" textAnchor="middle" fontSize="13" fill="#66788A">
                    내담 어르신
                  </text>
                  <text x="100" y="118" textAnchor="middle" fontSize="20" fontWeight="700" fill="#1F3A56">
                    {v.k.judged}명
                  </text>
                </svg>
                <div style={{ flex: "1 1 160px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  {(v.ages || []).map((a, i_a) => (
                    <Fragment key={i_a}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px" }}>
                        <span style={{ width: "12px", height: "12px", borderRadius: "3px", background: a.c, flex: "none" }} />
                        <span style={{ flex: "1" }}>
                          {a.name}
                        </span>
                        <b>
                          {a.p}
                        </b>
                        <span className="note" style={{ width: "44px", textAlign: "right" }}>
                          {a.v}명
                        </span>
                      </div>
                    </Fragment>
                  ))}
                </div>
              </div>
            </section>
          </div>
          <section className="card" aria-label="가구형태 · 의뢰 경로" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                가구형태 · 의뢰 경로
              </h2>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl" style={{ minWidth: "700px" }}>
                <thead>
                  <tr>
                    <th>
                      가구형태
                    </th>
                    <th>
                      건수
                    </th>
                    <th style={{ width: "26%" }}>
                      비율
                    </th>
                    <th>
                      가장 많은 의뢰 경로
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.actors || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td>
                          <b style={{ fontWeight: "500" }}>
                            {r.name}
                          </b>
                        </td>
                        <td>
                          {r.v}건
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span className="mini" style={{ flex: "1" }}>
                              <span style={{ width: r.w }} />
                            </span>
                            <span className="note" style={{ width: "44px" }}>
                              {r.p}
                            </span>
                          </div>
                        </td>
                        <td>
                          {r.top}
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card" aria-label="지역별 통계" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                지역별 통계
              </h2>
              <span className="note">
                어르신 거주 구 기준 · 주 돌봄 가족이 다른 기관 관할에 살면 두 기관이 공동사례관리
              </span>
              <span className="note" style={{ marginLeft: "auto" }}>
                {v.rgSum}
              </span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl" style={{ minWidth: "760px" }}>
                <thead>
                  <tr>
                    <th>
                      어르신 거주 지역
                    </th>
                    <th>
                      관할 기관
                    </th>
                    <th>
                      사례 수
                    </th>
                    <th style={{ width: "22%" }}>
                      비율
                    </th>
                    <th>
                      가족 타 지역 거주
                    </th>
                    <th>
                      공동사례관리
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.regions || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td>
                          <b style={{ fontWeight: "500" }}>
                            {r.name}
                          </b>
                        </td>
                        <td className="note">
                          {r.org}
                        </td>
                        <td>
                          {r.v}건
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span className="mini" style={{ flex: "1" }}>
                              <span style={{ width: r.w }} />
                            </span>
                            <span className="note" style={{ width: "44px" }}>
                              {r.p}
                            </span>
                          </div>
                        </td>
                        <td>
                          {r.away}건
                        </td>
                        <td>
                          <b className="brn">
                            {r.joint}건
                          </b>
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ padding: "16px 22px 20px", borderTop: "1px solid #DDE6EC", display: "flex", flexDirection: "column", gap: "10px" }}>
              <b style={{ fontSize: "14px" }}>
                공동사례관리 현황
              </b>
              {(v.joints || []).map((j, i_j) => (
                <Fragment key={i_j}>
                  <div className="rg-pair">
                    <span>
                      <b style={{ fontWeight: "500" }}>
                        어르신
                      </b>
                      {" "}{j.cg}{" · "}{j.co}
                    </span>
                    <span className="note" aria-hidden="true">
                      ↔
                    </span>
                    <span>
                      <b style={{ fontWeight: "500" }}>
                        가족
                      </b>
                      {" "}{j.pg}{" · "}{j.po}
                    </span>
                    <b className="brn" style={{ marginLeft: "auto" }}>
                      {j.v}건
                    </b>
                  </div>
                </Fragment>
              ))}
              {v.noJoint ? (
                <>
                  <span className="note">
                    {v.noJointText}
                  </span>
                </>
              ) : null}
            </div>
          </section>
          <section className="card" aria-label="사례관리 기간" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                사례관리 기간
              </h2>
              <span className="note">
                {v.mgAsOf}{" 기준 관리 중 사례"}
              </span>
              <label className="rg-std">
                <span>
                  1인당 적정 사례 수
                </span>
                <input className="inp" type="number" min="1" max="99" value={v.mgStd} onChange={v.setMgStd} aria-label="1인당 적정 사례 수" />
                <span>
                  건
                </span>
              </label>
            </div>
            <div style={{ padding: "18px 22px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "12px" }}>
              {(v.mgKpi || []).map((m, i_m) => (
                <Fragment key={i_m}>
                  <div className="rg-kpi">
                    <div className="sub">
                      {m.label}
                    </div>
                    <b className="brn" style={{ fontSize: "24px" }}>
                      {m.v}
                    </b>
                    <div className="note">
                      {m.note}
                    </div>
                  </div>
                </Fragment>
              ))}
            </div>
            <div style={{ padding: "0 22px 18px", display: "flex", flexDirection: "column", gap: "10px" }}>
              {(v.mgBins || []).map((g, i_g) => (
                <Fragment key={i_g}>
                  <div className="hb" style={{ gridTemplateColumns: "110px 1fr 96px" }} title={g.tip}>
                    <span>
                      {g.name}
                    </span>
                    <span className="track">
                      <span style={{ width: g.w }} />
                    </span>
                    <span className="note" style={{ color: "#1F3A56" }}>
                      {g.v}{"건 · "}{g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </div>
            <div style={{ overflowX: "auto", borderTop: "1px solid #DDE6EC" }}>
              <table className="tbl" style={{ minWidth: "720px" }}>
                <thead>
                  <tr>
                    <th>
                      상담사
                    </th>
                    <th>
                      관리 중
                    </th>
                    <th style={{ width: "26%" }}>
                      적정 사례 수 대비
                    </th>
                    <th>
                      6개월 이상
                    </th>
                    <th>
                      1년 이상
                    </th>
                    <th>
                      평균 기간
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.mgStaff || []).map((r, i_r) => (
                    <Fragment key={i_r}>
                      <tr>
                        <td>
                          <b style={{ fontWeight: "500" }}>
                            {r.name}
                          </b>
                        </td>
                        <td>
                          {r.v}건
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span className="mini" style={{ flex: "1" }}>
                              <span style={{ width: r.w, background: r.bar }} />
                            </span>
                            <span className={`chip ${r.cls}`} style={{ height: "22px", fontSize: "11.5px" }}>
                              {r.state}
                            </span>
                          </div>
                        </td>
                        <td>
                          {r.m6}건
                        </td>
                        <td>
                          {r.y1}건
                        </td>
                        <td>
                          {r.avg}
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "18px" }}>
            <section className="card" aria-label="연계 기관별 현황" style={{ padding: "20px 22px" }}>
              <h2 className="h2">
                연계 기관별 현황
              </h2>
              <div className="vb" style={{ marginTop: "14px", height: "200px" }} role="img" aria-label={v.svcAria}>
                {(v.svc || []).map((t, i_t) => (
                  <Fragment key={i_t}>
                    <div className="col" title={t.tip}>
                      <span className="note" style={{ color: "#1F3A56" }}>
                        {t.v}
                      </span>
                      <span className="b" style={{ height: t.h }} />
                    </div>
                  </Fragment>
                ))}
              </div>
              <div style={{ display: "flex", gap: "8px", padding: "6px 4px 0" }}>
                {(v.svc || []).map((t, i_t) => (
                  <Fragment key={i_t}>
                    <span className="note" style={{ flex: "1", minWidth: "0", textAlign: "center", lineHeight: "1.3" }}>
                      {t.label}
                    </span>
                  </Fragment>
                ))}
              </div>
            </section>
            <section className="card" aria-label="연계 진행 표" style={{ overflow: "hidden" }}>
              <div className="hd">
                <h2 className="h2">
                  연계 진행 상태
                </h2>
              </div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>
                      연계 기관
                    </th>
                    <th>
                      대상
                    </th>
                    <th>
                      완료
                    </th>
                    <th>
                      진행 중
                    </th>
                    <th>
                      완료율
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(v.svc || []).map((t, i_t) => (
                    <Fragment key={i_t}>
                      <tr>
                        <td>
                          {t.label}
                        </td>
                        <td className="note">
                          {t.target}
                        </td>
                        <td>
                          {t.done}
                        </td>
                        <td>
                          {t.ing}
                        </td>
                        <td>
                          <b className="brn">
                            {t.rate}
                          </b>
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
          <section className="card" aria-label="AI 분석" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h2 className="h2">
                AI가 본 이 기간
              </h2>
              <span className="chip c-ai">
                AI 초안
              </span>
            </div>
            {(v.insights || []).map((t, i_t) => (
              <Fragment key={i_t}>
                <div style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#C5D4DE", marginTop: "8px", flex: "none" }} />
                  <span>
                    {t}
                  </span>
                </div>
              </Fragment>
            ))}
          </section>
          <p className="ainote">
            AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
          </p>
        </main>
      </div>
    </div>
  );
}
