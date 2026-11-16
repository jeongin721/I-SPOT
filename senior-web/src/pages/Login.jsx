// 로그인 — 디자인 Login.dc.html(온담 시니어). 로그인 · 로그인 상태는 counselor-web 의 훅을 그대로 쓴다.
// 회원가입 팝업은 디자인 그대로(서버 연결 전, 승인제 회원가입은 아동 웹과 같은 API 로 나중에 붙인다).
// 관리자 로그인은 이번 범위 밖이라 관리자 계정도 홈으로 간다.
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDC } from '../dc';
import DesignLogic from '../design/Login.logic';
import { useAuthSession } from '@cw/data/useAuthSession';
import { useLogin } from '@cw/data/useLogin';
import { useLogoutNotice } from '@cw/data/useLogoutNotice';
import View from './Login.view';

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, email: '', password: '' };
  }

  async signIn() {
    const { login, navigate, dismissNotice } = this.props;
    const user = await login.login(this.state.email, this.state.password);
    if (!user) return;
    dismissNotice();
    if (user.must_change_password) {
      // 임시 비밀번호는 아동 웹에서 먼저 바꾼다(이 화면에는 변경 단계 디자인이 없다).
      this.setState({ changeNeeded: true });
      return;
    }
    navigate('/Home');
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const { login, notice } = this.props;
    return {
      ...base,
      loginHref: '#/Home',
      password: this.state.password,
      setPassword: (e) => this.setState({ password: e.target.value }),
      busy: login.submitting ? 'true' : 'false',
      submitLabel: login.submitting ? '로그인 중…' : '로그인',
      message: this.state.changeNeeded
        ? '임시 비밀번호예요. 아동 상담사 웹에서 비밀번호를 먼저 바꿔 주세요.'
        : login.error || notice || '',
      submit: (e) => {
        if (e && e.preventDefault) e.preventDefault();
        this.signIn();
      },
    };
  }
}

export default function Login(props) {
  const navigate = useNavigate();
  const session = useAuthSession();
  const login = useLogin();
  const { notice, dismiss: dismissNotice } = useLogoutNotice();
  useEffect(() => {
    if (session.status === 'signedIn') navigate('/Home', { replace: true });
  }, [session.status, navigate]);
  const v = useDC(Logic, { ...props, navigate, login, notice, dismissNotice });
  return <View v={v} />;
}
