import { useDC } from '../dc';
import DesignLogic from '../design/CaseInfo.logic';
import View from './CaseInfo.view';

export default function CaseInfo(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
