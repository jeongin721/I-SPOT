// 탭 4 › 초기면접지 (아동용) · 서식 4 (문서함에서 열기)
// 원본: 다솔 님 디자인 counselor-design/screens/CaseIntake.dc.html (10/22 판)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 사례 정보는 useCaseDetail 이 부르고, 화면에 쓸 값은
// src/data/screens/caseIntake.ts(caseIntakeValues)가 만든다. '저장' 은 바꾼 칸만 PATCH /cases/{id} 로 보낸다(useCaseDetail.saveCase).
// 새 사례 등록(CaseRegister)과 같은 서식을 사례 값으로 채워 사례 상세 안에서 연다. 고칠 수 있는 칸은 사례에 저장된 칸뿐이고
// (담당 상담원은 관리자만), 개별사건번호는 읽기만 한다.
// 실명 · 생년월일 · 사례관리대상자 · 면접대상자 · ② 가족관계 · 건강정도는 usePersonalInfo(GET · PUT …/personal-info, 암호화 저장)로
// 불러와 고친다. 값을 받기 전 · 못 받았으면 그 칸들은 막는다(통째로 바꾸는 PUT 이라 모르는 값을 지우지 않게).
// 나머지 칸은 서버에 칸이 없어 준비 중(입력 막음).
// 디자인의 '임시 저장' · '확정' 은 서식 작성 기록 · 확정 상태가 서버에 없어 '저장' 하나로 두었다.
// 10/29 디자인: ① 칸 묶음(rg-*) · 사례관리대상자 생년월일, ② 가족유형 21개 · 문제력 한 칸 · 건강정도 표(hs-*) · 칸 복사 단추.
// 복사 단추의 '이름 가려서' 는 이 사례에 등록된 이름 전부(실명 · 가족 · 별칭)를 가린다.
// 저장하지 않은 수정이 있으면 화면을 떠날 때 묻는다(useLeaveGuard). 다른 사례로 옮기거나 다시 로그인하면 고치던 것을 버린다.
import { Fragment } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import CopyButton from '../components/CopyButton';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { FamilyTable, HealthTable } from '../components/PersonalTables';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseSignals } from '../data/useCaseSignals';
import { useIntakeCounselors } from '../data/useCaseIntake';
import { usePersonalInfo } from '../data/usePersonalInfo';
import { INITIAL_CASE_INTAKE_STATE, caseIntakeValues } from '../data/screens/caseIntake';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useLeaveGuard } from '../data/screens/useLeaveGuard';
import { useTheme } from '../theme';
import './CaseIntake.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_CASE_INTAKE_STATE;
  }
  renderVals() {
    return caseIntakeValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

/** 준비 중 칸을 막아 두는 묶음(새 사례 등록과 같은 모양). */
const LOCKED_GROUP = {
  border: '0',
  margin: '0',
  padding: '0',
  minWidth: '0',
  display: 'flex',
  flexDirection: 'column',
  gap: '18px',
};

export default function CaseIntake(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const detail = useCaseDetail(caseId, { enabled: signedIn(session) });
  const signals = useCaseSignals(detail, { enabled: signedIn(session) });
  const counselors = useIntakeCounselors(session);
  const personal = usePersonalInfo(caseId, { enabled: signedIn(session) });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, detail, signals, counselors, personal, caseId });
  useLeaveGuard(v.unsaved);
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-CaseIntake">
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
            <NotiBell />
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
            <A
              className="btn btn-sm btn-s"
              to={v.backHref}
              aria-label="문서함으로 돌아가기"
              title="문서함으로 돌아가기"
            >
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
            <A to={v.backHref}>문서함</A> › 초기면접지 (아동용)
          </nav>

          {v.ready ? (
            <section className="card" aria-label="초기면접지 (아동용)" style={{ padding: '0 0 6px' }}>
              <div style={{ padding: '22px 30px 0', display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                <h2 className="h2">초기면접지 (아동용)</h2>
                <span className="note">{v.headNote}</span>
              </div>
              <div role="tablist" style={{ display: 'flex', margin: '16px 30px 0', borderBottom: '1px solid #EAE7DF' }}>
                {(v.formTabs || []).map((t, tIndex) => (
                  <Fragment key={tIndex}>
                    <button
                      type="button"
                      role="tab"
                      className="tabb"
                      aria-selected={t.sel}
                      onClick={t.go}
                      style={{ borderBottomColor: t.bd, color: t.fg, fontWeight: t.fw }}
                    >
                      {t.label}
                    </button>
                  </Fragment>
                ))}
              </div>

              <form
                onSubmit={v.save}
                style={{ padding: '22px 30px', display: 'flex', flexDirection: 'column', gap: '18px' }}
              >
                <p className="note" style={{ margin: 0 }}>
                  {v.savedNote}
                </p>
                <Notice value={v.personalNote} />
                {v.isA ? (
                  <fieldset disabled={v.locked} style={LOCKED_GROUP}>
                    <label className="fl">
                      <span className="lb">
                        사례 제목 <span className="req">*</span>
                      </span>
                      <input
                        className="inp"
                        type="text"
                        required
                        maxLength={v.caseTitle.max}
                        placeholder="예: 2026 상반기 신고 사례 (실명 · 주소는 넣지 마세요)"
                        value={v.caseTitle.value}
                        onChange={v.caseTitle.onChange}
                        aria-invalid={v.caseTitle.invalid}
                        style={{ borderColor: v.caseTitle.border }}
                      />
                    </label>
                    <div className="rg-grp">
                      <div className="rg4">
                      <label className="fl">
                        <span className="lb">
                          신고접수일 {' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span>
                        </span>
                        <input className="inp" type="date" disabled />
                      </label>
                      <label className="fl">
                        <span className="lb">
                          사례연계일 {' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span>
                        </span>
                        <input className="inp" type="date" disabled />
                      </label>
                      <label className="fl">
                        <span className="lb">
                          최초면접일 {' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span>
                        </span>
                        <input className="inp" type="date" disabled />
                      </label>
                      <label className="fl">
                        <span className="lb">
                          개별사건번호 {' '}<span className="note" style={{ fontWeight: '400' }}>(바꿀 수 없음)</span>
                        </span>
                        <input className="inp" type="text" readOnly value={v.caseNumber} />
                      </label>
                      </div>
                    </div>
                    <div className="rg-grp">
                      <div className="rg3">
                      <label className="fl">
                        <span className="lb">대상아동 이름</span>
                        <input
                          className="inp"
                          type="text"
                          autoComplete="off"
                          maxLength={v.childName.max}
                          placeholder="이름"
                          value={v.childName.value}
                          onChange={v.childName.onChange}
                          disabled={v.personalLocked}
                        />
                      </label>
                      <label className="fl">
                        <span className="lb">
                          아동 별칭 <span className="req">*</span>
                        </span>
                        <input
                          className="inp"
                          type="text"
                          required
                          maxLength={v.alias.max}
                          placeholder="실명 대신 부를 이름"
                          value={v.alias.value}
                          onChange={v.alias.onChange}
                          aria-invalid={v.alias.invalid}
                          style={{ borderColor: v.alias.border }}
                        />
                      </label>
                      <label className="fl">
                        <span className="lb">성별</span>
                        <select className="inp" value={v.gender.value} onChange={v.gender.onChange}>
                          <option value="">선택</option>
                          {(v.genderOptions || []).map((g) => (
                            <option key={g} value={g}>
                              {g}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="fl">
                        <span className="lb">생년월일</span>
                        <input
                          className="inp"
                          type="date"
                          min={v.childBirthDate.min}
                          max={v.childBirthDate.max}
                          value={v.childBirthDate.value}
                          onChange={v.childBirthDate.onChange}
                          disabled={v.personalLocked}
                        />
                      </label>
                      <label className="fl">
                        <span className="lb">출생연도{v.birthYear.readOnly ? ' (생년월일의 해)' : ''}</span>
                        <input
                          className="inp"
                          type="number"
                          inputMode="numeric"
                          min="1900"
                          max={v.birthYear.max}
                          placeholder="예: 2015"
                          value={v.birthYear.value}
                          onChange={v.birthYear.onChange}
                          readOnly={v.birthYear.readOnly}
                        />
                      </label>
                      </div>
                    </div>
                    <div className="rg-grp">
                      <div className="rg3">
                      <label className="fl">
                        <span className="lb">사례관리대상자</span>
                        <input
                          className="inp"
                          type="text"
                          autoComplete="off"
                          maxLength={v.targetName.max}
                          placeholder="이름"
                          value={v.targetName.value}
                          onChange={v.targetName.onChange}
                          disabled={v.personalLocked}
                        />
                      </label>
                      <label className="fl">
                        <span className="lb">사례관리대상자 관계</span>
                        <select
                          className="inp"
                          value={v.targetRelation.value}
                          onChange={v.targetRelation.onChange}
                          disabled={v.personalLocked}
                        >
                          <option value="">선택</option>
                          {v.targetRelationOptions.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="fl">
                        <span className="lb">보호자 유형</span>
                        <select className="inp" value={v.guardianType.value} onChange={v.guardianType.onChange}>
                          <option value="">선택</option>
                          {(v.guardianOptions || []).map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      {v.showGuardianNote ? (
                        <label className="fl">
                          <span className="lb">보호자 관계 메모 (실명 제외)</span>
                          <input
                            className="inp"
                            type="text"
                            maxLength={v.guardianNote.max}
                            placeholder="예: 이모"
                            value={v.guardianNote.value}
                            onChange={v.guardianNote.onChange}
                          />
                        </label>
                      ) : null}
                      <label className="fl">
                        <span className="lb">사례관리대상자 생년월일</span>
                        <input
                          className="inp"
                          type="date"
                          min={v.targetBirthDate.min}
                          max={v.targetBirthDate.max}
                          value={v.targetBirthDate.value}
                          onChange={v.targetBirthDate.onChange}
                          disabled={v.personalLocked}
                        />
                      </label>
                      </div>
                    </div>
                    <div className="rg-grp">
                      <div className="rg2">
                      <label className="fl">
                        <span className="lb">
                          조치결과 · 피해아동 {' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span>
                        </span>
                        <select className="inp" disabled>
                          <option>원가정보호</option>
                          <option>친인척보호</option>
                          <option>연고자에 의한 보호</option>
                          <option>가정위탁</option>
                          <option>시설입소</option>
                          <option>병원입원</option>
                          <option>기타</option>
                        </select>
                      </label>
                      <label className="fl">
                        <span className="lb">
                          조치결과 · 사례관리대상자 {' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span>
                        </span>
                        <select className="inp" disabled>
                          <option>지속관찰</option>
                          <option>아동과의 분리</option>
                          <option>고소 · 고발</option>
                          <option>기타</option>
                        </select>
                      </label>
                      </div>
                    </div>
                    <div className="rg-grp">
                      <div className="rg3">
                      <label className="fl">
                        <span className="lb">면접대상자</span>
                        <input
                          className="inp"
                          type="text"
                          autoComplete="off"
                          maxLength={v.intervieweeName.max}
                          placeholder="이름"
                          value={v.intervieweeName.value}
                          onChange={v.intervieweeName.onChange}
                          disabled={v.personalLocked}
                        />
                      </label>
                      <label className="fl">
                        <span className="lb">면접대상자 관계</span>
                        <input
                          className="inp"
                          type="text"
                          maxLength={v.intervieweeRelation.max}
                          placeholder="예: 피해아동"
                          value={v.intervieweeRelation.value}
                          onChange={v.intervieweeRelation.onChange}
                          disabled={v.personalLocked}
                        />
                      </label>
                      <label className="fl">
                        <span className="lb">담당 상담원</span>
                        {v.isAdmin ? (
                          <select className="inp" value={v.counselor.value} onChange={v.counselor.onChange}>
                            {(v.counselorOptions || []).map((o) => (
                              <option key={o.id} value={o.id}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input className="inp" type="text" readOnly value={v.counselorName} />
                        )}
                        {v.counselorNote ? (
                          <span className="note">
                            {v.counselorNote}
                            {v.counselorRetry ? (
                              <>
                                {' '}
                                <button type="button" className="btn btn-s btn-sm" onClick={v.counselorRetry}>
                                  다시 시도
                                </button>
                              </>
                            ) : null}
                          </span>
                        ) : null}
                      </label>
                      <label className="fl">
                        <span className="lb">
                          위험도 (우선) {' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span>
                        </span>
                        <select className="inp" disabled>
                          <option>선택</option>
                          <option>상</option>
                          <option>중</option>
                          <option>하</option>
                        </select>
                      </label>
                      </div>
                    </div>
                    <label className="fl">
                      <span className="lb">
                        사례연계 경위 {' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span>
                      </span>
                      <textarea className="ta2" rows="7" disabled style={{ minHeight: '180px' }}></textarea>
                    </label>
                    <label className="fl">
                      <span className="lb">사례 메모</span>
                      <textarea
                        className="ta2"
                        maxLength={v.notes.max}
                        placeholder="실명 · 연락처 · 주소 등 개인정보는 적지 마세요"
                        value={v.notes.value}
                        onChange={v.notes.onChange}
                      ></textarea>
                    </label>
                  </fieldset>
                ) : null}

                {v.isB ? (
                  <fieldset disabled={v.locked} style={LOCKED_GROUP}>
                    <p className="note" role="status" style={{ margin: 0 }}>
                      {v.tabNote}
                    </p>
                    <div className="sec">
                      가정상황{' '}
                      <span className="note" style={{ fontWeight: '400' }}>
                        (복수응답 가능)
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {(v.homes || []).map((o, oIndex) => (
                        <Fragment key={oIndex}>
                          <button
                            type="button"
                            className={o.on ? 'pk on' : 'pk'}
                            aria-pressed={o.on}
                            onClick={o.toggle}
                            disabled={o.disabled}
                            style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                          >
                            {o.mark} {o.label}
                          </button>
                        </Fragment>
                      ))}
                    </div>
                    <fieldset disabled style={LOCKED_GROUP}>
                      <label className="fl">
                        <span className="lb">보호자와 아동과의 관계{' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span></span>
                        <textarea className="ta2 ta1" rows="1" aria-label="보호자와 아동과의 관계"></textarea>
                        <CopyButton names={v.maskNames} />
                      </label>

                      <div className="sec">가족유형{' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span></div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {(v.fams || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button
                              type="button"
                              className="pk"
                              style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                            >
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </div>

                    </fieldset>

                    <div className="sec">가족관계</div>
                    <FamilyTable family={v.family} />

                    <div className="sec">
                      아동 특성{' '}
                      <span className="note" style={{ fontWeight: '400' }}>
                        (복수응답 가능)
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {(v.traits || []).map((o, oIndex) => (
                        <Fragment key={oIndex}>
                          <button
                            type="button"
                            className={o.on ? 'pk on' : 'pk'}
                            aria-pressed={o.on}
                            onClick={o.toggle}
                            disabled={o.disabled}
                            style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                          >
                            {o.mark} {o.label}
                          </button>
                        </Fragment>
                      ))}
                    </div>

                    <fieldset disabled style={LOCKED_GROUP}>
                      <div className="sec">문제력{' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span></div>
                      <label className="fl cp-in">
                        <textarea
                          className="ta2"
                          placeholder="피해아동/사례관리대상자/비가해보호자/가족구성원 등이 생각하는 현 상황, 현 상황이 초래된 이유 등에 대한 기재"
                          aria-label="문제력"
                        ></textarea>
                        <CopyButton names={v.maskNames} />
                      </label>
                    </fieldset>

                    <HealthTable health={v.health} />

                    <fieldset disabled style={LOCKED_GROUP}>

                      <div className="sec">대상자 태도 및 관찰내용{' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span></div>
                      <div className="g3">
                        <label className="fl">
                          <span className="lb">대상자 태도</span>
                          <textarea className="ta2"></textarea>
                          <CopyButton names={v.maskNames} />
                        </label>
                        <label className="fl">
                          <span className="lb">물리적 환경</span>
                          <textarea className="ta2"></textarea>
                          <CopyButton names={v.maskNames} />
                        </label>
                      </div>
                      <label className="fl">
                        <span className="lb">상담원 소견 및 향후 계획</span>
                        <textarea className="ta2" style={{ minHeight: '96px' }}></textarea>
                        <CopyButton names={v.maskNames} />
                      </label>
                    </fieldset>
                  </fieldset>
                ) : null}

                <Notice value={v.formError} />
                {v.missNote ? (
                  <p className="req" role="alert" style={{ margin: 0, fontSize: '13px', fontWeight: '500' }}>
                    {v.missNote}
                  </p>
                ) : null}
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    justifyContent: 'flex-end',
                    gap: '10px',
                    borderTop: '1px solid #EAE7DF',
                    paddingTop: '18px',
                  }}
                >
                  {v.statusNote ? (
                    <span className="note" role="status" style={{ marginRight: 'auto' }}>
                      {v.statusNote}
                    </span>
                  ) : null}
                  <button type="button" className="btn btn-s" onClick={v.goB}>
                    {v.midLabel}
                  </button>
                  {v.canReset ? (
                    <button type="button" className="btn btn-s" onClick={v.reset}>
                      되돌리기
                    </button>
                  ) : null}
                  <button type="submit" className="btn btn-p" disabled={!v.canSave}>
                    {v.saveLabel}
                  </button>
                </div>
              </form>
            </section>
          ) : null}
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
