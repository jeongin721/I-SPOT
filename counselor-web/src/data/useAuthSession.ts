// 로그인 상태를 화면에 알려 주는 훅.
//
// 화면 이동은 하지 않고 상태만 돌려준다. 로그인 화면으로 보낼지, 비밀번호 변경 단계를 보여 줄지는
// 이 훅을 쓰는 화면이 정한다. 그래서 라우터(react-router 버전 등)와 상관없이 어느 화면 코드에도 끼울 수 있다.
//
// 알아채는 것:
//  - 저장된 토큰으로 GET /auth/me 확인(새로고침해도 로그인 유지)
//  - 어느 요청이든 401 → 로그아웃(client 가 토큰을 지우고 UNAUTHORIZED_EVENT 를 보낸다)
//  - 403 PASSWORD_CHANGE_REQUIRED → 비밀번호 변경 필요(PASSWORD_CHANGE_REQUIRED_EVENT)
//  - 다른 탭의 로그아웃 · 다시 로그인(localStorage 토큰 칸의 storage 이벤트)
// ispotvscode/src/api/useAdminSession.ts 의 같은 처리를 화면 이동 없이 옮겼다.

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  PASSWORD_CHANGE_REQUIRED_EVENT,
  TOKEN_KEY,
  UNAUTHORIZED_EVENT,
  getToken,
  signOut,
} from "../api/client";
import { auth } from "../api/endpoints";
import type { User, UserRole } from "../api/types";

/**
 * checking           저장된 토큰을 확인하는 중
 * signedOut          로그인하지 않았거나 로그인이 끝났다(만료 · 폐기 · 로그아웃)
 * signedIn           로그인됨
 * mustChangePassword 임시 비밀번호로 로그인했다. 비밀번호를 바꾸기 전에는 다른 요청이 모두 403 이다
 * error              서버에 닿지 못하는 등 401 이 아닌 이유로 확인하지 못했다(error 에 문구)
 */
export type AuthStatus = "checking" | "signedOut" | "signedIn" | "mustChangePassword" | "error";

export interface AuthSession {
  status: AuthStatus;
  /** signedIn · mustChangePassword 일 때 로그인한 사용자. 그 밖에는 null. */
  me: User | null;
  /** 로그인한 사용자의 역할(서버가 GET /auth/me 로 준 값). 로그인 전 · 확인 중이면 null. */
  role: UserRole | null;
  /**
   * 관리자 화면을 써도 되는가. 로그인이 끝났고(signedIn) 서버가 준 역할이 관리자일 때만 true.
   * 임시 비밀번호 상태(mustChangePassword)는 관리자라도 false 다 — 다른 요청이 모두 403 이다.
   * 관리자 훅(useAdmin*)은 이 값이 false 면 서버를 부르지 않는다.
   */
  isAdmin: boolean;
  error: string | null;
  /** 다시 확인한다(오류 뒤 다시 시도, 이 탭에서 방금 로그인한 뒤). */
  recheck: () => void;
  /** 로그아웃한다. reason 은 로그인 화면에 보여 줄 문구다. */
  logout: (reason?: string) => void;
}

export function useAuthSession(): AuthSession {
  const [status, setStatus] = useState<AuthStatus>(() => (getToken() ? "checking" : "signedOut"));
  const [me, setMe] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  // 바뀌면 다시 확인한다(다른 탭 로그인 · 다시 시도).
  const [checkKey, setCheckKey] = useState(0);

  const recheck = useCallback(() => setCheckKey((key) => key + 1), []);

  useEffect(() => {
    const requestedToken = getToken();

    setError(null);

    if (!requestedToken) {
      setMe(null);
      setStatus("signedOut");
      return;
    }

    let cancelled = false;

    setStatus("checking");

    // 응답을 기다리는 사이에 다른 탭에서 로그아웃하거나 다른 계정으로 로그인하면 토큰이 바뀐다.
    // 그 응답은 옛 계정의 것이라 버리고 지금 토큰으로 다시 확인한다.
    const tokenChanged = () => getToken() !== requestedToken;

    auth
      .me()
      .then((user) => {
        if (cancelled) return;

        if (tokenChanged()) {
          recheck();
          return;
        }

        setMe(user);
        setStatus(user.must_change_password ? "mustChangePassword" : "signedIn");
      })
      .catch((caught) => {
        if (cancelled) return;

        // 옛 토큰의 실패다(늦게 온 401 은 client 도 무시한다). 지금 토큰으로 다시 확인한다.
        if (tokenChanged()) {
          recheck();
          return;
        }

        setMe(null);

        // 401 은 client 가 토큰을 지우고 UNAUTHORIZED_EVENT 를 보낸다. 여기서도 바로 로그아웃 상태로 둔다.
        if (caught instanceof ApiError && caught.isUnauthorized) {
          setStatus("signedOut");
          return;
        }

        setStatus("error");
        setError(caught instanceof ApiError ? caught.message : "로그인 상태를 확인하지 못했습니다.");
      });

    return () => {
      cancelled = true;
    };
  }, [checkKey, recheck]);

  useEffect(() => {
    function onUnauthorized() {
      setMe(null);
      setError(null);
      setStatus("signedOut");
    }

    function onPasswordChangeRequired() {
      // 사용자 정보가 아직 없으면(확인 중) 확인 결과가 must_change_password 로 온다.
      setStatus((current) => (current === "signedIn" ? "mustChangePassword" : current));
    }

    function onStorage(event: StorageEvent) {
      // key 가 null 이면 localStorage.clear() 다.
      if (event.key !== null && event.key !== TOKEN_KEY) return;

      if (!getToken()) {
        onUnauthorized();
      } else {
        // 토큰이 바뀌었다 — 다른 탭에서 다른 계정(또는 같은 계정)으로 다시 로그인했다.
        setMe(null);
        recheck();
      }
    }

    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    window.addEventListener(PASSWORD_CHANGE_REQUIRED_EVENT, onPasswordChangeRequired);
    window.addEventListener("storage", onStorage);

    return () => {
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
      window.removeEventListener(PASSWORD_CHANGE_REQUIRED_EVENT, onPasswordChangeRequired);
      window.removeEventListener("storage", onStorage);
    };
  }, [recheck]);

  const logout = useCallback((reason?: string) => signOut(reason), []);

  const role = me?.role ?? null;

  return { status, me, role, isAdmin: status === "signedIn" && role === "ADMIN", error, recheck, logout };
}
