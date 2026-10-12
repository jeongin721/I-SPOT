// 디자인 보드의 화면 로직(class + renderVals)을 React에서 그대로 쓰기 위한 작은 어댑터.
// - 각 화면 파일의 `class Logic extends DCLogic` 은 상태(state)와 화면에 쓸 값(renderVals)을 만들어요.
// - `useDC(Logic, props)` 가 그 인스턴스를 만들고, setState 하면 다시 그려요.
// 나중에 화면별로 useState / 커스텀 훅으로 옮겨도 되고, API 연결 시 renderVals 안의 예시 데이터만 바꾸면 돼요.
import { useEffect, useReducer, useRef } from 'react';

export class DCLogic {
  constructor(props) {
    this.props = props;
    this.state = {};
    this._rerender = null;
  }

  setState(patch) {
    const next = typeof patch === 'function' ? patch(this.state, this.props) : patch;
    this.state = { ...this.state, ...next };
    if (this._rerender) this._rerender();
  }
}

export function useDC(Logic, props) {
  const [, rerender] = useReducer((x) => x + 1, 0);
  const ref = useRef(null);
  if (!ref.current) ref.current = new Logic(props);
  const inst = ref.current;
  inst.props = props;
  inst._rerender = rerender;
  useEffect(() => {
    if (inst.componentDidMount) inst.componentDidMount();
    return () => {
      if (inst.componentWillUnmount) inst.componentWillUnmount();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return inst.renderVals();
}
