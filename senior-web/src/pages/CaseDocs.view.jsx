// CaseDocs 화면 마크업 — tools/dc2jsx.py 가 디자인(CaseDocs.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './CaseDocs.css';

export default function View({ v }) {
  return (
    <div className="pg-CaseDocs">
      <div className={v.themeCls} style={{ minHeight: "1350px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              <button type="button" className="btn btn-s" onClick={v.recOpen}>
                <span className="rec-dot" aria-hidden="true" />
                {" 녹음하기"}
              </button>
              <a className="btn btn-s" href={v.uploadHref} onClick={v.markBack}>
                ↑ 녹취 올리기
              </a>
            </div>
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
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px" }}>
            <div role="group" aria-label="문서 종류" className="seg">
              {(v.filters || []).map((f, i_f) => (
                <Fragment key={i_f}>
                  <button type="button" className={f.cls} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <a className="btn btn-p" href={v.uploadHref} onClick={v.markBack} style={{ marginLeft: "auto" }}>
              ↑ 자료 올리기
            </a>
          </section>
          <section className="card" aria-label="기관 서식" style={{ overflowX: "auto" }}>
            <div className="hd">
              <h2 className="h2">
                기관 서식
              </h2>
            </div>
            <table className="tbl" style={{ minWidth: "680px" }}>
              <thead>
                <tr>
                  <th>
                    서식
                  </th>
                  <th>
                    작성 시점
                  </th>
                  <th>
                    최근 작성
                  </th>
                  <th>
                    상태
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(v.forms || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <tr>
                      <td>
                        <button type="button" className="ttl-btn" onClick={r.view} aria-label={`${r.name} 내용 보기`}>
                          {r.name}
                        </button>
                        <span className="note" style={{ display: "block" }}>
                          {r.no}
                        </span>
                      </td>
                      <td className="note">
                        {r.when}
                      </td>
                      <td className="note">
                        {r.date}
                      </td>
                      <td>
                        <span className={r.stCls}>
                          {r.st}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button type="button" className="lnk-btn" onClick={r.view}>
                          열기
                        </button>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
          {v.cvOpen ? (
            <>
              <div className="fm-ov" role="dialog" aria-modal="true" aria-label={`${v.cvName} 내용 보기`}>
                <div className="fm-bar">
                  <b className="fm-t">
                    {v.cvName}
                  </b>
                  <span className={v.cvStCls}>
                    {v.cvSt}
                  </span>
                  <span className="note fm-st">
                    {v.cvMeta}
                  </span>
                  <a className="btn btn-sm btn-p" href={v.cvHref} onClick={v.cvEdit}>
                    수정
                  </a>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.cvClose}>
                    닫기
                  </button>
                </div>
                <div className="fm-body">
                  {(v.cvPages || []).map((pg, i_pg) => (
                    <Fragment key={i_pg}>
                      <div className="paper">
                        {(pg.blocks || []).map((bk, i_bk) => (
                          <Fragment key={i_bk}>
                            <div className="fg" style={{ gridTemplateColumns: bk.cols }}>
                              {(bk.cells || []).map((c, i_c) => (
                                <Fragment key={i_c}>
                                  <div className={c.cls} style={{ gridColumn: `span ${c.cs}`, gridRow: `span ${c.rs}` }}>
                                    {(c.segs || []).map((g, i_g) => (
                                      <Fragment key={i_g}>
                                        {g.isS ? (
                                          <>
                                            <span className="fs">
                                              {g.v}
                                            </span>
                                          </>
                                        ) : null}
                                        {g.isBr ? (
                                          <>
                                            <span className="fbr" />
                                          </>
                                        ) : null}
                                        {g.isSp ? (
                                          <>
                                            <span className={`fsp ${g.q}`} />
                                          </>
                                        ) : null}
                                        {g.isG ? (
                                          <>
                                            <span className="fgd">
                                              {g.v}
                                            </span>
                                          </>
                                        ) : null}
                                        {g.isV ? (
                                          <>
                                            <span className="fv" style={{ flex: g.fx, minWidth: g.w }}>
                                              {g.val}
                                            </span>
                                          </>
                                        ) : null}
                                        {g.isVT ? (
                                          <>
                                            <span className="fvt" style={{ minHeight: g.mh }}>
                                              {g.val}
                                            </span>
                                          </>
                                        ) : null}
                                        {g.isVC ? (
                                          <>
                                            <span className={g.cls}>
                                              <span className="fbox" aria-hidden="true">
                                                {g.mark}
                                              </span>
                                              <span className="fcl-t">
                                                {g.v}
                                              </span>
                                            </span>
                                          </>
                                        ) : null}
                                      </Fragment>
                                    ))}
                                  </div>
                                </Fragment>
                              ))}
                            </div>
                          </Fragment>
                        ))}
                      </div>
                    </Fragment>
                  ))}
                </div>
              </div>
            </>
          ) : null}
          <section className="card" aria-label="파일" style={{ overflowX: "auto" }}>
            <div className="hd">
              <h2 className="h2">
                녹취 · 일지 · 외부 문서
              </h2>
            </div>
            <table className="tbl" style={{ minWidth: "680px" }}>
              <thead>
                <tr>
                  <th>
                    파일
                  </th>
                  <th>
                    종류
                  </th>
                  <th>
                    회차
                  </th>
                  <th>
                    날짜
                  </th>
                  <th>
                    상태
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, i_r) => (
                  <Fragment key={i_r}>
                    <tr>
                      <td>
                        <b style={{ fontWeight: "500" }}>
                          {r.name}
                        </b>
                      </td>
                      <td className="note">
                        {r.kind}
                      </td>
                      <td>
                        {r.ses}
                      </td>
                      <td className="note">
                        {r.date}
                      </td>
                      <td>
                        <span className={r.stCls}>
                          {r.st}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <a href={r.href}>
                          {r.go}
                        </a>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
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
                        {v.caseLabel}
                      </b>
                      <span className="sub">
                        만 82세 · 독거
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
                            7회차 · 9/18 정기상담
                          </option>
                          <option value="6">
                            6회차 · 9/4 정기상담
                          </option>
                          <option value="5">
                            5회차 · 8/28 정기상담
                          </option>
                          <option value="4">
                            4회차 · 8/21 정기상담
                          </option>
                          <option value="3">
                            3회차 · 8/14 정기상담
                          </option>
                          <option value="2">
                            2회차 · 8/7 정기상담
                          </option>
                          <option value="1">
                            1회차 · 7/31 초기상담
                          </option>
                        </select>
                      </label>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="lb2">
                          상담 유형
                        </span>
                        <select className="inp" value={v.recKind} onChange={v.recKindSet} disabled={v.recLock}>
                          <option>
                            정기상담
                          </option>
                          <option>
                            방문상담
                          </option>
                          <option>
                            가족 상담
                          </option>
                          <option>
                            전화상담
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
                              상대방에게 녹음 사실을 알리고 동의를 받았어요
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
        </main>
      </div>
    </div>
  );
}
