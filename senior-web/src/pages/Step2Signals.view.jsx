// Step2Signals 화면 마크업 — tools/dc2jsx.py 가 디자인(Step2Signals.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './Step2Signals.css';

export default function View({ v }) {
  return (
    <div className="pg-Step2Signals">
      <div className={v.themeCls} style={{ minHeight: "1900px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
              사례 관리
            </a>
            {" › "}
            <a href={v.caseHref}>
              {v.caseCrumb}
            </a>
            {" › "}
            <a href={v.historyHref}>
              상담 이력
            </a>
            {" › "}
            <a href={v.detailHref}>
              {v.sesNo}
            </a>
          </nav>
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 280px" }}>
              <div className="sub">
                {v.sesSub}
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
            <a className="stp on" href={v.step2Href} aria-current="step">
              <span className="sn">
                2
              </span>
              <b style={{ fontWeight: "700" }}>
                정서·위기 신호 확인
              </b>
            </a>
            <a className="stp" href={v.step3Href}>
              <span className="sn">
                3
              </span>
              <b style={{ fontWeight: "500" }}>
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
          {v.hasStatus ? (
            <p role="alert" className="note" style={{ margin: "0" }}>
              {v.statusMsg}
            </p>
          ) : null}
          <section className="card" aria-label="위기도" style={{ padding: "22px 24px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "18px 28px" }}>
            <div style={{ flex: "1 1 280px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span className="chip c-ai">
                  AI 제안
                </span>
                <span className="note">
                  위기도 · 확인 제안일 뿐 판단이 아니에요
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "10px", marginTop: "4px" }}>
                <b style={{ fontSize: "30px", color: "#A33B2E" }}>
                  {v.aiLevel}
                </b>
                <span style={{ fontSize: "14px" }}>
                  {v.flagLine}
                </span>
                <span className="note">
                  {v.trendNote}
                </span>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <span className="note">
                상담사 판단
              </span>
              <div style={{ display: "flex", gap: "6px" }} role="radiogroup" aria-label="상담사 위기도">
                {(v.levels || []).map((l, i_l) => (
                  <Fragment key={i_l}>
                    <button type="button" role="radio" className="lvbtn" aria-checked={l.on} onClick={l.pick} style={{ background: l.bg, borderColor: l.bd, color: l.fg }}>
                      {l.label}
                    </button>
                  </Fragment>
                ))}
              </div>
              <span className="sub2">
                {v.decisionNote}
              </span>
            </div>
          </section>
          <section className="card" aria-label="신호별 우려 정도" style={{ overflow: "hidden" }}>
            <div className="hd">
              <h2 className="h2">
                {v.typesTitle}
              </h2>
              <span className="note">
                {v.typesNote}
              </span>
            </div>
            {(v.types || []).map((t, i_t) => (
              <Fragment key={i_t}>
                <div className="trow">
                  <div>
                    <b style={{ fontSize: "16px" }}>
                      {t.label}
                    </b>
                    <span style={{ display: "block", marginTop: "4px" }}>
                      <span className="chip" style={{ background: t.evBg, color: t.evFg }}>
                        {t.ev}
                      </span>
                    </span>
                    {t.flag ? (
                      <>
                        <span className="chip c-hi" style={{ marginTop: "6px" }}>
                          {t.flagText}
                        </span>
                      </>
                    ) : null}
                  </div>
                  <div>
                    <span className="note">
                      {t.colHead}
                    </span>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
                      <b style={{ fontSize: "22px" }}>
                        {t.sevText}
                      </b>
                      <span className="note">
                        {t.sevSuffix}
                      </span>
                      {t.fixed ? (
                        <>
                          <span className="chip c-normal" style={{ height: "20px", fontSize: "11px" }}>
                            상담사 수정
                          </span>
                        </>
                      ) : null}
                    </div>
                    <div className="meter">
                      {(t.boxes || []).map((b, i_b) => (
                        <Fragment key={i_b}>
                          <button type="button" aria-label={b.aria} onClick={b.pick} style={{ background: b.bg, color: b.fg, borderColor: b.bd }}>
                            {b.n}
                          </button>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                  <div style={{ minWidth: "0" }}>
                    <span className="note">
                      {t.col3Head}
                    </span>
                    <div style={{ fontSize: "14px", marginTop: "2px" }}>
                      {t.matched}
                    </div>
                    {(t.refs || []).map((r, i_r) => (
                      <Fragment key={i_r}>
                        <span className="sub2" style={{ display: "block", marginTop: "4px" }}>
                          {r}
                        </span>
                      </Fragment>
                    ))}
                    {t.open ? (
                      <>
                        <div style={{ marginTop: "10px", padding: "8px", borderRadius: "10px", background: "#F8FBFD" }}>
                          {(t.anchors || []).map((a, i_a) => (
                            <Fragment key={i_a}>
                              <div className="anchor" onClick={a.pick} style={{ background: a.bg, color: a.fg, fontWeight: a.fw }}>
                                <span>
                                  {a.n}
                                </span>
                                <span>
                                  {a.text}
                                </span>
                              </div>
                            </Fragment>
                          ))}
                        </div>
                      </>
                    ) : null}
                  </div>
                  <button type="button" className="btn btn-sm btn-s" onClick={t.toggle}>
                    {t.toggleLabel}
                  </button>
                </div>
              </Fragment>
            ))}
          </section>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "18px" }}>
            <section className="card" aria-label="회차별 추이" style={{ overflowX: "auto" }}>
              <div className="hd">
                <h2 className="h2">
                  회차별 추이
                </h2>
              </div>
              <table className="tbl mx">
                <thead>
                  <tr>
                    <th>
                      신호
                    </th>
                    <th>
                      {v.trH[0]}
                    </th>
                    <th>
                      {v.trH[1]}
                    </th>
                    <th>
                      {v.trH[2]}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      {v.trL[0]}
                    </td>
                    <td>
                      {v.trC[0][0]}
                    </td>
                    <td>
                      {v.trC[0][1]}
                    </td>
                    <td>
                      <b>
                        {v.trC[0][2]}
                      </b>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      {v.trL[1]}
                    </td>
                    <td className="note">
                      {v.trC[1][0]}
                    </td>
                    <td className="note">
                      {v.trC[1][1]}
                    </td>
                    <td className="note">
                      {v.trC[1][2]}
                    </td>
                  </tr>
                  <tr>
                    <td>
                      {v.trL[2]}
                    </td>
                    <td className="note">
                      {v.trC[2][0]}
                    </td>
                    <td>
                      {v.trC[2][1]}
                    </td>
                    <td>
                      <b>
                        {v.trC[2][2]}
                      </b>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      {v.trL[3]}
                    </td>
                    <td>
                      {v.trC[3][0]}
                    </td>
                    <td>
                      {v.trC[3][1]}
                    </td>
                    <td>
                      {v.trC[3][2]}
                    </td>
                  </tr>
                  <tr>
                    <td>
                      {v.trL[4]}
                    </td>
                    <td className="note">
                      {v.trC[4][0]}
                    </td>
                    <td className="note">
                      {v.trC[4][1]}
                    </td>
                    <td className="note">
                      {v.trC[4][2]}
                    </td>
                  </tr>
                  <tr>
                    <td>
                      위기도 (상담사)
                    </td>
                    <td>
                      {v.trLast[0]}
                    </td>
                    <td>
                      {v.trLast[1]}
                    </td>
                    <td>
                      <b>
                        {v.decisionShort}
                      </b>
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>
            <section className="card" aria-label="위기 확인 플래그와 위기 재발 요인" style={{ padding: "18px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <h2 className="h2">
                {v.flTitle}
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <div>
                  <span className="chip c-hi">
                    {v.fl[0].chip}
                  </span>
                  {v.fl[0].text}
                  <span className="sub2" style={{ display: "block" }}>
                    {v.fl[0].at}
                  </span>
                </div>
                <div>
                  <span className="chip c-hi">
                    {v.fl[1].chip}
                  </span>
                  {v.fl[1].text}
                  <span className="sub2" style={{ display: "block" }}>
                    {v.fl[1].at}
                  </span>
                </div>
                <div>
                  <span className="chip c-normal">
                    {v.fl[2].chip}
                  </span>
                  {v.fl[2].text}
                  <span className="sub2" style={{ display: "block" }}>
                    {v.fl[2].at}
                  </span>
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", paddingTop: "10px", borderTop: "1px solid #DDE6EC" }}>
                <span className="note" style={{ width: "100%" }}>
                  {v.rfNote}
                </span>
                <span className="chip c-normal">
                  {v.rf[0]}
                </span>
                <span className="chip c-normal">
                  {v.rf[1]}
                </span>
                <span className="chip c-sky" style={{ border: "1px solid #1F3A56", background: "#FFFFFF" }}>
                  {v.rf[2]}
                </span>
              </div>
            </section>
          </div>
          <section className="card" aria-label="상담사 확인 안내" style={{ padding: "18px 22px", display: "flex", flexDirection: "column", gap: "8px" }}>
            <h2 className="h2">
              상담사 확인 안내
            </h2>
            <div>
              <span className="chip c-ai">
                AI 제안
              </span>
              {" AI는 신호와 우려 정도를 제안할 뿐입니다. 위기도와 개입 여부는 상담사가 어르신 말씀을 직접 확인한 뒤 판단합니다."}
            </div>
            <div>
              <span className="chip c-hi">
                자살 생각
              </span>
              {" 죽음 · 자살 생각이 확인되면 먼저 S-04 자살위험 선별 체크를 하고, 109(자살예방상담) · 정신건강복지센터를 안내합니다. 즉각 위험이 있으면 119에 요청합니다."}
            </div>
            <div>
              <span className="chip c-normal">
                동의
              </span>
              {" 가족(보호자)에게는 어르신이 동의한 범위 안에서만 공유합니다. 단, 생명이 위급한 경우는 기관 지침을 따릅니다."}
            </div>
            <div>
              <span className="chip c-normal">
                보조 기능
              </span>
              {" 상담 중 학대 정황이 보이면 노인보호전문기관(1577-1389) 연계를 검토합니다(노인복지법상 의무 확인)."}
            </div>
          </section>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
            <a className="btn btn-s" href={v.step1Href}>
              ← 기록 확인 · 정서·위기 신호
            </a>
            <a className="btn btn-p" href={v.step3Href} onClick={v.save} style={{ marginLeft: "auto" }}>
              {v.saveLabel}
            </a>
          </div>
          <p className="ainote">
            AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
          </p>
        </main>
      </div>
    </div>
  );
}
