// DocBox 화면 마크업 — tools/dc2jsx.py 가 디자인(DocBox.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './DocBox.css';

export default function View({ v }) {
  return (
    <div className="pg-DocBox">
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
            <a className="on" href="#/DocBox">
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
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 260px" }}>
              <div className="sub">
                기관 서식 · 참고 문서 보관
              </div>
              <h1 style={{ margin: "2px 0 0", fontSize: "28px", fontWeight: "700" }}>
                문서함
              </h1>
            </div>
            <label className="btn btn-p" htmlFor="docbox-up" style={{ cursor: "pointer" }}>
              ↑ 문서 올리기
            </label>
            <input id="docbox-up" type="file" multiple onChange={v.onUpload} style={{ position: "absolute", width: "1px", height: "1px", opacity: "0", pointerEvents: "none" }} aria-label="문서 올리기" />
          </header>
          {v.hasMsg ? (
            <>
              <p className="note" role="status" style={{ margin: "-8px 0 0", color: "#1F3A56" }}>
                {v.msg}
              </p>
            </>
          ) : null}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "20px", alignItems: "flex-start" }}>
            <section className="card" aria-label="폴더" style={{ flex: "1 1 220px", maxWidth: "280px", padding: "14px", display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ display: "flex", alignItems: "center", padding: "4px 6px 8px" }}>
                <h2 className="h2" style={{ fontSize: "15px" }}>
                  폴더
                </h2>
                <button type="button" className="btn btn-sm btn-s" style={{ marginLeft: "auto" }} onClick={v.toggleNew}>
                  {v.newLabel}
                </button>
              </div>
              {v.adding ? (
                <>
                  <div style={{ display: "flex", gap: "6px", padding: "0 2px 8px" }}>
                    <input className="inp" type="text" placeholder="새 폴더 이름" aria-label="새 폴더 이름" value={v.newName} onChange={v.setNewName} style={{ flex: "1", minWidth: "0", height: "36px" }} />
                    <button type="button" className="btn btn-sm btn-p" onClick={v.addFolder}>
                      만들기
                    </button>
                  </div>
                </>
              ) : null}
              {(v.folders || []).map((f, i_f) => (
                <Fragment key={i_f}>
                  <button type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                    <span className="fico" aria-hidden="true" />
                    <span>
                      {f.name}
                    </span>
                    <span className="n">
                      {f.count}
                    </span>
                  </button>
                </Fragment>
              ))}
            </section>
            <section style={{ flex: "999 1 520px", minWidth: "0", display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 12px" }}>
                <div style={{ flex: "1 1 200px" }}>
                  <span className="note">
                    문서함
                  </span>
                  <span className="note">
                    {" › "}
                  </span>
                  <b>
                    {v.curName}
                  </b>
                  <span className="note" style={{ marginLeft: "8px" }}>
                    {v.shownCount}개
                  </span>
                </div>
                <div role="group" aria-label="정렬" className="seg">
                  <span className="seg-lb">
                    정렬
                  </span>
                  {(v.sorts || []).map((o, i_o) => (
                    <Fragment key={i_o}>
                      <button type="button" className={o.cls} aria-pressed={o.pressed} onClick={o.pick}>
                        {o.label}
                      </button>
                    </Fragment>
                  ))}
                </div>
              </div>
              {v.hasDocs ? (
                <>
                  <div className="dgrid">
                    {(v.docs || []).map((d, i_d) => (
                      <Fragment key={i_d}>
                        <article className="doc">
                          <div className="pv pv-click" role="button" tabIndex="0" aria-label={`${d.name} 내용 보기`} onClick={d.view}>
                            {d.isImg ? (
                              <>
                                <img src={d.url} alt="" />
                              </>
                            ) : null}
                            {d.isText ? (
                              <>
                                <div className="pv-page">
                                  <b>
                                    {d.pvTitle}
                                  </b>
                                  {d.pvBody}
                                </div>
                              </>
                            ) : null}
                            {d.isForm ? (
                              <>
                                <div className="pv-form" inert="">
                                  {(d.pv || []).map((pg, i_pg) => (
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
                                                        {g.isI ? (
                                                          <>
                                                            <input className="fi" type="text" aria-label={g.aria} defaultValue={g.val} style={{ width: g.w, flex: g.fx }} />
                                                          </>
                                                        ) : null}
                                                        {g.isN ? (
                                                          <>
                                                            <input className="fi fn" type="number" inputMode="numeric" min="1" max="10" step="1" aria-label={g.aria} defaultValue={g.val} />
                                                          </>
                                                        ) : null}
                                                        {g.isT ? (
                                                          <>
                                                            <textarea className="fta" rows={g.rows} aria-label={g.aria} defaultValue={g.val} />
                                                          </>
                                                        ) : null}
                                                        {g.isC ? (
                                                          <>
                                                            <label className={g.cls}>
                                                              <input type="checkbox" defaultChecked={g.on} aria-label={g.aria} />
                                                              <span className="fcl-t">
                                                                {g.v}
                                                              </span>
                                                            </label>
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
                                                            <span className={`${g.cls} fvc`}>
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
                              </>
                            ) : null}
                            {d.isOther ? (
                              <>
                                <div className="pv-other">
                                  <span className="pv-ext">
                                    {d.ext}
                                  </span>
                                  <span className="pv-lines">
                                    <i />
                                    <i style={{ width: "80%" }} />
                                    <i />
                                    <i style={{ width: "60%" }} />
                                  </span>
                                  <span className="note" style={{ fontSize: "11px" }}>
                                    첫 페이지 미리보기를 만들 수 없는 형식
                                  </span>
                                </div>
                              </>
                            ) : null}
                          </div>
                          <div className="dname dname-click" role="button" tabIndex="0" onClick={d.view}>
                            {d.name}
                          </div>
                          <div className="dmeta">
                            {d.meta}
                          </div>
                          {d.isForm ? (
                            <>
                              <button type="button" className="btn btn-sm btn-p" onClick={d.open}>
                                작성하기
                              </button>
                            </>
                          ) : null}
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <button type="button" className="btn btn-sm btn-s" onClick={d.download}>
                              <svg viewBox={"0 0 24 24"} width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M12 4v11M7 10l5 5 5-5" />
                                <path d="M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
                              </svg>
                              다운로드
                            </button>
                            <select className="mv" aria-label={d.mvLabel} value={d.folder} onChange={d.move}>
                              {(d.opts || []).map((m, i_m) => (
                                <Fragment key={i_m}>
                                  <option value={m.id}>
                                    {m.name}
                                  </option>
                                </Fragment>
                              ))}
                            </select>
                          </div>
                        </article>
                      </Fragment>
                    ))}
                  </div>
                </>
              ) : null}
              {v.noDocs ? (
                <>
                  <div className="empty">
                    이 폴더에는 아직 문서가 없어요 · ‘문서 올리기’로 추가하거나 다른 폴더의 문서를 옮겨 오세요
                  </div>
                </>
              ) : null}
            </section>
          </div>
          {v.fmOpen ? (
            <>
              <div className="fm-ov" role="dialog" aria-modal="true" aria-label={`${v.fmName} 작성`}>
                <div className="fm-bar">
                  <b className="fm-t">
                    {v.fmName}
                  </b>
                  <span className="note fm-st">
                    {v.fmState}
                  </span>
                  {v.fmEdit ? (
                    <>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.fmClear}>
                        모두 지우기
                      </button>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.fmDown}>
                        <svg viewBox={"0 0 24 24"} width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <path d="M12 4v11M7 10l5 5 5-5" />
                          <path d="M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
                        </svg>
                        다운로드
                      </button>
                      <button type="button" className="btn btn-sm btn-p" onClick={v.fmSave}>
                        저장
                      </button>
                    </>
                  ) : null}
                  {v.fmView ? (
                    <>
                      {v.fmCanEdit ? (
                        <>
                          <button type="button" className="btn btn-sm btn-p" onClick={v.fmToEdit}>
                            작성하기
                          </button>
                        </>
                      ) : null}
                      <button type="button" className="btn btn-sm btn-s" onClick={v.fmDown}>
                        <svg viewBox={"0 0 24 24"} width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <path d="M12 4v11M7 10l5 5 5-5" />
                          <path d="M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
                        </svg>
                        다운로드
                      </button>
                    </>
                  ) : null}
                  <button type="button" className="btn btn-sm btn-s" onClick={v.fmClose}>
                    닫기
                  </button>
                </div>
                {v.svOpen ? (
                  <>
                    <div className="sv-ov" onClick={v.svClose}>
                      <section className="sv" role="dialog" aria-modal="true" aria-label="문서로 저장" onClick={v.svStop}>
                        <b style={{ fontSize: "17px" }}>
                          {v.svTitle}
                        </b>
                        <label className="sv-f">
                          <span className="sv-l">
                            문서 제목
                          </span>
                          <input className="inp" type="text" value={v.svName} onChange={v.svSetName} aria-label="문서 제목" style={{ height: "40px" }} />
                        </label>
                        <label className="sv-f">
                          <span className="sv-l">
                            저장할 폴더
                          </span>
                          <select className="inp" value={v.svFolder} onChange={v.svSetFolder} aria-label="저장할 폴더" style={{ height: "40px" }}>
                            {(v.svOpts || []).map((m, i_m) => (
                              <Fragment key={i_m}>
                                <option value={m.id}>
                                  {m.name}
                                </option>
                              </Fragment>
                            ))}
                          </select>
                        </label>
                        {v.svErr ? (
                          <>
                            <span style={{ color: "#A33B2E", fontSize: "13px" }}>
                              문서 제목을 입력해 주세요.
                            </span>
                          </>
                        ) : null}
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                          <button type="button" className="btn btn-sm btn-s" onClick={v.svClose}>
                            취소
                          </button>
                          <button type="button" className="btn btn-sm btn-p" onClick={v.svOk}>
                            저장
                          </button>
                        </div>
                      </section>
                    </div>
                  </>
                ) : null}
                <div className="fm-body">
                  {v.fmIsText ? (
                    <>
                      <div className="paper">
                        <pre className="fpre">
                          {v.fmText}
                        </pre>
                      </div>
                    </>
                  ) : null}
                  {v.fmIsImg ? (
                    <>
                      <div className="paper" style={{ padding: "16px" }}>
                        <img src={v.fmImg} alt={v.fmName} style={{ display: "block", maxWidth: "100%", margin: "0 auto" }} />
                      </div>
                    </>
                  ) : null}
                  {v.fmIsOther ? (
                    <>
                      <div className="paper" style={{ textAlign: "center", color: "#55687A" }}>
                        지원하지 않는 형식입니다.
                      </div>
                    </>
                  ) : null}
                  {(v.fmPages || []).map((pg, i_pg) => (
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
                                        {g.isI ? (
                                          <>
                                            <input className="fi" type="text" aria-label={g.aria} value={g.val} onChange={g.set} style={{ width: g.w, flex: g.fx }} />
                                          </>
                                        ) : null}
                                        {g.isN ? (
                                          <>
                                            <input className="fi fn" type="number" inputMode="numeric" min="1" max="10" step="1" aria-label={g.aria} value={g.val} onChange={g.set} />
                                          </>
                                        ) : null}
                                        {g.isT ? (
                                          <>
                                            <textarea className="fta" rows={g.rows} aria-label={g.aria} value={g.val} onChange={g.set} />
                                          </>
                                        ) : null}
                                        {g.isC ? (
                                          <>
                                            <label className={g.cls}>
                                              <input type="checkbox" checked={g.on} onChange={g.tog} aria-label={g.aria} />
                                              <span className="fcl-t">
                                                {g.v}
                                              </span>
                                            </label>
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
                                            <span className={`${g.cls} fvc`}>
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
        </main>
      </div>
    </div>
  );
}
