// 새 사례 등록 (팝업 · 서식 4 초기면접지)
// 원본: 다솔 님 디자인 counselor-web-design/CaseRegister.dc.html (front_new 브랜치)
//
// 서버 연결: '등록' 은 useCaseRegister(POST /cases)로 서버가 받는 칸만 저장하고 새 사례 상세(?case=새 ID)로 간다.
// 화면에 쓸 값은 src/data/screens/caseRegister.ts(caseRegisterValues)가 만든다. 담당 상담원은 관리자만 고른다.
// ② 초기면접 내용의 가정상황 · 아동 특성은 저장한다(상담 일지에 초기면접 항목으로 보인다).
// 실명 · 생년월일 · 사례관리대상자 · 면접대상자 · ② 가족관계 · 건강정도는 같은 요청(personal_info)으로 암호화해 저장한다
// (2026-10-30 팀 결정, 표는 components/PersonalTables.jsx). 신고 · 연계일 · 조치 · ② 탭의 나머지 칸(관계 · 가족유형 · 문제력 · 태도 · 소견)은
// 서버에 칸이 없어 준비 중(입력 막음).
// 10/21 디자인(counselor-design/screens/CaseRegister.dc.html): 학대유형 칸 삭제, 필수 칸을 채워야 ② 탭으로 넘어감(빈 칸 표시 ·
// 남은 항목 안내), 닫기 · 취소는 이 팝업을 연 화면(?back=)으로. 날짜 달력 · '기타' 직접 입력은 그 칸이 준비 중이라 옮기지 않았다.
// 입력칸은 계정이 확인된 동안에만 보이고, 계정이 바뀌면 입력 · 요청 상태를 처음부터 만든다(아래 key).
import { Fragment } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import ThemeToggle from '../components/ThemeToggle';
import { FamilyTable, HealthTable } from '../components/PersonalTables';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseRegister } from '../data/useCaseRegister';
import { caseRegisterValues, initialRegisterState } from '../data/screens/caseRegister';
import { needsLogin, screenNotice } from '../data/screens/common';
import { readBackHref } from '../data/screens/links';
import { useScreenGo } from '../data/screens/useScreenGo';
import { useTheme } from '../theme';
import './CaseRegister.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialRegisterState();
  }
  renderVals() {
    return caseRegisterValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function CaseRegister(props) {
  const session = useAuthSession();
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  // 로그인 확인 중 · 확인 실패면 입력칸 없이 안내만 보인다. 다른 탭에서 다른 계정으로 로그인하면 이 단계를 거치므로
  // 앞 계정이 쓰던 초안은 사라진다. key 로 계정마다 새로 만들어, 초안 · 늦은 응답이 다른 계정에 남지 않게 한다.
  if (session.status !== 'signedIn' || !session.me) return <CaseRegisterWaiting session={session} />;
  return <CaseRegisterForm key={session.me.id} {...props} session={session} />;
}

function CaseRegisterWaiting({ session }) {
  const theme = useTheme();
  return (
    <div className="pg-CaseRegister">
      <div
        className={theme.cls}
        style={{
          minHeight: '100vh',
          background: 'rgba(47,58,68,0.40)',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          color: '#2B2A26',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'center',
          padding: '48px 16px',
        }}
      >
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="reg-title"
          style={{ width: '100%', maxWidth: '860px', background: '#FFFFFF', borderRadius: '24px', padding: '24px 30px' }}
        >
          <h1 id="reg-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
            새 사례 등록
          </h1>
          <Notice value={screenNotice({ session })} style={{ marginTop: '12px' }} />
        </section>
      </div>
    </div>
  );
}

function CaseRegisterForm(props) {
  const { session } = props;
  const register = useCaseRegister(session);
  const go = useScreenGo(useNavigate());
  const theme = useTheme();
  const back = readBackHref(useSearchParams()[0]);
  const v = useDC(Logic, { ...props, session, register, go, back });
  return (
    <div className="pg-CaseRegister">
      <div
        className={theme.cls}
        style={{
          minHeight: '1700px',
          background: 'rgba(47,58,68,0.40)',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          color: '#2B2A26',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'center',
          padding: '48px 16px',
          position: 'relative',
        }}
      >
        <div className="thm-abs">
          <ThemeToggle />
        </div>
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="reg-title"
          style={{
            width: '100%',
            maxWidth: '860px',
            background: '#FFFFFF',
            borderRadius: '24px',
            boxShadow: '0 20px 60px rgba(43, 42, 38,0.22)',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: '24px 30px 0', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <div>
              <h1 id="reg-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
                새 사례 등록
              </h1>
              <div className="note">초기면접지(아동용) · 서식 4</div>
            </div>
            <A
              to={v.closeHref}
              aria-label="닫기"
              style={{
                marginLeft: 'auto',
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: '#F7F6F2',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                textDecoration: 'none',
                color: '#2B2A26',
                fontSize: '18px',
              }}
            >
              ×
            </A>
          </div>
          <div role="tablist" style={{ display: 'flex', margin: '16px 30px 0', borderBottom: '1px solid #EAE7DF' }}>
            {(v.tabs || []).map((t, tIndex) => (
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
            onSubmit={v.submit}
            style={{ padding: '22px 30px', display: 'flex', flexDirection: 'column', gap: '18px' }}
          >
            <Notice value={v.notice} />
            <p className="note" style={{ margin: 0 }}>
              {v.savedNote}
            </p>
            {v.isA ? (
              <>
                <label className="fl">
                  <span className="lb">
                    사례 제목 <span className="req">*</span>
                  </span>
                  <input
                    className="inp"
                    type="text"
                    required
                    maxLength={v.title.max}
                    placeholder="예: 2026 상반기 신고 사례 (실명 · 주소는 넣지 마세요)"
                    value={v.title.value}
                    onChange={v.title.onChange}
                    aria-invalid={v.title.invalid}
                    style={{ borderColor: v.title.border }}
                  />
                </label>
                <div className="g3">
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
                    <span className="lb">개별사건번호</span>
                    <input
                      className="inp"
                      type="text"
                      maxLength={v.caseNumber.max}
                      placeholder="비우면 자동 (C-2026-0001 형식)"
                      value={v.caseNumber.value}
                      onChange={v.caseNumber.onChange}
                    />
                  </label>
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
                      <option value="여">여</option>
                      <option value="남">남</option>
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
                    />
                  </label>
                  <label className="fl">
                    <span className="lb">사례관리대상자 관계</span>
                    <select className="inp" value={v.targetRelation.value} onChange={v.targetRelation.onChange}>
                      <option value="">선택</option>
                      {v.targetRelationOptions.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="fl">
                    <span className="lb">사례관리대상자 생년월일</span>
                    <input
                      className="inp"
                      type="date"
                      min={v.targetBirthDate.min}
                      max={v.targetBirthDate.max}
                      value={v.targetBirthDate.value}
                      onChange={v.targetBirthDate.onChange}
                    />
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
                </div>

                <div className="g3">
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
                    />
                  </label>
                  <label className="fl">
                    <span className="lb">담당 상담원</span>
                    {v.isAdmin ? (
                      <select className="inp" value={v.counselor.value} onChange={v.counselor.onChange}>
                        <option value="">본인</option>
                        {(v.counselorOptions || []).map((o) => (
                          <option key={o.id} value={o.id}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input className="inp" type="text" readOnly value={v.meName} />
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
                <label className="fl">
                  <span className="lb">
                    사례연계 경위 {' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span>
                  </span>
                  <textarea className="ta2" disabled></textarea>
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
              </>
            ) : null}

            {v.isB ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
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
                <fieldset
                  disabled
                  style={{
                    border: '0',
                    margin: '0',
                    padding: '0',
                    minWidth: '0',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '18px',
                  }}
                >
                <label className="fl">
                  <span className="lb">보호자와 아동과의 관계{' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span></span>
                  <textarea className="ta2"></textarea>
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

                <fieldset
                  disabled
                  style={{
                    border: '0',
                    margin: '0',
                    padding: '0',
                    minWidth: '0',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '18px',
                  }}
                >
                <div className="sec">문제력{' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span></div>
                <div className="g3">
                  <label className="fl">
                    <span className="lb">현 상황</span>
                    <textarea className="ta2"></textarea>
                  </label>
                  <label className="fl">
                    <span className="lb">이유 인식</span>
                    <textarea className="ta2"></textarea>
                  </label>
                </div>
                </fieldset>

                <HealthTable health={v.health} />

                <fieldset
                  disabled
                  style={{
                    border: '0',
                    margin: '0',
                    padding: '0',
                    minWidth: '0',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '18px',
                  }}
                >

                <div className="sec">대상자 태도 및 관찰내용{' '}<span className="note" style={{ fontWeight: '400' }}>{v.notReady}</span></div>
                <div className="g3">
                  <label className="fl">
                    <span className="lb">대상자 태도</span>
                    <textarea className="ta2"></textarea>
                  </label>
                  <label className="fl">
                    <span className="lb">물리적 환경</span>
                    <textarea className="ta2"></textarea>
                  </label>
                </div>
                <label className="fl">
                  <span className="lb">상담원 소견 및 향후 계획</span>
                  <textarea className="ta2" style={{ minHeight: '96px' }}></textarea>
                </label>
                </fieldset>
              </div>
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
              <A className="btn btn-s" to={v.closeHref}>
                취소
              </A>
              <button type="button" className="btn btn-s" onClick={v.goB}>
                {v.midLabel}
              </button>
              <button type="submit" className="btn btn-p" disabled={v.submitting}>
                {v.submitLabel}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
