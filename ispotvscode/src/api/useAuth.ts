// 로그인 상태를 화면 전체에서 공유한다.
//
// 새로고침해도 로그인이 유지되도록, 저장된 토큰으로 /auth/me 를 한 번 확인한다.
// 토큰이 만료됐으면 조용히 지우고 로그아웃 상태로 둔다.

import { useCallback, useEffect, useState } from "react";

import { ApiError, clearToken, getToken } from "./client";
import { auth } from "./endpoints";
import type { User } from "./types";

export interface AuthState {
  user: User | null;
  /** 저장된 토큰을 확인하는 중. 이때는 로그인 화면을 보여주지 않는다. */
  checking: boolean;
  loggingIn: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [loggingIn, setLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 저장된 토큰 확인
  useEffect(() => {
    let cancelled = false;

    if (!getToken()) {
      setChecking(false);

      return;
    }

    auth
      .me()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        // 만료·폐기된 토큰이므로 지운다.
        clearToken();
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setLoggingIn(true);
    setError(null);

    try {
      const result = await auth.login({ email, password });

      setUser(result.user);

      return result.user;
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : "로그인 중 문제가 발생했습니다.";

      setError(message);

      throw caught;
    } finally {
      setLoggingIn(false);
    }
  }, []);

  const logout = useCallback(() => {
    auth.logout();
    setUser(null);
  }, []);

  return { user, checking, loggingIn, error, login, logout };
}
