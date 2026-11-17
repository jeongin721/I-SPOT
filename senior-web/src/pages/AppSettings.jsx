// 상담사 앱(폰) · 설정 — 디자인 AppSettings.dc.html.
//  - 내 정보: 로그인한 상담사 이름 · 이메일(GET /auth/me). 소속 기관은 서버에 없어 '—'.
//  - 어두운 화면: 디자인 그대로 이 브라우저에 기억(앱 화면에만 적용).
//  - 알림 4개 · Wi-Fi에서만 올리기: 폰 알림(푸시) · 연결 종류를 아는 기능이 아직 없어 꺼진 채로 두고, 누르면 '준비 중' 안내만.
//    업로드 실패 · 오늘 남은 상담은 앱 안의 알림(종)에 늘 보인다.
//  - 로그아웃: 웹과 같은 로그아웃(로그인 화면으로). 폰에 올리지 못한 녹음은 남는다(같은 계정으로 다시 로그인하면 보인다).
import { useDC } from '../dc';
import DesignLogic from '../design/AppSettings.logic';
import { DASH } from '../data/format';
import { useAppData, withApp } from './App.parts';
import View from './AppSettings.view';

const SOON = '알림 · 올리기 설정은 준비 중이에요. 업로드 실패와 오늘 남은 상담은 위 종 모양 알림에서 볼 수 있어요.';

class Logic extends withApp(DesignLogic) {
  renderVals() {
    const v = super.renderVals();
    const me = this.props.app.me;
    const name = me && me.name ? me.name : DASH;
    const soon = () => this.setState({ soon: true });
    return {
      ...v,
      meInitial: me && me.name ? me.name.slice(0, 1) : DASH,
      meName: me && me.name ? (name.endsWith('상담사') ? name : `${name} 상담사`) : DASH,
      meOrg: DASH,
      meEmail: (me && me.email) || DASH,
      tgs: (v.tgs || []).map((t) => ({ ...t, on: 'false', cls: 'tg', toggle: soon })),
      wifiCls: 'tg',
      wifiA: 'false',
      toggleWifi: soon,
      soonMsg: this.state.soon ? SOON : '',
      logout: this.props.app.shell.logout,
    };
  }
}

export default function AppSettings(props) {
  const app = useAppData();
  const v = useDC(Logic, { ...props, app });
  return <View v={v} />;
}
