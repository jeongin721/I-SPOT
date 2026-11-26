// 별칭으로 받은 줄(긴급 알림 띠 · 알림 종)의 이름 칸을 아동 실명으로 바꾼다(2026-11-26, 민규 #207 리뷰).
//
//  - 띠는 30초마다 다시 불러오므로 그 목록에 실명을 싣지 않는다. 대신 처음 보는 사례만 GET /cases/child-names 로 한 번 묻고
//    이 탭에 기억한다 — 서버 열람 기록은 처음 물을 때 1줄(다시 불러올 때마다 쌓이지 않는다). 새로 고치면 다시 묻는다.
//  - 실명이 없거나 볼 수 없는 사례 · 실패는 '없음' 으로 기억해 같은 탭에서 다시 묻지 않고, 화면은 별칭을 쓴다.
//  - 계정마다 따로 기억한다(다른 계정으로 로그인하면 앞 계정 이름을 쓰지 않는다).
import { useEffect, useState } from "react";
import { cases } from "../api/endpoints";

const known = new Map<string, Map<string, string | null>>();
const asking = new Set<string>();
// 같은 사례를 다른 화면 조각이 먼저 물었으면, 답이 왔을 때 기다리던 조각도 다시 그린다.
const listeners = new Set<() => void>();

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
    if (!userId || !idsKey) return undefined;

    const names = memo(userId);
    const missing = idsKey.split(",").filter((id) => !names.has(id) && !asking.has(`${userId}:${id}`));

    if (!missing.length) return undefined;

    missing.forEach((id) => asking.add(`${userId}:${id}`));
    cases
      .childNames(missing)
      .catch(() => ({}) as Record<string, string>)
      .then((found) => {
        missing.forEach((id) => {
          names.set(id, found[id]?.trim() || null);
          asking.delete(`${userId}:${id}`);
        });
        listeners.forEach((bump) => bump());
      });

    return undefined;
  }, [userId, idsKey]);

  return (caseId, fallback) => (userId && caseId ? known.get(userId)?.get(caseId) : null) || fallback;
}
