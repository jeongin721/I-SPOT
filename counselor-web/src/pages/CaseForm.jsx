// 탭 5 › 기관 서식 작성 (사정기록지 안전영역 · 사례관리 점검표 · 위험수준 척도 · 가족관계 척도)
// 원본: 다솔 님 디자인 CaseForm.dc.html (11/02 판 — 서식 고르는 탭 줄 대신 문서함 · 내담자 정보에서 서식을 골라 연다,
// 척도 선택지 '매우 아니다 ~ 매우 그렇다' · 상단 고정 합계, '확정').
//
// 서버 연결: 화면 주소 ?case=<사례 ID>&form=A|B|C|D. 사례 정보는 useCaseDetail, 서식 기록은 useCaseForms
// (GET · POST · PATCH /cases/{id}/forms, API_CONTRACT 22절)가 부르고, 화면에 쓸 값은 src/data/screens/caseForm.ts 가 만든다.
// 서식은 사례 단위로 차수마다 남는다. '임시 저장' 은 그 차수를 저장하고, '확정' 은 저장 뒤 확정한다(확정 차수는 고칠 수 없고,
// 고쳐 저장하면 다음 차수). 디자인의 AI 제안 · AI 초안은 서버에 없고 상담사 판단 칸이라 보이지 않는다(점수 합계만 계산).
// 저장하지 않은 수정이 있으면 화면을 떠날 때 묻는다(useLeaveGuard, 브라우저 뒤로 가기 포함).
import { Fragment } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import CopyButton from '../components/CopyButton';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseForms } from '../data/useCaseForms';
import { useCaseSignals } from '../data/useCaseSignals';
import { usePersonalInfo } from '../data/usePersonalInfo';
import { FORM_PARAM, INITIAL_CASE_FORM_STATE, caseFormValues } from '../data/screens/caseForm';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useLeaveGuard } from '../data/screens/useLeaveGuard';
import { useTheme } from '../theme';
import './CaseForm.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_CASE_FORM_STATE;
  }
  renderVals() {
    return caseFormValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function CaseForm(props) {
  const session = useAuthSession();
  const [params] = useSearchParams();
  const { caseId } = readScreenIds(params);
  const enabled = signedIn(session);
  const detail = useCaseDetail(caseId, { enabled });
  const signals = useCaseSignals(detail, { enabled });
  const personal = usePersonalInfo(caseId, { enabled });
  const forms = useCaseForms(caseId, { enabled });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, detail, signals, personal, forms, caseId, formParam: params.get(FORM_PARAM) });
  useLeaveGuard(v.unsaved, { guardBack: true });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-CaseForm">
      <div
        className={theme.cls}
        style={{
          minHeight: '1880px',
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
          <div>
            <A className="btn btn-sm btn-s" to="/CaseList">
              ← 목록
            </A>
          </div>
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › {v.crumb}
          </nav>
          <Notice value={v.notice} />
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <A className="btn btn-sm btn-s" to={v.backHref} aria-label="문서함으로 돌아가기" title="문서함으로 돌아가기">
              ←
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
                <span className="sub">{v.sub}</span>
                <span className={`chip ${v.riskCls}`}>{v.riskChip}</span>
              </div>
              <div className="note">{v.meta}</div>
            </div>
            <A className="btn btn-s" to={v.uploadHref}>
              ↑ 녹취 올리기
            </A>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A to={v.tabs.detail}>내담자 정보</A>
            <A to={v.tabs.history}>상담 이력</A>
            <A className="on" aria-current="page" to={v.tabs.docs}>
              문서함
            </A>
          </nav>
          <nav aria-label="위치" className="note" style={{ marginTop: '-8px' }}>
            <A to={v.backHref}>문서함</A> › 기관 서식 작성
          </nav>

          {v.tA ? (
            <>
              <section
                className="card"
                aria-label="사정기록지 안전영역"
                style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                  <h2 className="h2">사정기록지 · 안전영역</h2>
                  <span className="note">서식 6</span>
                </div>
                {(v.safety || []).map((g, gIndex) => (
                  <Fragment key={gIndex}>
                    <div className="grp">{g.name}</div>
                    {(g.items || []).map((it, itIndex) => (
                      <Fragment key={itIndex}>
                        <div className="item">
                          <span>{it.q}</span>
                          <span className="opt3" role="group" aria-label={it.q}>
                            {(it.opts || []).map((o, oIndex) => (
                              <Fragment key={oIndex}>
                                <button
                                  type="button"
                                  onClick={o.pick}
                                  style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                                >
                                  {o.label}
                                </button>
                              </Fragment>
                            ))}
                          </span>
                          {it.hasEv ? (
                            <>
                              <span className="ev">
                                <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                                  AI 제안 · {it.ai}
                                </span>
                                {it.ev}
                              </span>
                            </>
                          ) : null}
                        </div>
                      </Fragment>
                    ))}
                  </Fragment>
                ))}
                <div className="grp">환경</div>
                <div className="item">
                  <span>조부모, 친구, 이웃 등 신뢰할만한 주위 사람 (Key Person)</span>
                  <span className="opt3">
                    {(v.keyOpts || []).map((o, oIndex) => (
                      <Fragment key={oIndex}>
                        <button
                          type="button"
                          onClick={o.pick}
                          style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                        >
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  {v.keyEv ? (
                    <span className="ev">
                      <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                        AI 제안 · {v.keyEv}
                      </span>
                    </span>
                  ) : null}
                </div>
                <div className="grp">
                  안전점수{' '}
                  <span className="note" style={{ fontWeight: '400' }}>
                    1–10점
                  </span>
                </div>
                {(v.scoreRows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <div className="item" style={{ gridTemplateColumns: '150px 110px minmax(0, 1fr)' }}>
                      <span>{r.who}</span>
                      <input
                        className="inp"
                        type="number"
                        min="1"
                        max="10"
                        placeholder="( )점"
                        aria-label={`${r.who} 안전점수`}
                        style={{ width: '100px' }}
                        value={r.score}
                        onChange={(e) => r.setScore(e.target.value)}
                      />
                      <input
                        className="inp"
                        type="text"
                        placeholder="이유"
                        aria-label={`${r.who} 이유`}
                        style={{ width: '100%' }}
                        maxLength={300}
                        value={r.reason}
                        onChange={(e) => r.setReason(e.target.value)}
                      />
                    </div>
                  </Fragment>
                ))}
                <div className="grp">아동학대 위험수준별 개입 사정 척도</div>
                <div className="item" style={{ gridTemplateColumns: '1fr auto' }}>
                  <span>
                    위험요인 <b className="brn">{v.riskSum}점</b> / 보호요인 <b className="brn">{v.protSum}점</b>{' '}
                    <span className="note">· {v.filled}/43 입력</span>
                  </span>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.goC}>
                    척도 열기
                  </button>
                </div>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <b style={{ fontSize: '14px' }}>담당자 소견</b>
                  <textarea
                    className="ta2"
                    placeholder="직접 작성"
                    maxLength={5000}
                    value={v.opinionA}
                    onChange={(e) => v.setOpinionA(e.target.value)}
                  ></textarea>
                  <CopyButton names={v.maskNames} />
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
                  <b style={{ fontSize: '14px' }}>사정결과</b>
                  <span className="opt3">
                    {(v.resultOpts || []).map((o, oIndex) => (
                      <Fragment key={oIndex}>
                        <button
                          type="button"
                          onClick={o.pick}
                          style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                        >
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  <span className="note">상담원 판정</span>
                </div>
              </section>
            </>
          ) : null}

          {v.tB ? (
            <>
              <section
                className="card"
                aria-label="사례관리 점검표"
                style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                  <h2 className="h2">사례관리 점검표</h2>
                  <span className="note">서식 27</span>
                </div>
                <div className="fhead">
                  <div>
                    <span className="k">성명</span>
                    <span className="v">{v.fhead.name}</span>
                  </div>
                  <div>
                    <span className="k">담당 상담원</span>
                    <span className="v">{v.fhead.counselor}</span>
                  </div>
                  <div>
                    <span className="k">생년월일</span>
                    <span className="v">{v.fhead.birth}</span>
                  </div>
                  <div>
                    <span className="k">점검일/회차</span>
                    <span className="v">{v.fhead.round}</span>
                  </div>
                  <div>
                    <span className="k">점검장소</span>
                    <span className="v">
                      <input
                        className="inp"
                        type="text"
                        maxLength={100}
                        value={v.place}
                        onChange={(e) => v.setPlace(e.target.value)}
                        aria-label="점검장소"
                        style={{ height: '34px', width: '100%' }}
                      />
                    </span>
                  </div>
                  <div>
                    <span className="k">이전 점검일</span>
                    <span className="v">{v.fhead.prev}</span>
                  </div>
                </div>
                {(v.checks || []).map((c, cIndex) => (
                  <Fragment key={cIndex}>
                    <div className="item">
                      <span>{c.q}</span>
                      <span className="opt3" role="group" aria-label={c.q}>
                        {(c.opts || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button
                              type="button"
                              onClick={o.pick}
                              style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                            >
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <b style={{ fontSize: '14px' }}>담당 상담원 소견</b>
                    {v.aiDraft ? (
                      <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                        AI 초안
                      </span>
                    ) : null}
                  </span>
                  <textarea
                    className="ta2"
                    maxLength={5000}
                    value={v.opinionB}
                    onChange={(e) => v.setOpinionB(e.target.value)}
                  ></textarea>
                  <CopyButton names={v.maskNames} />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <b style={{ fontSize: '14px' }}>추후 계획</b>
                    {v.aiDraft ? (
                      <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                        AI 초안
                      </span>
                    ) : null}
                  </span>
                  <textarea
                    className="ta2"
                    maxLength={5000}
                    value={v.planB}
                    onChange={(e) => v.setPlanB(e.target.value)}
                  ></textarea>
                  <CopyButton names={v.maskNames} />
                </label>
              </section>
            </>
          ) : null}

          {v.tC ? (
            <>
              <section
                className="card"
                aria-label="위험수준별 개입 사정 척도"
                style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                  <h2 className="h2">아동학대 위험수준별 개입 사정 척도</h2>
                  <span className="note">참고자료 3 · 43문항 · 0~3점</span>
                </div>
                <div className="sumbar">
                  <div style={{ display: 'flex', alignItems: 'stretch', gap: '12px' }}>
                    <div className="sum" style={{ flex: '1', minWidth: '0' }}>
                      <div>
                        <div className="note">위험요인 (1~21)</div>
                        <b className="brn" style={{ fontSize: '24px' }}>
                          {v.riskSum}점
                        </b>
                        <span className="note"> / 63</span>
                      </div>
                      <div>
                        <div className="note">보호요인 (22~43)</div>
                        <b className="brn" style={{ fontSize: '24px' }}>
                          {v.protSum}점
                        </b>
                        <span className="note"> / 66</span>
                      </div>
                      <div>
                        <div className="note">입력</div>
                        <b style={{ fontSize: '24px' }}>{v.filled}</b>
                        <span className="note"> / 43 · 군 판정: 상담원</span>
                      </div>
                    </div>
                    <a className="btn btn-s" href="#scale-risk" onClick={v.scrollRisk} style={{ alignSelf: 'center' }}>
                      수정
                    </a>
                  </div>
                  <div className="sc sc-head" aria-hidden="true">
                    <span></span>
                    <span></span>
                    <span className="opt3 opt3-head">
                      <span>0점</span>
                      <span>1점</span>
                      <span>2점</span>
                      <span>3점</span>
                    </span>
                  </div>
                </div>
                {(v.scale || []).map((s, sIndex) => (
                  <Fragment key={sIndex}>
                    {s.head ? (
                      <>
                        <div className="grp" id={s.hid} style={{ marginTop: '6px' }}>
                          {s.headLabel}
                        </div>
                      </>
                    ) : null}
                    <div className="sc">
                      <span className="note">{s.n}</span>
                      <span>
                        {s.q}
                        <span className="src" style={{ display: 'block' }}>
                          {s.ev}
                        </span>
                      </span>
                      <span className="opt3" role="group" aria-label={s.q}>
                        {(s.opts || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button
                              type="button"
                              onClick={o.pick}
                              style={{
                                background: o.bg,
                                color: o.fg,
                                fontWeight: o.fw,
                                boxShadow: o.bd,
                                width: '84px',
                                padding: '0 6px',
                              }}
                            >
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
              </section>
            </>
          ) : null}

          {v.tD ? (
            <>
              <section
                className="card"
                aria-label="축약형 가족관계 척도"
                style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                  <h2 className="h2">축약형 가족관계 척도</h2>
                  <span className="note">참고자료 1 · 15문항</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
                  <span className="note">응답자</span>
                  <span className="opt3">
                    {(v.resp || []).map((o, oIndex) => (
                      <Fragment key={oIndex}>
                        <button
                          type="button"
                          onClick={o.pick}
                          style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                        >
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  <span style={{ marginLeft: 'auto' }}>
                    평균{' '}
                    <b className="brn" style={{ fontSize: '20px' }}>
                      {v.famAvg}
                    </b>
                    <span className="note"> 점 · {v.famN}/15 응답</span>
                  </span>
                </div>
                <div
                  className="note"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '38px minmax(0,1fr) auto',
                    gap: '10px',
                    padding: '0 4px',
                  }}
                >
                  <span></span>
                  <span></span>
                  <span>1 전혀 그렇지 않다 · 3 보통이다 · 5 항상 그렇다</span>
                </div>
                {(v.fam || []).map((s, sIndex) => (
                  <Fragment key={sIndex}>
                    <div className="sc">
                      <span className="note">{s.n}</span>
                      <span>{s.q}</span>
                      <span className="opt3">
                        {(s.opts || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button
                              type="button"
                              onClick={o.pick}
                              style={{
                                background: o.bg,
                                color: o.fg,
                                fontWeight: o.fw,
                                boxShadow: o.bd,
                                minWidth: '34px',
                              }}
                            >
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <p className="src" style={{ margin: '0' }}>
                  출처: 양옥경(2001) · 양옥경 · 김연수(2007) 축약, 사회복지공동모금회 척도집(2017)
                </p>
              </section>
            </>
          ) : null}

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            {v.statusNote ? (
              <span className="note" role={v.statusAlert ? 'alert' : 'status'}>
                {v.statusNote}
              </span>
            ) : null}
            <button
              type="button"
              className="btn btn-s"
              style={{ marginLeft: 'auto' }}
              onClick={v.saveDraft}
              disabled={!v.canSave}
            >
              임시 저장
            </button>
            <button type="button" className="btn btn-p" onClick={v.confirm} disabled={!v.canSave}>
              확정
            </button>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
