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

const TOKEN_KEY = "ispot_access_token";

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
