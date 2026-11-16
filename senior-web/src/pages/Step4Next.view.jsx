// Step4Next 화면 마크업 — tools/dc2jsx.py 가 디자인(Step4Next.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './Step4Next.css';

export default function View({ v }) {
  return (
    <div className="pg-Step4Next">
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
            {" › "}
            <a href="#/CaseInfo">
              김순자 C-2026-0351
            </a>
            {" › "}
            <a href="#/CaseHistory">
              상담 이력
            </a>
            {" › "}
            <a href="#/SessionDetail">
              8회차
            </a>
          </nav>
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 280px" }}>
              <div className="sub">
                10/2(금) 방문상담
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "2px" }}>
                <a className="btn btn-sm btn-s" href="#/CaseInfo" aria-label="내담자 정보로 돌아가기" title="내담자 정보로 돌아가기">
                  ←
                </a>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  8회차 처리 · 김순자
                </h1>
              </div>
            </div>
          </header>
          <nav className="steps" aria-label="회차 처리 단계">
            <a className="stp done" href="#/Step1Record">
              <span className="sn">
                ✓
              </span>
              <b style={{ fontWeight: "500" }}>
                기록 확인
              </b>
            </a>
            <a className="stp done" href="#/Step2Signals">
              <span className="sn">
                ✓
              </span>
              <b style={{ fontWeight: "500" }}>
                정서·위기 신호 확인
              </b>
            </a>
            <a className="stp done" href="#/Step3Summary">
              <span className="sn">
                ✓
              </span>
              <b style={{ fontWeight: "500" }}>
                상담일지 작성
              </b>
            </a>
            <a className="stp on" href="#/Step4Next" aria-current="step">
              <span className="sn">
                4
              </span>
              <b style={{ fontWeight: "700" }}>
                다음 상담 준비
              </b>
            </a>
          </nav>
          <section className="card" id="next-checks" aria-label="다음 상담 전 확인할 사항" style={{ scrollMarginTop: "16px", padding: "20px 22px", display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
              <h2 className="h2">
                다음 상담 전 확인할 사항
              </h2>
            </div>
            {(v.checks || []).map((c, i_c) => (
              <Fragment key={i_c}>
                <div className="qcard" style={{ flexDirection: "row", alignItems: "flex-start", gap: "12px" }}>
                  <input type="checkbox" checked={c.on} onChange={c.toggle} aria-label="브리핑에 넣기" style={{ width: "18px", height: "18px", marginTop: "4px", accentColor: "#5FA4D6" }} />
                  <div style={{ flex: "1", display: "flex", flexDirection: "column", gap: "6px" }}>
                    {c.notEdit ? (
                      <>
                        <span style={{ fontSize: "15px" }}>
                          {c.text}
                        </span>
                      </>
                    ) : null}
                    {c.isEdit ? (
                      <>
                        <textarea className="edit-in" rows="2" aria-label="확인 사항 수정" value={c.draft} onChange={c.setDraft} />
                      </>
                    ) : null}
                    <span className="note">
                      {"근거 · "}{c.why}
                    </span>
                  </div>
                  {c.edited ? (
                    <>
                      <span className="chip c-sand">
                        상담사 수정
                      </span>
                    </>
                  ) : null}
                  <button type="button" className="del-x" aria-label="확인 사항 삭제" title="삭제" onClick={c.del}>
                    <svg viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                      <path d="M6 6l12 12M18 6L6 18" />
                    </svg>
                  </button>
                </div>
              </Fragment>
            ))}
            {(v.nNewRows || []).map((r, i_r) => (
              <Fragment key={i_r}>
                <div className="qcard" style={{ flexDirection: "row", alignItems: "flex-start", gap: "12px", boxShadow: "inset 0 0 0 2px #1F3A56" }}>
                  <div style={{ flex: "1", display: "flex", flexDirection: "column", gap: "6px" }}>
                    <textarea className="edit-in" rows="2" aria-label="새 확인 사항" placeholder="새 확인 사항을 적어 주세요" value={r.draft} onChange={r.setDraft} />
                  </div>
                </div>
              </Fragment>
            ))}
            <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "flex-end", gap: "8px" }}>
              <button type="button" className="btn btn-sm btn-s" onClick={v.addN}>
                + 확인 사항 직접 추가
              </button>
              {v.nNotEdit ? (
                <>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.startN}>
                    수정
                  </button>
                </>
              ) : null}
              {v.nIsEdit ? (
                <>
                  <button type="button" className="btn btn-sm btn-p" onClick={v.nOk}>
                    확인
                  </button>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.nCancel}>
                    취소
                  </button>
                </>
              ) : null}
            </div>
          </section>
          <section className="card" aria-label="추가 질문" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px 12px" }}>
              <h2 className="h2">
                추가 질문
              </h2>
              <div role="tablist" className="seg" style={{ marginLeft: "auto" }}>
                <button type="button" role="tab" className={v.meetCls} onClick={v.showMeet}>
                  다음 상담에서 직접
                </button>
                <button type="button" role="tab" className={v.appCls} onClick={v.showApp}>
                  안부 앱으로 먼저
                </button>
              </div>
            </div>
            {(v.qs || []).map((q, i_q) => (
              <Fragment key={i_q}>
                <div className="qcard">
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                    <span className="chip c-sky">
                      {q.id}
                    </span>
                    {q.ok ? (
                      <>
                        <span className="chip c-sel">
                          {q.st}
                        </span>
                      </>
                    ) : null}
                    {q.edited ? (
                      <>
                        <span className="chip c-sand">
                          상담사 수정
                        </span>
                      </>
                    ) : null}
                    <span className="note" style={{ marginLeft: "auto" }}>
                      {"근거 · "}{q.why}
                    </span>
                  </div>
                  {q.notEdit ? (
                    <>
                      <div style={{ fontSize: "16px", fontWeight: "500" }}>
                        "{q.text}"
                      </div>
                      {q.hasOpts ? (
                        <>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                            {(q.opts || []).map((o, i_o) => (
                              <Fragment key={i_o}>
                                <span className="opt">
                                  {o}
                                </span>
                              </Fragment>
                            ))}
                          </div>
                        </>
                      ) : null}
                      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "flex-end", gap: "8px" }}>
                        <button type="button" className={`btn btn-sm ${q.okCls}`} onClick={q.approve}>
                          {q.okLabel}
                        </button>
                      </div>
                    </>
                  ) : null}
                  {q.isEdit ? (
                    <>
                      <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                        <span className="note">
                          질문 문장
                        </span>
                        <textarea className="edit-in" rows="2" aria-label="질문 문장 수정" value={q.draftText} onChange={q.setText} />
                      </label>
                      {q.hasOpts ? (
                        <>
                          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                            <span className="note">
                              답 보기 (쉼표로 구분)
                            </span>
                            <input className="edit-in" type="text" aria-label="답 보기 수정" value={q.draftOpts} onChange={q.setOpts} />
                          </label>
                        </>
                      ) : null}
                    </>
                  ) : null}
                </div>
              </Fragment>
            ))}
            {(v.qNewRows || []).map((r, i_r) => (
              <Fragment key={i_r}>
                <div className="qcard" style={{ boxShadow: "inset 0 0 0 2px #1F3A56" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                    <span className="chip c-sky">
                      직접 작성
                    </span>
                  </div>
                  <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <span className="note">
                      질문 문장
                    </span>
                    <textarea className="edit-in" rows="2" aria-label="새 질문 문장" placeholder="어르신께 여쭤볼 질문을 존댓말로 적어 주세요" value={r.text} onChange={r.setText} />
                  </label>
                  {r.withOpts ? (
                    <>
                      <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                        <span className="note">
                          답 보기 (쉼표로 구분)
                        </span>
                        <input className="edit-in" type="text" aria-label="새 질문 답 보기" placeholder="예: 좋아요, 그저 그래요, 안 좋아요, 말하기 어려워요" value={r.opts} onChange={r.setOpts} />
                      </label>
                    </>
                  ) : null}
                </div>
              </Fragment>
            ))}
            <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "flex-end", gap: "8px" }}>
              <button type="button" className="btn btn-sm btn-s" onClick={v.addQ}>
                + 질문 직접 추가
              </button>
              {v.qNotEdit ? (
                <>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.startQ}>
                    수정
                  </button>
                </>
              ) : null}
              {v.qIsEdit ? (
                <>
                  <button type="button" className="btn btn-sm btn-p" onClick={v.qOk}>
                    확인
                  </button>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.qCancel}>
                    취소
                  </button>
                </>
              ) : null}
            </div>
          </section>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" }}>
            <a className="btn btn-s" href="#/Step3Summary">
              ← 상담일지 작성
            </a>
            <a className="btn btn-p" href="#/CaseInfo?sec=brief" style={{ marginLeft: "auto" }}>
              8회차 처리 완료 · 브리핑 보기
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
