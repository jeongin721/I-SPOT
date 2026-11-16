import { useDC } from '../dc';
import DesignLogic from '../design/Step4Next.logic';
import View from './Step4Next.view';

export default function Step4Next(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
