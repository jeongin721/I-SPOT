// Settings 화면 마크업 — tools/dc2jsx.py 가 디자인(Settings.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './Settings.css';

export default function View({ v }) {
  return (
    <div className="pg-Settings">
      <div className={v.themeCls} style={{ minHeight: "800px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
          <a className="logo" href="#/Home" onClick={v.leaveReset}>
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
            <a href="#/Home" onClick={v.leaveReset}>
              홈
            </a>
            <a href="#/CaseList" onClick={v.leaveReset}>
              대상자 관리
            </a>
            <a href="#/Schedule" onClick={v.leaveReset}>
              일정
            </a>
            <a href="#/ChildLink" onClick={v.leaveReset}>
              안부 연계
              <span className="cnt">
                {v.cntApp}
              </span>
            </a>
            <a href="#/Followup" onClick={v.leaveReset}>
              후속관리
              <span className="cnt">
                {v.cntFollow}
              </span>
            </a>
            <a href="#/DocBox" onClick={v.leaveReset}>
              문서함
            </a>
            <a href="#/LawGuide" onClick={v.leaveReset}>
              법령 · 매뉴얼
            </a>
            <a href="#/Stats" onClick={v.leaveReset}>
              통계
            </a>
            <a className="on" href="#/Settings" onClick={v.leaveReset}>
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
            <div style={{ flex: "1 1 300px" }}>
              <nav aria-label="위치" className="note">
                {v.inSub ? (
                  <>
                    <a href="#/Settings">
                      설정
                    </a>
                    {" › "}{v.subTitle}
                  </>
                ) : null}
                {v.atHome ? (
                  <>
                    설정
                  </>
                ) : null}
              </nav>
              <h1 style={{ margin: "2px 0 0", fontSize: "28px", fontWeight: "700" }}>
                {v.title}
              </h1>
            </div>
            {v.inSub ? (
              <>
                <button type="button" className="btn btn-s" onClick={v.goHome}>
                  ← 설정
                </button>
              </>
            ) : null}
          </header>
          {v.atHome ? (
            <>
              <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "18px", maxWidth: "900px" }}>
                <button type="button" className="pick" onClick={v.goAccount}>
                  <b style={{ fontSize: "20px" }}>
                    계정
                  </b>
                </button>
                <button type="button" className="pick" onClick={v.goNotify}>
                  <b style={{ fontSize: "20px" }}>
                    알림 설정
                  </b>
                </button>
              </section>
            </>
          ) : null}
          {v.isAccount ? (
            <>
              <section className="card" aria-label="계정" style={{ padding: "6px 26px 14px", maxWidth: "900px" }}>
                <div className="row">
                  <span className="lab">
                    상담사 이름
                  </span>
                  {v.nameView ? (
                    <>
                      <b style={{ flex: "1", fontWeight: "500" }}>
                        {v.name}
                      </b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.editName}>
                        수정
                      </button>
                    </>
                  ) : null}
                  {v.nameEdit ? (
                    <>
                      <input className="edit-in" type="text" aria-label="상담사 이름" value={v.draft} onChange={v.setDraft} />
                      <button type="button" className="btn btn-sm btn-p" onClick={v.saveName}>
                        저장
                      </button>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.cancel}>
                        취소
                      </button>
                    </>
                  ) : null}
                </div>
                <div className="row">
                  <span className="lab">
                    계정 (연결된 이메일)
                  </span>
                  {v.mailView ? (
                    <>
                      <b style={{ flex: "1", fontWeight: "500" }}>
                        {v.mail}
                      </b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.editMail}>
                        변경
                      </button>
                    </>
                  ) : null}
                  {v.mailEdit ? (
                    <>
                      <input className="edit-in" type="email" aria-label="이메일" value={v.draft} onChange={v.setDraft} />
                      <button type="button" className="btn btn-sm btn-p" onClick={v.saveMail}>
                        인증 메일 보내기
                      </button>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.cancel}>
                        취소
                      </button>
                    </>
                  ) : null}
                </div>
                <div className="row">
                  <span className="lab">
                    비밀번호
                  </span>
                  <span style={{ flex: "1" }} className="sub">
                    {v.pwText}
                  </span>
                  <button type="button" className={`btn btn-sm ${v.pwCls}`} onClick={v.resetPw}>
                    {v.pwLabel}
                  </button>
                </div>
                <div className="row">
                  <span className="lab">
                    휴대폰 번호
                  </span>
                  {v.phoneView ? (
                    <>
                      <b style={{ flex: "1", fontWeight: "500" }}>
                        {v.phone}
                      </b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.editPhone}>
                        수정
                      </button>
                    </>
                  ) : null}
                  {v.phoneEdit ? (
                    <>
                      <span style={{ flex: "1", display: "flex", flexDirection: "column", gap: "4px", minWidth: "0" }}>
                        <input className="edit-in" type="tel" inputMode="numeric" placeholder="010-0000-0000" aria-label="휴대폰 번호" value={v.draft} onChange={v.setPhoneDraft} />
                        {v.phoneErr ? (
                          <>
                            <span style={{ color: "#A33B2E", fontSize: "13px" }}>
                              올바른 휴대폰 번호가 아닙니다.
                            </span>
                          </>
                        ) : null}
                      </span>
                      <button type="button" className="btn btn-sm btn-p" onClick={v.savePhone}>
                        저장
                      </button>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.cancel}>
                        취소
                      </button>
                    </>
                  ) : null}
                </div>
                <div className="row" style={{ borderBottom: "0" }}>
                  <span className="lab">
                    소속 기관
                  </span>
                  <b style={{ flex: "1", fontWeight: "500" }}>
                    {v.org}
                  </b>
                </div>
              </section>
              {v.mailSent ? (
                <>
                  <p className="note" style={{ margin: "0" }}>
                    인증 메일 발송됨
                  </p>
                </>
              ) : null}
              <p className="note" role="status" style={{ margin: "0" }}>
                {v.accountNote}
              </p>
            </>
          ) : null}
          {v.isNotify ? (
            <>
              <section className="card" aria-label="알림 설정" style={{ padding: "6px 26px 14px", maxWidth: "900px" }}>
                {(v.toggles || []).map((t, i_t) => (
                  <Fragment key={i_t}>
                    <div className="row">
                      <b style={{ flex: "1", fontWeight: "500" }}>
                        {t.label}
                      </b>
                      <button type="button" className="sw" role="switch" aria-checked={t.on} aria-label={t.label} onClick={t.flip} style={{ background: t.bg }}>
                        <span style={{ left: t.x }} />
                      </button>
                    </div>
                  </Fragment>
                ))}
                <div className="row" style={{ borderBottom: "0" }}>
                  <b style={{ flex: "1", fontWeight: "500" }}>
                    어르신 안부 답변 묶음 시간
                  </b>
                  <select className="inp" aria-label="안부 답변 묶음 시간" value={v.batch} onChange={v.setBatch}>
                    <option>
                      08:30
                    </option>
                    <option>
                      09:00
                    </option>
                    <option>
                      13:00
                    </option>
                    <option>
                      17:00
                    </option>
                  </select>
                </div>
              </section>
              <p className="note" role="status" style={{ margin: "0" }}>
                {v.notifyNote}
              </p>
              {v.urgentOff ? (
                <>
                  <p className="acc" style={{ margin: "0", fontSize: "13px", fontWeight: "500" }}>
                    위기 신호 알림 꺼짐 · 어르신의 자살 생각 표현·위기 신호를 바로 알 수 없어요
                  </p>
                </>
              ) : null}
            </>
          ) : null}
          {v.pwOpen ? (
            <>
              <div style={{ position: "fixed", inset: "0", zIndex: "30", background: "rgba(31,58,86,.40)", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" }}>
                <section role="dialog" aria-modal="true" aria-labelledby="pw-title" style={{ width: "100%", maxWidth: "400px", background: "#FFFFFF", border: "1px solid #D0DCE5", borderRadius: "24px", boxShadow: "0 20px 60px rgba(31,58,86,.22)", padding: "30px 30px 26px", display: "flex", flexDirection: "column", gap: "16px" }}>
                  <div>
                    <h2 id="pw-title" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                      {v.pwTitle}
                    </h2>
                    <p className="sub" style={{ margin: "6px 0 0", lineHeight: "1.6" }}>
                      {v.pwDesc}
                    </p>
                  </div>
                  <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    <span className="sub" style={{ fontWeight: "500" }}>
                      {v.pwInLabel}
                    </span>
                    <input className="inp" type="password" autoComplete="current-password" value={v.pwIn} onChange={v.setPwIn} style={{ width: "100%" }} />
                  </label>
                  {v.pwChange ? (
                    <>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="sub" style={{ fontWeight: "500" }}>
                          새 비밀번호
                        </span>
                        <input className="inp" type="password" autoComplete="new-password" value={v.pwNew} onChange={v.setPwNew} style={{ width: "100%" }} />
                      </label>
                      <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <span className="sub" style={{ fontWeight: "500" }}>
                          새 비밀번호 확인
                        </span>
                        <input className="inp" type="password" autoComplete="new-password" value={v.pwNew2} onChange={v.setPwNew2} style={{ width: "100%" }} />
                      </label>
                      <p className="note" style={{ margin: "0" }}>
                        {v.pwRule}
                      </p>
                    </>
                  ) : null}
                  {v.pwErr ? (
                    <p className="req" role="alert" style={{ margin: "0", fontSize: "13px", fontWeight: "500", color: "#A33B2E" }}>
                      {v.pwErr}
                    </p>
                  ) : null}
                  <div style={{ display: "flex", gap: "10px" }}>
                    <button type="button" className="btn btn-s" onClick={v.closePw} style={{ flex: "1" }}>
                      취소
                    </button>
                    {v.pwOk ? (
                      <>
                        <button type="button" className="btn btn-p" onClick={v.submitPw} style={{ flex: "1" }}>
                          확인
                        </button>
                      </>
                    ) : null}
                    {v.pwWait ? (
                      <>
                        <button type="button" className="btn btn-p" disabled={true} style={{ flex: "1", opacity: ".45", cursor: "default" }}>
                          확인
                        </button>
                      </>
                    ) : null}
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
