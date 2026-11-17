// CaseApp 화면 마크업 — tools/dc2jsx.py 가 디자인(CaseApp.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './CaseApp.css';

export default function View({ v }) {
  return (
    <div className="pg-CaseApp">
      <div className={v.themeCls} style={{ minHeight: "1650px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            <a className="on" href="#/CaseList">
              대상자 관리
            </a>
            <a href="#/Schedule">
              일정
            </a>
            <a href="#/ChildLink">
              안부 연계
              <span className="cnt">
                {v.cntApp}
              </span>
            </a>
            <a href="#/Followup">
              후속관리
              <span className="cnt">
                {v.cntFollow}
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
            <a href="#/CaseList">
              대상자 관리
            </a>
            {" › "}{v.crumb}
          </nav>
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px 18px" }}>
            <a className="btn btn-sm btn-s" href="#/CaseList">
              ← 목록
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
            <a href={v.docsHref}>
              문서함
            </a>
            <a className="on" href={v.appHref} aria-current="page">
              안부 연계
            </a>
          </nav>
          {v.k.hasQuote ? (
            <>
              <section aria-label="어르신이 남긴 말씀" className="quote">
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                  <b style={{ fontSize: "15px" }}>
                    어르신이 남긴 말씀 (음성 · 글)
                  </b>
                  <span style={{ fontSize: "12px" }}>
                    {v.k.quoteAt}
                  </span>
                </div>
                <div style={{ fontSize: "24px", fontWeight: "700", lineHeight: "1.5" }}>
                  "{v.k.quote}"
                </div>
              </section>
            </>
          ) : null}
          <section className="card" aria-label="안부 질문과 답" style={{ padding: "20px 22px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
              <h2 className="h2">
                안부 질문과 답
              </h2>
              <span className="note" style={{ marginLeft: "auto" }}>
                {v.k.last}{" 안부 응답"}
              </span>
              <a className="btn btn-sm btn-s" href={v.histHref} onClick={v.goAns}>
                지난 안부 기록 →
              </a>
            </div>
            <div className="qa-row note" style={{ padding: "8px 0" }}>
              <span>
                문항
              </span>
              <span>
                질문
              </span>
              <span>
                지난 답변 (3주 전 → 지난주)
              </span>
              <span>
                이번 답변
              </span>
              <span />
            </div>
            {(v.answers || []).map((a, i_a) => (
              <Fragment key={i_a}>
                <div className="qa-row" style={{ background: a.bg }}>
                  <span className="note">
                    {a.id}
                  </span>
                  <span>
                    {a.q}
                  </span>
                  <span className="prev">
                    {(a.prev || []).map((p, i_p) => (
                      <Fragment key={i_p}>
                        <span className="pv">
                          {p}
                        </span>
                      </Fragment>
                    ))}
                  </span>
                  <b style={{ fontWeight: a.fw }}>
                    {a.ans}
                    {a.changed ? (
                      <>
                        <span className="chg">
                          바뀜
                        </span>
                      </>
                    ) : null}
                  </b>
                  <span className="note">
                    {a.flagText}
                  </span>
                </div>
              </Fragment>
            ))}
          </section>
          <section className="card" aria-label="가족 관찰 메모" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
              <h2 className="h2">
                가족 관찰 메모
              </h2>
              <span className={v.k.famCls}>
                {v.k.famConsent}
              </span>
              <span className="note" style={{ marginLeft: "auto" }}>
                {v.k.famScope}
              </span>
            </div>
            {(v.famNotes || []).map((m, i_m) => (
              <Fragment key={i_m}>
                <div className="qcard">
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                    <b style={{ fontSize: "14px" }}>
                      {m.who}
                    </b>
                    <span className="note">
                      {m.at}
                    </span>
                  </div>
                  <span style={{ fontSize: "14px", lineHeight: "1.7" }}>
                    {m.text}
                  </span>
                </div>
              </Fragment>
            ))}
            <p className="note" style={{ margin: "0" }}>
              가족에게는 어르신이 동의하신 범위 안에서만 공유돼요. 내담자는 어르신 본인이며, 가족 메모는 참고 자료로만 씁니다.
            </p>
          </section>
          <section className="card" aria-label="확인할 답변" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "14px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
              <h2 className="h2">
                확인할 답변 · 추가 안부 질문
              </h2>
              <span className="chip c-check">
                {v.flagCount}개
              </span>
            </div>
            {(v.flags || []).map((f, i_f) => (
              <Fragment key={i_f}>
                <div className="flag">
                  <b style={{ fontSize: "15px" }}>
                    {f.q}
                  </b>
                  <div className="flow">
                    <span className="note" style={{ marginRight: "4px" }}>
                      3주 전 → 이번
                    </span>
                    {(f.flow || []).map((v, i_v) => (
                      <Fragment key={i_v}>
                        <span className={v.cls}>
                          {v.t}
                        </span>
                      </Fragment>
                    ))}
                  </div>
                  <div className="aibox">
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="chip c-ai">
                        AI 초안
                      </span>
                      <b style={{ fontSize: "13px" }}>
                        확인 제안
                      </b>
                      {f.n.edited ? (
                        <>
                          <span className="chip c-sand">
                            상담사 수정
                          </span>
                        </>
                      ) : null}
                      {f.n.notEdit ? (
                        <>
                          <button type="button" className="btn btn-sm btn-s" style={{ marginLeft: "auto", minHeight: "30px" }} onClick={f.n.startEdit}>
                            수정
                          </button>
                        </>
                      ) : null}
                    </div>
                    {f.n.notEdit ? (
                      <>
                        <span style={{ fontSize: "14px", lineHeight: "1.7" }}>
                          {f.n.text}
                        </span>
                      </>
                    ) : null}
                    {f.n.isEdit ? (
                      <>
                        <textarea className="edit-in" rows="3" aria-label="확인해 볼 점 수정" value={f.n.draft} onChange={f.n.setDraft} />
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                          <button type="button" className="btn btn-sm btn-p" onClick={f.n.save}>
                            저장
                          </button>
                          <button type="button" className="btn btn-sm btn-s" onClick={f.n.cancel}>
                            취소
                          </button>
                        </div>
                      </>
                    ) : null}
                    <a className="note srcl" href="#/Step1Record" onClick={f.goSrc} title="STT 원문 위치로 이동">
                      {"근거 · "}{f.src}{" ↗"}
                    </a>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px", paddingLeft: "14px", borderLeft: "3px solid #D9E3EA" }}>
                    <b style={{ fontSize: "13px" }}>
                      추가 안부 질문
                    </b>
                    {(f.qs || []).map((q, i_q) => (
                      <Fragment key={i_q}>
                        <div className="qcard" style={{ boxShadow: q.ring }}>
                          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                            <span className="chip c-sky">
                              {q.id}
                            </span>
                            <span className={q.stCls}>
                              {q.st}
                            </span>
                            {q.edited ? (
                              <>
                                <span className="chip c-sand">
                                  상담사 수정
                                </span>
                              </>
                            ) : null}
                            <a className="note srcl" href="#/Step1Record" onClick={q.goSrc} style={{ marginLeft: "auto" }} title="STT 원문 위치로 이동">
                              {"근거 · "}{q.why}{" ↗"}
                            </a>
                          </div>
                          {q.notEdit ? (
                            <>
                              <div style={{ fontSize: "16px", fontWeight: "500" }}>
                                "{q.text}"
                              </div>
                              {q.hasOpts ? (
                                <>
                                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px" }}>
                                    <span className="note" style={{ fontWeight: "700" }}>
                                      답변:
                                    </span>
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
                                <button type="button" className="btn btn-sm btn-s" onClick={q.startEdit}>
                                  수정
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
                              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                                <button type="button" className="btn btn-sm btn-p" onClick={q.save}>
                                  저장
                                </button>
                                <button type="button" className="btn btn-sm btn-s" onClick={q.cancel}>
                                  취소
                                </button>
                              </div>
                            </>
                          ) : null}
                        </div>
                      </Fragment>
                    ))}
                  </div>
                </div>
              </Fragment>
            ))}
          </section>
          <p className="ainote">
            AI는 판단하지 않고 확인할 점만 제안합니다. 최종 판단과 연락은 상담사가 하며, AI 문구도 존댓말·존중 언어 원칙을 따릅니다.
          </p>
        </main>
      </div>
    </div>
  );
}
