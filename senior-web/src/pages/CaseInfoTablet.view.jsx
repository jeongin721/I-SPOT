// CaseInfoTablet 화면 마크업 — tools/dc2jsx.py 가 디자인(CaseInfoTablet.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './CaseInfoTablet.css';

export default function View({ v }) {
  return (
    <div className="pg-CaseInfoTablet">
      <div className={v.themeCls} style={{ minHeight: "1350px", background: "#DEE6EC", color: "#1F3A56", fontFamily: "'IBM Plex Sans KR', sans-serif", fontSize: "14px", lineHeight: "1.6", display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
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
          <a className="cta" href={v.uploadHref} onClick={v.markBack}>
            ↑ 녹취 · 자료 올리기
          </a>
          <a className="cta2" href="#/CaseRegister" onClick={v.markBack}>
            + 새 대상자 등록
          </a>
          <nav className="nav" aria-label="메뉴">
            <a href="#/Home">
              홈
            </a>
            <a className="on" href="#/CaseList">
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
            <a href="#/DocBox">
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
          <nav aria-label="위치" className="note">
            <a href="#/CaseList">
              대상자 관리
            </a>
            {" › "}{v.crumb}
          </nav>
          {v.alertMsg ? (
            <p role="alert" className="note" style={{ margin: "0", color: "#A33B2E" }}>
              {v.alertMsg}
            </p>
          ) : null}
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px 18px" }}>
            <a className="btn btn-sm btn-s" href="#/CaseList">
              ← 목록
            </a>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h1 style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  {v.name}
                </h1>
                <span className="sub">
                  {v.sub}
                </span>
                <span className={v.riskCls}>
                  {v.riskLabel}
                </span>
              </div>
              <div className="note">
                {v.headNote}
              </div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              <button type="button" className="btn btn-s" onClick={v.recOpen}>
                <span className="rec-dot" aria-hidden="true" />
                {" 녹음하기"}
              </button>
              <a className="btn btn-s" href={v.uploadHref} onClick={v.markBack}>
                ↑ 녹취 올리기
              </a>
            </div>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <a className="on" aria-current="page" href={v.infoHref}>
              내담자 정보
            </a>
            <a href={v.historyHref}>
              상담 이력
            </a>
            <a href={v.docsHref}>
              문서함
            </a>
          </nav>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "18px" }}>
            <section className="card" aria-label="기본 정보" style={{ padding: "22px 24px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h2 className="h2">
                  기본 정보
                </h2>
                <a className="btn btn-sm btn-s" href={v.appHref} style={{ marginLeft: "auto" }}>
                  안부 연계 →
                </a>
              </div>
              <dl className="kv" style={{ gridTemplateColumns: "120px 1fr" }}>
                <dt>
                  사례 번호
                </dt>
                <dd>
                  {v.kvNo}
                </dd>
                <dt>
                  성함
                </dt>
                <dd>
                  {v.kvName}
                </dd>
                <dt>
                  생년월일
                </dt>
                <dd>
                  {v.kvBirth}
                </dd>
                <dt>
                  가구형태
                </dt>
                <dd>
                  {v.kvLiving}
                </dd>
                <dt>
                  주 돌봄자
                </dt>
                <dd>
                  {v.kvCarer}
                </dd>
                <dt>
                  비상연락
                </dt>
                <dd>
                  {v.kvEmergency}
                </dd>
                <dt>
                  동의 상태
                </dt>
                <dd style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                  {(v.consentChips || []).map((c, i_c) => (
                    <span key={i_c} className={c.cls}>
                      {c.text}
                    </span>
                  ))}
                </dd>
                <dt>
                  의뢰 경로
                </dt>
                <dd>
                  {v.kvReferral}
                </dd>
                <dt>
                  담당 상담사
                </dt>
                <dd>
                  {v.kvCounselor}
                </dd>
                <dt>
                  접수일
                </dt>
                <dd>
                  {v.kvReport}
                </dd>
                <dt>
                  배정일
                </dt>
                <dd>
                  {v.kvAssigned}
                </dd>
                <dt>
                  초기상담일
                </dt>
                <dd>
                  {v.kvFirst}
                </dd>
                <dt>
                  상담 회차
                </dt>
                <dd style={{ fontWeight: "700" }}>
                  {v.kvCount}
                </dd>
                <dt>
                  최근 상담
                </dt>
                <dd>
                  {v.kvLatest}
                </dd>
                <dt>
                  안부 앱
                </dt>
                <dd>
                  {v.kvApp}
                </dd>
              </dl>
            </section>
            <section className="card" aria-label="주호소 · 고려사항" style={{ padding: "22px 24px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h2 className="h2">
                  주호소 · 고려사항
                </h2>
                <span className={v.careCls} style={{ marginLeft: "auto" }}>
                  {v.careChip}
                </span>
              </div>
              <div className="note" style={{ marginTop: "4px", textAlign: "right" }}>
                {v.careNote}
              </div>
              <div className="note" style={{ marginTop: "10px" }}>
                주호소
              </div>
              <div style={{ margin: "6px 0 16px" }}>
                {v.complaint}
              </div>
              <div className="note">
                상담 영역
              </div>
              <div style={{ margin: "6px 0 16px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {(v.areaChips || []).map((t, i_t) => (
                  <span key={i_t} className="chip c-normal">
                    {t}
                  </span>
                ))}
              </div>
              <div className="note">
                주요 키워드
              </div>
              <div style={{ margin: "6px 0 16px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {(v.keywordChips || []).map((t, i_t) => (
                  <span key={i_t} className="chip c-normal">
                    {t}
                  </span>
                ))}
              </div>
              <div className="note">
                의사소통 고려
              </div>
              <div style={{ margin: "6px 0 16px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {(v.commChips || []).map((t, i_t) => (
                  <span key={i_t} className="chip c-normal">
                    {t}
                  </span>
                ))}
              </div>
              <div className="note">
                건강
              </div>
              <div style={{ margin: "6px 0 16px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {(v.healthChips || []).map((t, i_t) => (
                  <span key={i_t} className="chip c-normal">
                    {t}
                  </span>
                ))}
              </div>
              <div className="note">
                이용 서비스
              </div>
              <div style={{ marginTop: "6px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {(v.serviceChips || []).map((t, i_t) => (
                  <span key={i_t} className="chip c-normal">
                    {t}
                  </span>
                ))}
              </div>
            </section>
          </div>
          <section className="card" aria-label="현재 진행 상황" style={{ padding: "22px 24px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <h2 className="h2">
                현재 진행 상황
              </h2>
              <span className="note">
                {v.progNote}
              </span>
              <a className="btn btn-p btn-sm" href={v.contHref} style={{ marginLeft: "auto" }}>
                {v.contLabel}
              </a>
            </div>
            <div style={{ overflowX: "auto" }}>
              <div style={{ minWidth: "660px", display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", position: "relative" }}>
                <div style={{ position: "absolute", left: "10%", right: "10%", top: "17px", height: "2px", background: "#D9E3EA" }} />
                <div className="st">
                  <span className="sd" style={v.recDot}>
                    {v.recMark}
                  </span>
                  상담 녹음
                  <span className="note">
                    {v.recDate}
                  </span>
                </div>
                {(v.steps || []).map((t, i_t) => (
                  <a key={i_t} className="st stl" href={t.href}>
                    <span className="sd" style={t.dot}>
                      {t.mark}
                    </span>
                    <span style={t.lab}>
                      {t.label}
                    </span>
                    {i_t === 0 && v.st1Chip ? (
                      <span className="chip c-check">
                        {v.st1Chip}
                      </span>
                    ) : null}
                  </a>
                ))}
              </div>
            </div>
          </section>
          <div className="brief-wrap" id="brief" aria-label="상담 전 브리핑" role="region">
            <section style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 20px" }}>
              <div style={{ flex: "1 1 380px" }}>
                <div className="sub">
                  {v.briefSub}
                </div>
                <h2 style={{ margin: "2px 0 0", fontSize: "22px", fontWeight: "700" }}>
                  상담 전 브리핑
                </h2>
              </div>
              <button type="button" className="btn btn-s" aria-haspopup="dialog" onClick={v.outOpen}>
                인쇄 · PDF
              </button>
              {v.outShow ? (
                <>
                  <div className="out-ov">
                    <div className="out-dlg" role="dialog" aria-modal="true" aria-labelledby="out-t">
                      <b id="out-t" style={{ fontSize: "18px" }}>
                        {v.outTitle}
                      </b>
                      <span className="note" style={{ marginTop: "-6px" }}>
                        출력물에 들어갈 이름 표시 방식을 고르세요.
                      </span>
                      <div role="radiogroup" aria-label="이름 표시 방식" className="out-opts">
                        {(v.outOpts || []).map((o, i_o) => (
                          <Fragment key={i_o}>
                            <button type="button" role="radio" aria-checked={o.on} className={`out-opt ${o.cls}`} onClick={o.pick}>
                              <span className="out-rd" aria-hidden="true" />
                              <span style={{ flex: "1", display: "flex", flexDirection: "column", gap: "2px" }}>
                                <b style={{ fontSize: "14px" }}>
                                  {o.label}
                                </b>
                                <span className="note">
                                  {o.ex}
                                </span>
                              </span>
                            </button>
                          </Fragment>
                        ))}
                      </div>
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                        <button type="button" className="btn btn-s" onClick={v.outClose}>
                          취소
                        </button>
                        <button type="button" className="btn btn-p" onClick={v.outRun}>
                          {v.outGo}
                        </button>
                      </div>
                    </div>
                  </div>
                </>
              ) : null}
            </section>
            <section aria-label="먼저 볼 것" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <h2 className="h2">
                먼저 볼 것
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "18px" }}>
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
                    {v.lead2Has ? (
                      <>
                        {v.lead2From}{" "}
                        <span className="lead-arrow">
                          →
                        </span>
                        {" "}{v.lead2To}
                      </>
                    ) : v.lead2}
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
              </div>
            </section>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "18px" }}>
              <section className="card" style={{ padding: "26px 28px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <h2 className="h2">
                    확인할 사항
                  </h2>
                </div>
                {(v.checkRows || []).map((x, i_x) => (
                  <label key={i_x} className="rq">
                    <input type="checkbox" checked={x.done} onChange={x.toggle} />
                    <span>
                      {x.text}
                      <span className="src">
                        {x.src}
                      </span>
                    </span>
                  </label>
                ))}
                {v.checkEmpty ? (
                  <div className="rq">
                    <span>
                      —
                    </span>
                  </div>
                ) : null}
              </section>
              <section className="card" style={{ padding: "26px 28px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <h2 className="h2">
                    추가 질문
                  </h2>
                  <span className="chip c-ai">
                    {v.draftChip}
                  </span>
                  <a href={v.nextHref} style={{ marginLeft: "auto", fontSize: "13px" }}>
                    질문 수정
                  </a>
                </div>
                {(v.draftRows || []).map((q, i_q) => (
                  <div key={i_q} className="rq">
                    <span className="chip c-normal">
                      {q.chip}
                    </span>
                    <span>
                      {q.text}
                    </span>
                  </div>
                ))}
              </section>
            </div>
          </div>
          <section className="card" aria-label="기관 서식" style={{ padding: "20px 24px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px" }}>
            <b style={{ flex: "1 1 200px" }}>
              기관 서식
            </b>
            <span className="chip c-check">
              {v.formChip}
            </span>
            <a className="btn btn-p" href={v.formHref} onClick={v.goForm}>
              기관 서식 작성
            </a>
          </section>
          <section className="card" aria-label="후속관리 등록" style={{ padding: "20px 24px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px" }}>
            <b style={{ flex: "1 1 200px" }}>
              후속관리
            </b>
            {v.notReg ? (
              <>
                <button type="button" className="btn btn-y" onClick={v.reg}>
                  후속관리 등록
                </button>
              </>
            ) : null}
            {v.isReg ? (
              <>
                <span className="chip c-ok">
                  등록됨 · 초안 생성 중
                </span>
                <a className="btn btn-s" href="#/Followup">
                  후속관리 보기
                </a>
                <button type="button" className="btn btn-sm btn-s" onClick={v.unreg}>
                  등록 취소
                </button>
              </>
            ) : null}
          </section>
          <p className="ainote">
            AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
          </p>
        </main>
        {v.recShow ? (
          <>
            <div className="rec-ov">
              <section role="dialog" aria-modal="true" aria-labelledby="rec-title" className="rec-dlg">
                <div style={{ padding: "20px 24px 16px", borderBottom: "1px solid #DDE6EC", display: "flex", alignItems: "center", gap: "12px" }} className="rec-hd">
                  <h2 id="rec-title" style={{ margin: "0", fontSize: "20px", fontWeight: "700" }}>
                    녹음하기
                  </h2>
                  <button type="button" className="rec-x" aria-label="닫기" onClick={v.recClose}>
                    ×
                  </button>
                </div>
                <div style={{ padding: "20px 24px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
                  <div className="rec-case">
                    <span className="note">
                      사례
                    </span>
                    <b>
                      {v.caseLabel}
                    </b>
                    <span className="sub">
                      {v.sub}
                    </span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
                    <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      <span className="lb2">
                        상담 회차
                      </span>
                      <select className="inp" value={v.recSes} onChange={v.recSesSet} disabled={v.recLock}>
                        <option value="new">
                          새 회차 · 9회차
                        </option>
                        <option value="8">
                          8회차 · 10/2 방문상담
                        </option>
                        <option value="7">
                          7회차 · 9/18 내방상담
                        </option>
                        <option value="6">
                          6회차 · 9/4 방문상담
                        </option>
                        <option value="5">
                          5회차 · 8/28 내방상담
                        </option>
                        <option value="4">
                          4회차 · 8/21 방문상담
                        </option>
                        <option value="3">
                          3회차 · 8/14 전화상담
                        </option>
                        <option value="2">
                          2회차 · 8/7 방문상담
                        </option>
                        <option value="1">
                          1회차 · 7/31 초기상담(방문)
                        </option>
                      </select>
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      <span className="lb2">
                        상담 유형
                      </span>
                      <select className="inp" value={v.recKind} onChange={v.recKindSet} disabled={v.recLock}>
                        <option>
                          방문상담
                        </option>
                        <option>
                          내방상담
                        </option>
                        <option>
                          전화상담
                        </option>
                        <option>
                          가족 면담
                        </option>
                      </select>
                    </label>
                  </div>
                  <div className="rec-box">
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}>
                      <span className={`rec-dot ${v.recDotCls}`} aria-hidden="true" />
                      <span className="rec-status">
                        {v.recStatus}
                      </span>
                    </div>
                    <div className="rec-time" aria-live="polite">
                      {v.recTime}
                    </div>
                    {v.recIdle ? (
                      <>
                        <label className="rec-consent">
                          <input type="checkbox" checked={v.recConsent} onChange={v.recConsentSet} />
                          <span>
                            어르신(참석자)께 녹음 사실을 천천히 알리고 동의를 받았어요
                          </span>
                        </label>
                        {v.recErr ? (
                          <>
                            <span className="acc" style={{ fontSize: "13px" }}>
                              녹음 동의를 먼저 확인해 주세요.
                            </span>
                          </>
                        ) : null}
                        <button type="button" className="btn btn-p rec-main" onClick={v.recStart}>
                          <span className="rec-dot" aria-hidden="true" />
                          {" 녹음 시작"}
                        </button>
                      </>
                    ) : null}
                    {v.recRunning ? (
                      <>
                        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px" }}>
                          <button type="button" className="btn btn-s" onClick={v.recPause}>
                            {v.recPauseLabel}
                          </button>
                          <button type="button" className="btn btn-p" onClick={v.recStop}>
                            ■ 정지
                          </button>
                        </div>
                      </>
                    ) : null}
                    {v.recDone ? (
                      <>
                        {v.recHasUrl ? (
                          <>
                            <audio controls="" src={v.recUrl} style={{ width: "100%" }} />
                          </>
                        ) : null}
                        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px" }}>
                          <button type="button" className="btn btn-s" onClick={v.recReset}>
                            다시 녹음
                          </button>
                          <button type="button" className="btn btn-p" onClick={v.recSave}>
                            저장
                          </button>
                        </div>
                      </>
                    ) : null}
                    {v.recSaved ? (
                      <>
                        <p style={{ margin: "0", textAlign: "center" }}>
                          {"녹음을 저장했어요 · "}{v.recSummary}
                          <br />
                          <b>
                            STT 분석을 시작할까요?
                          </b>
                        </p>
                        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px" }}>
                          <button type="button" className="btn btn-s" onClick={v.recClose}>
                            나중에
                          </button>
                          <a className="btn btn-p" href={v.step1Href} onClick={v.recClose}>
                            기록 확인으로 →
                          </a>
                        </div>
                      </>
                    ) : null}
                    {v.recSim ? (
                      <>
                        <span className="note" style={{ textAlign: "center" }}>
                          이 미리보기에서는 마이크를 쓸 수 없어 녹음 흐름만 보여 드려요. 실제 화면에서는 마이크로 바로 녹음돼요.
                        </span>
                      </>
                    ) : null}
                  </div>
                </div>
              </section>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
