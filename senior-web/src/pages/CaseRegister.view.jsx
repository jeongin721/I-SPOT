// CaseRegister 화면 마크업 — tools/dc2jsx.py 가 디자인(CaseRegister.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './CaseRegister.css';

export default function View({ v }) {
  return (
    <div className="pg-CaseRegister">
      <div className={v.themeCls} style={{ minHeight: "1700px", background: "rgba(40,57,75,0.40)", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", color: "#1F3A56", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "48px 16px", position: "relative" }}>
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
        <section role="dialog" aria-modal="true" aria-labelledby="reg-title" style={{ width: "100%", maxWidth: "860px", background: "#FFFFFF", borderRadius: "24px", boxShadow: "0 20px 60px rgba(31, 58, 86,0.22)", overflow: "hidden" }}>
          <div style={{ padding: "24px 30px 0", display: "flex", alignItems: "flex-start", gap: "12px" }}>
            <div>
              <h1 id="reg-title" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                새 사례 등록
              </h1>
              <div className="note">
                S-01 초기상담지(시니어용) · 의뢰 · 접수 정보
              </div>
            </div>
            <a href={v.backHref} onClick={v.syncBack} aria-label="닫기" style={{ marginLeft: "auto", width: "40px", height: "40px", borderRadius: "50%", background: "#F8FBFD", display: "inline-flex", alignItems: "center", justifyContent: "center", textDecoration: "none", color: "#1F3A56", fontSize: "18px" }}>
              ×
            </a>
          </div>
          <div role="tablist" style={{ display: "flex", margin: "16px 30px 0", borderBottom: "1px solid #DDE6EC" }}>
            {(v.tabs || []).map((t, i_t) => (
              <Fragment key={i_t}>
                <button type="button" role="tab" className="tabb" aria-selected={t.sel} onClick={t.go} style={{ borderBottomColor: t.bd, color: t.fg, fontWeight: t.fw }}>
                  {t.label}
                </button>
              </Fragment>
            ))}
          </div>
          <form style={{ padding: "22px 30px", display: "flex", flexDirection: "column", gap: "18px" }} onSubmit={(e) => e.preventDefault()}>
            {v.isA ? (
              <>
                <div className="rg-grp">
                  <div className="rg4">
                    <label className="fl">
                      <span className="lb">
                        {"상담 접수일 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <span className="dpw">
                        <input className="inp dpi" type="text" inputMode="numeric" placeholder="YYYY-MM-DD" maxLength="10" value={v.fv.report} onChange={v.fs.report} style={{ borderColor: v.fe.report }} aria-invalid={v.fi.report} aria-label="상담 접수일" />
                        <button type="button" className="dp-btn" aria-label="상담 접수일 달력 열기" aria-expanded={v.dp.report.exp} onClick={v.dp.report.toggle}>
                          <svg viewBox={"0 0 24 24"} width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <rect x="3" y="5" width="18" height="16" rx="2" />
                            <path d="M16 3v4M8 3v4M3 10h18" />
                          </svg>
                        </button>
                        {v.dp.report.open ? (
                          <>
                            <span className="dp-bd" onClick={v.dp.report.close} />
                            <span className="dp-pop" role="dialog" aria-label="상담 접수일 선택">
                              {v.dp.report.isY ? (
                                <>
                                  <span className="dp-hd">
                                    <b>
                                      연도 선택
                                    </b>
                                  </span>
                                  <span className="dp-years" id={v.dp.report.listId}>
                                    {(v.dp.report.years || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-y ${o.cls}`} id={o.id} aria-pressed={o.on} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.report.isM ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="연도 선택으로" onClick={v.dp.report.toY}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.report.yLabel}
                                    </b>
                                  </span>
                                  <span className="dp-months">
                                    {(v.dp.report.months || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-m ${o.cls}`} disabled={o.dis} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.report.isD ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="월 선택으로" onClick={v.dp.report.toM}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.report.ymLabel}
                                    </b>
                                    <span style={{ marginLeft: "auto", display: "inline-flex", gap: "6px" }}>
                                      <button type="button" className="dp-nav" aria-label="이전 달" disabled={v.dp.report.prevDis} onClick={v.dp.report.prev}>
                                        ‹
                                      </button>
                                      <button type="button" className="dp-nav" aria-label="다음 달" disabled={v.dp.report.nextDis} onClick={v.dp.report.next}>
                                        ›
                                      </button>
                                    </span>
                                  </span>
                                  <span className="dp-days">
                                    {(v.dp.report.dows || []).map((w, i_w) => (
                                      <Fragment key={i_w}>
                                        <span className="dp-dow">
                                          {w}
                                        </span>
                                      </Fragment>
                                    ))}
                                    {(v.dp.report.days || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        {o.blank ? (
                                          <>
                                            <span />
                                          </>
                                        ) : null}
                                        {o.real ? (
                                          <>
                                            <button type="button" className={`dp-d ${o.cls}`} disabled={o.dis} aria-label={o.aria} onClick={o.pick}>
                                              {o.n}
                                            </button>
                                          </>
                                        ) : null}
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                            </span>
                          </>
                        ) : null}
                      </span>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        {"의뢰일 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <span className="dpw">
                        <input className="inp dpi" type="text" inputMode="numeric" placeholder="YYYY-MM-DD" maxLength="10" value={v.fv.link} onChange={v.fs.link} style={{ borderColor: v.fe.link }} aria-invalid={v.fi.link} aria-label="의뢰일" />
                        <button type="button" className="dp-btn" aria-label="의뢰일 달력 열기" aria-expanded={v.dp.link.exp} onClick={v.dp.link.toggle}>
                          <svg viewBox={"0 0 24 24"} width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <rect x="3" y="5" width="18" height="16" rx="2" />
                            <path d="M16 3v4M8 3v4M3 10h18" />
                          </svg>
                        </button>
                        {v.dp.link.open ? (
                          <>
                            <span className="dp-bd" onClick={v.dp.link.close} />
                            <span className="dp-pop" role="dialog" aria-label="의뢰일 선택">
                              {v.dp.link.isY ? (
                                <>
                                  <span className="dp-hd">
                                    <b>
                                      연도 선택
                                    </b>
                                  </span>
                                  <span className="dp-years" id={v.dp.link.listId}>
                                    {(v.dp.link.years || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-y ${o.cls}`} id={o.id} aria-pressed={o.on} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.link.isM ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="연도 선택으로" onClick={v.dp.link.toY}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.link.yLabel}
                                    </b>
                                  </span>
                                  <span className="dp-months">
                                    {(v.dp.link.months || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-m ${o.cls}`} disabled={o.dis} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.link.isD ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="월 선택으로" onClick={v.dp.link.toM}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.link.ymLabel}
                                    </b>
                                    <span style={{ marginLeft: "auto", display: "inline-flex", gap: "6px" }}>
                                      <button type="button" className="dp-nav" aria-label="이전 달" disabled={v.dp.link.prevDis} onClick={v.dp.link.prev}>
                                        ‹
                                      </button>
                                      <button type="button" className="dp-nav" aria-label="다음 달" disabled={v.dp.link.nextDis} onClick={v.dp.link.next}>
                                        ›
                                      </button>
                                    </span>
                                  </span>
                                  <span className="dp-days">
                                    {(v.dp.link.dows || []).map((w, i_w) => (
                                      <Fragment key={i_w}>
                                        <span className="dp-dow">
                                          {w}
                                        </span>
                                      </Fragment>
                                    ))}
                                    {(v.dp.link.days || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        {o.blank ? (
                                          <>
                                            <span />
                                          </>
                                        ) : null}
                                        {o.real ? (
                                          <>
                                            <button type="button" className={`dp-d ${o.cls}`} disabled={o.dis} aria-label={o.aria} onClick={o.pick}>
                                              {o.n}
                                            </button>
                                          </>
                                        ) : null}
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                            </span>
                          </>
                        ) : null}
                      </span>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        초기상담일
                      </span>
                      <span className="dpw">
                        <input className="inp dpi" type="text" inputMode="numeric" placeholder="YYYY-MM-DD" maxLength="10" value={v.fv.first} onChange={v.fs.first} aria-label="초기상담일" />
                        <button type="button" className="dp-btn" aria-label="초기상담일 달력 열기" aria-expanded={v.dp.first.exp} onClick={v.dp.first.toggle}>
                          <svg viewBox={"0 0 24 24"} width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <rect x="3" y="5" width="18" height="16" rx="2" />
                            <path d="M16 3v4M8 3v4M3 10h18" />
                          </svg>
                        </button>
                        {v.dp.first.open ? (
                          <>
                            <span className="dp-bd" onClick={v.dp.first.close} />
                            <span className="dp-pop" role="dialog" aria-label="초기상담일 선택">
                              {v.dp.first.isY ? (
                                <>
                                  <span className="dp-hd">
                                    <b>
                                      연도 선택
                                    </b>
                                  </span>
                                  <span className="dp-years" id={v.dp.first.listId}>
                                    {(v.dp.first.years || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-y ${o.cls}`} id={o.id} aria-pressed={o.on} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.first.isM ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="연도 선택으로" onClick={v.dp.first.toY}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.first.yLabel}
                                    </b>
                                  </span>
                                  <span className="dp-months">
                                    {(v.dp.first.months || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-m ${o.cls}`} disabled={o.dis} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.first.isD ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="월 선택으로" onClick={v.dp.first.toM}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.first.ymLabel}
                                    </b>
                                    <span style={{ marginLeft: "auto", display: "inline-flex", gap: "6px" }}>
                                      <button type="button" className="dp-nav" aria-label="이전 달" disabled={v.dp.first.prevDis} onClick={v.dp.first.prev}>
                                        ‹
                                      </button>
                                      <button type="button" className="dp-nav" aria-label="다음 달" disabled={v.dp.first.nextDis} onClick={v.dp.first.next}>
                                        ›
                                      </button>
                                    </span>
                                  </span>
                                  <span className="dp-days">
                                    {(v.dp.first.dows || []).map((w, i_w) => (
                                      <Fragment key={i_w}>
                                        <span className="dp-dow">
                                          {w}
                                        </span>
                                      </Fragment>
                                    ))}
                                    {(v.dp.first.days || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        {o.blank ? (
                                          <>
                                            <span />
                                          </>
                                        ) : null}
                                        {o.real ? (
                                          <>
                                            <button type="button" className={`dp-d ${o.cls}`} disabled={o.dis} aria-label={o.aria} onClick={o.pick}>
                                              {o.n}
                                            </button>
                                          </>
                                        ) : null}
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                            </span>
                          </>
                        ) : null}
                      </span>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        {"사례번호 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <input className="inp" type="text" value={v.fv.no} onChange={v.fs.no} style={{ borderColor: v.fe.no }} aria-invalid={v.fi.no} />
                    </label>
                  </div>
                </div>
                <div className="rg-grp">
                  <div className="rg3">
                    <label className="fl">
                      <span className="lb">
                        {"성명 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <input className="inp" type="text" placeholder="이름" value={v.fv.name} onChange={v.fs.name} style={{ borderColor: v.fe.name }} aria-invalid={v.fi.name} />
                    </label>
                    <label className="fl">
                      <span className="lb">
                        {"성별 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <select className="inp" value={v.fv.sex} onChange={v.fs.sex} style={{ borderColor: v.fe.sex }} aria-invalid={v.fi.sex}>
                        <option>
                          선택
                        </option>
                        <option>
                          여
                        </option>
                        <option>
                          남
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        {"생년월일 (연령) "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <span className="dpw">
                        <input className="inp dpi" type="text" inputMode="numeric" placeholder="YYYY-MM-DD" maxLength="10" value={v.fv.birth} onChange={v.fs.birth} style={{ borderColor: v.fe.birth }} aria-invalid={v.fi.birth} aria-label="생년월일" />
                        <button type="button" className="dp-btn" aria-label="생년월일 달력 열기" aria-expanded={v.dp.birth.exp} onClick={v.dp.birth.toggle}>
                          <svg viewBox={"0 0 24 24"} width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <rect x="3" y="5" width="18" height="16" rx="2" />
                            <path d="M16 3v4M8 3v4M3 10h18" />
                          </svg>
                        </button>
                        {v.dp.birth.open ? (
                          <>
                            <span className="dp-bd" onClick={v.dp.birth.close} />
                            <span className="dp-pop" role="dialog" aria-label="생년월일 선택">
                              {v.dp.birth.isY ? (
                                <>
                                  <span className="dp-hd">
                                    <b>
                                      연도 선택
                                    </b>
                                  </span>
                                  <span className="dp-years" id={v.dp.birth.listId}>
                                    {(v.dp.birth.years || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-y ${o.cls}`} id={o.id} aria-pressed={o.on} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.birth.isM ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="연도 선택으로" onClick={v.dp.birth.toY}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.birth.yLabel}
                                    </b>
                                  </span>
                                  <span className="dp-months">
                                    {(v.dp.birth.months || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-m ${o.cls}`} disabled={o.dis} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.birth.isD ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="월 선택으로" onClick={v.dp.birth.toM}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.birth.ymLabel}
                                    </b>
                                    <span style={{ marginLeft: "auto", display: "inline-flex", gap: "6px" }}>
                                      <button type="button" className="dp-nav" aria-label="이전 달" disabled={v.dp.birth.prevDis} onClick={v.dp.birth.prev}>
                                        ‹
                                      </button>
                                      <button type="button" className="dp-nav" aria-label="다음 달" disabled={v.dp.birth.nextDis} onClick={v.dp.birth.next}>
                                        ›
                                      </button>
                                    </span>
                                  </span>
                                  <span className="dp-days">
                                    {(v.dp.birth.dows || []).map((w, i_w) => (
                                      <Fragment key={i_w}>
                                        <span className="dp-dow">
                                          {w}
                                        </span>
                                      </Fragment>
                                    ))}
                                    {(v.dp.birth.days || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        {o.blank ? (
                                          <>
                                            <span />
                                          </>
                                        ) : null}
                                        {o.real ? (
                                          <>
                                            <button type="button" className={`dp-d ${o.cls}`} disabled={o.dis} aria-label={o.aria} onClick={o.pick}>
                                              {o.n}
                                            </button>
                                          </>
                                        ) : null}
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                            </span>
                          </>
                        ) : null}
                      </span>
                    </label>
                  </div>
                </div>
                <div className="rg-grp">
                  <div className="rg3">
                    <label className="fl">
                      <span className="lb">
                        연락처
                      </span>
                      <input className="inp" type="text" inputMode="tel" placeholder="010-0000-0000" />
                    </label>
                    <label className="fl">
                      <span className="lb">
                        주소
                      </span>
                      <input className="inp" type="text" placeholder="시·군·구 / 읍·면·동" />
                    </label>
                    <label className="fl">
                      <span className="lb">
                        비상연락 가족 (이름 · 관계 · 연락처)
                      </span>
                      <input className="inp" type="text" placeholder="예: 이정훈 · 아들 · 010-0000-0000" />
                    </label>
                  </div>
                </div>
                <div className="rg-grp">
                  <div className="rg3">
                    <label className="fl">
                      <span className="lb">
                        {"주 돌봄자 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <input className="inp" type="text" placeholder="이름 (없으면 '없음')" value={v.fv.target} onChange={v.fs.target} style={{ borderColor: v.fe.target }} aria-invalid={v.fi.target} />
                    </label>
                    <label className="fl">
                      <span className="lb">
                        {"관계 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <select className="inp" value={v.fv.rel} onChange={v.fs.rel} style={{ borderColor: v.fe.rel }} aria-invalid={v.fi.rel}>
                        <option>
                          선택
                        </option>
                        <option>
                          배우자
                        </option>
                        <option>
                          아들
                        </option>
                        <option>
                          딸
                        </option>
                        <option>
                          며느리
                        </option>
                        <option>
                          사위
                        </option>
                        <option>
                          손자녀
                        </option>
                        <option>
                          형제자매
                        </option>
                        <option>
                          친척
                        </option>
                        <option>
                          이웃 · 지인
                        </option>
                        <option>
                          없음
                        </option>
                        <option>
                          기타
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        주 돌봄자 생년월일 (연령)
                      </span>
                      <span className="dpw">
                        <input className="inp dpi" type="text" inputMode="numeric" placeholder="YYYY-MM-DD" maxLength="10" value={v.fv.tbirth} onChange={v.fs.tbirth} aria-label="주 돌봄자 생년월일" />
                        <button type="button" className="dp-btn" aria-label="주 돌봄자 생년월일 달력 열기" aria-expanded={v.dp.tbirth.exp} onClick={v.dp.tbirth.toggle}>
                          <svg viewBox={"0 0 24 24"} width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <rect x="3" y="5" width="18" height="16" rx="2" />
                            <path d="M16 3v4M8 3v4M3 10h18" />
                          </svg>
                        </button>
                        {v.dp.tbirth.open ? (
                          <>
                            <span className="dp-bd" onClick={v.dp.tbirth.close} />
                            <span className="dp-pop" role="dialog" aria-label="주 돌봄자 생년월일 선택">
                              {v.dp.tbirth.isY ? (
                                <>
                                  <span className="dp-hd">
                                    <b>
                                      연도 선택
                                    </b>
                                  </span>
                                  <span className="dp-years" id={v.dp.tbirth.listId}>
                                    {(v.dp.tbirth.years || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-y ${o.cls}`} id={o.id} aria-pressed={o.on} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.tbirth.isM ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="연도 선택으로" onClick={v.dp.tbirth.toY}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.tbirth.yLabel}
                                    </b>
                                  </span>
                                  <span className="dp-months">
                                    {(v.dp.tbirth.months || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        <button type="button" className={`dp-m ${o.cls}`} disabled={o.dis} onClick={o.pick}>
                                          {o.label}
                                        </button>
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                              {v.dp.tbirth.isD ? (
                                <>
                                  <span className="dp-hd">
                                    <button type="button" className="dp-nav" aria-label="월 선택으로" onClick={v.dp.tbirth.toM}>
                                      ←
                                    </button>
                                    <b>
                                      {v.dp.tbirth.ymLabel}
                                    </b>
                                    <span style={{ marginLeft: "auto", display: "inline-flex", gap: "6px" }}>
                                      <button type="button" className="dp-nav" aria-label="이전 달" disabled={v.dp.tbirth.prevDis} onClick={v.dp.tbirth.prev}>
                                        ‹
                                      </button>
                                      <button type="button" className="dp-nav" aria-label="다음 달" disabled={v.dp.tbirth.nextDis} onClick={v.dp.tbirth.next}>
                                        ›
                                      </button>
                                    </span>
                                  </span>
                                  <span className="dp-days">
                                    {(v.dp.tbirth.dows || []).map((w, i_w) => (
                                      <Fragment key={i_w}>
                                        <span className="dp-dow">
                                          {w}
                                        </span>
                                      </Fragment>
                                    ))}
                                    {(v.dp.tbirth.days || []).map((o, i_o) => (
                                      <Fragment key={i_o}>
                                        {o.blank ? (
                                          <>
                                            <span />
                                          </>
                                        ) : null}
                                        {o.real ? (
                                          <>
                                            <button type="button" className={`dp-d ${o.cls}`} disabled={o.dis} aria-label={o.aria} onClick={o.pick}>
                                              {o.n}
                                            </button>
                                          </>
                                        ) : null}
                                      </Fragment>
                                    ))}
                                  </span>
                                </>
                              ) : null}
                            </span>
                          </>
                        ) : null}
                      </span>
                    </label>
                  </div>
                </div>
                <div className="rg-grp">
                  <div className="rg2">
                    <label className="fl">
                      <span className="lb">
                        {"의뢰 경로 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <select className="inp" value={v.fv.m1} onChange={v.fs.m1} style={{ borderColor: v.fe.m1 }} aria-invalid={v.fi.m1}>
                        <option>
                          선택
                        </option>
                        <option>
                          본인
                        </option>
                        <option>
                          가족
                        </option>
                        <option>
                          행정복지센터(읍·면·동)
                        </option>
                        <option>
                          노인맞춤돌봄 수행기관(생활지원사)
                        </option>
                        <option>
                          의료기관
                        </option>
                        <option>
                          치매안심센터
                        </option>
                        <option>
                          정신건강복지센터
                        </option>
                        <option>
                          노인복지관 · 경로당
                        </option>
                        <option>
                          이웃 · 지인
                        </option>
                        <option>
                          기타
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        {"주 상담 영역 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <select className="inp" value={v.fv.m2} onChange={v.fs.m2} style={{ borderColor: v.fe.m2 }} aria-invalid={v.fi.m2}>
                        <option>
                          선택
                        </option>
                        <option>
                          정서·우울
                        </option>
                        <option>
                          상실·애도
                        </option>
                        <option>
                          고립·외로움
                        </option>
                        <option>
                          건강·인지
                        </option>
                        <option>
                          가족관계
                        </option>
                        <option>
                          경제·주거
                        </option>
                        <option>
                          생활 적응·여가
                        </option>
                        <option>
                          삶의 정리·죽음 준비
                        </option>
                      </select>
                    </label>
                  </div>
                </div>
                <div className="rg-grp">
                  <div className="rg3">
                    <label className="fl">
                      <span className="lb">
                        의뢰인 / 관계
                      </span>
                      <input className="inp" type="text" placeholder="예: 박○○ / 맞춤돌봄 생활지원사" />
                    </label>
                    <label className="fl">
                      <span className="lb">
                        담당 상담사
                      </span>
                      <input className="inp" type="text" defaultValue="이서연" />
                    </label>
                    <label className="fl">
                      <span className="lb">
                        위기도 (초기 판단)
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          일반
                        </option>
                        <option>
                          관심
                        </option>
                        <option>
                          집중
                        </option>
                        <option>
                          위기
                        </option>
                      </select>
                    </label>
                  </div>
                </div>
                <label className="fl">
                  <span className="lb">
                    {"주호소 "}
                    <span className="req">
                      *
                    </span>
                  </span>
                  <textarea className="ta2" rows="7" placeholder="어르신이 말씀하신 어려움 · 의뢰 경위 · 의뢰인이 관찰한 내용 (어르신의 말씀 중심으로 기재)" value={v.fv.how} onChange={v.fs.how} style={{ borderColor: v.fe.how, minHeight: "180px" }} aria-invalid={v.fi.how} />
                  <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                    <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                      <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                    </svg>
                    <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M5 12.5l4.5 4.5L19 7.5" />
                    </svg>
                  </button>
                  <span className="cp-menu" role="menu" aria-label="복사 방식">
                    <button type="button" role="menuitem" onClick={v.copyRaw}>
                      그대로 복사
                    </button>
                    <button type="button" role="menuitem" onClick={v.copyMask}>
                      이름 가려서 복사
                      <span className="cp-ex">
                        예) 김○자
                      </span>
                    </button>
                  </span>
                </label>
                <div className="sec">
                  {"상담 동의 "}
                  <span className="note" style={{ fontWeight: "400" }}>
                    (어르신 본인의 자기결정 존중)
                  </span>
                </div>
                <div className="rg-grp">
                  <div className="rg4">
                    <label className="fl">
                      <span className="lb">
                        {"상담 동의 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <select className="inp" value={v.fv.consent} onChange={v.fs.consent} style={{ borderColor: v.fe.consent }} aria-invalid={v.fi.consent}>
                        <option>
                          선택
                        </option>
                        <option>
                          본인 동의
                        </option>
                        <option>
                          대리 동의
                        </option>
                        <option>
                          동의 보류
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        대리 동의 시 사유 · 관계
                      </span>
                      <input className="inp" type="text" placeholder="예: 동의능력 확인 어려움 · 아들" />
                    </label>
                    <label className="fl">
                      <span className="lb">
                        {"가족 정보 공유 범위 "}
                        <span className="req">
                          *
                        </span>
                      </span>
                      <select className="inp" value={v.fv.share} onChange={v.fs.share} style={{ borderColor: v.fe.share }} aria-invalid={v.fi.share}>
                        <option>
                          선택
                        </option>
                        <option>
                          공유 동의
                        </option>
                        <option>
                          일부 동의
                        </option>
                        <option>
                          미동의
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        녹음 동의
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          동의
                        </option>
                        <option>
                          미동의
                        </option>
                      </select>
                    </label>
                  </div>
                </div>
                <label className="fl">
                  <span className="lb">
                    공유 가능 범위 메모
                  </span>
                  <input className="inp" type="text" placeholder="예: 상담 일정 · 건강 관련만 아들에게 공유 / 정서 상담 내용은 비공개" />
                </label>
                <p className="note" style={{ margin: "-8px 0 0" }}>
                  *판단능력 있는 성인으로서 원하지 않으시면 언제든 상담 · 개입을 멈출 수 있음을 안내합니다. 가족 공유는 어르신이 동의한 범위 안에서만 합니다. 동의능력이 불확실해 보여도 상담사는 진단하지 않으며, 필요하면 치매안심센터 연계를 검토합니다.
                </p>
                <div className="sec">
                  의사소통 고려사항
                </div>
                <div className="rg-grp">
                  <div className="rg3">
                    <label className="fl">
                      <span className="lb">
                        청력 · 보청기
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          양호
                        </option>
                        <option>
                          잘 안 들림(크게 · 천천히)
                        </option>
                        <option>
                          보청기 사용
                        </option>
                        <option>
                          한쪽 청력 저하
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        시력
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          양호
                        </option>
                        <option>
                          안경 사용
                        </option>
                        <option>
                          저하
                        </option>
                        <option>
                          거의 보이지 않음
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        큰 글씨 자료
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          필요
                        </option>
                        <option>
                          필요 없음
                        </option>
                      </select>
                    </label>
                  </div>
                </div>
                <div className="rg-grp">
                  <div className="rg2">
                    <label className="fl">
                      <span className="lb">
                        사투리 · 말 속도
                      </span>
                      <input className="inp" type="text" placeholder="예: 경상도 말씨 · 천천히 말씀하심 · 반복 확인 필요" />
                    </label>
                    <label className="fl">
                      <span className="lb">
                        선호 호칭
                      </span>
                      <input className="inp" type="text" placeholder="예: 김순자 님 / 선생님" />
                    </label>
                  </div>
                </div>
              </>
            ) : null}
            {v.isB ? (
              <>
                <div className="sec">
                  {"주요 어려움 · 정서 · 위기 신호 "}
                  <span className="note" style={{ fontWeight: "400" }}>
                    (복수응답 가능)
                  </span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {(v.homes || []).map((o, i_o) => (
                    <Fragment key={i_o}>
                      <button type="button" className="pk" onClick={o.toggle} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                        {o.mark}{" "}{o.label}
                      </button>
                    </Fragment>
                  ))}
                </div>
                {v.hmEdit ? (
                  <>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px" }}>
                      <input className="inp" type="text" placeholder="기타 내용 직접 입력" aria-label="주요 어려움 기타 직접 입력" value={v.hmDraft} onChange={v.hmDraftSet} style={{ flex: "1 1 280px", minWidth: "0", height: "36px" }} />
                      <button type="button" className="btn btn-p btn-sm" onClick={v.hmOk}>
                        확인
                      </button>
                      <button type="button" className="btn btn-s btn-sm" onClick={v.hmCancel}>
                        취소
                      </button>
                    </div>
                  </>
                ) : null}
                <p className="note" style={{ margin: "-8px 0 0" }}>
                  *자살 생각 표현이 있으면 S-04 자살위험 선별을 먼저 하고 자살예방상담 109를 안내합니다. 학대 정황이 보이면 노인보호전문기관(1577-1389) 연계를 검토합니다(노인복지법상 의무).
                </p>
                <label className="fl">
                  <span className="lb">
                    주 돌봄자 · 가족과의 관계
                  </span>
                  <textarea className="ta2 ta1" rows="1" aria-label="주 돌봄자 · 가족과의 관계" />
                  <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                    <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                      <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                    </svg>
                    <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M5 12.5l4.5 4.5L19 7.5" />
                    </svg>
                  </button>
                  <span className="cp-menu" role="menu" aria-label="복사 방식">
                    <button type="button" role="menuitem" onClick={v.copyRaw}>
                      그대로 복사
                    </button>
                    <button type="button" role="menuitem" onClick={v.copyMask}>
                      이름 가려서 복사
                      <span className="cp-ex">
                        예) 김○자
                      </span>
                    </button>
                  </span>
                </label>
                <div className="sec">
                  가구형태
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {(v.fams || []).map((o, i_o) => (
                    <Fragment key={i_o}>
                      <button type="button" className="pk" onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                        {o.label}
                      </button>
                    </Fragment>
                  ))}
                </div>
                {v.famEdit ? (
                  <>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px" }}>
                      {v.famIsInst ? (
                        <>
                          <span style={{ fontSize: "13px", fontWeight: "700" }}>
                            시설:
                          </span>
                        </>
                      ) : null}
                      <input className="inp" type="text" placeholder={v.famPh} aria-label={v.famAria} value={v.famDraft} onChange={v.famDraftSet} style={{ flex: "1 1 260px", minWidth: "0", height: "36px" }} />
                      <button type="button" className="btn btn-p btn-sm" onClick={v.famOk}>
                        확인
                      </button>
                      <button type="button" className="btn btn-s btn-sm" onClick={v.famCancel}>
                        취소
                      </button>
                    </div>
                  </>
                ) : null}
                <div className="sec">
                  가족관계
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="ft ftg">
                    <thead>
                      <tr>
                        <th>
                          성명
                        </th>
                        <th>
                          관계
                        </th>
                        <th>
                          나이
                        </th>
                        <th>
                          연락처
                        </th>
                        <th>
                          거주지
                        </th>
                        <th>
                          연락 빈도
                        </th>
                        <th>
                          동거여부
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {(v.famRows || []).map((r, i_r) => (
                        <Fragment key={i_r}>
                          <tr>
                            <td>
                              <input aria-label="성명" />
                            </td>
                            <td>
                              <input aria-label="관계" />
                            </td>
                            <td>
                              <input aria-label="나이" />
                            </td>
                            <td>
                              <input aria-label="연락처" />
                            </td>
                            <td>
                              <input aria-label="거주지" />
                            </td>
                            <td>
                              <input aria-label="연락 빈도" />
                            </td>
                            <td>
                              <input aria-label="동거여부" />
                            </td>
                          </tr>
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
                <button type="button" className="btn btn-sm btn-s" style={{ alignSelf: "flex-start" }} onClick={v.addRow}>
                  + 가족 추가
                </button>
                <div className="sec">
                  {"일상생활 · 도움이 필요한 활동 "}
                  <span className="note" style={{ fontWeight: "400" }}>
                    (ADL · IADL 간단 체크 · 복수응답 가능)
                  </span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {(v.traits || []).map((o, i_o) => (
                    <Fragment key={i_o}>
                      <button type="button" className="pk" onClick={o.toggle} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                        {o.mark}{" "}{o.label}
                      </button>
                    </Fragment>
                  ))}
                </div>
                {v.trEdit ? (
                  <>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px" }}>
                      <input className="inp" type="text" placeholder="기타 내용 직접 입력" aria-label="일상생활 기타 직접 입력" value={v.trDraft} onChange={v.trDraftSet} style={{ flex: "1 1 280px", minWidth: "0", height: "36px" }} />
                      <button type="button" className="btn btn-p btn-sm" onClick={v.trOk}>
                        확인
                      </button>
                      <button type="button" className="btn btn-s btn-sm" onClick={v.trCancel}>
                        취소
                      </button>
                    </div>
                  </>
                ) : null}
                <div className="sec">
                  주호소 상세 · 생활력
                </div>
                <label className="fl cp-in">
                  <textarea className="ta2" placeholder="어르신이 말씀하신 현재 어려움, 그렇게 된 계기(사별 · 퇴원 · 이사 등), 가족 · 의뢰인이 보는 상황을 어르신의 말씀 중심으로 기재" aria-label="주호소 상세" />
                  <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                    <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                      <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                    </svg>
                    <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M5 12.5l4.5 4.5L19 7.5" />
                    </svg>
                  </button>
                  <span className="cp-menu" role="menu" aria-label="복사 방식">
                    <button type="button" role="menuitem" onClick={v.copyRaw}>
                      그대로 복사
                    </button>
                    <button type="button" role="menuitem" onClick={v.copyMask}>
                      이름 가려서 복사
                      <span className="cp-ex">
                        예) 김○자
                      </span>
                    </button>
                  </span>
                </label>
                <div className="sec hs-sec">
                  <span aria-hidden="true">
                    (
                  </span>
                  <input className="hs-name" type="text" placeholder="이름" aria-label="건강 상태 기재 대상 이름" />
                  <span aria-hidden="true">
                    )
                  </span>
                  건강 상태
                </div>
                <p className="note" style={{ margin: "-8px 0 0" }}>
                  *어르신 본인 기준으로 기재 · 주 돌봄자 건강이 상담에 영향을 주면 이름을 바꿔 별도 기재
                </p>
                <div className="hs-tbl">
                  <div className="hs-row">
                    <span className="hs-k">
                      주요 질환
                    </span>
                    <div className="hs-v">
                      {(v.hs.dis || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" className="pk hs-pk" aria-pressed={o.on} onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                            {o.label}
                          </button>
                        </Fragment>
                      ))}
                      <span className="hs-t">
                        질환명
                      </span>
                      <input className="hs-in hs-w" type="text" aria-label="질환명" placeholder="질환명 입력" disabled={v.hs.off.dis} />
                    </div>
                  </div>
                  <div className="hs-row">
                    <span className="hs-k">
                      장애
                    </span>
                    <div className="hs-v">
                      {(v.hs.dsb || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" className="pk hs-pk" aria-pressed={o.on} onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                            {o.label}
                          </button>
                        </Fragment>
                      ))}
                      <span className="hs-t">
                        장애명
                      </span>
                      <input className="hs-in hs-w" type="text" aria-label="장애명" placeholder="장애명 입력" disabled={v.hs.off.dsb} />
                      <span className="hs-t">
                        장애 [
                      </span>
                      {(v.hs.dsbLv || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" className="pk hs-pk" aria-pressed={o.on} onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                            {o.label}
                          </button>
                        </Fragment>
                      ))}
                      <span className="hs-t">
                        ] 장애
                      </span>
                    </div>
                  </div>
                  <div className="hs-row">
                    <span className="hs-k">
                      입원 · 통원
                    </span>
                    <div className="hs-v">
                      {(v.hs.hosp || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" className="pk hs-pk" aria-pressed={o.on} onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                            {o.label}
                          </button>
                        </Fragment>
                      ))}
                      <input className="hs-in hs-n" type="text" inputMode="numeric" aria-label="입원 · 통원 횟수" disabled={v.hs.off.hosp} />
                      <span className="hs-t">
                        회 / 구분:
                      </span>
                      {(v.hs.hospT || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" className="pk hs-pk" aria-pressed={o.on} onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                            {o.label}
                          </button>
                        </Fragment>
                      ))}
                      <span className="hs-g">
                        <span className="hs-t">
                          / 총
                        </span>
                        <input className="hs-in hs-n" type="text" inputMode="numeric" aria-label="입원 · 통원 기간 년" disabled={v.hs.off.hosp} />
                        <span className="hs-t">
                          년
                        </span>
                        <input className="hs-in hs-n" type="text" inputMode="numeric" aria-label="입원 · 통원 기간 개월" disabled={v.hs.off.hosp} />
                        <span className="hs-t">
                          개월
                        </span>
                      </span>
                    </div>
                  </div>
                  <div className="hs-row">
                    <span className="hs-k">
                      정신건강 진료
                    </span>
                    <div className="hs-v">
                      {(v.hs.psy || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" className="pk hs-pk" aria-pressed={o.on} onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                            {o.label}
                          </button>
                        </Fragment>
                      ))}
                      <span className="hs-t">
                        진단명
                      </span>
                      <input className="hs-in hs-w" type="text" aria-label="진단명" placeholder="진단명 입력" disabled={v.hs.off.psy} />
                      <span className="hs-t">
                        / 관련 약 복용:
                      </span>
                      {(v.hs.med || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" className="pk hs-pk" aria-pressed={o.on} onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                            {o.label}
                          </button>
                        </Fragment>
                      ))}
                      <span className="hs-g">
                        <span className="hs-t">
                          (총
                        </span>
                        <input className="hs-in hs-n" type="text" inputMode="numeric" aria-label="약물복용 기간 년" disabled={v.hs.off.med} />
                        <span className="hs-t">
                          년
                        </span>
                        <input className="hs-in hs-n" type="text" inputMode="numeric" aria-label="약물복용 기간 개월" disabled={v.hs.off.med} />
                        <span className="hs-t">
                          개월)
                        </span>
                      </span>
                    </div>
                  </div>
                  <div className="hs-row">
                    <span className="hs-k">
                      타기관 상담
                    </span>
                    <div className="hs-v">
                      {(v.hs.cns || []).map((o, i_o) => (
                        <Fragment key={i_o}>
                          <button type="button" className="pk hs-pk" aria-pressed={o.on} onClick={o.pick} style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}>
                            {o.label}
                          </button>
                        </Fragment>
                      ))}
                      <span className="hs-t">
                        상담사유
                      </span>
                      <input className="hs-in hs-w" type="text" aria-label="상담사유" placeholder="상담사유 입력" disabled={v.hs.off.cns} />
                      <span className="hs-t">
                        /
                      </span>
                      <input className="hs-in hs-n" type="text" inputMode="numeric" aria-label="타기관 상담 횟수" disabled={v.hs.off.cns} />
                      <span className="hs-g">
                        <span className="hs-t">
                          회 / 기간 총
                        </span>
                        <input className="hs-in hs-n" type="text" inputMode="numeric" aria-label="타기관 상담 기간 년" disabled={v.hs.off.cns} />
                        <span className="hs-t">
                          년
                        </span>
                        <input className="hs-in hs-n" type="text" inputMode="numeric" aria-label="타기관 상담 기간 개월" disabled={v.hs.off.cns} />
                        <span className="hs-t">
                          개월
                        </span>
                      </span>
                    </div>
                  </div>
                  <div className="hs-row">
                    <span className="hs-k">
                      복용 약
                    </span>
                    <div className="hs-v">
                      <input className="hs-in hs-w" type="text" aria-label="복용 약" placeholder="예: 혈압약 · 당뇨약 · 수면제" />
                    </div>
                  </div>
                  <div className="hs-row">
                    <span className="hs-k">
                      장기요양등급
                    </span>
                    <div className="hs-v">
                      <input className="hs-in hs-w" type="text" aria-label="장기요양등급" placeholder="예: 없음 / 신청 중 / 4등급 / 인지지원등급" />
                    </div>
                  </div>
                  <div className="hs-row">
                    <span className="hs-k">
                      최근 낙상
                    </span>
                    <div className="hs-v">
                      <input className="hs-in hs-w" type="text" aria-label="최근 낙상" placeholder="예: 없음 / 2026-06 욕실에서 미끄러짐" />
                    </div>
                  </div>
                </div>
                <div className="sec">
                  사회관계
                </div>
                <div className="rg-grp">
                  <div className="rg3">
                    <label className="fl">
                      <span className="lb">
                        가족 · 지인 교류 빈도
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          거의 매일
                        </option>
                        <option>
                          주 1~2회
                        </option>
                        <option>
                          월 1~2회
                        </option>
                        <option>
                          거의 없음
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        경로당 · 노인복지관 이용
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          이용 중
                        </option>
                        <option>
                          이용 중단
                        </option>
                        <option>
                          이용 안 함
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        어려울 때 연락할 사람
                      </span>
                      <input className="inp" type="text" placeholder="예: 아들(주 1회 통화) · 옆집 이웃" />
                    </label>
                  </div>
                </div>
                <div className="sec">
                  경제
                </div>
                <div className="rg-grp">
                  <div className="rg3">
                    <label className="fl">
                      <span className="lb">
                        기초연금
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          수급
                        </option>
                        <option>
                          미수급
                        </option>
                        <option>
                          확인 필요
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        기초생활수급
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          해당 없음
                        </option>
                        <option>
                          생계급여
                        </option>
                        <option>
                          의료급여
                        </option>
                        <option>
                          주거급여
                        </option>
                        <option>
                          차상위
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        경제 상황 메모
                      </span>
                      <input className="inp" type="text" placeholder="예: 연금 외 소득 없음 · 의료비 부담" />
                    </label>
                  </div>
                </div>
                <div className="sec">
                  이용 중인 서비스
                </div>
                <div className="rg-grp">
                  <div className="rg4">
                    <label className="fl">
                      <span className="lb">
                        노인맞춤돌봄서비스
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          이용 중
                        </option>
                        <option>
                          연계 필요
                        </option>
                        <option>
                          해당 없음
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        노인장기요양보험
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          이용 중
                        </option>
                        <option>
                          연계 필요
                        </option>
                        <option>
                          해당 없음
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        방문건강관리(보건소)
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          이용 중
                        </option>
                        <option>
                          연계 필요
                        </option>
                        <option>
                          해당 없음
                        </option>
                      </select>
                    </label>
                    <label className="fl">
                      <span className="lb">
                        치매안심센터
                      </span>
                      <select className="inp">
                        <option>
                          선택
                        </option>
                        <option>
                          이용 중
                        </option>
                        <option>
                          연계 필요
                        </option>
                        <option>
                          해당 없음
                        </option>
                      </select>
                    </label>
                  </div>
                </div>
                <p className="note" style={{ margin: "-8px 0 0" }}>
                  *함께 검토할 연계 자원: 통합돌봄 창구(읍·면·동 행정복지센터), 정신건강복지센터, 노인복지관 프로그램
                </p>
                <div className="sec">
                  어르신 태도 및 관찰내용
                </div>
                <div className="g3">
                  <label className="fl">
                    <span className="lb">
                      어르신 태도 · 정서 상태
                    </span>
                    <textarea className="ta2" />
                    <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                      <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                        <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                      </svg>
                      <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M5 12.5l4.5 4.5L19 7.5" />
                      </svg>
                    </button>
                    <span className="cp-menu" role="menu" aria-label="복사 방식">
                      <button type="button" role="menuitem" onClick={v.copyRaw}>
                        그대로 복사
                      </button>
                      <button type="button" role="menuitem" onClick={v.copyMask}>
                        이름 가려서 복사
                        <span className="cp-ex">
                          예) 김○자
                        </span>
                      </button>
                    </span>
                  </label>
                  <label className="fl">
                    <span className="lb">
                      주거 환경 (안전 · 위생 · 난방)
                    </span>
                    <textarea className="ta2" />
                    <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                      <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                        <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                      </svg>
                      <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M5 12.5l4.5 4.5L19 7.5" />
                      </svg>
                    </button>
                    <span className="cp-menu" role="menu" aria-label="복사 방식">
                      <button type="button" role="menuitem" onClick={v.copyRaw}>
                        그대로 복사
                      </button>
                      <button type="button" role="menuitem" onClick={v.copyMask}>
                        이름 가려서 복사
                        <span className="cp-ex">
                          예) 김○자
                        </span>
                      </button>
                    </span>
                  </label>
                </div>
                <label className="fl">
                  <span className="lb">
                    상담사 소견 및 향후 계획
                  </span>
                  <textarea className="ta2" style={{ minHeight: "96px" }} />
                  <button type="button" className="cp-btn" title="복사" aria-label="내용 복사" onClick={v.copyMenu} aria-haspopup="true">
                    <svg className="cp-i" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" />
                      <rect x="3.5" y="9.5" width="11" height="11" rx="2" />
                    </svg>
                    <svg className="cp-ok" viewBox={"0 0 24 24"} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M5 12.5l4.5 4.5L19 7.5" />
                    </svg>
                  </button>
                  <span className="cp-menu" role="menu" aria-label="복사 방식">
                    <button type="button" role="menuitem" onClick={v.copyRaw}>
                      그대로 복사
                    </button>
                    <button type="button" role="menuitem" onClick={v.copyMask}>
                      이름 가려서 복사
                      <span className="cp-ex">
                        예) 김○자
                      </span>
                    </button>
                  </span>
                </label>
              </>
            ) : null}
            {v.showMiss ? (
              <>
                <p className="req" role="alert" style={{ margin: "0", fontSize: "13px", fontWeight: "500" }}>
                  {"기본 정보 필수 항목을 모두 입력해야 초기상담 내용으로 넘어갈 수 있어요 · 남은 항목: "}{v.missText}
                </p>
              </>
            ) : null}
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "flex-end", gap: "10px", borderTop: "1px solid #DDE6EC", paddingTop: "18px" }}>
              <a className="btn btn-s" href={v.backHref} onClick={v.syncBack}>
                취소
              </a>
              <button type="button" className="btn btn-s" onClick={v.goB}>
                {v.midLabel}
              </button>
              <a className="btn btn-p" href="#/CaseInfo">
                등록
              </a>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
