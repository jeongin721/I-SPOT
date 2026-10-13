// 3 · 상담 요약 (사정 관점) · 상담 일지 (기관 양식)
// 원본: I-SPOT 디자인 캔버스 보드 NoteWrite.dc.html (자동 변환 후 다듬어 쓰세요)
//
// 서버 연결: 화면 주소 ?case=…&session=…. 상담 요약은 useSummaryReview(고치기 · 저장 · 승인), 상담 일지는
// useSessionDocuments(상담일지 문서 만들기 · 고치기 · 승인), 머리는 useSessionDetail · useCaseDetail 이 부르고,
// 화면에 쓸 값은 src/data/screens/noteWrite.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// '요약 승인' 은 회차를 '승인 완료' 로 바꾸므로 따로 단추를 두고 한 번 더 묻는다. 아래 '저장 · …' 단추는 저장만 한다.
import { Fragment } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSessionDetail } from '../data/useSessionDetail';
import { useSessionDocuments } from '../data/useSessionDocuments';
import { useSummaryReview } from '../data/useSummaryReview';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { INITIAL_NOTE_STATE, noteWriteValues } from '../data/screens/noteWrite';
import { sessionCaseId } from '../data/screens/sessionDetail';
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

export default function NoteWrite(props) {
  const session = useAuthSession();
  const ids = readScreenIds(useSearchParams()[0]);
  const go = useNavigate();
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const summary = useSummaryReview(ids.sessionId, { enabled });
  const docs = useSessionDocuments(ids.sessionId, { enabled });
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, summary, docs, go });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-NoteWrite">
      <div
        style={{
          minHeight: '2000px',
          background: '#FFFEFA',
          color: '#2F3A44',
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <aside className="side" aria-label="주 메뉴">
          <A className="logo" to="/Main">
            <span className="mk">IS</span>
            <b style={{ fontSize: '17px' }}>I-SPOT</b>
          </A>
          <A className="cta" to="/UploadModal">
            ↑ 녹취 · 자료 올리기
          </A>
          <A className="cta2" to="/CaseRegister">
            + 새 사례 등록
          </A>
          <nav className="nav" aria-label="메뉴">
            <A to="/Main">홈</A>
            <A className="on" to="/CaseList">
              사례 관리
            </A>
            <A to="/Schedule">일정</A>
            <A to="/ChildLink">
              아이 연계<span className="cnt">4</span>
            </A>
            <A to="/Closure">
              종결 검토<span className="cnt">2</span>
            </A>
            <A to="/Stats">통계</A>
            <A to="/Settings">설정</A>
          </nav>
          <div className="me">
            <span className="av">{v.meInitial}</span>
            <b style={{ fontWeight: '500' }}>{v.meName}</b>
            <A to="/Login" className="note" style={{ marginLeft: 'auto' }} onClick={v.logout}>
              로그아웃
            </A>
          </div>
        </aside>
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
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › <A to={v.caseHref}>{v.caseLabel}</A> ›{' '}
            <A to={v.historyHref}>상담 이력</A> › <A to={v.sessionHref}>{v.sessionLabel}</A>
          </nav>
          <Notice value={v.notice} />
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 280px' }}>
              <div className="sub">{v.sub}</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
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
            {(v.summaryEv || []).map((e, eIndex) => (
              <span key={eIndex} className="ev">
                <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                  {e.label}
                </span>
                {e.ev}
              </span>
            ))}
            {v.summaryError ? (
              <p className="note" role="alert" style={{ margin: 0, color: '#93452E' }}>
                {v.summaryError}
              </p>
            ) : null}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-s" onClick={v.saveSummary} disabled={!v.canSaveSummary}>
                요약 저장
              </button>
              <button type="button" className="btn btn-p" onClick={v.askSummary} disabled={!v.canApproveSummary}>
                요약 승인
              </button>
            </div>
            {v.summaryAsk ? (
              <div
                role="alertdialog"
                aria-label="승인 확인"
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '12px 14px',
                  borderRadius: '12px',
                  background: '#F8F5EC',
                }}
              >
                <span style={{ flex: '1 1 260px' }}>{v.summaryAskText}</span>
                <button type="button" className="btn btn-sm btn-s" onClick={v.cancelAsk}>
                  취소
                </button>
                <button type="button" className="btn btn-sm btn-p" onClick={v.approveSummary}>
                  승인
                </button>
              </div>
            ) : null}
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
              <textarea
                className="ta2"
                style={{ minHeight: '104px' }}
                {...v.statement}
              />
            </label>
            <div className="grp">대상자 태도 및 관찰내용</div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <b style={{ fontSize: '14px' }}>(대상자 태도)</b>
                {v.aiDraft ? (
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 초안 · 녹취에서
                  </span>
                ) : null}
              </span>
              <textarea
                className="ta2"
                {...v.attitude}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>(물리적 환경)</b>
              <textarea className="ta2" placeholder="상담원 작성" {...v.environment} />
              <span className="note acc">신변안전 · 기관 복귀 후 기록 (현장 기록 금지)</span>
            </label>
            <div className="grp">아동 특성</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {(v.traits || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <button
                    type="button"
                    className="chipck"
                    onClick={t.toggle}
                    disabled={t.disabled}
                    style={{ background: t.bg, borderColor: t.bd, color: t.fg, fontWeight: t.fw }}
                  >
                    {t.mark} {t.label}
                  </button>
                </Fragment>
              ))}
            </div>
            {(v.traitEv || []).map((e, eIndex) => (
              <Fragment key={eIndex}>
                <span className="ev">
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안 · {e.label}
                  </span>
                  {e.ev}
                </span>
              </Fragment>
            ))}
            <div className="grp">가정상황</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {(v.homes || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <button
                    type="button"
                    className="chipck"
                    onClick={t.toggle}
                    disabled={t.disabled}
                    style={{ background: t.bg, borderColor: t.bd, color: t.fg, fontWeight: t.fw }}
                  >
                    {t.mark} {t.label}
                  </button>
                </Fragment>
              ))}
            </div>
            {(v.homeEv || []).map((e, eIndex) => (
              <Fragment key={eIndex}>
                <span className="ev">
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안 · {e.label}
                  </span>
                  {e.ev}
                </span>
              </Fragment>
            ))}
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>위험 신호 검토 결과</b>
              <textarea
                className="ta2"
                {...v.signals}
              />
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
              <textarea
                className="ta2"
                style={{ minHeight: '96px' }}
                {...v.opinion}
              />
            </label>
            {v.docError ? (
              <p className="note" role="alert" style={{ margin: 0, color: '#93452E' }}>
                {v.docError}
              </p>
            ) : null}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-s" onClick={v.saveDoc} disabled={!v.canSaveDoc}>
                일지 저장
              </button>
              <button type="button" className="btn btn-p" onClick={v.askDoc} disabled={!v.canApproveDoc}>
                일지 승인
              </button>
            </div>
            {v.docAsk ? (
              <div
                role="alertdialog"
                aria-label="승인 확인"
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '12px 14px',
                  borderRadius: '12px',
                  background: '#F8F5EC',
                }}
              >
                <span style={{ flex: '1 1 260px' }}>{v.docAskText}</span>
                <button type="button" className="btn btn-sm btn-s" onClick={v.cancelAsk}>
                  취소
                </button>
                <button type="button" className="btn btn-sm btn-p" onClick={v.approveDoc}>
                  승인
                </button>
              </div>
            ) : null}
          </section>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <A className="btn btn-s" to={v.backHref}>
              ← 위험 신호 검토
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
