import { useDC } from '../dc';
import DesignLogic from '../design/Login.logic';
import View from './Login.view';

export default function Login(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
