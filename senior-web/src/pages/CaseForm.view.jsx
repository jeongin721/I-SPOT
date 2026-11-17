// CaseForm 화면 마크업 — tools/dc2jsx.py 가 디자인(CaseForm.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './CaseForm.css';

export default function View({ v }) {
  return (
    <div className="pg-CaseForm">
      <div className={v.themeCls} style={{ minHeight: "1880px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
          <div>
            <a className="btn btn-sm btn-s" href="#/CaseList">
              ← 목록
            </a>
          </div>
          <nav aria-label="위치" className="note">
            <a href="#/CaseList">
              대상자 관리
            </a>
            {" › "}{v.crumb}
          </nav>
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px 18px" }}>
            <a className="btn btn-sm btn-s" href={v.docsHref} aria-label="문서함으로 돌아가기" title="문서함으로 돌아가기">
              ←
            </a>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  {v.name}
                </h1>
                <span className="sub">
                  {v.sub}
                </span>
                <span className={v.riskCls}>
                  {v.riskLabel}
                </span>
              </div>
              <div className="note">
                {v.headNote}
              </div>
            </div>
            <a className="btn btn-s" href={v.uploadHref} onClick={v.markBack}>
              ↑ 녹취 올리기
            </a>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <a href={v.infoHref}>
              내담자 정보
            </a>
            <a href={v.historyHref}>
              상담 이력
            </a>
            <a className="on" aria-current="page" href={v.docsHref}>
              문서함
            </a>
          </nav>
          <nav aria-label="위치" className="note" style={{ marginTop: "-8px" }}>
            <a href={v.docsHref}>
              문서함
            </a>
            {" › 기관 서식 작성"}
          </nav>
          {v.formNote ? (
            <p className="note" role="status" style={{ margin: "-8px 0 0" }}>
              {v.formNote}
            </p>
          ) : null}
          <div className="opt3" role="tablist" aria-label="서식 선택" style={{ flexWrap: "wrap", alignSelf: "flex-start" }}>
            {(v.tabs || []).map((t, i_t) => (
              <Fragment key={i_t}>
                <button type="button" role="tab" aria-selected={t.on} onClick={t.pick} style={{ background: t.bg, color: t.fg, fontWeight: t.fw, boxShadow: t.bd }}>
                  {t.label}
                </button>
              </Fragment>
            ))}
          </div>
          {v.tA ? (
            <>
              <section className="card" aria-label="욕구 · 자원 사정기록지" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "14px" }}>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                  <h2 className="h2">
                    욕구 · 자원 사정기록지
                  </h2>
                  <span className="note">
                    S-02 · 영역별 욕구 정도 (높음 · 보통 · 낮음)
                  </span>
                </div>
                {(v.safety || []).map((g, i_g) => (
                  <Fragment key={i_g}>
                    <div className="grp">
                      {g.name}
                    </div>
                    {(g.items || []).map((it, i_it) => (
                      <Fragment key={i_it}>
                        <div className="item">
                          <span>
                            {it.q}
                          </span>
                          <span className="opt3" role="group" aria-label={it.q}>
                            {(it.opts || []).map((o, i_o) => (
                              <Fragment key={i_o}>
                                <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}>
                                  {o.label}
                                </button>
                              </Fragment>
                            ))}
                          </span>
                          {it.hasEv ? (
                            <>
                              <span className="ev">
                                <span className="chip c-ai" style={{ height: "20px", fontSize: "11px" }}>
                                  {"AI 제안 · "}{it.ai}
                                </span>
                                {it.ev}
                              </span>
                            </>
                          ) : null}
                        </div>
                      </Fragment>
                    ))}
                  </Fragment>
                ))}
                <div className="grp">
                  강점 · 자원
                </div>
                <div className="item">
                  <span>
                    어려울 때 연락하고 의지할 수 있는 사람 (Key Person: 가족 · 이웃 · 생활지원사 등)
                  </span>
                  <span className="opt3">
                    {(v.keyOpts || []).map((o, i_o) => (
                      <Fragment key={i_o}>
                        <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}>
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  <span className="ev">
                    <span className="chip c-ai" style={{ height: "20px", fontSize: "11px" }}>
                      {v.keyAi}
                    </span>
                    {v.keyEv}
                  </span>
                </div>
                <div className="grp">
                  {"생활 안정감 점수 "}
                  <span className="note" style={{ fontWeight: "400" }}>
                    1–10점 · 요즘 지내시기가 어떤지
                  </span>
                </div>
                {(v.scoreRows || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <div className="item" style={{ gridTemplateColumns: "150px 110px minmax(0, 1fr)" }}>
                      <span>
                        {r.who}
                      </span>
                      <input className="inp" type="number" min="1" max="10" placeholder="( )점" aria-label={`${r.who} 생활 안정감 점수`} style={{ width: "100px" }} />
                      <input className="inp" type="text" placeholder="이유" aria-label={`${r.who} 이유`} style={{ width: "100%" }} />
                    </div>
                  </Fragment>
                ))}
                <div className="grp">
                  위기도 평가표
                </div>
                <div className="item" style={{ gridTemplateColumns: "1fr auto" }}>
                  <span>
                    {"위험요인 "}
                    <b className="brn">
                      {v.riskSum}점
                    </b>
                    {" / 보호요인 "}
                    <b className="brn">
                      {v.protSum}점
                    </b>
                    <span className="note">
                      {"· "}{v.filled}/43 입력
                    </span>
                  </span>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.goC}>
                    척도 열기
                  </button>
                </div>
                <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <b style={{ fontSize: "14px" }}>
                    담당 상담사 소견
                  </b>
                  <textarea className="ta2" placeholder="직접 작성" />
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
                        {v.maskEx}
                      </span>
                    </button>
                  </span>
                </label>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px" }}>
                  <b style={{ fontSize: "14px" }}>
                    위기도 판정
                  </b>
                  <span className="opt3">
                    {(v.resultOpts || []).map((o, i_o) => (
                      <Fragment key={i_o}>
                        <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}>
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  <span className="note">
                    상담사 종합 판단 · 본인 의사 존중
                  </span>
                </div>
              </section>
            </>
          ) : null}
          {v.tB ? (
            <>
              <section className="card" aria-label="사례관리 점검표" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "14px" }}>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                  <h2 className="h2">
                    사례관리 점검표 (시니어)
                  </h2>
                  <span className="note">
                    3개월마다 · 어르신 본인 의사 확인 포함
                  </span>
                </div>
                <div className="fhead">
                  <div>
                    <span className="k">
                      성명
                    </span>
                    <span className="v">
                      {v.fhName}
                    </span>
                  </div>
                  <div>
                    <span className="k">
                      담당 상담사
                    </span>
                    <span className="v">
                      {v.fhCounselor}
                    </span>
                  </div>
                  <div>
                    <span className="k">
                      생년월일
                    </span>
                    <span className="v">
                      {v.fhBirth}
                    </span>
                  </div>
                  <div>
                    <span className="k">
                      점검일/회차
                    </span>
                    <span className="v">
                      {v.fhDate}
                    </span>
                  </div>
                  <div>
                    <span className="k">
                      점검장소
                    </span>
                    <span className="v">
                      <input className="inp" type="text" defaultValue={v.fhPlace} aria-label="점검장소" style={{ height: "34px", width: "100%" }} />
                    </span>
                  </div>
                  <div>
                    <span className="k">
                      이전 점검일
                    </span>
                    <span className="v">
                      {v.fhPrev}
                    </span>
                  </div>
                </div>
                {(v.checks || []).map((c, i_c) => (
                  <Fragment key={i_c}>
                    <div className="item">
                      <span>
                        {c.q}
                      </span>
                      <span className="opt3" role="group" aria-label={c.q}>
                        {(c.opts || []).map((o, i_o) => (
                          <Fragment key={i_o}>
                            <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}>
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <span style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <b style={{ fontSize: "14px" }}>
                      담당 상담사 소견
                    </b>
                    <span className="chip c-ai" style={{ height: "20px", fontSize: "11px" }}>
                      {v.draftChip}
                    </span>
                  </span>
                  <textarea className="ta2" defaultValue={v.ckOpinion} />
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
                        {v.maskEx}
                      </span>
                    </button>
                  </span>
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <span style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <b style={{ fontSize: "14px" }}>
                      추후 계획
                    </b>
                    <span className="chip c-ai" style={{ height: "20px", fontSize: "11px" }}>
                      {v.draftChip}
                    </span>
                  </span>
                  <textarea className="ta2" defaultValue={v.ckPlan} />
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
                        {v.maskEx}
                      </span>
                    </button>
                  </span>
                </label>
              </section>
            </>
          ) : null}
          {v.tC ? (
            <>
              <section className="card" aria-label="위기도 평가표" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                  <h2 className="h2">
                    위기도 평가표
                  </h2>
                  <span className="note">
                    43문항 · 0~3점 · 위기도: 일반 · 관심 · 집중 · 위기
                  </span>
                </div>
                <div className="sumbar">
                  <div style={{ display: "flex", alignItems: "stretch", gap: "12px" }}>
                    <div className="sum" style={{ flex: "1", minWidth: "0" }}>
                      <div>
                        <div className="note">
                          위험요인 (1~21)
                        </div>
                        <b className="brn" style={{ fontSize: "24px" }}>
                          {v.riskSum}점
                        </b>
                        <span className="note">
                          {" / 63"}
                        </span>
                      </div>
                      <div>
                        <div className="note">
                          보호요인 (22~43)
                        </div>
                        <b className="brn" style={{ fontSize: "24px" }}>
                          {v.protSum}점
                        </b>
                        <span className="note">
                          {" / 66"}
                        </span>
                      </div>
                      <div>
                        <div className="note">
                          입력
                        </div>
                        <b style={{ fontSize: "24px" }}>
                          {v.filled}
                        </b>
                        <span className="note">
                          {" / 43 · 위기도 판정: 상담사"}
                        </span>
                      </div>
                    </div>
                    <a className="btn btn-s" href="#scale-risk" style={{ alignSelf: "center" }}>
                      수정
                    </a>
                  </div>
                  <div className="sc sc-head" aria-hidden="true">
                    <span />
                    <span />
                    <span className="opt3 opt3-head">
                      <span>
                        0점
                      </span>
                      <span>
                        1점
                      </span>
                      <span>
                        2점
                      </span>
                      <span>
                        3점
                      </span>
                    </span>
                  </div>
                </div>
                <p className="note" style={{ margin: "0" }}>
                  *점수는 참고용이며 위기도는 상담사가 종합 판단합니다. 2 · 3번(자살 생각 · 시도)에 해당하면 점수와 관계없이 S-04 자살위험 선별과 109 안내를 먼저 합니다.
                </p>
                {(v.scale || []).map((s, i_s) => (
                  <Fragment key={i_s}>
                    {s.head ? (
                      <>
                        <div className="grp" id={s.hid} style={{ marginTop: "6px" }}>
                          {s.headLabel}
                        </div>
                      </>
                    ) : null}
                    <div className="sc">
                      <span className="note">
                        {s.n}
                      </span>
                      <span>
                        {s.q}
                        <span className="src" style={{ display: "block" }}>
                          {s.ev}
                        </span>
                      </span>
                      <span className="opt3" role="group" aria-label={s.q}>
                        {(s.opts || []).map((o, i_o) => (
                          <Fragment key={i_o}>
                            <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd, width: "84px", padding: "0 6px" }}>
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
              </section>
            </>
          ) : null}
          {v.tD ? (
            <>
              <section className="card" aria-label="가족 지지 · 관계 척도" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                  <h2 className="h2">
                    가족 지지 · 관계 척도
                  </h2>
                  <span className="note">
                    15문항 · 어르신 본인 응답 우선
                  </span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px" }}>
                  <span className="note">
                    응답자
                  </span>
                  <span className="opt3">
                    {(v.resp || []).map((o, i_o) => (
                      <Fragment key={i_o}>
                        <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}>
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  <span style={{ marginLeft: "auto" }}>
                    {"평균 "}
                    <b className="brn" style={{ fontSize: "20px" }}>
                      {v.famAvg}
                    </b>
                    <span className="note">
                      {" 점 · "}{v.famN}/15 응답
                    </span>
                  </span>
                </div>
                <div className="note" style={{ display: "grid", gridTemplateColumns: "38px minmax(0,1fr) auto", gap: "10px", padding: "0 4px" }}>
                  <span />
                  <span />
                  <span>
                    1 전혀 그렇지 않다 · 3 보통이다 · 5 항상 그렇다
                  </span>
                </div>
                {(v.fam || []).map((s, i_s) => (
                  <Fragment key={i_s}>
                    <div className="sc">
                      <span className="note">
                        {s.n}
                      </span>
                      <span>
                        {s.q}
                      </span>
                      <span className="opt3">
                        {(s.opts || []).map((o, i_o) => (
                          <Fragment key={i_o}>
                            <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd, minWidth: "34px" }}>
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <p className="src" style={{ margin: "0" }}>
                  기관 내부 시니어용 재구성 문항 · 참고용 (원 척도: 양옥경 가족관계 척도) · 가족 응답은 어르신 동의 범위 안에서만 받습니다.
                </p>
              </section>
            </>
          ) : null}
          {v.tE ? (
            <>
              <section className="card" aria-label="단축형 노인우울척도 SGDS-K" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                  <h2 className="h2">
                    단축형 노인우울척도 (SGDS-K)
                  </h2>
                  <span className="note">
                    S-03 · 15문항 · 예/아니오
                  </span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px" }}>
                  <span className="note">
                    최근 1주일 기준 · 한 문항씩 천천히 여쭙고, 잘 안 들리시면 다시 확인합니다.
                  </span>
                  <span style={{ marginLeft: "auto" }}>
                    {"합계 "}
                    <b className="brn" style={{ fontSize: "20px" }}>
                      {v.gdSum}
                    </b>
                    <span className="note">
                      {" / 15점 · "}{v.gdN}/15 응답
                    </span>
                  </span>
                </div>
                {(v.gds || []).map((s, i_s) => (
                  <Fragment key={i_s}>
                    <div className="sc">
                      <span className="note">
                        {s.n}
                      </span>
                      <span>
                        {s.q}
                        <span className="src" style={{ display: "block" }}>
                          {s.rule}
                        </span>
                      </span>
                      <span className="opt3" role="group" aria-label={s.q}>
                        {(s.opts || []).map((o, i_o) => (
                          <Fragment key={i_o}>
                            <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd, minWidth: "64px" }}>
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <p className="note" style={{ margin: "0" }}>
                  <b>
                    선별 결과이며 진단 아님 · 기준 이상 시 정신건강복지센터 연계 검토
                  </b>
                </p>
                <p className="src" style={{ margin: "0" }}>
                  요약 문항명으로 표기 · 실시할 때는 기관에 비치된 정식 문항지를 사용합니다.
                </p>
              </section>
            </>
          ) : null}
          {v.tF ? (
            <>
              <section className="card" aria-label="자살위험 선별 체크" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "14px" }}>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "8px" }}>
                  <h2 className="h2">
                    자살위험 선별 체크
                  </h2>
                  <span className="note">
                    S-04 · 위기 신호 최우선 확인
                  </span>
                </div>
                <p className="note" style={{ margin: "0" }}>
                  직접적이고 차분하게 여쭙니다. 자살에 대해 묻는 것이 위험을 높이지 않습니다. 말씀을 끝까지 듣고 판단하지 않습니다.
                </p>
                <div className="grp">
                  위험 신호
                </div>
                {(v.srRisk || []).map((c, i_c) => (
                  <Fragment key={i_c}>
                    <div className="item">
                      <span>
                        {c.q}
                      </span>
                      <span className="opt3" role="group" aria-label={c.q}>
                        {(c.opts || []).map((o, i_o) => (
                          <Fragment key={i_o}>
                            <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}>
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <div className="grp">
                  보호요인
                </div>
                {(v.srProt || []).map((c, i_c) => (
                  <Fragment key={i_c}>
                    <div className="item">
                      <span>
                        {c.q}
                      </span>
                      <span className="opt3" role="group" aria-label={c.q}>
                        {(c.opts || []).map((o, i_o) => (
                          <Fragment key={i_o}>
                            <button type="button" onClick={o.pick} style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}>
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <div className="item" style={{ gridTemplateColumns: "1fr auto" }}>
                  <span>
                    {"선별 결과 "}
                    <b className="brn">
                      {v.srLevel}
                    </b>
                    <span className="note">
                      {"· "}{v.srN}/9 응답
                    </span>
                  </span>
                  <span className="chip c-hi">
                    자살예방상담 109
                  </span>
                </div>
                <p className="note" style={{ margin: "0" }}>
                  {v.srGuide}
                </p>
                <p className="note" style={{ margin: "0" }}>
                  위기 시 즉시: 자살예방상담 109 안내 · 정신건강복지센터 연계 · 생명이 위급하면 119 / 112 요청 · 어르신을 혼자 두지 않기 · 위험한 수단 멀리하기 · 담당 관리자 보고
                </p>
                <p className="src" style={{ margin: "0" }}>
                  선별 결과이며 진단 아님 · 결과는 상담사가 종합 판단합니다.
                </p>
              </section>
            </>
          ) : null}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" }}>
            <button type="button" className="btn btn-s" style={{ marginLeft: "auto" }} onClick={v.saveDraft}>
              임시 저장
            </button>
            <button type="button" className="btn btn-p" onClick={v.saveDone}>
              확정
            </button>
          </div>
          <p className="ainote">
            AI 분석은 참고용 확인 제안이며, 최종 판단은 상담사가 합니다. AI 요약도 존댓말 · 존중 언어 원칙을 지킵니다.
          </p>
        </main>
      </div>
    </div>
  );
}
