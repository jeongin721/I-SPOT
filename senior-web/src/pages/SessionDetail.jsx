import { useDC } from '../dc';
import DesignLogic from '../design/SessionDetail.logic';
import View from './SessionDetail.view';

export default function SessionDetail(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
