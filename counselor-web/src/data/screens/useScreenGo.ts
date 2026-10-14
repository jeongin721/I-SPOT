// 요청이 끝난 뒤 다음 화면으로 옮길 때 쓰는 이동 함수. 화면 이동 함수(react-router 의 navigate)를 받아 감싼다.
//
// 저장 · 확정 응답을 기다리는 사이 사람이 다른 회차나 다른 화면으로 옮겼으면, 늦게 온 응답이 앞 회차의 다음 화면으로
// 끌고 가지 않게 한다. 요청을 보낼 때의 회차 ID 를 넘기면 그 회차를 아직 보고 있을 때만 옮긴다.

import { useCallback, useEffect, useRef } from "react";

import type { ScreenIds } from "./links";

export type ScreenGo = (href: string, forSessionId?: string | null) => void;

export function useScreenGo(navigate: (href: string) => void, ids: ScreenIds): ScreenGo {
  const current = useRef(ids);
  current.current = ids;
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  return useCallback(
    (href: string, forSessionId?: string | null) => {
      if (!mounted.current) return;
      if (forSessionId !== undefined && current.current.sessionId !== forSessionId) return;

      navigate(href);
    },
    [navigate],
  );
}
