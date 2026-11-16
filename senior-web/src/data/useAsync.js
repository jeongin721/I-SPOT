// 서버에서 값을 한 번 읽어 오는 작은 훅. deps 가 바뀌면 다시 읽고, reload() 로 다시 읽을 수 있다.
// 화면이 사라진 뒤 도착한 응답은 버린다.
import { useCallback, useEffect, useRef, useState } from 'react';

export function useAsync(load, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const seq = useRef(0);
  const run = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    Promise.resolve()
      .then(load)
      .then(
        (data) => id === seq.current && setState({ data, error: null, loading: false }),
        (error) => id === seq.current && setState({ data: null, error, loading: false }),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    run();
    return () => {
      seq.current += 1;
    };
  }, [run]);
  return { ...state, reload: run };
}
