// 회원가입 팝업의 서버 요청 훅(API_CONTRACT 3절 '회원가입'). 단계 · 칸 값은 화면(src/data/screens/signup.ts)이 들고,
// 이 훅은 설정 조회 · 인증번호 보내기 · 확인 · 대기 신청만 한다.
//
// - 신청만으로는 계정이 생기지 않는다. 관리자가 승인해야 로그인할 수 있다.
// - 확인 토큰은 저장하지 않고 이 훅의 ref(메모리)에만 둔다. 팝업을 닫거나 처음부터 다시 하면 버린다.
// - 오류 문구는 Backend 문구를 그대로 쓴다. 횟수 제한(429)은 남은 초, 틀린 번호(422)는 남은 횟수를 함께 넘긴다.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { signup } from "../api/endpoints";
import { passwordReasons } from "./usePasswordChange";

const FALLBACK = "요청 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.";

/** 실패 결과. restart 면 토큰 · 번호를 더 쓸 수 없어 이메일 단계부터 다시 한다. */
export interface SignupFailure {
  ok: false;
  message: string;
  /** 429 RATE_LIMITED 의 남은 초. */
  retryAfter?: number;
  /** 422 VERIFICATION_CODE_MISMATCH 의 남은 횟수(4 → 0). */
  remainingAttempts?: number;
  /** 422 WEAK_PASSWORD 의 사유 문장. */
  reasons?: string[];
  restart?: boolean;
}

export type SignupResult<T> = ({ ok: true } & T) | SignupFailure;

export interface SignupState {
  /** 설정을 읽기 전 · 읽지 못했으면 false(단추를 숨긴다). */
  enabled: boolean;
  allowedDomains: string[];
  busy: boolean;
  sendCode: (email: string) => Promise<SignupResult<{ resendAfter: number; expiresIn: number }>>;
  verify: (email: string, code: string) => Promise<SignupResult<object>>;
  submit: (name: string, password: string) => Promise<SignupResult<object>>;
  /** 받은 토큰을 버린다(팝업 닫기 · 처음부터 다시). */
  reset: () => void;
}

// DUPLICATE_RESOURCE 는 이미 계정이나 대기 신청이 있는 이메일이다. 이때 토큰은 쓰여 같은 토큰으로 다시 낼 수 없다.
const RESTART_CODES = new Set(["VERIFICATION_CODE_EXPIRED", "SIGNUP_TOKEN_INVALID", "DUPLICATE_RESOURCE"]);

/** 422 VALIDATION_ERROR 의 이메일 사유는 이 고정 문구로 시작한다(한글 아이디 등). 공통 문구 대신 이것을 보여 준다. */
const EMAIL_FORMAT_MESSAGE = "이메일 형식이 올바르지 않습니다. 영문 주소만 받습니다.";

function toFailure(caught: unknown): SignupFailure {
  if (!(caught instanceof ApiError)) return { ok: false, message: FALLBACK };

  const details = (caught.details ?? {}) as {
    retry_after_seconds?: unknown;
    remaining_attempts?: unknown;
    fields?: { reason?: unknown }[];
  };
  const emailBad =
    caught.code === "VALIDATION_ERROR" &&
    Array.isArray(details.fields) &&
    details.fields.some((field) => String(field?.reason ?? "").includes(EMAIL_FORMAT_MESSAGE));
  const failure: SignupFailure = { ok: false, message: emailBad ? EMAIL_FORMAT_MESSAGE : caught.message || FALLBACK };

  if (typeof details.retry_after_seconds === "number") failure.retryAfter = details.retry_after_seconds;
  if (typeof details.remaining_attempts === "number") failure.remainingAttempts = details.remaining_attempts;
  if (caught.code === "WEAK_PASSWORD") failure.reasons = passwordReasons(caught);
  if (RESTART_CODES.has(caught.code)) failure.restart = true;

  return failure;
}

export function useSignup(): SignupState {
  const [enabled, setEnabled] = useState(false);
  const [allowedDomains, setAllowedDomains] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const token = useRef<string | null>(null);
  // 두 번 눌러도 요청은 하나만 보낸다.
  const inFlight = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    signup
      .settings()
      .then((settings) => {
        if (!mounted.current) return;
        setEnabled(settings.enabled === true);
        setAllowedDomains(Array.isArray(settings.allowed_email_domains) ? settings.allowed_email_domains : []);
      })
      .catch(() => {
        // 설정을 못 읽으면(옛 Backend · 연결 끊김) 단추를 숨긴 채 둔다.
      });

    return () => {
      mounted.current = false;
      token.current = null;
    };
  }, []);

  const run = useCallback(async <T,>(call: () => Promise<T>): Promise<SignupResult<T>> => {
    if (inFlight.current) return { ok: false, message: "" };

    inFlight.current = true;
    setBusy(true);

    try {
      return { ok: true, ...(await call()) };
    } catch (caught) {
      return toFailure(caught);
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }, []);

  const sendCode = useCallback(
    (email: string) =>
      run(async () => {
        const sent = await signup.sendCode(email.trim());

        return { resendAfter: sent.resend_after_seconds, expiresIn: sent.expires_in_seconds };
      }),
    [run],
  );

  const verify = useCallback(
    (email: string, code: string) =>
      run(async () => {
        const verified = await signup.verifyCode(email.trim(), code);

        token.current = verified.verification_token;

        return {};
      }),
    [run],
  );

  const submit = useCallback(
    async (name: string, password: string): Promise<SignupResult<object>> => {
      const current = token.current;

      if (!current) {
        return { ok: false, message: "인증 시간이 지났습니다. 이메일 인증부터 다시 해 주세요.", restart: true };
      }

      const result = await run(async () => {
        await signup.submit({ verification_token: current, name: name.trim(), password });

        return {};
      });

      // 신청했거나 토큰을 더 쓸 수 없으면 버린다. 약한 비밀번호는 같은 토큰으로 다시 낸다.
      if (result.ok || result.restart) token.current = null;

      return result;
    },
    [run],
  );

  const reset = useCallback(() => {
    token.current = null;
  }, []);

  return { enabled, allowedDomains, busy, sendCode, verify, submit, reset };
}
