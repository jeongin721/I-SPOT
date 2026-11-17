// AppNext 화면 마크업 — tools/dc2jsx.py 가 디자인(AppNext.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './AppNext.css';

export default function View({ v }) {
  return (
    <div className="pg-AppNext">
      <div className={v.rootCls}>
        <header className="ahd">
          <a className="ibtn" href={v.backHref} aria-label="뒤로 가기">
            <svg viewBox={"0 0 24 24"} width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M15 5l-7 7 7 7" />
            </svg>
          </a>
          <div className="tl">
            <div className="sub">
              <a href="#/AppSchedule" style={{ color: "inherit" }}>
                ‹ 일정
              </a>
              {v.nextSub}
            </div>
            <h1 style={{ fontSize: "19px" }}>
              {v.nextTitle}
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
          {v.msg ? <p className="note" role="alert" style={{ margin: "0", color: "var(--red)" }}>{v.msg}</p> : null}
          <p className="sec-t">
            먼저 볼 것
          </p>
          <div className="card lead">
            <span className="lead-tag">
              어르신이 남긴 말씀
            </span>
            <b className="lead-main">
              {v.lead1}
            </b>
            <span className="src">
              {v.lead1Src}
            </span>
          </div>
          <div className="card lead">
            <span className="lead-tag">
              안부 응답 변화
            </span>
            <span className="lead-q">
              {v.lead2Q}
            </span>
            <b className="lead-main">
              {v.lead2From}
              <span className="arrow">
                →
              </span>
              {v.lead2To}
            </b>
            <span className="src">
              {v.lead2Src}
            </span>
          </div>
          <div className="card lead">
            <span className="lead-tag">
              처음 나온 이야기
            </span>
            <span className="lead-q">
              {v.lead3Q}
            </span>
            <b className="lead-main">
              {v.lead3}
            </b>
            <span className="src">
              {v.lead3Src}
            </span>
          </div>
          <p className="sec-t">
            {"확인할 사항 "}
            <span className="note">
              ({v.doneN}/{v.checkTotal})
            </span>
          </p>
          {(v.checks || []).map((c, i_c) => (
            <Fragment key={i_c}>
              <label className="rq">
                <input type="checkbox" checked={c.on} onChange={c.toggle} />
                <span>
                  {c.text}
                  <span className="src">
                    {c.src}
                  </span>
                </span>
              </label>
            </Fragment>
          ))}
          <p className="sec-t">
            {"추가 안부 질문 "}
            <span className="chip ai" style={{ marginLeft: "4px" }}>
              {v.draftChip}
            </span>
          </p>
          <div className="rq" style={{ cursor: "default" }}>
            <span className="chip">
              {v.q1.chip}
            </span>
            <span>
              {v.q1.text}
            </span>
          </div>
          <div className="rq" style={{ cursor: "default" }}>
            <span className="chip">
              {v.q2.chip}
            </span>
            <span>
              {v.q2.text}
            </span>
          </div>
          <div className="rq" style={{ cursor: "default" }}>
            <span className="chip">
              {v.q3.chip}
            </span>
            <span>
              {v.q3.text}
            </span>
          </div>
          <p className="note" style={{ margin: "0" }}>
            다음 상담 준비 내용 수정과 질문 편집은 웹에서 할 수 있어요. AI는 확인할 점을 제안할 뿐 판단하지 않으며, 최종 판단은 상담사가 합니다. AI 문구도 존댓말 · 존중 언어 원칙을 지켜요.
          </p>
          <a className="btn btn-p btn-block cta" href={v.recHref} onClick={v.goRec}>
            이 상담 녹음 시작
          </a>
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
