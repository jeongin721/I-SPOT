// Step1Record 화면 마크업 — tools/dc2jsx.py 가 디자인(Step1Record.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './Step1Record.css';

export default function View({ v }) {
  return (
    <div className="pg-Step1Record">
      <div className={v.themeCls} style={{ minHeight: "1250px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
            + 새 사례 등록
          </a>
          <nav className="nav" aria-label="메뉴">
            <a href="#/Home">
              홈
            </a>
            <a className="on" href="#/CaseList">
              사례 관리
            </a>
            <a href="#/Schedule">
              일정
            </a>
            <a href="#/Soon?name=ChildLink">
              안부 연계
              <span className="cnt">
                4
              </span>
            </a>
            <a href="#/Soon?name=Closure">
              종결 검토
              <span className="cnt">
                2
              </span>
            </a>
            <a href="#/Soon?name=DocBox">
              문서함
            </a>
            <a href="#/Soon?name=LawGuide">
              법령 · 매뉴얼
            </a>
            <a href="#/Soon?name=Stats">
              통계
            </a>
            <a href="#/Soon?name=Settings">
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
              사례 관리
            </a>
            {" › "}
            <a href={v.caseHref}>
              {v.caseCrumb}
            </a>
            {" › "}
            <a href={v.historyHref}>
              상담 이력
            </a>
            {" › "}
            <a href={v.detailHref}>
              {v.slNo}
            </a>
          </nav>
          <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 14px" }}>
            <div style={{ flex: "1 1 280px" }}>
              <div className="sub">
                {v.slSub}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px", marginTop: "2px" }}>
                <a className="btn btn-sm btn-s" href={v.caseHref} aria-label="내담자 정보로 돌아가기" title="내담자 정보로 돌아가기">
                  ←
                </a>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  {v.slNo}{" 처리 · "}{v.caseName}
                </h1>
                <div className="sl-wrap">
                  <button type="button" className="sl-btn" aria-haspopup="listbox" aria-expanded={v.slExp} onClick={v.slToggle}>
                    {v.slBtn}
                    <svg className="sl-car" viewBox={"0 0 24 24"} width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M6 9l6 6 6-6" />
                    </svg>
                  </button>
                  {v.slOpen ? (
                    <>
                      <div className="sl-pop" role="listbox" aria-label="회차 선택">
                        <div className="sl-hd">
                          {"회차 선택 "}
                          <span className="note">
                            {v.slHead}
                          </span>
                        </div>
                        <div className="sl-list">
                          {(v.slItems || []).map((o, i_o) => (
                            <Fragment key={i_o}>
                              <button type="button" role="option" aria-selected={o.on} className={`sl-opt ${o.cls}`} onClick={o.pick}>
                                <b className="sl-no">
                                  {o.no}
                                </b>
                                <span className="sl-meta">
                                  {o.meta}
                                </span>
                                <span className={o.stCls} style={{ height: "22px", fontSize: "11.5px" }}>
                                  {o.st}
                                </span>
                              </button>
                            </Fragment>
                          ))}
                        </div>
                      </div>
                    </>
                  ) : null}
                </div>
              </div>
            </div>
          </header>
          <nav className="steps" aria-label="회차 처리 단계">
            <a className="stp on" href={v.step1Href} aria-current="step">
              <span className="sn">
                1
              </span>
              <b style={{ fontWeight: "700" }}>
                기록 확인
              </b>
            </a>
            <a className="stp" href={v.step2Href}>
              <span className="sn">
                2
              </span>
              <b style={{ fontWeight: "500" }}>
                정서·위기 신호 확인
              </b>
            </a>
            <a className="stp" href={v.step3Href}>
              <span className="sn">
                3
              </span>
              <b style={{ fontWeight: "500" }}>
                상담일지 작성
              </b>
            </a>
            <a className="stp" href={v.step4Href}>
              <span className="sn">
                4
              </span>
              <b style={{ fontWeight: "500" }}>
                다음 상담 준비
              </b>
            </a>
          </nav>
          {v.hasStatus ? (
            <p role="alert" className="note" style={{ margin: "0" }}>
              {v.statusMsg}
            </p>
          ) : null}
          {v.done ? (
            <>
              <section className="card" aria-label="기록 확인" style={{ overflow: "hidden" }}>
                <div className="hd">
                  <h2 className="h2">
                    {v.viewTitle}
                  </h2>
                  <span className={v.chipCls}>
                    {v.chipText}
                  </span>
                  {v.xaShow ? (
                    <>
                      <span className="xa" tabIndex="0" aria-describedby="xa-pop">
                        {v.xaText}
                        <span className="xa-pop" id="xa-pop" role="tooltip">
                          <b>
                            음향 분석 제외 구간
                          </b>
                          {(v.xaItems || []).map((x, i_x) => (
                            <Fragment key={i_x}>
                              <button type="button" className="xa-it" onClick={x.go}>
                                <span className="xa-t">
                                  {x.t}
                                </span>
                                <span>
                                  {x.text}
                                </span>
                              </button>
                            </Fragment>
                          ))}
                          <span className="xa-note">
                            1초보다 짧아 떨림 · 웅얼거림 · 작게 말함을 분석하지 않은 어르신 발화예요. '이상 없음'과는 달라요.
                          </span>
                        </span>
                      </span>
                    </>
                  ) : null}
                  <div style={{ marginLeft: "auto", display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    <button type="button" className={`btn btn-sm ${v.allCls}`} onClick={v.showAll}>
                      전체 STT 보기
                    </button>
                    <button type="button" className={`btn btn-sm ${v.lowCls}`} onClick={v.showLow}>
                      {"확인 필요 구간 보기 · "}{v.lowLeft}
                    </button>
                  </div>
                </div>
                <div className={`ln-box ${v.boxCls}`}>
                  {(v.lines || []).map((l, i_l) => (
                    <Fragment key={i_l}>
                      <div className="ln" id={l.lid} style={{ background: l.bg, boxShadow: l.ring }}>
                        <span>
                          <button type="button" className="tbtn" aria-label={`${l.t}부터 듣기`} onClick={l.play}>
                            {l.t}
                          </button>
                        </span>
                        <span style={{ display: "flex", flexDirection: "column", gap: "2px", alignItems: "flex-start" }}>
                          <span className="spw">
                            <button type="button" className="chip" title="눌러서 화자 선택" aria-haspopup="listbox" aria-expanded={l.spExp} aria-label={`화자 바꾸기 · 지금 ${l.spLabel}`} onClick={l.toggleSp} style={{ border: "0", cursor: "pointer", font: "inherit", fontSize: "12px", background: "#ECF5FA", color: "#55687A", fontWeight: l.spFw }}>
                              {l.spLabel}{" ▾"}
                            </button>
                            {l.spMenu ? (
                              <>
                                <span className={`spmenu ${l.spDir}`} role="listbox" aria-label="화자 선택">
                                  {(l.spOpts || []).map((o, i_o) => (
                                    <Fragment key={i_o}>
                                      <button type="button" role="option" aria-selected={o.sel} className={o.cls} onClick={o.pick}>
                                        {o.label}
                                      </button>
                                    </Fragment>
                                  ))}
                                </span>
                              </>
                            ) : null}
                          </span>
                          {l.spFix ? (
                            <>
                              <span className="note" style={{ fontSize: "11px" }}>
                                상담사 수정
                              </span>
                            </>
                          ) : null}
                        </span>
                        <span style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                          {l.edit ? (
                            <>
                              <input className="in" type="text" value={l.text} onChange={l.change} aria-label={l.aria} />
                            </>
                          ) : null}
                          {l.read ? (
                            <>
                              <span style={{ fontSize: "15px" }}>
                                {l.text}
                              </span>
                            </>
                          ) : null}
                          <span className="note" style={{ color: l.hintFg }}>
                            {l.hint}
                          </span>
                          {l.hasCues ? (
                            <>
                              <span className="cues">
                                {(l.cues || []).map((c, i_c) => (
                                  <Fragment key={i_c}>
                                    <span className="cue">
                                      <b>
                                        {c.name}
                                      </b>
                                      {c.hasNum ? (
                                        <>
                                          <span className="num">
                                            {c.num}
                                          </span>
                                        </>
                                      ) : null}
                                      <span className="cmp">
                                        {c.at}
                                      </span>
                                    </span>
                                  </Fragment>
                                ))}
                              </span>
                            </>
                          ) : null}
                          {l.hasLaws ? (
                            <>
                              <span className="laws">
                                {(l.laws || []).map((w, i_w) => (
                                  <Fragment key={i_w}>
                                    <span className="law">
                                      <span className="sig">
                                        {w.sig}
                                      </span>
                                      <span className="ref">
                                        {"확인 서식 "}
                                        <span className="art">
                                          {w.no}
                                        </span>
                                      </span>
                                      <span className="sum">
                                        {w.sum}
                                      </span>
                                      <a className="orig" href={v.portal} target="_blank" rel="noopener noreferrer">
                                        기준 보기 ↗
                                      </a>
                                    </span>
                                  </Fragment>
                                ))}
                              </span>
                            </>
                          ) : null}
                          {l.hasHold ? (
                            <>
                              <span className="hold">
                                {l.hold}
                              </span>
                            </>
                          ) : null}
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span className="note">
                            {l.conf}
                          </span>
                          {l.edit ? (
                            <>
                              <button type="button" className="btn btn-sm btn-s" onClick={l.ok}>
                                {l.okLabel}
                              </button>
                            </>
                          ) : null}
                        </span>
                      </div>
                    </Fragment>
                  ))}
                </div>
                <div className="legend">
                  <span>
                    왼쪽 시간을 누르면 그 위치부터 녹음을 다시 들을 수 있습니다.
                  </span>
                  <span>
                    같은 화자가 다른 사람 말 없이 이어서 말한 문장은 한 줄로 묶어 보여 줍니다. 1초보다 짧아 목소리 신호를 분석하지 못한 구간은 줄마다 표시하지 않고 제목 옆 '음향 분석 제외'에 모아 보여 줍니다.
                  </span>
                  <span className="k">
                    <span className="cue">
                      <b>
                        목소리 신호
                      </b>
                    </span>
                    {" 확인 필요 구간의 어르신 발화에서만, 이 어르신의 이번 상담 평소 목소리와 비교해 떨림 · 웅얼거림 · 작게 말함 중 해당하는 것만 표시합니다. 다시 들어볼 곳을 알려주는 정보이며 감정 상태나 위기 여부를 판단하지 않습니다. 연세 · 건강에 따른 평소 떨림일 수 있으니 직접 들어 확인해 주세요."}
                  </span>
                  <span className="k">
                    <span className="sig">
                      우울감
                    </span>
                    {" 정서·위기 신호(우울감 · 식사·수면 변화 · 고립 · 죽음 관련 언급)가 감지된 발화에 확인할 기관 서식과 안내를 표시합니다. 기준 보기를 누르면 법령 · 매뉴얼에서 확인 기준을 볼 수 있습니다. 진단하거나 위기를 확정하지 않습니다."}
                  </span>
                  <span className="k">
                    <span className="sig">
                      자살 생각
                    </span>
                    {" 죽음 · 자살 관련 언급은 화자 확인 후 가장 먼저 표시합니다. 상담사가 S-04 자살위험 선별 체크로 차분히 직접 여쭙고, 필요하면 109(자살예방상담) · 정신건강복지센터를 안내합니다. 즉각 위험이 있으면 119에 요청합니다."}
                  </span>
                  <span>
                    예시 화면 · 서식은 기관 내부 시니어 상담 서식(S-01~S-08) · 목소리 신호는 예시 표시 · AI 요약도 존댓말 · 존중 언어 원칙을 지킵니다
                  </span>
                </div>
                <div style={{ height: "16px" }} />
              </section>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
                <a className="btn btn-p" href={v.step2Href} onClick={v.goStep2} style={{ marginLeft: "auto" }}>
                  {v.nextLabel}
                </a>
              </div>
            </>
          ) : null}
          <p className="ainote">
            AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
          </p>
          {v.hasToast ? (
            <>
              <div className="toast" role="status">
                {v.toast}
              </div>
            </>
          ) : null}
          <div className="player" role="region" aria-label="녹음 재생">
            <div className="pl-ctrls">
              {v.plHasMarks ? (
                <>
                  <span className="pl-legend" style={{ position: "absolute", left: "20px" }}>
                    <i aria-hidden="true" />
                    {"확인 필요 구간 "}{v.plMarkCount}곳
                  </span>
                </>
              ) : null}
              <button type="button" className="pl-b" aria-label="5초 뒤로" title="5초 뒤로" onClick={v.plBack}>
                <svg viewBox={"0 0 24 24"} width="18" height="18" fill="currentColor" aria-hidden="true">
                  <path d="M11 6v12L2.5 12z" />
                  <path d="M21 6v12l-8.5-6z" />
                </svg>
              </button>
              <button type="button" className="pl-b pl-main" aria-label={v.plPlayLabel} title={v.plPlayLabel} onClick={v.plToggle}>
                {v.plOn ? (
                  <>
                    <svg viewBox={"0 0 24 24"} width="18" height="18" fill="currentColor" aria-hidden="true">
                      <rect x="6" y="5" width="4" height="14" rx="1" />
                      <rect x="14" y="5" width="4" height="14" rx="1" />
                    </svg>
                  </>
                ) : null}
                {v.plOff ? (
                  <>
                    <svg viewBox={"0 0 24 24"} width="18" height="18" fill="currentColor" aria-hidden="true">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </>
                ) : null}
              </button>
              <button type="button" className="pl-b" aria-label="정지" title="정지" onClick={v.plStop}>
                <svg viewBox={"0 0 24 24"} width="18" height="18" fill="currentColor" aria-hidden="true">
                  <rect x="6" y="6" width="12" height="12" rx="1.5" />
                </svg>
              </button>
              <button type="button" className="pl-b" aria-label="5초 앞으로" title="5초 앞으로" onClick={v.plFwd}>
                <svg viewBox={"0 0 24 24"} width="18" height="18" fill="currentColor" aria-hidden="true">
                  <path d="M13 6v12l8.5-6z" />
                  <path d="M3 6v12l8.5-6z" />
                </svg>
              </button>
            </div>
            <div className="pl-time">
              <span className="pl-t">
                {v.plCur}
              </span>
              <span className="pl-track">
                <input type="range" className="pl-range" min="0" max={v.plMax} step="1" value={v.plPos} onChange={v.plSeek} aria-label="재생 위치" style={{ backgroundSize: `${v.plPct} 100%` }} />
                {(v.plMarks || []).map((m, i_m) => (
                  <Fragment key={i_m}>
                    <button type="button" className="pl-mark" style={{ left: m.left }} aria-label={`확인 필요 구간 ${m.t} 확인하기`} title={`확인 필요 구간 ${m.t}`} onClick={m.go} />
                  </Fragment>
                ))}
              </span>
              <span className="pl-t">
                {v.plDur}
              </span>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
