// CaseInfo 화면 마크업 — tools/dc2jsx.py 가 디자인(CaseInfo.dc.html)에서 만든 파일. 그 뒤 서버 값 바인딩(v.*)만 손으로 더했다 — 다시 풀면 바인딩이 지워지니 diff 로 옮긴다.
/* eslint-disable */
import { Fragment } from 'react';
import './CaseInfo.css';

export default function View({ v }) {
  return (
    <div className="pg-CaseInfo">
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
            {" › 김순자 C-2026-0351"}
          </nav>
          <section style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px 18px" }}>
            <a className="btn btn-sm btn-s" href="#/CaseList">
              ← 목록
            </a>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h1 className="h1-sans" style={{ margin: "0", fontSize: "28px", fontWeight: "700" }}>
                  김순자
                </h1>
                <span className="sub">
                  만 82세 · 여 · 독거
                </span>
                <span className="chip c-hi">
                  위기도 집중
                </span>
              </div>
              <div className="note">
                C-2026-0351 · 다음 상담 오늘 16:00
              </div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              <button type="button" className="btn btn-s" onClick={v.recOpen}>
                <span className="rec-dot" aria-hidden="true" />
                {" 녹음하기"}
              </button>
              <a className="btn btn-s" href="#/Upload" onClick={v.markBack}>
                ↑ 녹취 올리기
              </a>
            </div>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <a className="on" aria-current="page" href="#/CaseInfo">
              내담자 정보
            </a>
            <a href="#/CaseHistory">
              상담 이력
            </a>
            <a href="#/Soon?name=CaseDocs">
              문서함
            </a>
          </nav>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "18px" }}>
            <section className="card" aria-label="기본 정보" style={{ padding: "22px 24px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                <h2 className="h2">
                  기본 정보
                </h2>
                <a className="btn btn-sm btn-s" href="#/Soon?name=CaseApp" style={{ marginLeft: "auto" }}>
                  안부 연계 →
                </a>
              </div>
              <dl className="kv" style={{ gridTemplateColumns: "120px 1fr" }}>
                <dt>
                  사례 번호
                </dt>
                <dd>
                  C-2026-0351
                </dd>
                <dt>
                  성함
                </dt>
                <dd>
                  김순자 (여) · 호칭 "김순자 님"
                </dd>
                <dt>
                  생년월일
                </dt>
                <dd>
                  1944-03-14 (만 82세)
                </dd>
                <dt>
                  가구형태
                </dt>
                <dd>
                  독거 (배우자 2025년 사별)
                </dd>
                <dt>
                  주 돌봄자
                </dt>
                <dd>
                  이정훈 / 아들 · 만 54세 · 타 지역 거주 (주 1회 통화)
                </dd>
                <dt>
                  비상연락
                </dt>
                <dd>
                  이정훈(아들) 010-****-2741 · 생활지원사 주 1회 방문
                </dd>
                <dt>
                  동의 상태
                </dt>
                <dd style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                  <span className="chip c-ok">
                    상담 본인 동의
                  </span>
                  <span className="chip c-ok">
                    녹음 동의
                  </span>
                  <span className="chip c-check">
                    가족 공유 일부 동의
                  </span>
                </dd>
                <dt>
                  의뢰 경로
                </dt>
                <dd>
                  노인맞춤돌봄 생활지원사 의뢰
                </dd>
                <dt>
                  담당 상담사
                </dt>
                <dd>
                  이서연
                </dd>
                <dt>
                  접수일
                </dt>
                <dd>
                  2026-07-28
                </dd>
                <dt>
                  배정일
                </dt>
                <dd>
                  2026-07-29
                </dd>
                <dt>
                  초기상담일
                </dt>
                <dd>
                  2026-07-31 (방문)
                </dd>
                <dt>
                  상담 회차
                </dt>
                <dd style={{ fontWeight: "700" }}>
                  8회
                </dd>
                <dt>
                  최근 상담
                </dt>
                <dd>
                  2026-10-02 · 방문상담
                </dd>
                <dt>
                  안부 앱
                </dt>
                <dd>
                  연결됨 (9/18) · 2주 응답 12/14
                </dd>
              </dl>
            </section>
            <section className="card" aria-label="주호소 · 고려사항" style={{ padding: "22px 24px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h2 className="h2">
                  주호소 · 고려사항
                </h2>
                <span className="chip c-hi" style={{ marginLeft: "auto" }}>
                  위기도 집중
                </span>
              </div>
              <div className="note" style={{ marginTop: "4px", textAlign: "right" }}>
                상담사 지정 · 9/18
              </div>
              <div className="note" style={{ marginTop: "10px" }}>
                주호소
              </div>
              <div style={{ margin: "6px 0 16px" }}>
                배우자와 사별 후 식사를 거르고 외출이 줄었음 · 불면 · 기분 저하
              </div>
              <div className="note">
                상담 영역
              </div>
              <div style={{ margin: "6px 0 16px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                <span className="chip c-normal">
                  상실 · 애도
                </span>
                <span className="chip c-normal">
                  정서 · 우울
                </span>
                <span className="chip c-normal">
                  고립 · 외로움 (확인 중)
                </span>
              </div>
              <div className="note">
                주요 키워드
              </div>
              <div style={{ margin: "6px 0 16px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                <span className="chip c-normal">
                  #사별
                </span>
                <span className="chip c-normal">
                  #외로움
                </span>
                <span className="chip c-normal">
                  #식사 거름
                </span>
                <span className="chip c-normal">
                  #불면
                </span>
                <span className="chip c-normal">
                  #외출 감소
                </span>
              </div>
              <div className="note">
                의사소통 고려
              </div>
              <div style={{ margin: "6px 0 16px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                <span className="chip c-normal">
                  보청기(왼쪽)
                </span>
                <span className="chip c-normal">
                  큰 글씨 자료
                </span>
                <span className="chip c-normal">
                  천천히 · 반복 확인
                </span>
              </div>
              <div className="note">
                건강
              </div>
              <div style={{ margin: "6px 0 16px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                <span className="chip c-normal">
                  고혈압 · 무릎 관절염
                </span>
                <span className="chip c-normal">
                  복약 2종(혈압약 · 진통제)
                </span>
                <span className="chip c-normal">
                  장기요양등급 없음
                </span>
              </div>
              <div className="note">
                이용 서비스
              </div>
              <div style={{ marginTop: "6px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                <span className="chip c-normal">
                  노인맞춤돌봄(주 1회)
                </span>
                <span className="chip c-normal">
                  방문건강관리(보건소)
                </span>
                <span className="chip c-normal">
                  경로당 (최근 이용 줄어듦)
                </span>
              </div>
            </section>
          </div>
          <section className="card" aria-label="현재 진행 상황" style={{ padding: "22px 24px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <h2 className="h2">
                현재 진행 상황
              </h2>
              <span className="note">
                8회차 (10/2)
              </span>
              <a className="btn btn-p btn-sm" href="#/Step1Record" style={{ marginLeft: "auto" }}>
                이어서 하기 · 기록 확인
              </a>
            </div>
            <div style={{ overflowX: "auto" }}>
              <div style={{ minWidth: "660px", display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", position: "relative" }}>
                <div style={{ position: "absolute", left: "10%", right: "10%", top: "17px", height: "2px", background: "#D9E3EA" }} />
                <div className="st">
                  <span className="sd" style={{ background: "#ECF5FA", color: "#55687A" }}>
                    ✓
                  </span>
                  상담 녹음
                  <span className="note">
                    10/7
                  </span>
                </div>
                <a className="st stl" href="#/Step1Record">
                  <span className="sd" style={{ background: "#FFFFFF", border: "2px solid #1F3A56", color: "#1F3A56" }}>
                    1
                  </span>
                  <b style={{ fontWeight: "700", color: "#1F3A56" }}>
                    기록 확인
                  </b>
                  <span className="chip c-check">
                    저신뢰 3곳
                  </span>
                </a>
                <a className="st stl" href="#/Step2Signals">
                  <span className="sd" style={{ background: "#DDE6EC", color: "#66788A" }}>
                    2
                  </span>
                  <span style={{ color: "#66788A" }}>
                    정서·위기 신호 확인
                  </span>
                </a>
                <a className="st stl" href="#/Step3Summary">
                  <span className="sd" style={{ background: "#DDE6EC", color: "#66788A" }}>
                    3
                  </span>
                  <span style={{ color: "#66788A" }}>
                    상담일지 작성
                  </span>
                </a>
                <a className="st stl" href="#/Step4Next">
                  <span className="sd" style={{ background: "#DDE6EC", color: "#66788A" }}>
                    4
                  </span>
                  <span style={{ color: "#66788A" }}>
                    다음 상담 준비
                  </span>
                </a>
              </div>
            </div>
          </section>
          <div className="brief-wrap" id="brief" aria-label="상담 전 브리핑" role="region">
            <section style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "10px 20px" }}>
              <div style={{ flex: "1 1 380px" }}>
                <div className="sub">
                  오늘 16:00 · 9회차 방문상담 · 자택 방문
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
                    "다음에 오시면 할 얘기가 있어요"
                  </b>
                  <span className="src">
                    10/7 22:10 · 안부 앱 (음성)
                  </span>
                </div>
                <div className="card lead">
                  <span className="lead-tag">
                    안부 응답 변화
                  </span>
                  <span className="lead-q">
                    오늘 기분은 어떠세요?
                  </span>
                  <b className="lead-main">
                    {"보통이에요 "}
                    <span className="lead-arrow">
                      →
                    </span>
                    {" 별로예요"}
                  </b>
                  <span className="src">
                    10/6 · QB-E-05
                  </span>
                </div>
                <div className="card lead">
                  <span className="lead-tag">
                    처음 나온 이야기
                  </span>
                  <span className="lead-q">
                    식사 · 건강
                  </span>
                  <b className="lead-main">
                    "끼니를 그냥 넘길 때가 많아요"
                  </b>
                  <span className="src">
                    8회차 02:15 · 화자 확인 중
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
                  <a href="#/Step4Next?sec=next-checks" onClick={v.goChecks} style={{ marginLeft: "auto", fontSize: "13px" }}>
                    전체 확인
                  </a>
                </div>
                <div className="rq-list" tabIndex="0" aria-label="확인할 사항 목록">
                  <label className="rq">
                    <input type="checkbox" defaultChecked="" />
                    <span>
                      "이렇게 살아서 뭐 하나" 말씀 이후 마음 변화 (S-04 재확인 · 109 안내)
                      <span className="src">
                        근거 · 7회차 05:10
                      </span>
                    </span>
                  </label>
                  <label className="rq">
                    <input type="checkbox" defaultChecked="" />
                    <span>
                      02:15 발화 화자 · 식사 상황
                      <span className="src">
                        근거 · 8회차 02:15
                      </span>
                    </span>
                  </label>
                  <label className="rq">
                    <input type="checkbox" />
                    <span>
                      어르신이 꺼내고 싶은 이야기부터
                      <span className="src">
                        근거 · 10/7 안부 앱 말씀
                      </span>
                    </span>
                  </label>
                  <label className="rq">
                    <input type="checkbox" />
                    <span>
                      위기 시 연락 계획(생활지원사 · 상담사)이 실제로 쓰였는지
                      <span className="src">
                        근거 · 7회차 연락 계획 · 7회차 02:40
                      </span>
                    </span>
                  </label>
                  <label className="rq">
                    <input type="checkbox" />
                    <span>
                      안부 앱 '오늘 기분' 응답이 바뀐 이유
                      <span className="src">
                        근거 · 10/6 QB-E-05
                      </span>
                    </span>
                  </label>
                  <label className="rq">
                    <input type="checkbox" />
                    <span>
                      아들에게 상담 내용 공유 범위 (가족 공유 일부 동의)
                      <span className="src">
                        근거 · 10/27 메모
                      </span>
                    </span>
                  </label>
                </div>
              </section>
              <section className="card" style={{ padding: "26px 28px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <h2 className="h2">
                    추가 질문
                  </h2>
                  <span className="chip c-ai">
                    AI 초안
                  </span>
                  <a href="#/Step4Next" style={{ marginLeft: "auto", fontSize: "13px" }}>
                    질문 수정
                  </a>
                </div>
                <div className="rq">
                  <span className="chip c-normal">
                    열린 질문
                  </span>
                  <span>
                    "요즘 하루는 주로 어떻게 보내세요? 이야기 나눌 분이 계세요?"
                  </span>
                </div>
                <div className="rq">
                  <span className="chip c-normal">
                    열린 질문
                  </span>
                  <span>
                    "지난번에 살아서 뭐 하나 싶다고 하셨던 마음은 요즘 어떠세요?"
                  </span>
                </div>
                <div className="rq">
                  <span className="chip c-normal">
                    QB-N-01
                  </span>
                  <span>
                    "요즘 식사는 주로 어떻게 하세요?"
                  </span>
                </div>
              </section>
            </div>
          </div>
          <section className="card" aria-label="기관 서식" style={{ padding: "20px 24px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px" }}>
            <b style={{ flex: "1 1 200px" }}>
              기관 서식
            </b>
            <span className="chip c-check">
              점검표 3차 작성 전
            </span>
            <a className="btn btn-p" href="#/Soon?name=CaseForm" onClick={v.goForm}>
              기관 서식 작성
            </a>
          </section>
          <section className="card" aria-label="종결 검토 등록" style={{ padding: "20px 24px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px" }}>
            <b style={{ flex: "1 1 200px" }}>
              종결 검토
            </b>
            {v.notReg ? (
              <>
                <button type="button" className="btn btn-y" onClick={v.reg}>
                  종결 검토 등록
                </button>
              </>
            ) : null}
            {v.isReg ? (
              <>
                <span className="chip c-ok">
                  등록됨 · 초안 생성 중
                </span>
                <a className="btn btn-s" href="#/Soon?name=Closure">
                  종결 검토 보기
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
                      김순자 · C-2026-0351
                    </b>
                    <span className="sub">
                      만 82세 · 여 · 독거
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
                          <a className="btn btn-p" href="#/Step1Record" onClick={v.recClose}>
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
