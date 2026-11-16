import { useDC } from '../dc';
import DesignLogic from '../design/Upload.logic';
import View from './Upload.view';

export default function Upload(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
