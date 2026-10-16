// 로그인 화면이 보여 줄 "왜 로그아웃됐는지" 문구.
//
// client 가 로그인을 끝낼 때(토큰 만료 · 폐기, 비밀번호 변경 등) 이유를 sessionStorage 에 남긴다.
// 다른 화면에서 끊겨 로그인 화면으로 왔으면 처음 그릴 때 읽고, 로그인 화면에 있는 동안 끊기면 이벤트로 받는다.
// 한 번 읽은 이유는 지운다(새로고침해도 다시 나오지 않게).

import { useCallback, useEffect, useState } from "react";

import { UNAUTHORIZED_EVENT, clearLogoutReason, readLogoutReason } from "../api/client";

export interface LogoutNotice {
  /** 없으면 빈 문자열. */
  notice: string;
  dismiss: () => void;
}

export function useLogoutNotice(): LogoutNotice {
  const [notice, setNotice] = useState(readLogoutReason);

  useEffect(() => {
    // 그리는 함수(useState 초기값)에서 지우면 StrictMode 의 두 번째 그리기에서 사라진다. 그래서 여기서 지운다.
    clearLogoutReason();

    function onUnauthorized(event: Event) {
      const message = (event as CustomEvent<{ message: string | null } | undefined>).detail?.message;

      if (message) {
        setNotice(message);
        clearLogoutReason();
      }
    }

    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);

    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const dismiss = useCallback(() => setNotice(""), []);

  return { notice, dismiss };
}
