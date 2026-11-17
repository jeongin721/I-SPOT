// LoginTablet 화면 마크업 — tools/dc2jsx.py 가 디자인(LoginTablet.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './LoginTablet.css';

export default function View({ v }) {
  return (
    <div className="pg-LoginTablet">
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
        <form onSubmitCapture={v.submit} style={{ width: "100%", maxWidth: "400px", background: "#FFFFFF", border: "1px solid #D0DCE5", borderRadius: "24px", boxShadow: "8px 8px 22px rgba(132,152,166,.30), -8px -8px 22px rgba(255,255,255,.95)", padding: "36px 34px", display: "flex", flexDirection: "column", gap: "18px" }} onSubmit={(e) => e.preventDefault()}>
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
            <input className="inp" type="password" value={v.password} onChange={v.setPassword} autoComplete="current-password" />
          </label>
          <a className="btn btn-p" href={v.loginHref} onClick={v.submit} aria-disabled={v.busy} style={{ width: "100%", marginTop: "4px" }}>
            {v.submitLabel}
          </a>
          <button type="button" className="btn btn-s" onClick={v.openCode} style={{ width: "100%" }}>
            회원가입
          </button>
          {v.message ? (
            <p className="lb" role="alert" style={{ margin: "-6px 0 0", fontWeight: "400", textAlign: "center" }}>
              {v.message}
            </p>
          ) : null}
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
        {v.codeOpen ? (
          <>
            <div style={{ position: "absolute", inset: "0", zIndex: "10", background: "rgba(31,58,86,.40)", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" }}>
              <section role="dialog" aria-modal="true" aria-labelledby="code-title" style={{ width: "100%", maxWidth: "400px", background: "#FFFFFF", border: "1px solid #D0DCE5", borderRadius: "24px", boxShadow: "0 20px 60px rgba(31,58,86,.22)", padding: "30px 30px 26px", display: "flex", flexDirection: "column", gap: "16px" }}>
                <div>
                  <h2 id="code-title" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                    회원가입 인증번호 입력
                  </h2>
                  <p className="lb" style={{ margin: "6px 0 0", fontWeight: "400", lineHeight: "1.6" }}>
                    <b style={{ fontWeight: "700" }}>
                      {v.email}
                    </b>
                    {" 로 회원가입 인증번호 6자리를 보냈어요. 메일에서 확인 후 입력해 주세요."}
                  </p>
                </div>
                <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <span className="lb">
                    인증번호
                  </span>
                  <input className="inp" type="text" inputMode="numeric" maxLength="6" placeholder="6자리 숫자" value={v.code} onChange={v.setCode} style={{ letterSpacing: ".2em", fontSize: "18px", textAlign: "center" }} />
                </label>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px" }}>
                  <span className="lb" style={{ fontWeight: "400", flex: "1" }}>
                    {v.sentNote}
                  </span>
                  <button type="button" className="btn btn-s" onClick={v.resend} style={{ minHeight: "34px", padding: "0 14px", fontSize: "13px" }}>
                    다시 보내기
                  </button>
                </div>
                <div style={{ display: "flex", gap: "10px" }}>
                  <button type="button" className="btn btn-s" onClick={v.closeCode} style={{ flex: "1" }}>
                    취소
                  </button>
                  {v.codeOk ? (
                    <>
                      <button type="button" className="btn btn-p" onClick={v.confirmCode} style={{ flex: "1" }}>
                        확인
                      </button>
                    </>
                  ) : null}
                  {v.codeWait ? (
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
      </div>
    </div>
  );
}
