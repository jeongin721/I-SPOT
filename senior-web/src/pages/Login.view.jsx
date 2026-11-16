// Login 화면 마크업 — tools/dc2jsx.py 가 디자인(Login.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './Login.css';

export default function View({ v }) {
  return (
    <div className="pg-Login">
      <div className={v.themeCls} style={{ minHeight: "720px", background: "#F4F9FD", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", alignItems: "center", justifyContent: "center", padding: "48px 24px", position: "relative" }}>
        <div className="thm-abs">
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
        <form style={{ width: "100%", maxWidth: "400px", background: "#FFFFFF", border: "1px solid #D0DCE5", borderRadius: "24px", boxShadow: "8px 8px 22px rgba(132,152,166,.30), -8px -8px 22px rgba(255,255,255,.95)", padding: "36px 34px", display: "flex", flexDirection: "column", gap: "18px" }} onSubmit={(e) => e.preventDefault()}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
            <span className="mk">
              온
            </span>
            <b style={{ fontSize: "20px" }}>
              온담
            </b>
          </div>
          <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <span className="lb">
              기관 이메일
            </span>
            <input className="inp" type="email" placeholder="name@기관.kr" value={v.email} onChange={v.setEmail} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <span className="lb">
              비밀번호
            </span>
            <input className="inp" type="password" defaultValue="password" />
          </label>
          <a className="btn btn-p" href={v.loginHref} style={{ width: "100%", marginTop: "4px" }}>
            로그인
          </a>
          <button type="button" className="btn btn-s" onClick={v.openCode} style={{ width: "100%" }}>
            회원가입
          </button>
          {v.joined ? (
            <>
              <p className="lb" role="status" style={{ margin: "-6px 0 0", fontWeight: "400", textAlign: "center" }}>
                회원가입 인증이 완료됐어요. 로그인해 주세요.
              </p>
            </>
          ) : null}
          <div role="group" aria-label="로그인 유형" className="lseg">
            {(v.roles || []).map((r, i_r) => (
              <Fragment key={i_r}>
                <button type="button" className={r.cls} aria-pressed={r.pressed} onClick={r.pick}>
                  {r.label}
                </button>
              </Fragment>
            ))}
          </div>
        </form>
        {v.suStep1 ? (
          <>
            <div className="sf-ov">
              <section role="dialog" aria-modal="true" aria-labelledby="su-title" className="sf-dlg" style={{ background: "#FFFFFF" }}>
                <div className="sf-top">
                  <h2 id="su-title" className="sf-title" aria-live="polite">
                    {v.suTitle}
                  </h2>
                  <button type="button" className="sf-x" aria-label="닫기" onClick={v.suClose}>
                    ×
                  </button>
                </div>
                <div className="sf-body">
                  {v.suShowName ? (
                    <>
                      <div className="sf-row sf-slide">
                        <label className={`sf-f ${v.suNameCls}`}>
                          <span className="sf-lb">
                            이름
                          </span>
                          <input type="text" placeholder="이름" value={v.suName} onChange={v.suSetName} onKeyDown={v.suKeyName} aria-label="이름" />
                        </label>
                      </div>
                    </>
                  ) : null}
                  {v.suShowBirth ? (
                    <>
                      <div className="sf-row sf-slide">
                        <label className={`sf-f ${v.suBirthCls}`}>
                          <span className="sf-lb">
                            생년월일
                          </span>
                          <input type="text" inputMode="numeric" maxLength="8" placeholder="예: 19990919" value={v.suBirth} onChange={v.suSetBirth} onKeyDown={v.suKeyBirth} aria-label="생년월일 8자리" />
                        </label>
                        {v.suBirthBad ? (
                          <>
                            <p className="sf-err">
                              올바른 날짜가 아닙니다.
                            </p>
                          </>
                        ) : null}
                      </div>
                    </>
                  ) : null}
                  {v.suShowSex ? (
                    <>
                      <div className="sf-row sf-slide">
                        <div className={`sf-f ${v.suSexCls}`}>
                          <span className="sf-lb">
                            성별
                          </span>
                          <div className="sf-sex" role="radiogroup" aria-label="성별">
                            {(v.suSexOpts || []).map((o, i_o) => (
                              <Fragment key={i_o}>
                                <button type="button" role="radio" aria-checked={o.on} className={o.cls} onClick={o.pick}>
                                  {o.label}
                                </button>
                              </Fragment>
                            ))}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : null}
                  {v.suShowPhone ? (
                    <>
                      <div className="sf-row sf-slide">
                        <label className={`sf-f ${v.suPhoneCls}`}>
                          <span className="sf-lb">
                            휴대폰 번호
                          </span>
                          <input type="tel" inputMode="numeric" maxLength="13" placeholder="예: 010-1234-5678" value={v.suPhone} onChange={v.suSetPhone} onKeyDown={v.suKeyPhone} aria-label="휴대폰 번호" />
                        </label>
                        {v.suPhoneBad ? (
                          <>
                            <p className="sf-err">
                              올바른 휴대폰 번호가 아닙니다.
                            </p>
                          </>
                        ) : null}
                      </div>
                    </>
                  ) : null}
                  {v.suShowEmail ? (
                    <>
                      <div className="sf-row sf-slide">
                        <div className={`sf-f ${v.suEmailCls}`}>
                          <span className="sf-lb">
                            이메일
                          </span>
                          <div className="sf-mail">
                            <input type="email" placeholder="name@기관.kr" value={v.suEmail} onChange={v.suSetEmail} onKeyDown={v.suKeyEmail} readOnly={v.suEmailLock} aria-label="이메일" />
                            {v.suSendOn ? (
                              <>
                                <button type="button" className="sf-get on" onClick={v.suResend}>
                                  인증번호 받기
                                </button>
                              </>
                            ) : null}
                            {v.suSendOff ? (
                              <>
                                <button type="button" className="sf-get" disabled={true}>
                                  {v.suSendLabel}
                                </button>
                              </>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : null}
                  {v.suShowCode ? (
                    <>
                      <div className="sf-row sf-code">
                        <label className="sf-f on">
                          <span className="sf-lb">
                            인증번호
                          </span>
                          <input type="text" inputMode="numeric" maxLength="6" placeholder="6자리 숫자" value={v.suCode} onChange={v.suSetCode} onKeyDown={v.suKeyCode} aria-label="인증번호" style={{ letterSpacing: ".2em" }} />
                        </label>
                        <div className="sf-sub">
                          <span className={v.suTimerCls}>
                            {v.suTimer}
                          </span>
                          <span style={{ flex: "1" }}>
                            {v.suSentNote}
                          </span>
                          <button type="button" className="sf-mini" onClick={v.suResend}>
                            다시 보내기
                          </button>
                        </div>
                      </div>
                    </>
                  ) : null}
                </div>
                {v.suNextOn ? (
                  <>
                    <button type="button" className="sf-next on" onClick={v.suNext}>
                      다음
                    </button>
                  </>
                ) : null}
                {v.suNextOff ? (
                  <>
                    <button type="button" className="sf-next" disabled={true}>
                      다음
                    </button>
                  </>
                ) : null}
              </section>
              {v.suWrong ? (
                <>
                  <div className="sf-ov sf-ov2">
                    <section role="alertdialog" aria-modal="true" aria-labelledby="su-wrong" className="sf-dlg sf-small" style={{ background: "#FFFFFF" }}>
                      <span className="sf-check sf-warn" aria-hidden="true">
                        !
                      </span>
                      <h2 id="su-wrong" className="sf-title" style={{ textAlign: "center" }}>
                        인증번호가 틀렸습니다.
                      </h2>
                      <button type="button" className="sf-next on" onClick={v.suWrongOk}>
                        확인
                      </button>
                    </section>
                  </div>
                </>
              ) : null}
            </div>
          </>
        ) : null}
        {v.suStep2 ? (
          <>
            <div className="sf-ov">
              <section role="dialog" aria-modal="true" aria-labelledby="su2-title" className="sf-dlg" style={{ background: "#FFFFFF" }}>
                <div className="sf-top">
                  <h2 id="su2-title" className="sf-title">
                    계정 정보를 입력하세요.
                  </h2>
                  <button type="button" className="sf-x" aria-label="닫기" onClick={v.suClose}>
                    ×
                  </button>
                </div>
                <div className="sf-body sf-down">
                  <label className="sf-f">
                    <span className="sf-lb">
                      이름
                    </span>
                    <input type="text" placeholder="이름" value={v.suName2} onChange={v.suSetName2} onKeyDown={v.suKeyName2} aria-label="이름" />
                  </label>
                  <label className="sf-f lock">
                    <span className="sf-lb">
                      {"아이디 "}
                      <span className="sf-note">
                        인증한 이메일 · 변경 불가
                      </span>
                    </span>
                    <input type="text" defaultValue={v.suEmail} readOnly={true} aria-readonly="true" aria-label="아이디" />
                  </label>
                  <div>
                    <div className="sf-f">
                      <label className="sf-lb" htmlFor="su-pw">
                        {"비밀번호 "}
                        <span className="sf-rule">
                          8~16자의 영문 대소문자, 숫자, 특수문자 포함
                        </span>
                      </label>
                      <div className="sf-pw">
                        <input id="su-pw" type={v.suPwType} value={v.suPw} onChange={v.suSetPw} onKeyDown={v.suKeyPw} maxLength="16" />
                        <button type="button" className="sf-eye" aria-label={v.suPwEyeLab} title={v.suPwEyeLab} aria-pressed={v.suPwShowP} onClick={v.suPwToggle}>
                          {v.suPwShow ? (
                            <>
                              <svg viewBox={"0 0 24 24"} width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M3 3l18 18" />
                                <path d="M10.6 5.1A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.2M6.1 6.1C3.5 7.8 2 12 2 12s3.5 7 10 7c1.6 0 3-.4 4.3-1" />
                                <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
                              </svg>
                            </>
                          ) : null}
                          {v.suPwShowN ? (
                            <>
                              <svg viewBox={"0 0 24 24"} width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
                                <circle cx="12" cy="12" r="3" />
                              </svg>
                            </>
                          ) : null}
                        </button>
                      </div>
                    </div>
                    {v.suPwRuleBad ? (
                      <>
                        <p className="sf-err" role="alert">
                          8~16자의 영문 대소문자, 숫자, 특수문자 포함
                        </p>
                      </>
                    ) : null}
                  </div>
                  <div>
                    <div className="sf-f">
                      <label className="sf-lb" htmlFor="su-pw2">
                        비밀번호 재입력
                      </label>
                      <div className="sf-pw">
                        <input id="su-pw2" type={v.suPw2Type} value={v.suPw2} onChange={v.suSetPw2} onKeyDown={v.suKeyPw2} />
                        <button type="button" className="sf-eye" aria-label={v.suPw2EyeLab} title={v.suPw2EyeLab} aria-pressed={v.suPw2ShowP} onClick={v.suPw2Toggle}>
                          {v.suPw2Show ? (
                            <>
                              <svg viewBox={"0 0 24 24"} width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M3 3l18 18" />
                                <path d="M10.6 5.1A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.2M6.1 6.1C3.5 7.8 2 12 2 12s3.5 7 10 7c1.6 0 3-.4 4.3-1" />
                                <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
                              </svg>
                            </>
                          ) : null}
                          {v.suPw2ShowN ? (
                            <>
                              <svg viewBox={"0 0 24 24"} width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
                                <circle cx="12" cy="12" r="3" />
                              </svg>
                            </>
                          ) : null}
                        </button>
                      </div>
                    </div>
                    {v.suPwBad ? (
                      <>
                        <p className="sf-err" role="alert">
                          동일한 비밀번호가 아닙니다.
                        </p>
                      </>
                    ) : null}
                  </div>
                </div>
                <div className="sf-btns">
                  <button type="button" className="sf-cancel" onClick={v.suClose}>
                    취소
                  </button>
                  {v.suDoneOn ? (
                    <>
                      <button type="button" className="sf-next on" onClick={v.suDone}>
                        완료
                      </button>
                    </>
                  ) : null}
                  {v.suDoneOff ? (
                    <>
                      <button type="button" className="sf-next" disabled={true}>
                        완료
                      </button>
                    </>
                  ) : null}
                </div>
              </section>
            </div>
          </>
        ) : null}
        {v.suStep3 ? (
          <>
            <div className="sf-ov">
              <section role="alertdialog" aria-modal="true" aria-labelledby="su3-title" className="sf-dlg sf-small" style={{ background: "#FFFFFF" }}>
                <span className="sf-check" aria-hidden="true">
                  ✓
                </span>
                <h2 id="su3-title" className="sf-title" style={{ textAlign: "center" }}>
                  회원가입이 완료되었습니다.
                </h2>
                <button type="button" className="sf-next on" onClick={v.suClose}>
                  확인
                </button>
              </section>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
