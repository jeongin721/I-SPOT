// 탭 1 · 내담자 정보 + 기관 서식 + 종결 검토 등록
// 원본: 다솔 님 디자인 counselor-web-design/CaseDetail.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 사례 정보 · 회차는 useCaseDetail 이 부르고, 화면에 쓸 값은
// src/data/screens/caseDetail.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다(디자인이 바뀌면 JSX 만 바꾼다).
// 서버에 없는 값(사례관리대상자 · 신고접수일 · 서비스 · 일정 등)은 '—', 종결 검토 등록은 준비 중.
// 위험도 · 학대 유형 · 주요 키워드는 분석이 끝난 가장 최근 회차(useCaseSignals)의 상담원 판단 · AI 결과로 채운다(caseDetail.ts 머리 주석).
// '초기면접 내용' 카드는 디자인에 없어 더한 칸이다: 사례 등록 ② 탭의 가정상황 · 아동 특성을 단어로 보이고 '수정' 으로 고친다
// (고르기 단추는 CaseRegister 와 같은 모양).
// 10/21 디자인(counselor-design/screens/CaseDetail.dc.html): '녹음하기' 창(마이크 녹음 → 녹취 올리기와 같은 업로드 · 원문 변환,
// components/RecordDialog.jsx), '아이 연계 →' 단추(탭에서 빠짐), 진행 단계 칸 링크, 사정결과 · 서비스 · 다음 일정 상자 삭제.
// 10/29 디자인: 상담 전 브리핑이 탭에서 빠지고 이 화면 '현재 진행 상황' 아래(#brief)로 들어왔다. 값은 예전 브리핑 화면과
// 같은 preBriefingValues(분석이 끝난 가장 최근 회차). 주소에 view=brief 가 있으면 그 자리로 스크롤한다. '인쇄 · PDF' 는
// 이름 표시 방식(실명 그대로 / 이름 가리기)을 고르는 창을 띄우고 브리핑만 인쇄한다(가리기는 사례 별칭만 — 서버에 실명이 없다).
// 녹음 중이거나 올리지 않은 녹음이 있으면 화면을 떠날 때 묻는다(초기면접 수정과 같은 useLeaveGuard).
// 녹음하기 창의 주인 · 버리기 규칙은 data/useRecordFlow.ts(상담 이력 · 문서함과 같이 쓴다).
import { Fragment, useEffect, useRef, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import RecordDialog from '../components/RecordDialog';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseSignals } from '../data/useCaseSignals';
import { useFollowupChecks } from '../data/useFollowupChecks';
import { useFollowupQuestions } from '../data/useFollowupQuestions';
import { useSignalHistory } from '../data/useSignalHistory';
import { INITIAL_CASE_DETAIL_STATE, caseDetailValues } from '../data/screens/caseDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { preBriefingValues } from '../data/screens/preBriefing';
import { maskExample, maskName } from '../data/maskName';
import { useLeaveGuard } from '../data/screens/useLeaveGuard';
import { useRecordFlow } from '../data/useRecordFlow';
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

/** 브리핑만 인쇄한다(body.print-brief). 이름 가리기면 인쇄하는 동안만 브리핑 글자를 바꾸고 되돌린다. */
function printBrief(root, name, mask) {
  const changed = [];
  if (root && mask && name) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const next = maskName(node.nodeValue, name);
      if (next !== node.nodeValue) {
        changed.push([node, node.nodeValue]);
        node.nodeValue = next;
      }
    }
  }
  document.body.classList.add('print-brief');
  try {
    window.print();
  } finally {
    document.body.classList.remove('print-brief');
    changed.forEach(([node, value]) => {
      node.nodeValue = value;
    });
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
  const [params] = useSearchParams();
  const briefQuestions = useFollowupQuestions(signals.session?.id ?? null, { enabled: signedIn(session) });
  const history = useSignalHistory(caseId, { enabled: signedIn(session) });
  const briefChecks = useFollowupChecks(signals.session?.id ?? null, { enabled: signedIn(session) });
  const brief = preBriefingValues({ session, detail, signals, questions: briefQuestions, caseId, history, checks: briefChecks });
  const briefRef = useRef(null);
  const [outOpen, setOutOpen] = useState(false);
  const [outMask, setOutMask] = useState(true);
  const wantBrief = params.get('view') === 'brief';
  const briefReady = Boolean(detail.caseInfo);
  useEffect(() => {
    if (wantBrief && briefReady && briefRef.current) briefRef.current.scrollIntoView({ block: 'start' });
  }, [wantBrief, briefReady]);
  const rec = useRecordFlow(session, caseId, v.canRecord);
  useLeaveGuard(v.unsaved || rec.unsaved);
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
            <NotiBell />
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
                <h1 className="h1-sans" style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>
                  {v.title}
                </h1>
                <span className="sub">{v.sub}</span>
                <span className={`chip ${v.riskCls}`}>{v.riskChip}</span>
              </div>
              <div className="note">{v.meta}</div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-s"
                onClick={rec.start}
                disabled={!rec.canOpen}
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
                {(v.keywords || []).map((k, kIndex) =>
                  k.href ? (
                    <A key={kIndex} className="chip c-normal" to={k.href} title={`근거 · ${k.where}`}>
                      {k.text}
                      <span style={{ marginLeft: '6px', fontSize: '11px', opacity: 0.75 }}>{k.where}</span>
                    </A>
                  ) : (
                    <span key={kIndex} className="chip c-normal">
                      {k.text}
                    </span>
                  ),
                )}
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

          <div className="brief-wrap" id="brief" ref={briefRef} aria-label="상담 전 브리핑" role="region">
            <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 20px' }}>
              <div style={{ flex: '1 1 380px' }}>
                <div className="sub">{brief.lead}</div>
                <h2 style={{ margin: '2px 0 0', fontSize: '22px', fontWeight: '700' }}>상담 전 브리핑</h2>
              </div>
              <button type="button" className="btn btn-s" aria-haspopup="dialog" onClick={() => setOutOpen(true)}>
                인쇄 · PDF
              </button>
              {outOpen ? (
                <div className="out-ov">
                  <div className="out-dlg" role="dialog" aria-modal="true" aria-labelledby="out-t">
                    <b id="out-t" style={{ fontSize: '18px' }}>
                      인쇄 · PDF
                    </b>
                    <span className="note" style={{ marginTop: '-6px' }}>
                      출력물에 들어갈 이름 표시 방식을 고르세요.
                    </span>
                    <div role="radiogroup" aria-label="이름 표시 방식" className="out-opts">
                      {[
                        [false, '실명 그대로', `예) ${v.title || '이서윤'}`],
                        [true, '이름 가리기', `예) ${maskExample(v.title || '이서윤')}`],
                      ].map(([m, label, ex]) => (
                        <button
                          key={label}
                          type="button"
                          role="radio"
                          aria-checked={outMask === m ? 'true' : 'false'}
                          className={`out-opt ${outMask === m ? 'on' : ''}`}
                          onClick={() => setOutMask(m)}
                        >
                          <span className="out-rd" aria-hidden="true"></span>
                          <span style={{ flex: '1', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <b style={{ fontSize: '14px' }}>{label}</b>
                            <span className="note">{ex}</span>
                          </span>
                        </button>
                      ))}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                      <button type="button" className="btn btn-s" onClick={() => setOutOpen(false)}>
                        취소
                      </button>
                      <button
                        type="button"
                        className="btn btn-p"
                        onClick={() => {
                          setOutOpen(false);
                          printBrief(briefRef.current, v.title, outMask);
                        }}
                      >
                        인쇄
                      </button>
                    </div>
                  </div>
                </div>
              ) : null}
            </section>
            <section aria-label="먼저 볼 것" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <h2 className="h2">먼저 볼 것</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '18px' }}>
                {(brief.firstCards || []).map((c) => (
                  <div key={c.key} className="card lead">
                    <span className="lead-tag">{c.title}</span>
                    {c.q ? <span className="lead-q">{c.q}</span> : null}
                    {c.main ? <b className="lead-main">{c.main}</b> : null}
                    <span className="src">{c.src || c.note}</span>
                  </div>
                ))}
              </div>
            </section>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '18px' }}>
              <section
                className="card"
                style={{ padding: '26px 28px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h2 className="h2">확인할 사항</h2>
                </div>
                {brief.checksNote ? <span className="note">{brief.checksNote}</span> : null}
                {(brief.checks || []).map((c) => (
                  <div key={c.key} className="rq">
                    <span>
                      {c.text}
                      {c.href ? (
                        <A className="src" to={c.href}>
                          근거 · {c.why}
                        </A>
                      ) : (
                        <span className="src">근거 · {c.why}</span>
                      )}
                    </span>
                  </div>
                ))}
                {brief.checksError ? (
                  <span className="note" role="alert" style={{ color: '#A33B2E' }}>
                    {brief.checksError}
                  </span>
                ) : null}
              </section>
              <section
                className="card"
                style={{ padding: '26px 28px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h2 className="h2">추가 질문</h2>
                  <span className="chip c-ai">AI 초안</span>
                  {brief.questionHref ? (
                    <A to={brief.questionHref} style={{ marginLeft: 'auto', fontSize: '13px' }}>
                      질문 수정
                    </A>
                  ) : null}
                </div>
                {brief.questions.map((q) => (
                  <div key={q.key} className="rq">
                    <span className="chip c-normal">{q.chip}</span>
                    <span>"{q.text}"</span>
                  </div>
                ))}
                {brief.questionNote ? <span className="note">{brief.questionNote}</span> : null}
              </section>
            </div>
          </div>

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
          {rec.show ? (
            <RecordDialog
              caseId={caseId}
              caseName={v.recordCase}
              caseSub={v.sub}
              targets={v.recordTargets}
              recorder={rec.recorder}
              upload={rec.upload}
              onClose={rec.close}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}
