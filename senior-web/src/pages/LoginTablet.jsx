// 로그인(태블릿) — 디자인 LoginTablet.dc.html. 데스크톱 Login.jsx 와 같은 로그인 동작(counselor-web 훅)을 태블릿 마크업에 붙인다.
//  - 로그인하면 태블릿 홈(HomeTablet)으로. '관리자 로그인' 을 고르고 관리자 계정이면 태블릿 관리자 홈(AdminHomeTablet)으로.
//  - 회원가입: 디자인의 인증번호 팝업은 서버 연결 전이라 열지 않고 짧은 안내만 보인다(승인제 회원가입은 아동 웹과 같은 API 로 나중에 붙인다).
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDC } from '../dc';
import DesignLogic from '../design/LoginTablet.logic';
import { useAuthSession } from '@cw/data/useAuthSession';
import { useLogin } from '@cw/data/useLogin';
import { useLogoutNotice } from '@cw/data/useLogoutNotice';
import View from './LoginTablet.view';

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, email: '', password: '' };
  }

  async signIn() {
    const { login, navigate, dismissNotice } = this.props;
    this.setState({ joinNote: false });
    const user = await login.login(this.state.email, this.state.password);
    if (!user) return;
    dismissNotice();
    if (user.must_change_password) {
      // 임시 비밀번호는 아동 웹에서 먼저 바꾼다(이 화면에는 변경 단계 디자인이 없다).
      this.setState({ changeNeeded: true });
      return;
    }
    navigate(this.state.role === 'admin' && user.role === 'ADMIN' ? '/AdminHomeTablet' : '/HomeTablet');
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const { login, notice } = this.props;
    const submit = (e) => {
      if (e && e.preventDefault) e.preventDefault();
      this.signIn();
    };
    let message = login.error || notice || '';
    if (this.state.changeNeeded) message = '임시 비밀번호예요. 아동 상담사 웹에서 비밀번호를 먼저 바꿔 주세요.';
    else if (this.state.joinNote) message = '회원가입은 준비 중이에요. 기관 관리자에게 계정을 요청해 주세요.';
    return {
      ...base,
      loginHref: '#/HomeTablet',
      password: this.state.password,
      setPassword: (e) => this.setState({ password: e.target.value }),
      busy: login.submitting ? 'true' : 'false',
      submitLabel: login.submitting ? '로그인 중…' : '로그인',
      message,
      submit,
      // 인증번호 팝업 대신 안내 한 줄.
      codeOpen: false,
      joined: false,
      openCode: () => this.setState({ joinNote: true, changeNeeded: false }),
    };
  }
}

export default function LoginTablet(props) {
  const navigate = useNavigate();
  const session = useAuthSession();
  const login = useLogin();
  const { notice, dismiss: dismissNotice } = useLogoutNotice();
  useEffect(() => {
    if (session.status === 'signedIn') navigate('/HomeTablet', { replace: true });
  }, [session.status, navigate]);
  const v = useDC(Logic, { ...props, navigate, login, notice, dismissNotice });
  return <View v={v} />;
}
