// 1 · STT 검수 (화자: 피해아동 · 사례관리대상자 · 상담원)
// 원본: 다솔 님 디자인 counselor-web-design/SttReview.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=…&session=…. 원문은 useTranscriptReview, 회차 · 사례 머리는 useSessionDetail · useCaseDetail 이
// 부르고, 화면에 쓸 값은 src/data/screens/sttReview.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 변환 중이면 단계 이름(진행률 % 는 Backend 에 없음), 끝나면 발화 줄. 고친 발화만 저장하고 확정한 뒤 AI 분석을 요청하고
// 유형별 위험도로 간다(10/27 디자인, 분석 요청은 useSessionAnalysis).
// 10/21 디자인(counselor-design/screens/SttReview.dc.html): 제목 옆 '←'(내담자 정보), 시간 단추(그 발화부터 다시 듣기 — 10/28 동작),
// 화자 고르기 목록, 주소 ?seg=<발화 ID> 가 가리키는 줄 표시 · 스크롤(useSttFocus), 범례,
// 현재 단계 강조. 10/27 디자인: 단계 이름 '유형별 위험도', 다음 단추 '원문 확정 · 유형별 위험도 →'(확정 + AI 분석 요청 + 이동).
// 10/22 디자인: 아래 '위험 신호' 구역을 빼고, '전체 STT' 보기는 일정 높이 상자(.ln-box) 안에서 스크롤하고,
// 하단 고정 재생 바(SttPlayer — 10/28 부터 실제 재생, 확인 안 한 저신뢰 표시를 누르면 그 줄로 이동)를 붙였다.
// 10/28: 녹음 재생(useSessionAudio → Blob URL, useAudioPlayer)과 아동 발화 줄의 음성 참고 표시(useVoiceMarks, 칩 .cues).
// 저장 · 확정 단추는 디자인의 다음 단추 자리(STT 카드 아래)에 있다. 디자인의 분석 알림(job-toast)은 앱 전체 작업이라 여기 없다.
// 11/03: 전체 STT 보기는 같은 화자가 이어 말한 발화를 한 문단(ParaRow, 시간은 범위)으로 합치고, 다시 들어 확인할 발화는 줄(LineRow)로 따로 보인다.
import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import SessionPick from '../components/SessionPick';
import Sidebar from '../components/Sidebar';
import StepNav from '../components/StepNav';
import SttPlayer from '../components/SttPlayer';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAudioPlayer } from '../data/useAudioPlayer';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSessionDetail } from '../data/useSessionDetail';
import { useSessionAnalysis } from '../data/useSessionAnalysis';
import { useSessionAudio } from '../data/useSessionAudio';
import { useTranscriptReview } from '../data/useTranscriptReview';
import { useVoiceMarks } from '../data/useVoiceMarks';
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

/**
 * 줄의 화자 단추와 화자 고르기 목록. 목록은 단추 위치를 재어 화면 기준 고정 위치(position: fixed)에 띄운다 — 전체 보기
 * 스크롤 상자나 카드 안에 두면 줄이 적거나 끝쪽일 때 상자 밖으로 잘렸다(Codex #75 F4 · R2). 아래 공간이 모자라면 위로 연다.
 * 목록 밖을 스크롤하거나 창 크기가 바뀌면 닫는다(띄운 자리가 단추와 어긋나지 않게).
 */
function SpeakerPicker({ l }) {
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const [place, setPlace] = useState(null);
  const open = l.spMenu;
  // toggleSp 는 그릴 때마다 새 함수라 ref 로 들고, 아래 효과는 열림 여부에만 반응한다(재고 다시 그리기가 되풀이되지 않게).
  const toggleRef = useRef(l.toggleSp);
  toggleRef.current = l.toggleSp;

  useLayoutEffect(() => {
    if (!open) {
      setPlace(null);
      return undefined;
    }
    const button = buttonRef.current;
    const menu = menuRef.current;
    if (button && menu) {
      const r = button.getBoundingClientRect();
      const h = menu.offsetHeight;
      const w = menu.offsetWidth;
      const gap = 4;
      const below = window.innerHeight - r.bottom;
      const up = below < h + gap && r.top > below;
      setPlace({
        top: up ? Math.max(8, r.top - h - gap) : r.bottom + gap,
        left: Math.max(8, Math.min(r.left, window.innerWidth - w - 8)),
      });
    }
    const close = (event) => {
      if (event && event.target instanceof Node && menuRef.current && menuRef.current.contains(event.target)) return;
      toggleRef.current();
    };
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => {
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
    };
  }, [open]);

  // 화자를 고칠 수 없는 화면(원문을 잠근 뒤 · 핵심 발화 보기)에서는 글자로만 보인다(11/03 — 눌러도 아무것도 안 열리는 단추였다).
  if (l.spStatic) {
    return (
      <span
        className="chip"
        style={{ fontSize: '12px', background: '#F2EFE8', color: '#66625A', fontWeight: l.spFw }}
        title="원문을 잠근 뒤에는 화자를 바꿀 수 없습니다"
      >
        {l.sp}
      </span>
    );
  }

  return (
    <span className="spw" onKeyDown={l.spKey}>
      <button
        ref={buttonRef}
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
      {open ? (
        <span
          ref={menuRef}
          className="spmenu"
          role="listbox"
          aria-label="화자 선택"
          style={
            place
              ? { position: 'fixed', top: `${place.top}px`, left: `${place.left}px`, zIndex: 60 }
              : { position: 'fixed', top: '0', left: '0', zIndex: 60, visibility: 'hidden' }
          }
        >
          {(l.spOpts || []).map((o) => (
            <button key={o.value} type="button" role="option" aria-selected={o.sel} className={o.cls} onClick={o.pick}>
              {o.label}
            </button>
          ))}
        </span>
      ) : null}
    </span>
  );
}

/** 발화 한 줄(확인할 곳 · 핵심 발화 보기의 모든 줄, 전체 STT 보기에서 따로 보이는 줄). */
function LineRow({ l, focusRef, nowRef }) {
  return (
    <div className="ln" ref={l.focus ? focusRef : undefined} style={{ background: l.bg, boxShadow: l.ring }}>
      <span>
        <button type="button" className="tbtn" aria-label={l.playAria} onClick={l.play ?? undefined} disabled={!l.play}>
          {l.t}
        </button>
      </span>
      <span style={{ display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' }}>
        <SpeakerPicker l={l} />
        {l.spFix ? (
          <span className="note" style={{ fontSize: '11px' }}>
            상담원 수정
          </span>
        ) : null}
      </span>
      <span ref={l.now ? nowRef : undefined} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {l.edit ? (
          <input
            className="in"
            type="text"
            value={l.text}
            onChange={l.onText}
            readOnly={!l.canEdit}
            aria-label={l.aria}
          />
        ) : null}
        {l.read ? <span style={{ fontSize: '15px' }}>{l.text}</span> : null}
        <span className="note" style={{ color: l.hintFg }}>
          {l.hint}
        </span>
        {l.laws.length > 0 ? (
          <span className="laws">
            {l.laws.map((w) => (
              <span key={w.key} className="law">
                <span className="sig">{w.sig}</span>
                <span className="ref">
                  {w.law} <span className="art">{w.art}</span>
                </span>
                <span className="sum">{w.sum}</span>
                {w.url ? (
                  <a className="orig" href={w.url} target="_blank" rel="noopener noreferrer">
                    원문보기 ↗
                  </a>
                ) : null}
              </span>
            ))}
          </span>
        ) : null}
        {l.cues.length > 0 ? (
          <span className="cues" aria-label="음성 참고 표시">
            {l.cues.map((c) => (
              <span key={c.key} className={c.cls} title={c.title || undefined}>
                <b>{c.name}</b>
                {c.num ? <span className="num">{c.num}</span> : null}
                {c.cmp ? <span className="cmp">{c.cmp}</span> : null}
              </span>
            ))}
          </span>
        ) : null}
        {l.hold ? <span className="hold">{l.hold}</span> : null}
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span className="note">{l.conf}</span>
        {l.check ? (
          <button type="button" className="btn btn-sm btn-s" onClick={l.ok}>
            {l.okLabel}
          </button>
        ) : null}
      </span>
    </div>
  );
}

/**
 * 같은 화자 문단(전체 STT 보기, 2026-11-03). 문장마다 발화 하나라 누르면 그 문장을 고치거나(입력칸이 문단 아래 열린다)
 * 읽기 화면에서는 그 문장부터 다시 듣는다. 줄 칸 순서(시간 · 화자 · 글 · 오른쪽)는 LineRow 와 같다.
 */
function ParaRow({ b, nowRef }) {
  const press = (s) => (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      s.pick();
    }
  };
  return (
    <div className="ln para" style={{ background: '#FFFFFF', boxShadow: b.now ? 'inset 4px 0 0 #C2A36B' : 'none' }}>
      <span>
        <button type="button" className="tbtn" aria-label={b.playAria} onClick={b.play ?? undefined} disabled={!b.play}>
          {b.t}
        </button>
      </span>
      <span style={{ display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' }}>
        <SpeakerPicker l={b} />
        {b.spFix ? (
          <span className="note" style={{ fontSize: '11px' }}>
            상담원 수정
          </span>
        ) : null}
      </span>
      <span style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <p className="para-text">
          {b.sentences.map((s) => (
            <Fragment key={s.key}>
              {s.pick ? (
                <span
                  ref={s.now ? nowRef : undefined}
                  className={s.cls}
                  role="button"
                  tabIndex={0}
                  title={s.title}
                  aria-label={s.aria}
                  aria-pressed={s.on}
                  onClick={s.pick}
                  onKeyDown={press(s)}
                >
                  {s.text}
                </span>
              ) : (
                <span ref={s.now ? nowRef : undefined} className={s.cls} title={s.title}>
                  {s.text}
                </span>
              )}{' '}
            </Fragment>
          ))}
        </p>
        {b.hint ? <span className="note">{b.hint}</span> : null}
        {b.editor ? (
          <span className="snt-edit">
            <button
              type="button"
              className="tbtn"
              aria-label={b.editor.playAria}
              onClick={b.editor.play ?? undefined}
              disabled={!b.editor.play}
            >
              {b.editor.t}
            </button>
            <SpeakerPicker l={b.editor} />
            <input
              className="in"
              type="text"
              value={b.editor.text}
              onChange={b.editor.onText}
              readOnly={!b.editor.canEdit}
              aria-label={b.editor.aria}
              autoFocus
            />
            <button type="button" className="btn btn-sm btn-s" onClick={b.closeEditor}>
              닫기
            </button>
          </span>
        ) : null}
      </span>
      <span></span>
    </div>
  );
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
  const analysis = useSessionAnalysis(ids.sessionId, { enabled });
  const hasAudio = detail.session?.hasAudio ?? false;
  const audio = useSessionAudio(ids.sessionId, { enabled: enabled && hasAudio });
  // 원문이 보이면 녹음 파일을 미리 받아 둔다 — 브라우저는 사용자 조작 직후에만 재생을 허용해, 누른 뒤 받기 시작하면 늦을 수 있다.
  const player = useAudioPlayer(audio, { prefetch: review.info !== null });
  const marks = useVoiceMarks(ids.sessionId, {
    enabled,
    waiting: review.info !== null,
    transcriptVersion: review.info?.version ?? null,
  });
  const theme = useTheme();
  const v = useDC(Logic, {
    ...props,
    session,
    ids,
    detail,
    caseDetail,
    review,
    analysis,
    player,
    marks,
    go,
    focusSegment,
  });
  // 주소의 seg, 또는 재생 바 표시를 눌러 고른 줄(v.focusId)로 스크롤한다. 누를 때마다 v.focusRequest 가 바뀐다.
  const focusRef = useSttFocus(ids.sessionId, v.focusId, v.focusRequest);
  // 주소의 seg · 회차가 바뀌면(뒤로 가기 포함) 재생 바 표시로 옮겨 간 줄을 잊는다.
  const { clearJump } = v;
  useEffect(() => {
    clearJump();
  }, [focusSegment, ids.sessionId]); // eslint-disable-line react-hooks/exhaustive-deps
  // 재생 중이면 지금 듣는 발화(v.nowId)가 전체 STT 상자 안에 보이게 상자만 스크롤한다(11/03 — 페이지는 움직이지 않는다).
  const nowRef = useRef(null);
  useEffect(() => {
    const el = nowRef.current;
    if (!v.nowFollow || !el) return;
    const box = el.closest('.ln-box.scroll');
    if (!box) return;
    const b = box.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    if (r.top < b.top || r.bottom > b.bottom) box.scrollTop += r.top - b.top - 24;
  }, [v.nowId, v.nowFollow]);
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
            <NotiBell session={session} />
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
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px', marginTop: '2px' }}>
                <A
                  className="btn btn-sm btn-s"
                  to={v.caseHref}
                  aria-label="내담자 정보로 돌아가기"
                  title="내담자 정보로 돌아가기"
                >
                  ←
                </A>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
                <SessionPick label={v.pickLabel} head={v.pickHead} items={v.picks || []} />
              </div>
            </div>
          </header>
          <StepNav steps={v.steps} />
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
              <section className="card" aria-label="기록 확인" style={{ overflow: 'hidden' }}>
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
                  {(v.blocks || []).map((b) =>
                    b.kind === 'para' ? (
                      <ParaRow key={b.key} b={b} nowRef={nowRef} />
                    ) : (
                      <LineRow key={b.key} l={b.line} focusRef={focusRef} nowRef={nowRef} />
                    ),
                  )}
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
                <button
                  type="button"
                  className="btn btn-p"
                  onClick={v.next}
                  disabled={!v.canNext}
                  title={v.nextHint || undefined}
                >
                  {v.nextLabel}
                </button>
                {v.nextHint ? (
                  <span className="note" style={{ width: '100%', textAlign: 'right' }}>
                    {v.nextHint}
                  </span>
                ) : null}
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
