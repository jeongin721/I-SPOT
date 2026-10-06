// Backend 호출 창구.
//
// 화면 코드는 fetch 를 직접 쓰지 않고 반드시 이 파일을 거친다.
// 토큰 부착 · 응답 봉투(data/error) 해제 · 오류 형식 통일을 한곳에서 처리하기 위해서다.

import type { DataResponse, ErrorResponse } from "./types";

/**
 * 개발 중에는 비워두면 vite proxy 가 /api 를 localhost:8000 으로 넘긴다.
 * 배포 시에는 .env 에 VITE_API_BASE_URL 을 넣는다.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

const API_PREFIX = "/api/v1";

/** localStorage 의 토큰 칸. 다른 탭의 로그아웃 · 로그인을 알아채는 데도 쓴다(AppLayout 의 storage 이벤트). */
export const TOKEN_KEY = "ispot_access_token";

/** 로그인 요청 경로. 이 요청의 401 은 비밀번호가 틀린 것이라 로그인 만료로 보지 않는다. */
const LOGIN_PATH = "/auth/login";

// =========================================================
// 토큰 보관
// =========================================================

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    // 사생활 보호 모드 등에서 localStorage 접근이 막힐 수 있다.
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // 저장에 실패해도 이번 세션 동안의 호출은 진행되게 둔다.
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // 무시
  }
}

/**
 * 토큰이 만료 · 폐기되어 다시 로그인해야 할 때 window 에 보내는 이벤트.
 * AppLayout 이 받아서 로그인 화면으로 보낸다.
 */
export const UNAUTHORIZED_EVENT = "ispot:unauthorized";

/**
 * 임시 비밀번호로 로그인해 비밀번호를 바꿔야 할 때(403 PASSWORD_CHANGE_REQUIRED) window 에 보내는 이벤트.
 * AppLayout 이 받아서 내 정보(비밀번호 변경) 화면으로 보낸다. 그 화면이 부르는 GET /auth/me 와
 * POST /auth/me/password 는 Backend 가 열어 두어(API_CONTRACT 3절) 다시 보내지는 일이 없다.
 */
export const PASSWORD_CHANGE_REQUIRED_EVENT = "ispot:password-change-required";

/** 로그인 화면이 따로 저장해 두는 이름 · 역할. 토큰이 끊기면 함께 지운다. */
export const SESSION_INFO_KEY = "ispot_auth";

/** 로그인 정보를 모두 지운다. 로그아웃과 토큰 만료가 같은 길을 쓴다. */
export function clearSession(): void {
  clearToken();

  try {
    localStorage.removeItem(SESSION_INFO_KEY);
  } catch {
    // 무시
  }
}

/**
 * 토큰이 끊겨 로그인 화면으로 보낼 때 그 이유(서버 문구)를 넘기는 sessionStorage 칸.
 * 예: 현재 비밀번호를 여러 번 틀려 끊긴 경우. 로그인 화면이 처음 그릴 때 보여 주고 지운다.
 */
export const LOGOUT_REASON_KEY = "ispot_logout_reason";

/** 로그인 화면이 보여 줄 로그아웃 이유. 없으면 빈 문자열. 읽기만 한다(지우는 것은 clearLogoutReason). */
export function readLogoutReason(): string {
  try {
    return sessionStorage.getItem(LOGOUT_REASON_KEY) ?? "";
  } catch {
    return "";
  }
}

export function clearLogoutReason(): void {
  try {
    sessionStorage.removeItem(LOGOUT_REASON_KEY);
  } catch {
    // 무시
  }
}

/**
 * 로그인 정보를 지우고 AppLayout 에 알린다. reason 이 있으면 로그인 화면이 보여 주도록 남긴다.
 * 이벤트의 detail.message 에도 같은 문구를 싣는다.
 */
function notifyUnauthorized(reason?: string): void {
  clearSession();

  if (reason) {
    try {
      sessionStorage.setItem(LOGOUT_REASON_KEY, reason);
    } catch {
      // 저장하지 못하면 이유 없이 로그인 화면으로 간다.
    }
  }

  window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT, { detail: { message: reason ?? null } }));
}

// =========================================================
// 오류
// =========================================================

/**
 * Backend 가 돌려준 오류를 그대로 담는다.
 * code 는 backend/app/core/errors.py 의 ErrorCode 값이다.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: unknown;

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }

  /** 로그인이 필요하거나 만료된 상태인가. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  /** 권한이 없거나 남의 자료인가. */
  get isForbidden(): boolean {
    return this.status === 403 || this.status === 404;
  }
}

// =========================================================
// 요청
// =========================================================

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON 으로 보낼 본문. FormData 를 보낼 때는 body 를 쓴다. */
  json?: unknown;
  /** 파일 업로드용. json 과 함께 쓰지 않는다. */
  body?: FormData;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = `${BASE_URL}${API_PREFIX}${path}`;

  if (!query) return url;

  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.append(key, String(value));
  }

  const qs = params.toString();

  return qs ? `${url}?${qs}` : url;
}

/**
 * Backend 를 호출하고 data 안의 값만 돌려준다.
 * 실패하면 ApiError 를 던지므로 호출부는 try/catch 로 받는다.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", json, body, query, signal } = options;

  const headers: Record<string, string> = {};
  const token = getToken();

  if (token) headers.Authorization = `Bearer ${token}`;

  // FormData 는 브라우저가 boundary 를 포함한 Content-Type 을 직접 붙여야 한다.
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;

  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : body,
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;

    throw new ApiError(
      "NETWORK_ERROR",
      "서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요.",
      0,
    );
  }

  // 204 No Content — 삭제 등
  if (response.status === 204) return undefined as T;

  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    throw new ApiError(
      "INVALID_RESPONSE",
      "서버 응답을 해석할 수 없습니다.",
      response.status,
    );
  }

  if (!response.ok) {
    const failure = payload as Partial<ErrorResponse>;

    // 401 이면 만료 · 폐기다(비밀번호 변경, 강제 로그아웃 · 정지 포함). 토큰이 없어서 난 401 도 같다 —
    // 다른 탭에서 로그아웃해 이 탭의 토큰이 이미 지워진 경우다. 로그인 요청의 401(비밀번호 틀림)만 뺀다.
    // 토큰을 실어 보낸 요청이면 서버 문구(예: "현재 비밀번호를 여러 번 틀려 로그아웃했습니다.")를 로그인 화면에 넘긴다.
    // 토큰 없이 보낸 요청의 문구("Authorization 헤더가 없습니다.")는 사용자에게 뜻이 없어 넘기지 않는다.
    //
    // 단, 응답이 오기 전에 이 탭이나 다른 탭이 다시 로그인해 토큰이 바뀌었다면(요청에 실은 토큰과 지금 토큰이 다르면)
    // 늦게 도착한 옛 토큰의 401 이다. 새 토큰을 지우면 방금 로그인한 사용자가 또 로그아웃되므로 무시한다.
    if (response.status === 401 && path !== LOGIN_PATH && getToken() === token) {
      notifyUnauthorized(token ? failure.error?.message : undefined);
    }

    if (response.status === 403 && failure.error?.code === "PASSWORD_CHANGE_REQUIRED") {
      window.dispatchEvent(new Event(PASSWORD_CHANGE_REQUIRED_EVENT));
    }

    throw new ApiError(
      failure.error?.code ?? "UNKNOWN_ERROR",
      failure.error?.message ?? "요청을 처리하지 못했습니다.",
      response.status,
      failure.error?.details,
    );
  }

  return (payload as DataResponse<T>).data;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"], signal?: AbortSignal) =>
    request<T>(path, { method: "GET", query, signal }),

  post: <T>(path: string, json?: unknown) => request<T>(path, { method: "POST", json }),

  patch: <T>(path: string, json?: unknown) => request<T>(path, { method: "PATCH", json }),

  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),

  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};
