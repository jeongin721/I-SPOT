// Upload 화면 마크업 — tools/dc2jsx.py 가 디자인(Upload.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './Upload.css';

export default function View({ v }) {
  return (
    <div className="pg-Upload">
      <div className={v.themeCls} style={{ minHeight: "1000px", background: "rgba(40,57,75,0.40)", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", color: "#1F3A56", display: "flex", alignItems: "center", justifyContent: "center", padding: "48px 16px", position: "relative" }}>
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
        <section role="dialog" aria-modal="true" aria-labelledby="up-title" style={{ width: "100%", maxWidth: "640px", background: "#FFFFFF", borderRadius: "24px", boxShadow: "0 20px 60px rgba(31, 58, 86,0.22)", overflow: "hidden" }}>
          <div style={{ padding: "24px 30px 18px", borderBottom: "1px solid #DDE6EC" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <h1 id="up-title" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                녹취 · 자료 올리기
              </h1>
              <a href={v.backHref} onClick={v.syncBack} aria-label="닫기" style={{ marginLeft: "auto", width: "40px", height: "40px", borderRadius: "50%", background: "#F8FBFD", display: "inline-flex", alignItems: "center", justifyContent: "center", textDecoration: "none", color: "#1F3A56", fontSize: "18px" }}>
                ×
              </a>
            </div>
            <ol aria-label="업로드 단계" style={{ listStyle: "none", margin: "14px 0 0", padding: "0", display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {(v.steps || []).map((s, i_s) => (
                <Fragment key={i_s}>
                  <li style={{ display: "inline-flex", alignItems: "center", gap: "6px", padding: "6px 12px 6px 6px", borderRadius: "999px", fontSize: "13px", background: s.bg, color: s.fg, fontWeight: s.fw }}>
                    <span style={{ width: "22px", height: "22px", borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: "12px", fontWeight: "700", background: s.dotBg, color: s.dotFg }}>
                      {s.mark}
                    </span>
                    {s.label}
                  </li>
                </Fragment>
              ))}
            </ol>
          </div>
          <div style={{ padding: "24px 30px", minHeight: "360px" }}>
            {v.s1 ? (
              <>
                <p className="lb">
                  어느 어르신의 자료인가요?
                </p>
                <input className="inp" type="search" aria-label="이름 또는 사례 ID 검색" placeholder="이름 또는 사례 ID 검색" style={{ width: "100%" }} />
                <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "10px", maxHeight: "320px", overflowY: "auto", paddingRight: "6px" }}>
                  {(v.cases || []).map((c, i_c) => (
                    <Fragment key={i_c}>
                      <button type="button" className="opt" onClick={c.pick} style={{ borderColor: c.bd, background: c.bg, font: "inherit", textAlign: "left" }}>
                        <span style={{ width: "18px", height: "18px", borderRadius: "50%", border: `2px solid ${c.dot}`, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: c.fill }} />
                        </span>
                        <span>
                          <b style={{ fontWeight: "500" }}>
                            {c.name}
                          </b>
                          <span className="note">
                            {c.meta}
                          </span>
                        </span>
                      </button>
                    </Fragment>
                  ))}
                </div>
                <div style={{ marginTop: "16px", padding: "14px 16px", borderRadius: "14px", border: "1px dashed #C5D4DE", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px" }}>
                  <span style={{ flex: "1 1 240px", fontSize: "13px" }}>
                    찾는 어르신이 없나요?
                  </span>
                  <a className="btn btn-sm btn-s" href="#/CaseRegister" onClick={v.resetFlow}>
                    + 새 사례 등록
                  </a>
                </div>
              </>
            ) : null}
            {v.s2 ? (
              <>
                <div style={{ padding: "12px 16px", borderRadius: "14px", background: "#F8FBFD", marginBottom: "16px" }}>
                  <b style={{ fontWeight: "500" }}>
                    {v.caseName}
                  </b>
                </div>
                <p className="lb">
                  몇 회차 상담인가요?
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "320px", overflowY: "auto", paddingRight: "6px" }}>
                  {(v.sessions || []).map((x, i_x) => (
                    <Fragment key={i_x}>
                      <button type="button" className="opt" onClick={x.pick} style={{ borderColor: x.bd, background: x.bg, font: "inherit", textAlign: "left" }}>
                        <span style={{ width: "18px", height: "18px", borderRadius: "50%", border: `2px solid ${x.dot}`, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: x.fill }} />
                        </span>
                        <span>
                          <b style={{ fontWeight: "500" }}>
                            {x.label}
                          </b>
                          <span className="note" style={{ display: "block" }}>
                            {x.meta}
                          </span>
                        </span>
                      </button>
                    </Fragment>
                  ))}
                </div>
              </>
            ) : null}
            {v.s3 ? (
              <>
                <div style={{ padding: "12px 16px", borderRadius: "14px", background: "#F8FBFD", marginBottom: "16px" }}>
                  <b style={{ fontWeight: "500" }}>
                    {v.caseName}
                  </b>
                  {" · "}{v.sesLabel}
                </div>
                <p className="lb">
                  파일 선택
                </p>
                <label style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "6px", padding: "26px", borderRadius: "16px", border: "1.5px dashed #C5D4DE", background: "#F8FBFD", cursor: "pointer", textAlign: "center" }}>
                  <span style={{ width: "52px", height: "52px", borderRadius: "50%", background: "#ECF5FA", display: "inline-flex", alignItems: "center", justifyContent: "center", color: "#55687A", fontSize: "22px", fontWeight: "700" }}>
                    ↑
                  </span>
                  <b style={{ fontWeight: "500" }}>
                    파일을 끌어 놓거나 눌러서 선택
                  </b>
                  <input type="file" aria-label="파일 선택" onChange={v.pickFile} style={{ fontSize: "13px", marginTop: "6px" }} />
                </label>
                {v.hasFile ? (
                  <>
                    <div style={{ marginTop: "12px", display: "flex", alignItems: "center", gap: "10px", padding: "10px 14px", borderRadius: "12px", border: "1px solid #D9E3EA" }}>
                      <span className="chip c-sky">
                        {v.fileKind}
                      </span>
                      <span style={{ flex: "1", minWidth: "0", overflowWrap: "anywhere" }}>
                        {v.fileName}
                      </span>
                      <span className="note">
                        {v.fileSize}
                      </span>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.clearFile} aria-label="선택한 파일 빼기">
                        빼기
                      </button>
                    </div>
                  </>
                ) : null}
                <div style={{ marginTop: "14px", display: "flex", flexWrap: "wrap", gap: "10px" }}>
                  <div className="fmt">
                    <b style={{ fontSize: "13px" }}>
                      음성 파일
                    </b>
                    <span className="note">
                      MP3 · M4A · WAV · 최대 2시간
                    </span>
                  </div>
                  <div className="fmt">
                    <b style={{ fontSize: "13px" }}>
                      문서 파일
                    </b>
                    <span className="note">
                      PDF · HWPX · DOCX · TXT
                    </span>
                  </div>
                </div>
                <div style={{ marginTop: "14px", padding: "12px 16px", borderRadius: "14px", border: "1px dashed #C5D4DE", display: "flex", flexDirection: "column", gap: "6px" }}>
                  <b style={{ fontSize: "13px" }}>
                    녹음 동의 확인
                  </b>
                  <span className="note">
                    어르신 본인(또는 대리 동의 시 사유 · 관계 기록)의 녹음 동의를 받은 상담만 올려 주세요. 동의 내용은 S-01 초기상담지에서 확인할 수 있어요. 가족 통화가 함께 녹음됐다면 가족에게도 녹음 사실을 알렸는지 확인해 주세요.
                  </span>
                  <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer" }}>
                    <input type="checkbox" aria-label="녹음 동의를 확인했어요" />
                    녹음 동의를 확인했어요
                  </label>
                </div>
              </>
            ) : null}
          </div>
          <div style={{ padding: "18px 30px 24px", display: "flex", alignItems: "center", gap: "10px", borderTop: "1px solid #DDE6EC" }}>
            {v.s1 ? (
              <>
                <a className="btn btn-s" href={v.backHref} onClick={v.syncBack}>
                  취소
                </a>
              </>
            ) : null}
            {v.notFirst ? (
              <>
                <button type="button" className="btn btn-s" onClick={v.prev}>
                  이전
                </button>
              </>
            ) : null}
            <span style={{ flex: "1" }} />
            {v.notLast ? (
              <>
                <button type="button" className="btn btn-p" onClick={v.next}>
                  다음
                </button>
              </>
            ) : null}
            {v.s3 ? (
              <>
                <button type="button" className="btn btn-p" onClick={v.upload}>
                  업로드
                </button>
              </>
            ) : null}
          </div>
        </section>
        {v.confirm ? (
          <>
            <div style={{ position: "absolute", inset: "0", background: "rgba(40,57,75,0.30)", display: "flex", alignItems: "center", justifyContent: "center", padding: "16px" }}>
              <section role="alertdialog" aria-labelledby="ok-title" style={{ width: "100%", maxWidth: "440px", background: "#FFFFFF", borderRadius: "22px", boxShadow: "0 20px 60px rgba(31, 58, 86,0.28)", padding: "28px 28px 22px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <span style={{ width: "48px", height: "48px", borderRadius: "50%", background: "#ECF5FA", color: "#55687A", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: "22px", fontWeight: "700" }}>
                  ✓
                </span>
                <h2 id="ok-title" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                  업로드했어요
                </h2>
                <p style={{ margin: "0" }}>
                  {v.caseName}{" · "}{v.sesLabel}{v.confirmFile}
                  <br />
                  {"STT 분석 시작 · "}
                  <b>
                    검수 화면으로 이동할까요?
                  </b>
                </p>
                <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: "6px" }}>
                  <a className="btn btn-s" href={v.backHref} onClick={v.syncBack}>
                    나중에
                  </a>
                  <a className="btn btn-p" href="#/Step1Record" onClick={v.resetFlow}>
                    이동
                  </a>
                </div>
              </section>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
