// 상담사 앱(폰)을 연결 없이 열어도 녹음할 수 있게 마지막으로 확인한 계정 · 담당 사례를 이 폰에 기억한다.
//
// 현장(가정방문 등)은 연결이 약하다. 연결 없이 앱을 열면 로그인 확인(GET /auth/me) · 사례 목록이 실패해 아이를 고를 수 없고
// 녹음 대기열도 누구 것인지 몰라 비어 보인다. 그래서
//  - 계정: 로그인이 확인되면 그 계정 ID 를 지금 토큰의 끝 몇 글자와 함께 둔다. 같은 토큰으로 확인이 실패(연결 없음)하면 그 ID 를 쓴다.
//    로그아웃 · 다른 계정 로그인으로 토큰이 바뀌면 맞지 않아 쓰지 않는다. 401(로그인 만료)은 원래대로 로그인 화면으로 간다.
//  - 사례: 담당 진행 중 사례의 ID · 아이 이름 · 별칭만 둔다(목록 표시용). 서버 값을 받을 때마다 바꾼다.
// 이 값은 이 폰의 localStorage 에만 있고 서버로 보내지 않는다.

import { getToken } from "../api/client";

const USER_KEY = "ispot-app-user";
const CASES_KEY = "ispot-app-cases";

export interface CachedCase {
  id: string;
  child_name?: string | null;
  child_alias: string;
}

function fingerprint(token: string | null): string | null {
  return token ? token.slice(-24) : null;
}

export function rememberAppUser(id: string): void {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify({ id, fp: fingerprint(getToken()) }));
  } catch {
    // 저장이 막힌 브라우저
  }
}

/** 지금 토큰으로 앞서 확인한 계정 ID. 없거나 토큰이 바뀌었으면 null. */
export function cachedAppUserId(): string | null {
  try {
    const saved = JSON.parse(localStorage.getItem(USER_KEY) || "null") as { id?: string; fp?: string } | null;
    const fp = fingerprint(getToken());

    return saved?.id && fp && saved.fp === fp ? saved.id : null;
  } catch {
    return null;
  }
}

export function rememberCases(userId: string, rows: CachedCase[]): void {
  try {
    const slim = rows.map((row) => ({ id: row.id, child_name: row.child_name ?? null, child_alias: row.child_alias }));

    localStorage.setItem(CASES_KEY, JSON.stringify({ userId, rows: slim }));
  } catch {
    // 저장이 막힌 브라우저
  }
}

export function cachedCases(userId: string): CachedCase[] | null {
  try {
    const saved = JSON.parse(localStorage.getItem(CASES_KEY) || "null") as { userId?: string; rows?: CachedCase[] } | null;

    return saved?.userId === userId && Array.isArray(saved.rows) ? saved.rows : null;
  } catch {
    return null;
  }
}

/**
 * 예전 판(11/10 8bc057e — 메모를 폰에만 저장하던 판)이 남긴 메모를 지운다(민규 #170 3). 아이 이름과 메모 본문이 들어 있다.
 * 메모는 이제 서버에 저장하므로 폰에 둘 까닭이 없다. 앱을 열 때 한 번 부른다.
 */
export function purgeLegacyMemos(): void {
  try {
    const keys: string[] = [];

    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);

      if (key && key.startsWith("ispot-app-memo:")) keys.push(key);
    }
    keys.forEach((key) => localStorage.removeItem(key));
  } catch {
    // 저장소를 못 읽는 브라우저
  }
}
