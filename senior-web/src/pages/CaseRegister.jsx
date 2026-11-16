import { useDC } from '../dc';
import DesignLogic from '../design/CaseRegister.logic';
import View from './CaseRegister.view';

export default function CaseRegister(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
