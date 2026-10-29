// 탭 1 · 내담자 정보 + 기관 서식 + 종결 검토 등록
// 원본: 다솔 님 디자인 counselor-web-design/CaseDetail.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 사례 정보 · 회차는 useCaseDetail 이 부르고, 화면에 쓸 값은
// src/data/screens/caseDetail.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다(디자인이 바뀌면 JSX 만 바꾼다).
// 서버에 없는 값(위험도 · 사례관리대상자 · 신고접수일 · 서비스 · 일정 등)은 '—', 종결 검토 등록은 준비 중.
// '초기면접 내용' 카드는 디자인에 없어 더한 칸이다: 사례 등록 ② 탭의 가정상황 · 아동 특성을 단어로 보이고 '수정' 으로 고친다
// (고르기 단추는 CaseRegister 와 같은 모양).
// 10/21 디자인(counselor-design/screens/CaseDetail.dc.html): '녹음하기' 창(마이크 녹음 → 녹취 올리기와 같은 업로드 · 원문 변환,
// components/RecordDialog.jsx), '아이 연계 →' 단추(탭에서 빠짐), 진행 단계 칸 링크, 사정결과 · 서비스 · 다음 일정 상자 삭제.
// 녹음 중이거나 올리지 않은 녹음이 있으면 화면을 떠날 때 묻는다(초기면접 수정과 같은 useLeaveGuard).
// 녹음은 창을 연 계정 · 사례의 것이다. 다른 탭에서 계정이 바뀌거나 다른 사례로 가거나 사례를 볼 수 없게 되면(403 등) 녹음을
// 버리고(마이크 끄기 · 들어 보기 주소 해제 · 올리기 멈춤) 창을 닫는다 — 앞 계정의 녹음을 새 계정이 듣거나 저장하지 않게.
import { Fragment, useEffect, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import RecordDialog, { recordingUnsaved } from '../components/RecordDialog';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAudioRecorder } from '../data/useAudioRecorder';
import { useAudioUpload } from '../data/useAudioUpload';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseSignals } from '../data/useCaseSignals';
import { useFollowupQuestions } from '../data/useFollowupQuestions';
import { INITIAL_CASE_DETAIL_STATE, caseDetailValues } from '../data/screens/caseDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useLeaveGuard } from '../data/screens/useLeaveGuard';
import './CaseDetail.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_CASE_DETAIL_STATE;
  }
  renderVals() {
    return caseDetailValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function CaseDetail(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const detail = useCaseDetail(caseId, { enabled: signedIn(session) });
  const signals = useCaseSignals(detail, { enabled: signedIn(session) });
  const theme = useTheme();
  const questions = useFollowupQuestions(detail.sessions[0]?.id ?? null, { enabled: signedIn(session) });
  const v = useDC(Logic, { ...props, session, detail, signals, questions, caseId });
  const [recOpen, setRecOpen] = useState(false);
  const recorder = useAudioRecorder();
  const upload = useAudioUpload();
  // 녹음의 주인: 창을 연 계정 · 사례. 지금 주인과 다르거나 사례를 볼 수 없으면 그 녹음은 낡았다.
  const owner = session.status === 'signedIn' && session.me && caseId ? `${session.me.id}|${caseId}` : null;
  const [recOwner, setRecOwner] = useState(null);
  const recStale = recOpen && (owner === null || owner !== recOwner || !v.canRecord);
  const { reset: resetRecorder } = recorder;
  const { reset: resetUpload } = upload;
  useEffect(() => {
    if (!recStale) return;
    resetRecorder();
    resetUpload();
    setRecOpen(false);
    setRecOwner(null);
  }, [recStale, resetRecorder, resetUpload]);
  useLeaveGuard(
    v.unsaved || (!recStale && (recordingUnsaved(recorder, upload) || (upload.busy && upload.phase !== 'transcribing'))),
  );
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-CaseDetail">
      <div
        className={theme.cls}
        style={{
          minHeight: '1350px',
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
            <A to="/CaseList">사례 관리</A> › {v.crumb}
          </nav>
          <Notice value={v.notice} />
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <A className="btn btn-sm btn-s" to="/CaseList">
              ← 목록
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
                <span className="sub">{v.sub}</span>
                <span className={`chip ${v.riskCls}`}>{v.riskChip}</span>
              </div>
              <div className="note">{v.meta}</div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-s"
                onClick={() => {
                  setRecOwner(owner);
                  setRecOpen(true);
                }}
                disabled={!v.canRecord || owner === null}
              >
                <span className="rec-dot" aria-hidden="true"></span> 녹음하기
              </button>
              <A className="btn btn-s" to={v.uploadHref}>
                ↑ 녹취 올리기
              </A>
            </div>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A className="on" aria-current="page" to={v.tabs.detail}>
              내담자 정보
            </A>
            <A to={v.tabs.history}>상담 이력</A>
            <A to={v.tabs.briefing}>상담 전 브리핑</A>
            <A to={v.tabs.docs}>문서함</A>
          </nav>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '18px' }}>
            <section className="card" aria-label="기본 정보" style={{ padding: '22px 24px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">기본 정보</h2>
                <A className="btn btn-sm btn-s" to={v.tabs.app} style={{ marginLeft: 'auto' }}>
                  아이 연계 →
                </A>
              </div>
              <dl className="kv" style={{ gridTemplateColumns: '120px 1fr' }}>
                {(v.basics || []).map((b, bIndex) => (
                  <Fragment key={bIndex}>
                    <dt>{b.label}</dt>
                    <dd style={b.strong ? { fontWeight: '700' } : undefined}>{b.value}</dd>
                  </Fragment>
                ))}
              </dl>
            </section>
            <section className="card" aria-label="주요 위험 요인" style={{ padding: '22px 24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">주요 위험 요인</h2>
                <span className={`chip ${v.riskCls}`} style={{ marginLeft: 'auto' }}>
                  {v.riskChip}
                </span>
              </div>
              <div className="note" style={{ marginTop: '4px', textAlign: 'right' }}>
                상담사 지정 · {v.riskBy}
              </div>
              {v.riskNote ? (
                <div className="note" role="alert" style={{ marginTop: '4px', color: '#A33B2E' }}>
                  {v.riskNote}
                </div>
              ) : null}
              <div className="note" style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                학대 유형
                {v.typesAi ? (
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안
                  </span>
                ) : null}
              </div>
              <div style={{ margin: '6px 0 16px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {(v.abuseTypes || []).map((t, tIndex) => (
                  <span key={tIndex} className="chip c-normal">
                    {t}
                  </span>
                ))}
              </div>
              <div className="note" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                주요 키워드
                {v.keywordsAi ? (
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안
                  </span>
                ) : null}
              </div>
              <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {(v.keywords || []).map((k, kIndex) => (
                  <span key={kIndex} className="chip c-normal">
                    {k}
                  </span>
                ))}
              </div>
              {v.typesAi || v.keywordsAi ? (
                <div className="note" style={{ marginTop: '10px' }}>
                  {v.aiNote}
                </div>
              ) : null}
            </section>
          </div>

          <section className="card intake" aria-label="초기면접 내용" style={{ padding: '22px 24px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">초기면접 내용</h2>
              <span className="note">서식 4 ②</span>
              {v.intake.canEdit ? (
                <button
                  type="button"
                  className="btn btn-s btn-sm"
                  onClick={v.intake.startEdit}
                  style={{ marginLeft: 'auto' }}
                >
                  수정
                </button>
              ) : null}
            </div>
            {v.intake.editing ? (
              <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <p className="note" style={{ margin: 0 }}>
                  {v.intake.editNote}
                </p>
                <div className="sec">
                  가정상황{' '}
                  <span className="note" style={{ fontWeight: '400' }}>
                    (복수응답 가능)
                  </span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {v.intake.homes.map((o) => (
                    <button
                      key={o.label}
                      type="button"
                      className={o.on ? 'pk on' : 'pk'}
                      aria-pressed={o.on}
                      onClick={o.toggle}
                      disabled={o.disabled}
                      style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                    >
                      {o.mark} {o.label}
                    </button>
                  ))}
                </div>
                <div className="sec">
                  아동 특성{' '}
                  <span className="note" style={{ fontWeight: '400' }}>
                    (복수응답 가능)
                  </span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {v.intake.traits.map((o) => (
                    <button
                      key={o.label}
                      type="button"
                      className={o.on ? 'pk on' : 'pk'}
                      aria-pressed={o.on}
                      onClick={o.toggle}
                      disabled={o.disabled}
                      style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                    >
                      {o.mark} {o.label}
                    </button>
                  ))}
                </div>
                <Notice value={v.intake.error} />
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', gap: '8px' }}>
                  <button type="button" className="btn btn-s btn-sm" onClick={v.intake.cancel} disabled={v.intake.saving}>
                    취소
                  </button>
                  <button type="button" className="btn btn-p btn-sm" onClick={v.intake.save} disabled={v.intake.saving}>
                    {v.intake.saveLabel}
                  </button>
                </div>
              </div>
            ) : (
              <dl className="kv" style={{ gridTemplateColumns: '120px 1fr' }}>
                {v.intake.rows.map((r) => (
                  <Fragment key={r.label}>
                    <dt>{r.label}</dt>
                    <dd className={r.empty ? 'note' : undefined}>{r.text}</dd>
                  </Fragment>
                ))}
              </dl>
            )}
          </section>

          <section className="card" aria-label="현재 진행 상황" style={{ padding: '22px 24px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <h2 className="h2">현재 진행 상황</h2>
              <span className="note">{v.latestLabel}</span>
              <A className="btn btn-p btn-sm" to={v.continueHref} style={{ marginLeft: 'auto' }}>
                {v.continueLabel}
              </A>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <div
                style={{
                  minWidth: '660px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: '10%',
                    right: '10%',
                    top: '17px',
                    height: '2px',
                    background: '#E7E4DC',
                  }}
                />
                {(v.progress || []).map((p, pIndex) => {
                  const inner = (
                    <>
                      <span className="sd" style={p.dot}>
                        {p.mark}
                      </span>
                      {p.done ? <span>{p.label}</span> : null}
                      {p.current ? <b style={{ fontWeight: '700', color: '#2B2A26' }}>{p.label}</b> : null}
                      {p.pending ? <span style={{ color: '#7A776F' }}>{p.label}</span> : null}
                      {p.chip ? <span className="chip c-check">{p.chip}</span> : null}
                    </>
                  );
                  return p.href ? (
                    <A key={pIndex} className="st stl" to={p.href}>
                      {inner}
                    </A>
                  ) : (
                    <div key={pIndex} className="st">
                      {inner}
                    </div>
                  );
                })}
              </div>
            </div>
          </section>

          <section
            className="card"
            aria-label="기관 서식"
            style={{ padding: '20px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px' }}
          >
            <b style={{ flex: '1 1 200px' }}>기관 서식</b>
            <span className="chip c-check">{v.formsChip}</span>
            <A className="btn btn-p" to={v.formsHref}>
              기관 서식 작성
            </A>
          </section>

          <section
            className="card"
            aria-label="종결 검토 등록"
            style={{ padding: '20px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px' }}
          >
            <b style={{ flex: '1 1 200px' }}>종결 검토</b>
            <button
              type="button"
              className="btn btn-y"
              disabled
              title={v.notReady}
              style={{ opacity: 0.5, cursor: 'not-allowed' }}
            >
              종결 검토 등록 · {v.notReady}
            </button>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
          {recOpen && !recStale ? (
            <RecordDialog
              caseId={caseId}
              caseName={v.recordCase}
              caseSub={v.sub}
              targets={v.recordTargets}
              recorder={recorder}
              upload={upload}
              onClose={() => setRecOpen(false)}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}
