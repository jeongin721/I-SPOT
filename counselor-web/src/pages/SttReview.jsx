// 1 · STT 검수 (화자: 피해아동 · 사례관리대상자 · 상담원)
// 원본: 다솔 님 디자인 counselor-web-design/SttReview.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=…&session=…. 원문은 useTranscriptReview, 회차 · 사례 머리는 useSessionDetail · useCaseDetail 이
// 부르고, 화면에 쓸 값은 src/data/screens/sttReview.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 변환 중이면 단계 이름(진행률 % 는 Backend 에 없음), 끝나면 발화 줄. 고친 발화만 저장하고 확정한 뒤 위험 신호 검토로 간다.
// 10/21 디자인(counselor-design/screens/SttReview.dc.html): 제목 옆 '←'(내담자 정보), 시간 단추(다시 듣기 — 준비 중),
// 화자 고르기 목록, 주소 ?seg=<발화 ID> 가 가리키는 줄 표시 · 스크롤(useSttFocus), 범례,
// 현재 단계 강조. 단계 이름 · '원문 확정 · 신호 분석' 단추와 그 뒤 흐름은 앱 그대로다(분석 시작 흐름은 팀 결정 전).
// 10/22 디자인: 아래 '위험 신호' 구역을 빼고, '전체 STT' 보기는 일정 높이 상자(.ln-box) 안에서 스크롤하고,
// 하단 고정 재생 바(SttPlayer — 재생 단추는 준비 중, 확인 안 한 저신뢰 표시를 누르면 그 줄로 이동)를 붙였다.
// 저장 · 확정 단추는 디자인의 다음 단추 자리(STT 카드 아래)에 있다. 디자인의 분석 알림(job-toast)은 앱 전체 작업이라 여기 없다.
import { Fragment } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import SttPlayer from '../components/SttPlayer';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSessionDetail } from '../data/useSessionDetail';
import { useTranscriptReview } from '../data/useTranscriptReview';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { sessionCaseId } from '../data/screens/sessionDetail';
import { useLeaveGuard } from '../data/screens/useLeaveGuard';
import { useScreenGo } from '../data/screens/useScreenGo';
import { useSttFocus } from '../data/screens/useSttFocus';
import { INITIAL_STT_STATE, readFocusSegment, sttReviewValues } from '../data/screens/sttReview';
import './SttReview.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_STT_STATE;
  }
  renderVals() {
    return sttReviewValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function SttReview(props) {
  const session = useAuthSession();
  const [search] = useSearchParams();
  const ids = readScreenIds(search);
  const focusSegment = readFocusSegment(search);
  const go = useScreenGo(useNavigate());
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const review = useTranscriptReview(ids.sessionId, { enabled });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, review, go, focusSegment });
  // 주소의 seg, 또는 재생 바 표시를 눌러 고른 줄(v.focusId)로 스크롤한다. 누를 때마다 v.focusRequest 가 바뀐다.
  const focusRef = useSttFocus(ids.sessionId, v.focusId, v.focusRequest);
  useLeaveGuard(v.unsaved);
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-SttReview">
      <div
        className={theme.cls}
        style={{
          minHeight: '1250px',
          background: '#E9E7E1',
          color: '#2B2A26',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <Sidebar active="CaseList" session={session} />
        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          <div className="thm-bar">
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › <A to={v.caseHref}>{v.caseLabel}</A> › <A to={v.historyHref}>상담 이력</A>{' '}
            › <A to={v.sessionHref}>{v.sessionLabel}</A>
          </nav>
          <Notice value={v.notice} />
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 280px' }}>
              <div className="sub">{v.sub}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '2px' }}>
                <A
                  className="btn btn-sm btn-s"
                  to={v.caseHref}
                  aria-label="내담자 정보로 돌아가기"
                  title="내담자 정보로 돌아가기"
                >
                  ←
                </A>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
              </div>
            </div>
          </header>
          <nav className="steps" aria-label="회차 처리 단계">
            {(v.steps || []).map((t, tIndex) => (
              <A key={tIndex} className={t.cls} to={t.href} aria-current={t.current}>
                <span className="sn">{t.mark}</span>
                <b style={{ fontWeight: t.weight }}>{t.label}</b>
              </A>
            ))}
          </nav>
          {v.analyzing ? (
            <>
              <section
                className="card"
                aria-live="polite"
                style={{ padding: '28px 26px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="chip c-sky">{v.progressChip}</span>
                  <b>{v.stageLabel}</b>
                </div>
                {v.error ? (
                  <p className="note" role="alert" style={{ margin: 0, color: '#A33B2E' }}>
                    {v.error}
                  </p>
                ) : null}
                {v.progressAction ? (
                  <button
                    type="button"
                    className="btn btn-sm btn-s"
                    style={{ alignSelf: 'flex-start' }}
                    onClick={v.progressAction}
                  >
                    {v.progressActionLabel}
                  </button>
                ) : null}
              </section>
            </>
          ) : null}

          {v.done ? (
            <>
              <section className="card" aria-label="STT 검수" style={{ overflow: 'hidden' }}>
                <div className="hd">
                  <h2 className="h2">{v.viewTitle}</h2>
                  <span className={v.chipCls}>{v.chipText}</span>
                  <div style={{ marginLeft: 'auto', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    <button type="button" className={`btn btn-sm ${v.allCls}`} onClick={v.showAll}>
                      전체 STT 보기
                    </button>
                    <button type="button" className={`btn btn-sm ${v.lowCls}`} onClick={v.showLow}>
                      저신뢰 구간 보기 · {v.lowLeft}
                    </button>
                  </div>
                </div>
                <div className={v.boxCls}>
                  {(v.lines || []).map((l) => (
                    <Fragment key={l.key}>
                      <div
                        className="ln"
                        ref={l.focus ? focusRef : undefined}
                        style={{ background: l.bg, boxShadow: l.ring }}
                      >
                        <span>
                          <button
                            type="button"
                            className="tbtn"
                            aria-label={l.playAria}
                            onClick={l.play ?? undefined}
                            disabled={!l.play}
                          >
                            {l.t}
                          </button>
                        </span>
                        <span style={{ display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' }}>
                          <span className="spw" onKeyDown={l.spKey}>
                            <button
                              type="button"
                              className="chip"
                              title="눌러서 화자 선택"
                              aria-haspopup="listbox"
                              aria-expanded={l.spMenu}
                              aria-label={`화자 바꾸기 · 지금 ${l.sp}`}
                              onClick={l.toggleSp}
                              disabled={!l.canEdit}
                              style={{
                                border: '0',
                                cursor: 'pointer',
                                font: 'inherit',
                                fontSize: '12px',
                                background: '#F2EFE8',
                                color: '#66625A',
                                fontWeight: l.spFw,
                              }}
                            >
                              {l.sp} ▾
                            </button>
                            {l.spMenu ? (
                              <span className="spmenu" role="listbox" aria-label="화자 선택">
                                {(l.spOpts || []).map((o) => (
                                  <button
                                    key={o.value}
                                    type="button"
                                    role="option"
                                    aria-selected={o.sel}
                                    className={o.cls}
                                    onClick={o.pick}
                                  >
                                    {o.label}
                                  </button>
                                ))}
                              </span>
                            ) : null}
                          </span>
                          {l.spFix ? (
                            <>
                              <span className="note" style={{ fontSize: '11px' }}>
                                상담원 수정
                              </span>
                            </>
                          ) : null}
                        </span>
                        <span style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {l.edit ? (
                            <>
                              <input
                                className="in"
                                type="text"
                                value={l.text}
                                onChange={l.onText}
                                readOnly={!l.canEdit}
                                aria-label={l.aria}
                              />
                            </>
                          ) : null}
                          {l.read ? (
                            <>
                              <span style={{ fontSize: '15px' }}>{l.text}</span>
                            </>
                          ) : null}
                          <span className="note" style={{ color: l.hintFg }}>
                            {l.hint}
                          </span>
                        </span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span className="note">{l.conf}</span>
                          {l.check ? (
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
                  <span>{v.playNote}</span>
                  <span className="k">
                    <span className="cue">
                      <b>목소리 신호</b>
                    </span>{' '}
                    {v.cueNote}
                  </span>
                  <span className="k">
                    <span className="sig">관련 조문</span> {v.lawNote}
                  </span>
                </div>
                <div style={{ height: '16px' }}></div>
              </section>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
                <span className="note">{v.versionLabel}</span>
                {v.error ? (
                  <span className="note" role="alert" style={{ color: '#A33B2E' }}>
                    {v.error}
                  </span>
                ) : null}
                <button
                  type="button"
                  className="btn btn-s"
                  onClick={v.save}
                  disabled={!v.canSave}
                  style={{ marginLeft: 'auto' }}
                >
                  저장
                </button>
                <button type="button" className="btn btn-p" onClick={v.next} disabled={!v.canNext}>
                  {v.nextLabel}
                </button>
              </div>
            </>
          ) : null}
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
          <SttPlayer p={v.player} />
        </main>
      </div>
    </div>
  );
}
