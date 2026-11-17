// AppHome 화면 마크업 — tools/dc2jsx.py 가 디자인(AppHome.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AppHome.css';

export default function View({ v }) {
  return (
    <div className="pg-AppHome">
      <div className={v.rootCls}>
        <header className="ahd">
          <div className="tl">
            <span className="brand">
              <span className="mk">
                온
              </span>
              온담
            </span>
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
          <section className="hello" aria-label="인사">
            <span>
              안녕하세요,
            </span>
            <b>
              {v.hello}
            </b>
            <small>
              {v.today}
            </small>
          </section>
          <a className="hero" href="#/AppCases" aria-label="대상자 목록 보기">
            <span className="hero-top">
              <span>
                내 사례 현황
              </span>
              <span className="hero-go">
                대상자 목록
                <svg viewBox={"0 0 24 24"} width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M9 5l7 7-7 7" />
                </svg>
              </span>
            </span>
            <span className="stats">
              <span className="stat">
                <b>
                  {v.statCases}
                </b>
                <span>
                  담당 사례
                </span>
              </span>
              <span className="stat">
                <b>
                  {v.statWeek}
                </b>
                <span>
                  이번 주 상담
                </span>
              </span>
              <span className="stat">
                <b>
                  {v.statToday}
                </b>
                <span>
                  오늘 상담
                </span>
              </span>
            </span>
          </a>
          {v.loadErr ? <p className="note" role="alert" style={{ margin: "0", color: "var(--red)" }}>{v.loadErr}</p> : null}
          <div className="sec-h">
            <h2>
              시니어 상담 공지사항
            </h2>
            <span className="note">
              {v.unreadN}
            </span>
          </div>
          <section className="card list" aria-label="시니어 상담 공지사항">
            {(v.notices || []).map((n, i_n) => (
              <Fragment key={i_n}>
                <button type="button" className={n.cls} onClick={n.open}>
                  <span className="lt">
                    <b>
                      {n.title}
                    </b>
                    <span className="note">
                      {n.meta}
                    </span>
                  </span>
                  {n.imp ? (
                    <>
                      <span className="chip red">
                        중요
                      </span>
                    </>
                  ) : null}
                </button>
              </Fragment>
            ))}
          </section>
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
              <section className="sheet" role="dialog" aria-modal="true" aria-label="공지사항" onClick={v.stop}>
                <span className="grab" aria-hidden="true" />
                <div className="sh-hd">
                  <b>
                    {v.v.title}
                  </b>
                </div>
                <span className="note">
                  {v.v.meta}
                </span>
                <p className="body">
                  {v.v.body}
                </p>
                <button type="button" className="btn btn-block" onClick={v.shClose}>
                  닫기
                </button>
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
