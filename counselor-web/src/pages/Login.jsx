// 로그인
// 원본: 다솔 님 디자인 counselor-web-design/Login.dc.html (front_new 브랜치)
//
// 서버 연결: 로그인 · 로그인 상태 · 비밀번호 변경은 src/data 의 훅이 하고, 이 파일은 배치만 한다.
// 디자인을 바꿀 때는 아래 Login 함수의 훅과 Logic 을 그대로 두고 JSX 만 갈아 끼우면 된다.
//  - 로그인은 이메일(Backend 계약). 10/21 디자인(counselor-design/screens/Login.dc.html)대로 OTP 칸은 뺐다.
//  - 임시 비밀번호로 들어오면 같은 카드가 비밀번호 변경 단계로 바뀐다. 바꾸면 다시 로그인한다.
//  - 로그인 유형(상담사 · 관리자)은 들어갈 화면만 고른다. 관리자 화면은 서버 역할이 관리자일 때만 가고, 아니면 /Main.
//  - 회원가입은 디자인의 3단계 팝업(본인 인증 → 계정 정보 → 완료)이다. 생년월일 · 성별 · 휴대폰 칸은 받지 않기로 해서 뺐고,
//    마지막은 대기 신청이다(관리자 승인 뒤 로그인). 값은 src/data/screens/signup.ts, 요청은 useSignup.
//    서버 설정(SIGNUP_ENABLED)이 꺼져 있으면 회원가입 단추를 숨긴다.
import { Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { INITIAL_SIGNUP_UI, signupValues } from '../data/screens/signup';
import { useAuthSession } from '../data/useAuthSession';
import { useLogin } from '../data/useLogin';
import { useLogoutNotice } from '../data/useLogoutNotice';
import { useSignup } from '../data/useSignup';
import { PASSWORD_RULE_TEXT, usePasswordChange } from '../data/usePasswordChange';
import './Login.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    // pwFor: 변경 단계 칸(current · next · confirm)이 어느 계정 것인가(설정 화면의 pwFor 와 같은 방식).
    this.state = {
      email: '',
      password: '',
      current: '',
      next: '',
      confirm: '',
      pwFor: null,
      role: 'staff',
      ...INITIAL_SIGNUP_UI,
    };
  }

  // 회원가입 팝업이 열려 있는 동안 1초마다 다시 그린다(인증 남은 시간 · 다시 보내기 대기 초).
  componentDidMount() {
    this._tick = setInterval(() => {
      if (this.state.su === 1) this.setState({});
    }, 1000);
  }

  componentWillUnmount() {
    clearInterval(this._tick);
  }

  async signIn() {
    const s = this.state;
    const user = await this.props.login.login(s.email, s.password);
    if (!user) return;
    // 로그인했으니 앞서 남은 로그아웃 이유는 지운다(이 계정이 '다른 계정으로 로그인'을 눌렀을 때 앞 사람 문구가 다시 뜨지 않게).
    this.props.dismissNotice();
    if (user.must_change_password) {
      // 방금 친 임시 비밀번호를 현재 비밀번호 칸에 옮겨 두고, 로그인 상태를 다시 확인해 변경 단계로 넘어간다.
      // 새 비밀번호 · 확인 칸은 비운다(앞 계정에서 치다 만 값이 남아 있으면 이 계정에 그대로 들어가 버린다).
      this.setState({ current: s.password, password: '', next: '', confirm: '', pwFor: user.id });
      this.props.session.recheck();
    } else {
      this.props.navigate(s.role === 'admin' && user.role === 'ADMIN' ? '/AdminHome' : '/Main');
    }
  }

  async changePassword() {
    const s = this.state;
    const ok = await this.props.pwChange.change({
      currentPassword: s.current,
      newPassword: s.next,
      confirmPassword: s.confirm,
    });
    // 바꾸면 로그아웃되고 로그인 단계로 돌아간다("새 비밀번호로 다시 로그인" 문구가 뜬다).
    if (ok) this.setState({ password: '', current: '', next: '', confirm: '' });
  }

  renderVals() {
    const { session, login, pwChange, notice } = this.props;
    const changing = session.status === 'mustChangePassword';
    // 변경 단계의 칸 · 오류는 그 계정 것이다. 다른 탭에서 다른 계정(임시 비밀번호)으로 바뀌면 그리는 중에 비운다 —
    // 앞 계정의 임시 비밀번호가 새 계정의 변경 요청에 실려 나가지 않게.
    const meId = session.me ? session.me.id : null;
    if (changing && meId && this.state.pwFor !== meId) {
      this.state = { ...this.state, current: '', next: '', confirm: '', pwFor: meId };
      pwChange.clearErrors();
    }
    const s = this.state;
    const field = (key) => ({ value: s[key], onChange: (e) => this.setState({ [key]: e.target.value }) });
    const busy = changing ? pwChange.submitting : login.submitting;
    return {
      ...signupValues({
        getState: () => this.state,
        setState: (patch) => this.setState(patch),
        signup: this.props.signup,
        now: Date.now(),
      }),
      changing,
      email: field('email'),
      password: field('password'),
      current: field('current'),
      next: field('next'),
      confirm: field('confirm'),
      // 로그인 실패 문구가 있으면 그것을, 없으면 로그아웃된 이유(토큰 만료 · 비밀번호 변경 등)를 보여 준다.
      message: changing ? '' : login.error || notice,
      errors: changing ? pwChange.errors : [],
      meName: session.me ? session.me.name : '',
      ruleText: PASSWORD_RULE_TEXT,
      roles: [
        ['staff', '상담사 로그인'],
        ['admin', '관리자 로그인'],
      ].map(([value, label]) => ({
        label,
        cls: s.role === value ? 'on' : '',
        pressed: s.role === value ? 'true' : 'false',
        pick: () => this.setState({ role: value }),
      })),
      busy,
      submitLabel: changing ? (busy ? '바꾸는 중…' : '비밀번호 바꾸기') : busy ? '로그인 중…' : '로그인',
      submit: (e) => {
        e.preventDefault();
        if (changing) this.changePassword();
        else this.signIn();
      },
      // 다른 계정으로 바꿀 때는 이메일 · 비밀번호 칸을 모두 비우고 오류 문구도 지운 뒤 로그아웃한다.
      switchAccount: () => {
        this.setState({ email: '', password: '', current: '', next: '', confirm: '' });
        pwChange.clearErrors();
        session.logout();
      },
    };
  }
}

// 비밀번호 보기 · 숨기기(디자인 Login.dc.html 의 눈 단추).
function PwEye({ eye }) {
  return (
    <button
      type="button"
      className="sf-eye"
      aria-label={eye.label}
      title={eye.label}
      aria-pressed={eye.pressed}
      onClick={eye.toggle}
    >
      {eye.show ? (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 3l18 18"></path>
          <path d="M10.6 5.1A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.2M6.1 6.1C3.5 7.8 2 12 2 12s3.5 7 10 7c1.6 0 3-.4 4.3-1"></path>
          <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"></path>
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
      )}
    </button>
  );
}

export default function Login(props) {
  const navigate = useNavigate();
  const session = useAuthSession();
  const login = useLogin();
  const pwChange = usePasswordChange();
  const signup = useSignup();
  const { notice, dismiss: dismissNotice } = useLogoutNotice();
  const theme = useTheme();
  const v = useDC(Logic, { ...props, navigate, session, login, pwChange, signup, notice, dismissNotice });
  return (
    <div className="pg-Login">
      <div
        className={theme.cls}
        style={{
          minHeight: '720px',
          background: '#F2F2F0',
          color: '#2B2A26',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '48px 24px',
          position: 'relative',
        }}
      >
        <div className="thm-abs">
          <ThemeToggle />
        </div>
        <form
          onSubmit={v.submit}
          noValidate
          style={{
            width: '100%',
            maxWidth: '400px',
            background: '#FFFFFF',
            border: '1px solid #E2DED3',
            borderRadius: '24px',
            boxShadow: '8px 8px 22px var(--sd), -8px -8px 22px var(--sl)',
            padding: '36px 34px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <span className="mk">IS</span>
            <b style={{ fontSize: '20px' }}>I-SPOT</b>
          </div>
          {/* 단계마다 key 를 달리해 입력 칸을 새로 만든다(로그인 칸의 값 · 막힌 OTP 칸이 변경 칸으로 이어지지 않게). */}
          {v.changing ? (
            <Fragment key="change">
              <p className="sub" style={{ margin: '-6px 0 0' }}>
                {v.meName ? `${v.meName} 님, ` : ''}임시 비밀번호로 로그인했습니다. 새 비밀번호를 정해 주세요.
              </p>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb">현재(임시) 비밀번호</span>
                <input className="inp" type="password" autoComplete="current-password" {...v.current} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb">새 비밀번호</span>
                <input className="inp" type="password" autoComplete="new-password" {...v.next} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb">새 비밀번호 확인</span>
                <input className="inp" type="password" autoComplete="new-password" {...v.confirm} />
              </label>
              <p className="note" style={{ margin: '-6px 0 0' }}>
                {v.ruleText}
              </p>
            </Fragment>
          ) : (
            <Fragment key="login">
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb">기관 이메일</span>
                <input className="inp" type="email" autoComplete="username" placeholder="name@기관.kr" {...v.email} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb">비밀번호</span>
                <input className="inp" type="password" autoComplete="current-password" {...v.password} />
              </label>
            </Fragment>
          )}
          {v.message ? (
            <p role="alert" className="acc" style={{ margin: '0', fontSize: '13px' }}>
              {v.message}
            </p>
          ) : null}
          {v.errors.length > 0 ? (
            <ul role="alert" className="acc" style={{ margin: '0', paddingLeft: '18px', fontSize: '13px' }}>
              {v.errors.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          ) : null}
          <button
            type="submit"
            className="btn btn-p"
            disabled={v.busy}
            style={{ width: '100%', marginTop: '4px', opacity: v.busy ? 0.6 : 1 }}
          >
            {v.submitLabel}
          </button>
          {v.changing ? null : (
            <>
              {v.signupOn ? (
                <button type="button" className="btn btn-s" onClick={v.openSignup} style={{ width: '100%' }}>
                  회원가입
                </button>
              ) : null}
              {v.joined ? (
                <p className="lb" role="status" style={{ margin: '-6px 0 0', fontWeight: '400', textAlign: 'center' }}>
                  가입 신청이 접수됐어요. 관리자가 승인하면 로그인할 수 있어요.
                </p>
              ) : null}
              <div role="group" aria-label="로그인 유형" className="lseg">
                {v.roles.map((r) => (
                  <button key={r.label} type="button" className={r.cls} aria-pressed={r.pressed} onClick={r.pick}>
                    {r.label}
                  </button>
                ))}
              </div>
            </>
          )}
          {v.changing ? (
            <button
              type="button"
              className="note"
              onClick={v.switchAccount}
              style={{ background: 'none', border: '0', cursor: 'pointer', textDecoration: 'underline' }}
            >
              다른 계정으로 로그인
            </button>
          ) : null}
        </form>
        {v.suStep1 ? (
          <div className="sf-ov">
            <section role="dialog" aria-modal="true" aria-labelledby="su-title" className="sf-dlg" style={{ background: '#FFFFFF' }}>
              <div className="sf-top">
                <h2 id="su-title" className="sf-title" aria-live="polite">
                  {v.suTitle}
                </h2>
                <button type="button" className="sf-x" aria-label="닫기" onClick={v.suClose}>
                  ×
                </button>
              </div>
              <div className="sf-body">
                {v.suShowName ? (
                  <div className="sf-row sf-slide">
                    <label className={`sf-f ${v.suNameCls}`}>
                      <span className="sf-lb">이름</span>
                      <input
                        type="text"
                        placeholder="이름"
                        autoComplete="name"
                        value={v.suName}
                        onChange={v.suSetName}
                        onKeyDown={v.suKey}
                        aria-label="이름"
                      />
                    </label>
                  </div>
                ) : null}
                {v.suShowEmail ? (
                  <div className="sf-row sf-slide">
                    <div className={`sf-f ${v.suEmailCls}`}>
                      <span className="sf-lb">이메일</span>
                      <div className="sf-mail">
                        <input
                          type="email"
                          placeholder="name@기관.kr"
                          autoComplete="email"
                          value={v.suEmail}
                          onChange={v.suSetEmail}
                          onKeyDown={v.suKey}
                          readOnly={v.suEmailLock}
                          aria-label="이메일"
                        />
                        {v.suSendOn ? (
                          <button type="button" className="sf-get on" onClick={v.suResend}>
                            인증번호 받기
                          </button>
                        ) : (
                          <button type="button" className="sf-get" disabled>
                            {v.suSendLabel}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ) : null}
                {v.suShowCode ? (
                  <div className="sf-row sf-code">
                    <label className="sf-f on">
                      <span className="sf-lb">인증번호</span>
                      <input
                        type="text"
                        inputMode="numeric"
                        maxLength={6}
                        placeholder="6자리 숫자"
                        autoComplete="one-time-code"
                        value={v.suCode}
                        onChange={v.suSetCode}
                        onKeyDown={v.suKey}
                        aria-label="인증번호"
                        style={{ letterSpacing: '.2em' }}
                      />
                    </label>
                    <div className="sf-sub">
                      <span className={v.suTimerCls}>{v.suTimer}</span>
                      <span style={{ flex: '1' }}>{v.suSentNote}</span>
                      <button type="button" className="sf-mini" onClick={v.suResend} disabled={!v.suResendOn}>
                        {v.suResendLabel}
                      </button>
                    </div>
                    <p className="sf-rule" style={{ display: 'block', margin: '8px 0 0' }}>
                      {v.suSpamNote}
                    </p>
                  </div>
                ) : null}
                {v.suError ? (
                  <p className="sf-err" role="alert">
                    {v.suError}
                  </p>
                ) : null}
              </div>
              {v.suNextOn ? (
                <button type="button" className="sf-next on" onClick={v.suNext}>
                  {v.suNextLabel}
                </button>
              ) : (
                <button type="button" className="sf-next" disabled>
                  {v.suNextLabel}
                </button>
              )}
            </section>
            {v.suWrong ? (
              <div className="sf-ov sf-ov2">
                <section
                  role="alertdialog"
                  aria-modal="true"
                  aria-labelledby="su-wrong"
                  className="sf-dlg sf-small"
                  style={{ background: '#FFFFFF' }}
                >
                  <span className="sf-check sf-warn" aria-hidden="true">
                    !
                  </span>
                  <h2 id="su-wrong" className="sf-title" style={{ textAlign: 'center' }}>
                    {v.suWrong.title}
                  </h2>
                  <p className="sf-lb" style={{ margin: '0', textAlign: 'center' }}>
                    {v.suWrong.note}
                  </p>
                  <button type="button" className="sf-next on" onClick={v.suWrongOk}>
                    확인
                  </button>
                </section>
              </div>
            ) : null}
          </div>
        ) : null}

        {v.suStep2 ? (
          <div className="sf-ov">
            <section role="dialog" aria-modal="true" aria-labelledby="su2-title" className="sf-dlg" style={{ background: '#FFFFFF' }}>
              <div className="sf-top">
                <h2 id="su2-title" className="sf-title">
                  계정 정보를 입력하세요.
                </h2>
                <button type="button" className="sf-x" aria-label="닫기" onClick={v.suClose}>
                  ×
                </button>
              </div>
              <div className="sf-body sf-down">
                <label className="sf-f">
                  <span className="sf-lb">이름</span>
                  <input
                    type="text"
                    placeholder="이름"
                    autoComplete="name"
                    value={v.suName2}
                    onChange={v.suSetName2}
                    onKeyDown={v.suKey}
                    aria-label="이름"
                  />
                </label>
                <label className="sf-f lock">
                  <span className="sf-lb">
                    아이디 <span className="sf-note">인증한 이메일 · 변경 불가</span>
                  </span>
                  <input type="text" value={v.suEmail} readOnly aria-readonly="true" aria-label="아이디" />
                </label>
                <div>
                  <div className="sf-f">
                    <label className="sf-lb" htmlFor="su-pw">
                      비밀번호 <span className="sf-rule">{v.ruleText}</span>
                    </label>
                    <div className="sf-pw">
                      <input
                        id="su-pw"
                        type={v.suPwEye.type}
                        autoComplete="new-password"
                        value={v.suPw}
                        onChange={v.suSetPw}
                        onKeyDown={v.suKey}
                      />
                      <PwEye eye={v.suPwEye} />
                    </div>
                  </div>
                  {v.suErrors.map((message) => (
                    <p key={message} className="sf-err" role="alert">
                      {message}
                    </p>
                  ))}
                </div>
                <div>
                  <div className="sf-f">
                    <label className="sf-lb" htmlFor="su-pw2">
                      비밀번호 재입력
                    </label>
                    <div className="sf-pw">
                      <input
                        id="su-pw2"
                        type={v.suPw2Eye.type}
                        autoComplete="new-password"
                        value={v.suPw2}
                        onChange={v.suSetPw2}
                        onKeyDown={v.suKey}
                      />
                      <PwEye eye={v.suPw2Eye} />
                    </div>
                  </div>
                  {v.suPwBad ? (
                    <p className="sf-err" role="alert">
                      동일한 비밀번호가 아닙니다.
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="sf-btns">
                <button type="button" className="sf-cancel" onClick={v.suClose}>
                  취소
                </button>
                {v.suDoneOn ? (
                  <button type="button" className="sf-next on" onClick={v.suDone}>
                    {v.suDoneLabel}
                  </button>
                ) : (
                  <button type="button" className="sf-next" disabled>
                    {v.suDoneLabel}
                  </button>
                )}
              </div>
            </section>
          </div>
        ) : null}

        {v.suStep3 ? (
          <div className="sf-ov">
            <section
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="su3-title"
              className="sf-dlg sf-small"
              style={{ background: '#FFFFFF' }}
            >
              <span className="sf-check" aria-hidden="true">
                ✓
              </span>
              <h2 id="su3-title" className="sf-title" style={{ textAlign: 'center' }}>
                가입 신청이 접수되었습니다.
              </h2>
              <p className="sf-lb" style={{ margin: '0', textAlign: 'center' }}>
                관리자 승인 뒤 로그인할 수 있습니다.
              </p>
              <button type="button" className="sf-next on" onClick={v.suFinish}>
                확인
              </button>
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}
