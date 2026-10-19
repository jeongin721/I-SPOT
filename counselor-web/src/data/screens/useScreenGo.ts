// 요청이 끝난 뒤 다음 화면으로 옮길 때 쓰는 이동 함수. 화면 이동 함수(react-router 의 navigate)를 받아 감싼다.
//
// 저장 · 확정 응답을 기다리는 사이 사람이 다른 회차나 다른 화면으로 옮겼으면, 늦게 온 응답이 앞 회차의 다음 화면으로
// 끌고 가지 않게 한다. 요청을 보낼 때 잡은 표를 확인하는 함수(데이터 훅의 isCurrent)를 넘기면 그 표가 아직 지금 대상일
// 때만 옮긴다. 회차 ID 만 비교하면 다른 회차에 갔다 돌아온 경우(A → B → A) · 다시 로그인한 경우를 가리지 못한다.

import { useCallback, useEffect, useRef } from "react";

export type ScreenGo = (href: string, stillCurrent?: () => boolean) => void;

export function useScreenGo(navigate: (href: string) => void): ScreenGo {
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  return useCallback(
    (href: string, stillCurrent?: () => boolean) => {
      if (!mounted.current) return;
      if (stillCurrent && !stillCurrent()) return;

      navigate(href);
    },
    [navigate],
  );
}
