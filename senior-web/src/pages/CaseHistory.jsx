import { useDC } from '../dc';
import DesignLogic from '../design/CaseHistory.logic';
import View from './CaseHistory.view';

export default function CaseHistory(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
