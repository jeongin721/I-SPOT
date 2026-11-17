// AppMemo 화면 마크업 — tools/dc2jsx.py 가 디자인(AppMemo.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AppMemo.css';

export default function View({ v }) {
  return (
    <div className="pg-AppMemo">
      <div className={v.rootCls}>
        <header className="ahd">
          <div className="tl">
            <div className="sub">
              방문 상담 현장에서 바로 적어 두기
            </div>
            <h1>
              메모
            </h1>
          </div>
          <button type="button" className="ibtn" aria-label={`알림 ${v.ntCount}건`} onClick={v.ntToggle}>
            <svg viewBox={"0 0 24 24"} width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M6 9.5a6 6 0 0 1 12 0c0 4.2 1.4 6 2.2 6.9a.6.6 0 0 1-.45 1H4.25a.6.6 0 0 1-.45-1C4.6 15.5 6 13.7 6 9.5z" />
              <path d="M10 20.2a2.2 2.2 0 0 0 4 0" />
            </svg>
            {v.ntHas ? (
              <>
                <span className="badge">
                  {v.ntCount}
                </span>
              </>
            ) : null}
          </button>
          <a className={v.setCls} href="#/AppSettings" aria-label="설정" aria-current={v.setCur}>
            <svg viewBox={"0 0 24 24"} width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </a>
        </header>
        <main className="amain">
          {v.msg && !v.shOpen ? <p className="note" role="alert" style={{ margin: "0", color: "var(--red)" }}>{v.msg}</p> : null}
          <section className="card" style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "10px" }} aria-label="새 메모">
            <select className="inp" value={v.nChild} onChange={v.setNChild} aria-label="관련 어르신">
              <option value="">
                관련 어르신 선택 안 함
              </option>
              {(v.elderOpts || []).map((k, i_k) => (
                <Fragment key={i_k}>
                  <option value={k.v}>
                    {k.label}
                  </option>
                </Fragment>
              ))}
            </select>
            <textarea className="inp" rows="3" placeholder="예) 보청기 착용, 천천히 말씀드리기 · 약 봉투 확인" value={v.nText} onChange={v.setNText} aria-label="메모 내용" />
            <button type="button" className="btn btn-p" onClick={v.add}>
              메모 저장
            </button>
          </section>
          <p className="sec-t">
            {"최근 메모 · "}{v.count}개
          </p>
          {(v.memos || []).map((m, i_m) => (
            <Fragment key={i_m}>
              <div className="card mi" role="button" tabIndex="0" onClick={m.open}>
                <div className="mi-top">
                  {m.hasChild ? (
                    <>
                      <span className="chip gold">
                        {m.elder}
                      </span>
                    </>
                  ) : null}
                  <span className="note" style={{ marginLeft: "auto" }}>
                    {m.t}
                  </span>
                </div>
                <p>
                  {m.text}
                </p>
              </div>
            </Fragment>
          ))}
        </main>
        <nav className="tabs" aria-label="앱 메뉴">
          {(v.tabs || []).map((t, i_t) => (
            <Fragment key={i_t}>
              <a className={t.cls} href={t.href} aria-label={t.aria} aria-current={t.cur}>
                <span className="ti">
                  {t.isHome ? (
                    <>
                      <svg viewBox={"0 0 24 24"} width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M3.5 11L12 4l8.5 7" />
                        <path d="M6 9.5V20h4.5v-5.5h3V20H18V9.5" />
                      </svg>
                      <svg className="fi1" viewBox={"0 0 24 24"} width="22" height="22" aria-hidden="true">
                        <path fill="currentColor" fillRule="evenodd" d="M12 2.6 2.6 10.3c-.4.3-.6.8-.6 1.3V20a1.5 1.5 0 0 0 1.5 1.5h17A1.5 1.5 0 0 0 22 20v-8.4c0-.5-.2-1-.6-1.3zM9.8 21.5v-5.8h4.4v5.8z" />
                      </svg>
                    </>
                  ) : null}
                  {t.isRec ? (
                    <>
                      <svg viewBox={"0 0 24 24"} width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <rect x="9" y="3" width="6" height="11" rx="3" />
                        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
                      </svg>
                    </>
                  ) : null}
                  {t.isUp ? (
                    <>
                      <svg viewBox={"0 0 24 24"} width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M12 15V4M7 9l5-5 5 5" />
                        <path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" />
                      </svg>
                      <svg className="fi1" viewBox={"0 0 24 24"} width="22" height="22" aria-hidden="true">
                        <path fill="currentColor" d="M2.5 14h5.2l1.6 2.4h5.4l1.6-2.4h5.2V19a2 2 0 0 1-2 2h-15a2 2 0 0 1-2-2z" />
                        <path fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" d="M12 13V3.5M7.5 8 12 3.5 16.5 8" />
                      </svg>
                    </>
                  ) : null}
                  {t.isCal ? (
                    <>
                      <svg viewBox={"0 0 24 24"} width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <rect x="3" y="5" width="18" height="16" rx="2" />
                        <path d="M16 3v4M8 3v4M3 10h18" />
                      </svg>
                      <svg className="fi1" viewBox={"0 0 24 24"} width="22" height="22" aria-hidden="true">
                        <path fill="currentColor" d="M5 4.5h14A2.5 2.5 0 0 1 21.5 7v12a2.5 2.5 0 0 1-2.5 2.5H5A2.5 2.5 0 0 1 2.5 19V7A2.5 2.5 0 0 1 5 4.5z" />
                        <path fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" d="M16 2.5v4M8 2.5v4" />
                        <path fill="none" style={{ stroke: "var(--card)" }} strokeWidth="2" d="M2.5 10h19" />
                      </svg>
                    </>
                  ) : null}
                  {t.isMemo ? (
                    <>
                      <svg viewBox={"0 0 24 24"} width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M5 3h10l4 4v14H5z" />
                        <path d="M9 11h6M9 15h6" />
                      </svg>
                      <svg className="fi1" viewBox={"0 0 24 24"} width="22" height="22" aria-hidden="true">
                        <path fill="currentColor" d="M5.5 2.5h9.6l4.4 4.4V20a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4.5 20V4A1.5 1.5 0 0 1 5.5 2.5z" />
                        <path fill="none" style={{ stroke: "var(--card)" }} strokeWidth="2" strokeLinecap="round" d="M8.5 11h7M8.5 15h7" />
                      </svg>
                    </>
                  ) : null}
                </span>
                {t.hasLabel ? (
                  <>
                    <span>
                      {t.label}
                    </span>
                  </>
                ) : null}
              </a>
            </Fragment>
          ))}
        </nav>
        {v.shOpen ? (
          <>
            <div className="ov" onClick={v.shClose}>
              <section className="sheet" role="dialog" aria-modal="true" aria-label="메모 수정" onClick={v.stop}>
                <span className="grab" aria-hidden="true" />
                <div className="sh-hd">
                  <b>
                    메모
                  </b>
                  <span className="note">
                    {v.eT}
                  </span>
                </div>
                <select className="inp" value={v.eChild} onChange={v.setEChild} aria-label="관련 어르신">
                  <option value="">
                    관련 어르신 선택 안 함
                  </option>
                  {(v.elderOpts || []).map((k, i_k) => (
                    <Fragment key={i_k}>
                      <option value={k.v}>
                        {k.label}
                      </option>
                    </Fragment>
                  ))}
                </select>
                <textarea className="inp" rows="5" value={v.eText} onChange={v.setEText} aria-label="메모 내용" />
                {v.msg ? <p className="note" role="alert" style={{ margin: "0", color: "var(--red)" }}>{v.msg}</p> : null}
                {v.noAsk ? (
                  <>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "8px" }}>
                      <button type="button" className="btn btn-red" onClick={v.askDel}>
                        삭제
                      </button>
                      <button type="button" className="btn btn-p" onClick={v.saveEdit}>
                        수정 저장
                      </button>
                    </div>
                  </>
                ) : null}
                {v.ask ? (
                  <>
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px", padding: "14px", borderRadius: "12px", background: "var(--redsoft)" }}>
                      <b style={{ color: "var(--red)" }}>
                        이 메모를 삭제할까요?
                      </b>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                        <button type="button" className="btn" onClick={v.cancelDel}>
                          취소
                        </button>
                        <button type="button" className="btn" style={{ background: "var(--red)", borderColor: "var(--red)", color: "#FFFFFF" }} onClick={v.del}>
                          삭제
                        </button>
                      </div>
                    </div>
                  </>
                ) : null}
              </section>
            </div>
          </>
        ) : null}
        {v.ntOpen ? (
          <>
            <div className="ov" onClick={v.ntClose}>
              <section className="sheet" role="dialog" aria-modal="true" aria-label="알림" onClick={v.stop}>
                <span className="grab" aria-hidden="true" />
                <div className="sh-hd">
                  <b>
                    알림
                  </b>
                  <button type="button" className="btn btn-sm" onClick={v.ntClose}>
                    닫기
                  </button>
                </div>
                {(v.notes || []).map((n, i_n) => (
                  <Fragment key={i_n}>
                    <div className={`nt ${n.red}`}>
                      <b>
                        {n.title}
                      </b>
                      <span className="note">
                        {n.sub}
                      </span>
                      {n.desc ? (
                        <>
                          <span style={{ fontSize: "13.5px" }}>
                            {n.desc}
                          </span>
                        </>
                      ) : null}
                      {n.hasAct ? (
                        <>
                          <button type="button" className="btn btn-sm btn-p" style={{ alignSelf: "flex-start" }} onClick={n.go}>
                            {n.act}
                          </button>
                        </>
                      ) : null}
                      {n.hasLink ? (
                        <>
                          <a className="btn btn-sm" style={{ alignSelf: "flex-start" }} href={n.href} onClick={n.nav}>
                            {n.linkLabel}
                          </a>
                        </>
                      ) : null}
                    </div>
                  </Fragment>
                ))}
              </section>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
