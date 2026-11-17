// 시작 화면(로그인 전 표지) — 디자인 Start.dc.html. 로그인 없이 열린다(useShell 을 쓰지 않는다).
// 서버 값이 없는 소개 화면이라 디자인 그대로 그리고, 로그인 단추는 #/Login 으로 간다.
import { useDC } from '../dc';
import DesignLogic from '../design/Start.logic';
import View from './Start.view';

class Logic extends DesignLogic {}

export default function Start(props) {
  const v = useDC(Logic, props);
  return <View v={v} />;
}
