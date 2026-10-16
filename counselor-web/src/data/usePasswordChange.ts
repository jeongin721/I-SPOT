// 본인 비밀번호 변경 훅(POST /auth/me/password). 임시 비밀번호 변경 단계와 설정 화면이 함께 쓴다.
//
// 성공하면 Backend 가 그 계정의 토큰을 모두 끊는다(API_CONTRACT 3절). 그래서 성공하면 바로 로그아웃하고
// "새 비밀번호로 다시 로그인" 문구를 로그인 화면에 남긴다. 화면은 로그아웃 상태(useAuthSession)를 보고 움직이면 된다.
//
// 오류는 Backend 문구를 그대로 쓴다. 422 WEAK_PASSWORD 는 사유가 details.reasons 에 문장 배열로 온다.
// 현재 비밀번호를 정해진 횟수(기본 5번)만큼 틀리면 서버가 토큰을 끊는다(401 — client 가 로그아웃시키고 이유를 남긴다).

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, getToken, signOut } from "../api/client";
import { auth } from "../api/endpoints";

export { PASSWORD_RULE_TEXT } from "../api/types";

export const PASSWORD_CHANGED_MESSAGE = "비밀번호를 바꿨습니다. 새 비밀번호로 다시 로그인해 주세요.";

export interface PasswordChangeInput {
  currentPassword: string;
  newPassword: string;
  /** 새 비밀번호 확인 칸. newPassword 와 다르면 서버에 보내지 않는다. */
  confirmPassword: string;
}

export interface PasswordChangeState {
  submitting: boolean;
  /** 보여 줄 오류 문장들. 없으면 빈 배열. */
  errors: string[];
  /** 성공하면 true. 이미 로그아웃된 뒤다. */
  change: (input: PasswordChangeInput) => Promise<boolean>;
  clearErrors: () => void;
}

/** WEAK_PASSWORD 는 details.reasons 에 사유 문장 배열이 온다. */
function passwordReasons(caught: ApiError): string[] {
  const details = caught.details as { reasons?: unknown } | undefined;

  return Array.isArray(details?.reasons)
    ? details.reasons.filter((reason): reason is string => typeof reason === "string")
    : [];
}

export function usePasswordChange(): PasswordChangeState {
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const inFlight = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  const change = useCallback(async ({ currentPassword, newPassword, confirmPassword }: PasswordChangeInput) => {
    if (inFlight.current) return false;

    if (!currentPassword || !newPassword) {
      setErrors(["현재 비밀번호와 새 비밀번호를 모두 입력해 주세요."]);
      return false;
    }

    if (newPassword !== confirmPassword) {
      setErrors(["새 비밀번호와 확인 칸이 다릅니다."]);
      return false;
    }

    inFlight.current = true;
    setSubmitting(true);
    setErrors([]);

    // 요청할 때의 토큰. 응답을 기다리는 사이 다른 탭에서 다른 계정으로 로그인하면 토큰이 바뀐다.
    const requestedToken = getToken();

    try {
      await auth.changePassword({ current_password: currentPassword, new_password: newPassword });

      // 그사이 토큰이 바뀌었으면(다른 탭에서 같은 계정 · 다른 계정으로 다시 로그인) 그 새 로그인은 그대로 두고,
      // 이 응답을 지금 화면의 성공으로 돌려주지 않는다 — 돌려주면 화면이 새 로그인에서 치던 칸을 비운다.
      if (getToken() !== requestedToken) return false;

      // 토큰이 이미 끊겼으므로 이 탭과 다른 탭 모두 로그아웃한다.
      signOut(PASSWORD_CHANGED_MESSAGE);

      return true;
    } catch (caught) {
      if (!mounted.current) return false;

      // 그사이 다른 탭에서 다시 로그인했으면 앞 계정의 실패다. 지금 계정의 화면에 오류를 띄우지 않는다.
      if (getToken() !== requestedToken) return false;

      if (caught instanceof ApiError) {
        // 401 은 로그인이 끝난 것이다. client 가 로그아웃시키고 이유를 로그인 화면에 남겼다.
        if (caught.isUnauthorized) return false;

        const reasons = passwordReasons(caught);
        const messages = reasons.length > 0 ? reasons : [caught.message];

        // 남은 횟수는 서버가 주지 않는다. 끊기기 전에 미리 알린다.
        if (caught.code === "INVALID_CURRENT_PASSWORD") {
          messages.push("현재 비밀번호를 계속 틀리면(기본 5번) 보안을 위해 로그아웃됩니다.");
        }

        setErrors(messages);
      } else {
        setErrors(["비밀번호를 바꾸지 못했습니다. 잠시 후 다시 시도해 주세요."]);
      }

      return false;
    } finally {
      inFlight.current = false;
      if (mounted.current) setSubmitting(false);
    }
  }, []);

  const clearErrors = useCallback(() => setErrors([]), []);

  return { submitting, errors, change, clearErrors };
}
