import { useDC } from '../dc';
import DesignLogic from '../design/Schedule.logic';
import View from './Schedule.view';

export default function Schedule(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
