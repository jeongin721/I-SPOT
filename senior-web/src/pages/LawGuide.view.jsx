// LawGuide 화면 마크업 — tools/dc2jsx.py 가 디자인(LawGuide.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './LawGuide.css';

export default function View({ v }) {
  return (
    <div className="pg-LawGuide">
      <div className={v.themeCls} style={{ minHeight: "1000px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            <a className="on" href="#/LawGuide">
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 260px" }}>
              <div className="sub">
                2026년 노인보건복지사업안내 · 노인복지법 · 돌봄통합지원법
              </div>
              <h1 style={{ margin: "2px 0 0", fontSize: "28px", fontWeight: "700" }}>
                법령 · 매뉴얼
              </h1>
            </div>
          </header>
          <div className="seg lg-tabs" role="tablist" aria-label="법령 · 매뉴얼 보기">
            {(v.tabs || []).map((t, i_t) => (
              <Fragment key={i_t}>
                <button type="button" role="tab" className={t.cls} aria-selected={t.sel} onClick={t.pick}>
                  {t.label}
                </button>
              </Fragment>
            ))}
          </div>
          {v.tabAi ? (
            <>
              <section className="card lg-chat" aria-label="AI에게 묻기">
                <div className="lg-chat-hd">
                  <span className="lg-ai" aria-hidden="true">
                    AI
                  </span>
                  <div style={{ flex: "1", minWidth: "0" }}>
                    <h2 className="h2">
                      법령 · 매뉴얼 AI에게 묻기
                    </h2>
                    <span className="note">
                      시니어 상담 관련 법령(노인복지법 · 돌봄통합지원법 · 정신건강복지법 · 자살예방법 · 치매관리법 등)과 보건복지부 사업안내 · 지침을 함께 참조해 답해요. 답변마다 근거 자료와 법령을 함께 보여 드려요.
                    </span>
                  </div>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.chatReset}>
                    새 대화
                  </button>
                </div>
                <div className="lg-msgs" id="lg-msgs" aria-live="polite">
                  {(v.msgs || []).map((m, i_m) => (
                    <Fragment key={i_m}>
                      <div className={`lg-msg ${m.cls}`}>
                        <div className="lg-bub">
                          <span style={{ whiteSpace: "pre-line" }}>
                            {m.text}
                          </span>
                          {m.hasRefs ? (
                            <>
                              <div className="lg-refs">
                                <span className="lg-refl">
                                  근거
                                </span>
                                {(m.refs || []).map((r, i_r) => (
                                  <Fragment key={i_r}>
                                    <button type="button" className="lg-ref" onClick={r.open}>
                                      {r.label}
                                    </button>
                                  </Fragment>
                                ))}
                                {(m.laws || []).map((w, i_w) => (
                                  <Fragment key={i_w}>
                                    <a className="lg-ref law" href={w.url} target="_blank" rel="noopener">
                                      {w.label}{" ↗"}
                                    </a>
                                  </Fragment>
                                ))}
                              </div>
                            </>
                          ) : null}
                        </div>
                      </div>
                    </Fragment>
                  ))}
                  {v.typing ? (
                    <>
                      <div className="lg-msg lg-b">
                        <div className="lg-bub lg-typing">
                          <i />
                          <i />
                          <i />
                          <span className="note" style={{ marginLeft: "6px" }}>
                            매뉴얼과 법령에서 찾는 중
                          </span>
                        </div>
                      </div>
                    </>
                  ) : null}
                </div>
                <div className="lg-sugg">
                  {(v.suggs || []).map((q, i_q) => (
                    <Fragment key={i_q}>
                      <button type="button" className="lg-chip" onClick={q.ask}>
                        {q.label}
                      </button>
                    </Fragment>
                  ))}
                </div>
                <form className="lg-ask" onSubmit={v.submit}>
                  <input className="inp" type="text" placeholder="예: 가족에게 상담 내용을 공유해도 되나요?" value={v.draft} onChange={v.setDraft} aria-label="질문 입력" />
                  <button type="submit" className="btn btn-p">
                    보내기
                  </button>
                </form>
                <p className="note" style={{ margin: "0" }}>
                  AI 답변은 참고용이며 판단이 아니라 확인할 내용을 제안해요. 최종 결정은 지침 원문과 법령을 확인해 주세요.
                </p>
              </section>
            </>
          ) : null}
          {v.tabRef ? (
            <>
              <section className="card lg-refbox" aria-label="업무 단계별 참고사항">
                <div className="lg-ref-hd">
                  <div style={{ flex: "1 1 280px" }}>
                    <h2 className="h2">
                      업무 단계별 참고사항 · 주요 조문
                    </h2>
                    <span className="note">
                      상담 단계별 기준과 시니어 상담 관련 법령 · 지침의 주요 내용을 정리했어요. 줄을 누르면 펼쳐져요.
                    </span>
                  </div>
                  <div className="lg-src">
                    <span className="note">
                      원문 자료
                    </span>
                    <button type="button" className="lg-chip" onClick={v.openToc}>
                      참고 자료 목록
                    </button>
                    <a className="lg-chip" href="https://www.law.go.kr/법령/노인복지법" target="_blank" rel="noopener">
                      노인복지법 ↗
                    </a>
                    <a className="lg-chip" href="https://www.law.go.kr/법령/의료ㆍ요양등지역돌봄의통합지원에관한법률" target="_blank" rel="noopener">
                      돌봄통합지원법 ↗
                    </a>
                    <a className="lg-chip" href="https://www.law.go.kr/법령/자살예방및생명존중문화조성을위한법률" target="_blank" rel="noopener">
                      자살예방법 ↗
                    </a>
                  </div>
                </div>
                <div className="lg-filter">
                  <div className="seg" role="group" aria-label="분류">
                    {(v.filters || []).map((p, i_p) => (
                      <Fragment key={i_p}>
                        <button type="button" className={p.cls} aria-pressed={p.on} onClick={p.pick}>
                          {p.label}
                        </button>
                      </Fragment>
                    ))}
                  </div>
                </div>
                {(v.refs || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <div className={`lg-item ${r.cls}`} id={r.domId}>
                      <button type="button" className="lg-row" aria-expanded={r.exp} onClick={r.toggle}>
                        <span className={`lg-step ${r.stepCls}`}>
                          {r.step}
                        </span>
                        <span className="lg-tt">
                          <b>
                            {r.title}
                          </b>
                          <span className="note">
                            {r.sum}
                          </span>
                        </span>
                        <span className="lg-pg">
                          {r.pages}
                        </span>
                        <span className="lg-chev" aria-hidden="true">
                          ⌄
                        </span>
                      </button>
                      {r.open ? (
                        <>
                          <div className="lg-body">
                            <ul>
                              {(r.items || []).map((it, i_it) => (
                                <Fragment key={i_it}>
                                  <li>
                                    {it}
                                  </li>
                                </Fragment>
                              ))}
                            </ul>
                            <div className="lg-refs">
                              <span className="lg-refl">
                                근거
                              </span>
                              <span className="lg-ref static">
                                {r.pages}
                              </span>
                              {(r.laws || []).map((w, i_w) => (
                                <Fragment key={i_w}>
                                  <a className="lg-ref law" href={w.url} target="_blank" rel="noopener">
                                    {w.label}{" ↗"}
                                  </a>
                                </Fragment>
                              ))}
                            </div>
                          </div>
                        </>
                      ) : null}
                    </div>
                  </Fragment>
                ))}
              </section>
            </>
          ) : null}
          <p className="ainote">
            요약은 2026년 노인보건복지사업안내(보건복지부) 등 관련 지침과 법령을 바탕으로 정리한 것이며 조문 원문이 아닙니다. 조문과 개정 여부는 국가법령정보센터 원문으로 확인하세요. 긴급 연락처: 자살예방상담 109 · 보건복지상담센터 129 · 치매상담콜센터 1899-9988 · 노인보호전문기관 1577-1389 · 응급 119 · 경찰 112
          </p>
        </main>
      </div>
    </div>
  );
}
