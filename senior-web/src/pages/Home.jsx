import { useDC } from '../dc';
import DesignLogic from '../design/Home.logic';
import View from './Home.view';

export default function Home(props) {
  const v = useDC(DesignLogic, props);
  return <View v={v} />;
}
