import { useDC } from '../dc';
import DesignLogic from '../design/Step1Record.logic';
import View from './Step1Record.view';

export default function Step1Record(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
