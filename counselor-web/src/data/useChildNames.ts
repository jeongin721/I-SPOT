// 별칭으로 받은 줄(긴급 알림 띠 · 알림 종)의 이름 칸을 아동 실명으로 바꾼다(2026-11-26, 민규 #207 리뷰).
//
//  - 띠는 30초마다 다시 불러오므로 그 목록에 실명을 싣지 않는다. 대신 처음 보는 사례만 GET /cases/child-names 로 한 번 묻고
//    이 탭에 기억한다 — 서버 열람 기록은 처음 물을 때 1줄(다시 불러올 때마다 쌓이지 않는다). 새로 고치면 다시 묻는다.
//  - 실명이 없거나 볼 수 없는 사례 · 실패는 '없음' 으로 기억해 같은 탭에서 다시 묻지 않고, 화면은 별칭을 쓴다.
//  - 계정마다 따로 기억한다(다른 계정으로 로그인하면 앞 계정 이름을 쓰지 않는다).
//  - 로그인이 끝나면(로그아웃 · 토큰 만료, 다른 탭의 로그아웃) 기억한 실명을 모두 버린다. 그 사이에 온 답도 버린다(민규 11/26 리뷰).
//  - 서버는 한 번에 50개까지 받으므로 50개씩 나눠 묻고, 실제로 물은 사례만 기억한다(민규 11/26 리뷰).
import { useEffect, useState } from "react";
import { getToken, UNAUTHORIZED_EVENT } from "../api/client";
import { CHILD_NAMES_MAX, cases } from "../api/endpoints";

const known = new Map<string, Map<string, string | null>>();
const asking = new Set<string>();
// 같은 사례를 다른 화면 조각이 먼저 물었으면, 답이 왔을 때 기다리던 조각도 다시 그린다.
const listeners = new Set<() => void>();
// 기억한 실명을 받을 때의 토큰. 토큰이 바뀌었으면(로그아웃 · 다시 로그인) 기억을 버린다.
let knownToken: string | null = null;

function forgetAll(): void {
  known.clear();
  asking.clear();
  knownToken = null;
}

if (typeof window !== "undefined") {
  window.addEventListener(UNAUTHORIZED_EVENT, forgetAll);
  // 다른 탭의 로그아웃은 토큰 칸이 지워진 것으로 안다.
  window.addEventListener("storage", () => {
    if (knownToken !== null && getToken() !== knownToken) forgetAll();
  });
}

function sameLogin(): boolean {
  const token = getToken();

  if (token !== knownToken) {
    forgetAll();
    knownToken = token;
  }

  return token !== null;
}

function memo(userId: string): Map<string, string | null> {
  let names = known.get(userId);

  if (!names) {
    names = new Map();
    known.set(userId, names);
  }

  return names;
}

/** 사례 ID → 실명 찾기. 아직 모르거나 실명이 없으면 fallback(별칭). */
export function useChildNames(
  userId: string | null | undefined,
  caseIds: ReadonlyArray<string | null | undefined>,
): (caseId: string | null | undefined, fallback: string) => string {
  const [, setVersion] = useState(0);

  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    listeners.add(bump);
    return () => {
      listeners.delete(bump);
    };
  }, []);
  const ids = userId ? Array.from(new Set(caseIds.filter((id): id is string => Boolean(id)))).sort() : [];
  const idsKey = ids.join(",");

  useEffect(() => {
    if (!userId || !idsKey || !sameLogin()) return undefined;

    const token = knownToken;
    const names = memo(userId);
    const missing = idsKey.split(",").filter((id) => !names.has(id) && !asking.has(`${userId}:${id}`));

    if (!missing.length) return undefined;

    missing.forEach((id) => asking.add(`${userId}:${id}`));

    for (let start = 0; start < missing.length; start += CHILD_NAMES_MAX) {
      const chunk = missing.slice(start, start + CHILD_NAMES_MAX);
      cases
        .childNames(chunk)
        .catch(() => ({}) as Record<string, string>)
        .then((found) => {
          // 묻는 사이 로그인이 끝났거나 바뀌었으면 답을 버린다(새 기억은 forgetAll 로 이미 비었다).
          if (getToken() !== token || known.get(userId) !== names) return;
          chunk.forEach((id) => {
            names.set(id, found[id]?.trim() || null);
            asking.delete(`${userId}:${id}`);
          });
          listeners.forEach((bump) => bump());
        });
    }

    return undefined;
  }, [userId, idsKey]);

  const current = userId && getToken() !== null && getToken() === knownToken ? known.get(userId) : undefined;
  return (caseId, fallback) => (caseId ? current?.get(caseId) : null) || fallback;
}
