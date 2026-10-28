// 3 · 상담 요약 (사정 관점) · 상담 일지 (기관 양식)
// 원본: 다솔 님 디자인 counselor-web-design/NoteWrite.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=…&session=…. 상담 요약은 useSummaryReview(고치기 · 저장 · 승인), 상담 일지는
// useSessionDocuments(상담일지 문서 만들기 · 고치기 · 승인), 머리는 useSessionDetail · useCaseDetail 이 부르고,
// 화면에 쓸 값은 src/data/screens/noteWrite.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// '요약 승인' · '일지 승인' 은 누르면 바로 승인한다(승인한 뒤 '요약 수정' · '일지 수정' 으로 풀 수 있다).
// '요약 승인' 은 회차를 '승인 완료' 로 바꾼다. 아래 '저장 · …' 단추는 저장만 한다.
// 10/21 디자인(counselor-design/screens/NoteWrite.dc.html): 제목 옆 '←'(내담자 정보로), 칸 이름 괄호 삭제, 현재 단계 강조,
// 아동 특성 · 가정상황의 '수정 → 확인'(펼치면 고르기 단추, 접으면 고른 항목만 ✓ — 값은 noteWrite.ts 의 pickSection).
// 디자인에 없는 '요약 승인' · '일지 승인' · '요약 수정' · '일지 수정' 단추와 AI 초안 · AI 근거 표시는 그대로 둔다(AI 생성 → 상담사
// 확인 → 승인 흐름). 단계 이름은 10/27 디자인대로 '유형별 위험도' 다(칸 이름 '위험 신호 검토 결과' 는 디자인 그대로).
import { Fragment, useMemo } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import StepNav from '../components/StepNav';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useRiskAssessments } from '../data/useRiskAssessments';
import { useRiskSignals } from '../data/useRiskSignals';
import { useSessionAnalysis } from '../data/useSessionAnalysis';
import { useSessionDetail } from '../data/useSessionDetail';
import { useSessionDocuments } from '../data/useSessionDocuments';
import { useSummaryReview } from '../data/useSummaryReview';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { INITIAL_NOTE_STATE, noteAiDraft, noteWriteValues } from '../data/screens/noteWrite';
import { sessionCaseId } from '../data/screens/sessionDetail';
import { useLeaveGuard } from '../data/screens/useLeaveGuard';
import { useScreenGo } from '../data/screens/useScreenGo';
import './NoteWrite.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_NOTE_STATE;
  }
  renderVals() {
    return noteWriteValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

// 아동 특성 · 가정상황 한 칸(10/21 디자인의 '수정 → 확인'). 초기면접 항목은 늘 단어로 보이고, 이 일지에서 추가로 고른 항목은
// 접으면 ✓ 칸으로, '수정' 으로 펼치면 고르기 단추로 보인다. 값(intake · pick)은 noteWrite.ts 가 만든다.
function PickSection({ title, intake, pick, ev }) {
  return (
    <>
      <div className="grp" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {title}
        <button
          type="button"
          className={`btn btn-sm ${pick.btnCls}`}
          style={{ marginLeft: 'auto' }}
          aria-pressed={pick.open}
          onClick={pick.toggle}
          disabled={!pick.canToggle}
          title={pick.btnTitle}
        >
          {pick.btnLabel}
        </button>
      </div>
      <div className="intake">
        <span className="k">초기면접</span>
        {intake && intake.words.length ? (
          <span className="words">{intake.words.join(', ')}</span>
        ) : (
          <span className="note">{intake ? intake.note : ''}</span>
        )}
      </div>
      {pick.open ? (
        <fieldset className="cklist">
          <legend>
            추가로 확인한 항목 <span className="note">초기면접에서 고른 항목은 목록에서 뺍니다</span>
          </legend>
          <div className="picks">
            {pick.choices.map((t) => (
              <button
                key={t.label}
                type="button"
                className={t.on ? 'chipck on' : 'chipck'}
                aria-pressed={t.on}
                onClick={t.toggle}
                disabled={t.disabled}
                style={{ background: t.bg, borderColor: t.bd, color: t.fg, fontWeight: t.fw }}
              >
                {t.mark} {t.label}
                {t.hint ? <span className="note"> · {t.hint}</span> : null}
              </button>
            ))}
          </div>
        </fieldset>
      ) : (
        <div className="intake">
          <span className="k">추가로 확인한 항목</span>
          {pick.picked.length ? (
            <span className="picks">
              {pick.picked.map((t) => (
                <span
                  key={t.label}
                  className="chipck on"
                  style={{ cursor: 'default', background: '#F1EADA', borderColor: '#2B2A26', fontWeight: '700' }}
                >
                  ✓ {t.label}
                  {t.hint ? <span className="note"> · {t.hint}</span> : null}
                </span>
              ))}
            </span>
          ) : (
            <span className="note">선택된 항목 없음</span>
          )}
        </div>
      )}
      {(ev || []).map((e, eIndex) => (
        <span key={eIndex} className="ev">
          <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
            AI 제안 · {e.label}
          </span>
          {e.ev}
        </span>
      ))}
    </>
  );
}

export default function NoteWrite(props) {
  const session = useAuthSession();
  const ids = readScreenIds(useSearchParams()[0]);
  const go = useScreenGo(useNavigate());
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const summary = useSummaryReview(ids.sessionId, { enabled });
  const docs = useSessionDocuments(ids.sessionId, { enabled });
  // 일지 '아동 진술' · '위험 신호 검토 결과' AI 초안 재료(noteWrite.ts 머리 주석). 초안은 저장한 일지가 없을 때만 쓰므로
  // 일지 목록을 받았고 저장한 일지가 없을 때만 부른다(요청 수 — 민규 #95 리뷰).
  const draftNeeded = enabled && !docs.loading && !docs.error && docs.consultationRecord === null;
  const analysis = useSessionAnalysis(ids.sessionId, { enabled: draftNeeded });
  const signals = useRiskSignals(ids.sessionId, analysis.analysis, { enabled: draftNeeded });
  const risk = useRiskAssessments(ids.sessionId, { enabled: draftNeeded });
  const aiDraft = useMemo(
    () => noteAiDraft(summary.evidence, signals.cards, risk.loaded && !risk.loadError ? risk.rows : null),
    [summary.evidence, signals.cards, risk.loaded, risk.loadError, risk.rows],
  );
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, summary, docs, aiDraft, go });
  useLeaveGuard(v.unsaved);
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-NoteWrite">
      <div
        className={theme.cls}
        style={{
          minHeight: '2000px',
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
          <StepNav steps={v.steps} />
          <section
            className="card"
            aria-label="상담 요약"
            style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">상담 요약</h2>
              <span className="chip c-ai">{v.summaryChip}</span>
            </div>
            {v.summaryNote ? (
              <p className="note" role="status" style={{ margin: 0 }}>
                {v.summaryNote}
                {v.summaryLink ? (
                  <>
                    {' '}
                    <A to={v.summaryLink.href}>{v.summaryLink.label}</A>
                  </>
                ) : null}
              </p>
            ) : null}
            {(v.sums || []).map((r, rIndex) => (
              <Fragment key={rIndex}>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                    <b style={{ fontSize: '14px' }}>{r.k}</b>
                    {r.src ? (
                      <span className="ev" style={{ fontSize: '12px' }}>
                        근거 · {r.src}
                      </span>
                    ) : null}
                  </span>
                  <textarea className="ta2" aria-label={r.k} value={r.v} onChange={r.onChange} readOnly={r.readOnly} />
                </label>
              </Fragment>
            ))}
            {v.summaryError ? (
              <p className="note" role="alert" style={{ margin: 0, color: '#A33B2E' }}>
                {v.summaryError}
              </p>
            ) : null}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'flex-end' }}>
              {v.summaryApproved ? (
                <button type="button" className="btn btn-s" onClick={v.reopenSummary} disabled={!v.canReopenSummary}>
                  요약 수정
                </button>
              ) : (
                <>
                  <button type="button" className="btn btn-s" onClick={v.saveSummary} disabled={!v.canSaveSummary}>
                    요약 저장
                  </button>
                  <button type="button" className="btn btn-p" onClick={v.approveSummary} disabled={!v.canApproveSummary}>
                    요약 승인
                  </button>
                </>
              )}
            </div>
          </section>

          <section
            className="card"
            aria-label="상담 일지"
            style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">상담 일지 · 서비스제공 일지</h2>
              <span className="chip c-ai">{v.docChip}</span>
              {v.docNote ? <span className="note">{v.docNote}</span> : null}
            </div>
            <div className="fhead">
              {(v.fhead || []).map((f, fIndex) => (
                <div key={fIndex}>
                  <span className="k">{f.k}</span>
                  <span className="v">{f.v}</span>
                </div>
              ))}
            </div>

            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>아동 진술</b>
              <textarea className="ta2" style={{ minHeight: '104px' }} {...v.statement} />
            </label>

            <div className="grp">대상자 태도 및 관찰내용</div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <b style={{ fontSize: '14px' }}>대상자 태도</b>
                {v.aiDraft ? (
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 초안 · 녹취에서
                  </span>
                ) : null}
              </span>
              <textarea className="ta2" {...v.attitude} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>물리적 환경</b>
              <textarea className="ta2" placeholder="상담원 작성" {...v.environment} />
              <span className="note acc">신변안전 · 기관 복귀 후 기록 (현장 기록 금지)</span>
            </label>

            <PickSection title="아동 특성" intake={v.traitIntake} pick={v.traitPick} ev={v.traitEv} />

            <PickSection title="가정상황" intake={v.homeIntake} pick={v.homePick} ev={v.homeEv} />

            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>위험 신호 검토 결과</b>
              <textarea className="ta2" {...v.signals} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <b style={{ fontSize: '14px' }}>상담원 소견 및 향후 계획</b>
                {v.aiDraft ? (
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 초안
                  </span>
                ) : null}
              </span>
              <textarea className="ta2" style={{ minHeight: '96px' }} {...v.opinion} />
            </label>
            {v.docError ? (
              <p className="note" role="alert" style={{ margin: 0, color: '#A33B2E' }}>
                {v.docError}
              </p>
            ) : null}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'flex-end' }}>
              {v.docApproved ? (
                <button type="button" className="btn btn-s" onClick={v.reopenDoc} disabled={!v.canReopenDoc}>
                  일지 수정
                </button>
              ) : (
                <>
                  <button type="button" className="btn btn-s" onClick={v.saveDoc} disabled={!v.canSaveDoc}>
                    일지 저장
                  </button>
                  <button type="button" className="btn btn-p" onClick={v.approveDoc} disabled={!v.canApproveDoc}>
                    일지 승인
                  </button>
                </>
              )}
            </div>
          </section>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <A className="btn btn-s" to={v.backHref}>
              ← 유형별 위험도
            </A>
            <button
              type="button"
              className="btn btn-p"
              onClick={v.next}
              disabled={!v.canNext}
              style={{ marginLeft: 'auto' }}
            >
              {v.nextLabel}
            </button>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
