import { useDC } from '../dc';
import DesignLogic from '../design/CaseList.logic';
import View from './CaseList.view';

export default function CaseList(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
