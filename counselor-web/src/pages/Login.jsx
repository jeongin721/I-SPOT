// 로그인
// 원본: 다솔 님 디자인 counselor-web-design/Login.dc.html (front_new 브랜치)
//
// 서버 연결: 로그인 · 로그인 상태 · 비밀번호 변경은 src/data 의 훅이 하고, 이 파일은 배치만 한다.
// 디자인을 바꿀 때는 아래 Login 함수의 훅과 Logic 을 그대로 두고 JSX 만 갈아 끼우면 된다.
//  - 로그인은 이메일(Backend 계약). OTP 는 Backend 에 없어 칸만 두고 막아 둔다(팀 결정 대기).
//  - 임시 비밀번호로 들어오면 같은 카드가 비밀번호 변경 단계로 바뀐다. 바꾸면 다시 로그인한다.
//  - 역할과 상관없이 로그인하면 /Main 으로 간다.
import { Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useLogin } from '../data/useLogin';
import { useLogoutNotice } from '../data/useLogoutNotice';
import { PASSWORD_RULE_TEXT, usePasswordChange } from '../data/usePasswordChange';
import './Login.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    // pwFor: 변경 단계 칸(current · next · confirm)이 어느 계정 것인가(설정 화면의 pwFor 와 같은 방식).
    this.state = { email: '', password: '', current: '', next: '', confirm: '', pwFor: null };
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
      this.props.navigate('/Main');
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

export default function Login(props) {
  const navigate = useNavigate();
  const session = useAuthSession();
  const login = useLogin();
  const pwChange = usePasswordChange();
  const { notice, dismiss: dismissNotice } = useLogoutNotice();
  const theme = useTheme();
  const v = useDC(Logic, { ...props, navigate, session, login, pwChange, notice, dismissNotice });
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
                <span className="lb">이메일</span>
                <input className="inp" type="email" autoComplete="username" {...v.email} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb">비밀번호</span>
                <input className="inp" type="password" autoComplete="current-password" {...v.password} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb">OTP 인증번호</span>
                <input className="inp" type="text" inputMode="numeric" placeholder="준비 중" disabled />
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
      </div>
    </div>
  );
}
