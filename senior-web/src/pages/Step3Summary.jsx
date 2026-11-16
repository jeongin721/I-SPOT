import { useDC } from '../dc';
import DesignLogic from '../design/Step3Summary.logic';
import View from './Step3Summary.view';

export default function Step3Summary(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
