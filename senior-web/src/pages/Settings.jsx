// 설정 — 디자인 Settings.dc.html.
//  - 계정: 상담사 이름 · 이메일은 로그인한 사람(GET /auth/me). 휴대폰 번호 · 소속 기관은 서버 칸이 없어 '—'.
//    이름 · 이메일 · 휴대폰 '수정' 은 디자인대로 화면에서만 바뀐다(서버에 내 정보 고치기 API 가 없다) — 아래 안내 줄로 드러낸다.
//    이메일 '인증 메일 보내기' 는 실제로 보내지 않으니 '발송됨' 을 띄우지 않는다.
//  - 비밀번호: 디자인의 '비밀번호 확인' 창을 비밀번호 바꾸기 창으로 쓴다(현재 · 새 · 새 확인).
//    POST /auth/me/password(@cw usePasswordChange). 성공하면 서버가 토큰을 모두 끊으므로 로그아웃되고 로그인 화면에 안내가 남는다.
//    오류는 서버 문구(WEAK_PASSWORD 사유 · SAME_PASSWORD · INVALID_CURRENT_PASSWORD · PASSWORD_REUSED)를 창 안에 보인다.
//  - 계정 화면에 들어가기 전 '비밀번호 확인' 은 서버에 확인 API 가 없어(맞는지 볼 수 없다) 거치지 않고 바로 연다.
//  - 알림 설정은 서버 칸이 없어 화면에서만 바뀐다(안내 줄).
import { useDC } from '../dc';
import DesignLogic from '../design/Settings.logic';
import { usePasswordChange, PASSWORD_RULE_TEXT } from '@cw/data/usePasswordChange';
import { useShell } from '../data/useShell';
import { DASH } from '../data/format';
import View from './Settings.view';

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    // 디자인 예시(이서연 · 메일 · 휴대폰)는 지우고 로그인한 사람 값으로 채운다.
    this.state = { ...this.state, name: '', mail: '', phone: '', pwNew: '', pwNew2: '', edited: false };
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { shell, pw } = this.props;
    const me = shell.session.me;
    const name = s.edited && s.name ? s.name : (me && me.name) || DASH;
    const mail = s.mailEdited && s.mail ? s.mail : (me && me.email) || DASH;
    const closePw = () => {
      pw.clearErrors();
      this.setState({ pwOpen: false, pwIn: '', pwNew: '', pwNew2: '' });
    };
    const ready = !!(s.pwIn && s.pwNew && s.pwNew2) && !pw.submitting;
    return {
      ...base,
      ...shell,
      cntApp: '',
      cntFollow: '',
      // 계정은 바로 연다(서버에 '비밀번호만 확인' API 가 없다).
      goAccount: () => this.setState({ view: 'account', edit: null }),
      name,
      mail,
      phone: s.phone || DASH,
      editName: () => this.setState({ edit: 'name', draft: name === DASH ? '' : name }),
      saveName: () => this.setState({ edit: null, name: this.state.draft || name, edited: true }),
      editMail: () => this.setState({ edit: 'mail', draft: mail === DASH ? '' : mail, mailSent: false }),
      saveMail: () => this.setState({ edit: null, mail: this.state.draft || mail, mailEdited: true, mailSent: false }),
      editPhone: () => this.setState({ edit: 'phone', draft: s.phone || '', phoneErr: false }),
      mailSent: false,
      org: DASH,
      accountNote: '상담사 이름 · 이메일 · 휴대폰 번호는 아직 서버에 저장되지 않아요(이 화면에서만 바뀌어요). 비밀번호만 실제로 바뀝니다.',
      notifyNote: '알림 설정은 아직 서버에 저장되지 않아요(이 화면에서만 바뀌어요).',
      // 비밀번호 바꾸기(디자인 '비밀번호 확인' 창)
      pwText: '마지막 변경 —',
      pwLabel: '비밀번호 바꾸기',
      pwCls: 'btn-p',
      resetPw: () => {
        pw.clearErrors();
        this.setState({ pwOpen: true, pwIn: '', pwNew: '', pwNew2: '' });
      },
      pwChange: true,
      pwTitle: '비밀번호 바꾸기',
      pwDesc: '지금 비밀번호를 넣고 새 비밀번호를 두 번 입력해 주세요. 바꾸면 다시 로그인해야 해요.',
      pwInLabel: '현재 비밀번호',
      pwNew: s.pwNew,
      pwNew2: s.pwNew2,
      setPwNew: (e) => this.setState({ pwNew: e.target.value }),
      setPwNew2: (e) => this.setState({ pwNew2: e.target.value }),
      pwRule: PASSWORD_RULE_TEXT,
      pwErr: pw.errors.join(' '),
      pwOk: ready,
      pwWait: !ready,
      closePw,
      submitPw: async () => {
        if (!ready) return;
        // 성공하면 hook 이 로그아웃시키고(useShell 이 로그인 화면으로 보낸다) 안내 문구를 남긴다.
        const ok = await pw.change({ currentPassword: this.state.pwIn, newPassword: this.state.pwNew, confirmPassword: this.state.pwNew2 });
        if (ok) this.setState({ pwOpen: false, pwIn: '', pwNew: '', pwNew2: '' });
      },
    };
  }
}

export default function Settings(props) {
  const shell = useShell();
  const pw = usePasswordChange();
  const v = useDC(Logic, { ...props, shell, pw });
  return <View v={v} />;
}
