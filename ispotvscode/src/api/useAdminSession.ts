// 관리자 화면(/admin) 진입 확인과 로그인 끊김 감지.
//
// 상담사 앱은 AppLayout 이 같은 일을 한다. 관리자 화면은 AppLayout 밖이라 따로 둔다.
// - 들어올 때 GET /auth/me 로 역할을 서버에서 다시 확인한다(localStorage 의 이름 · 역할은 믿지 않는다).
//   토큰이 없거나 401 → /login, 관리자가 아니면 → /dashboard, 임시 비밀번호면 → /profile(비밀번호 변경).
// - 화면을 쓰는 중에 토큰이 만료 · 폐기되면(401, 강제 로그아웃 포함) client 가 보내는 이벤트로 /login 으로 보낸다.
// - 다른 탭에서 로그아웃하면 /login 으로, 다른 계정으로 로그인하면 역할을 다시 확인한다(storage 이벤트).

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  ApiError,
  PASSWORD_CHANGE_REQUIRED_EVENT,
  SESSION_INFO_KEY,
  TOKEN_KEY,
  UNAUTHORIZED_EVENT,
  clearSession,
  getToken,
} from "./client";
import { auth } from "./endpoints";
import type { User } from "./types";

export interface AdminSession {
  /** 확인이 끝난 관리자. 확인 중이거나 다른 곳으로 보내는 중이면 null. */
  me: User | null;
  /** 서버에 닿지 못하는 등 401 이 아닌 이유로 확인하지 못했을 때의 문구. */
  error: string | null;
  retry: () => void;
  logout: () => void;
}

export function useAdminSession(): AdminSession {
  const navigate = useNavigate();
  const [me, setMe] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  // 바뀌면 다시 확인한다(다른 탭 로그인 · 다시 시도).
  const [checkKey, setCheckKey] = useState(0);

  useEffect(() => {
    const requestedToken = getToken();

    if (!requestedToken) {
      navigate("/login", { replace: true });
      return;
    }

    let cancelled = false;

    // 응답을 기다리는 사이에 다른 탭에서 로그아웃하거나 다른 계정으로 로그인하면 토큰이 바뀐다.
    // 그 응답은 옛 계정의 것이라 그대로 따르면 잘못된 화면으로 간다(예: 옛 상담사 응답으로 /dashboard 로 가 버려
    // 새로 들어온 관리자가 관리자 화면을 못 봄). storage 이벤트보다 응답이 먼저 오면 생기므로, 토큰을 직접 비교해
    // 다르면 그 응답은 버리고 지금 토큰으로 다시 확인한다.
    const tokenChanged = () => getToken() !== requestedToken;
    const recheck = () => {
      setMe(null);
      setCheckKey((key) => key + 1);
    };

    setError(null);

    auth
      .me()
      .then((user) => {
        if (cancelled) return;

        if (tokenChanged()) {
          recheck();
        } else if (user.role !== "ADMIN") {
          setMe(null);
          navigate("/dashboard", { replace: true });
        } else if (user.must_change_password) {
          // 임시 비밀번호면 /auth/me · /auth/me/password 말고는 모두 403 이다. 상담사 앱의 내 정보 화면에서 바꾼다.
          // 바꾸면 다시 로그인하게 되고, 그때 로그인 화면이 /admin 으로 보낸다.
          setMe(null);
          navigate("/profile", { replace: true, state: { mustChangePassword: true } });
        } else {
          setMe(user);
        }
      })
      .catch((caught) => {
        if (cancelled) return;

        // 옛 토큰의 실패다(늦게 온 401 은 client 도 무시한다). 지금 토큰으로 다시 확인한다.
        if (tokenChanged()) {
          recheck();
          return;
        }

        // 401 은 client 가 토큰을 지우고 UNAUTHORIZED_EVENT 를 보낸다(아래에서 /login 으로).
        if (caught instanceof ApiError && caught.isUnauthorized) return;

        setMe(null);
        setError(caught instanceof ApiError ? caught.message : "로그인 상태를 확인하지 못했습니다.");
      });

    return () => {
      cancelled = true;
    };
  }, [navigate, checkKey]);

  useEffect(() => {
    function onUnauthorized() {
      setMe(null);
      navigate("/login", { replace: true });
    }

    function onPasswordChangeRequired() {
      setMe(null);
      navigate("/profile", { replace: true, state: { mustChangePassword: true } });
    }

    function onStorage(event: StorageEvent) {
      if (event.key !== null && event.key !== TOKEN_KEY && event.key !== SESSION_INFO_KEY) return;

      if (!getToken()) {
        onUnauthorized();
      } else if (event.key !== SESSION_INFO_KEY) {
        // 토큰이 바뀌었다 — 다른 탭에서 다른 계정(또는 같은 계정)으로 다시 로그인했다. 역할부터 다시 본다.
        setMe(null);
        setCheckKey((key) => key + 1);
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
  }, [navigate]);

  const retry = useCallback(() => setCheckKey((key) => key + 1), []);

  const logout = useCallback(() => {
    clearSession();
    navigate("/login", { replace: true });
  }, [navigate]);

  return { me, error, retry, logout };
}
