import { useDC } from '../dc';
import DesignLogic from '../design/Step2Signals.logic';
import View from './Step2Signals.view';

export default function Step2Signals(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
