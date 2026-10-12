// 로그인 요청 훅. 화면은 입력값만 넘기고, 결과에 따라 어디로 갈지는 화면이 정한다.
//
// 로그인은 Backend(POST /auth/login)가 판정한다. 틀린 비밀번호 · 없는 계정 · 잠금은 같은 401 · 같은 문구이고,
// 정지 · 휴면 · 임시 비밀번호 만료는 403 으로 이유를 알려 준다. 화면은 Backend 문구를 그대로 보여 준다.
// 2단계 인증(OTP)은 Backend 에 없다(팀 결정 대기).

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, clearLogoutReason } from "../api/client";
import { auth } from "../api/endpoints";
import type { User } from "../api/types";

export interface LoginState {
  submitting: boolean;
  error: string | null;
  /** 성공하면 사용자를 돌려준다. must_change_password 면 비밀번호부터 바꿔야 한다. 실패하면 null(error 에 문구). */
  login: (email: string, password: string) => Promise<User | null>;
  clearError: () => void;
}

export function useLogin(): LoginState {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 두 번 눌러도 요청은 하나만 보낸다(상태 값은 다음 그리기까지 바뀌지 않아 ref 로 막는다).
  const inFlight = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    if (inFlight.current) return null;

    const trimmed = email.trim();

    if (!trimmed || !password) {
      setError("이메일과 비밀번호를 입력해 주세요.");
      return null;
    }

    inFlight.current = true;
    setSubmitting(true);
    setError(null);

    try {
      const result = await auth.login({ email: trimmed, password });

      // 이 화면이 뜬 뒤에 늦게 도착한 401 이 남긴 이유가 다음 로그아웃 때 다시 보이지 않게 지운다.
      clearLogoutReason();

      return result.user;
    } catch (caught) {
      if (mounted.current) {
        setError(
          caught instanceof ApiError
            ? caught.message
            : "로그인 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        );
      }

      return null;
    } finally {
      inFlight.current = false;
      if (mounted.current) setSubmitting(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { submitting, error, login, clearError };
}
