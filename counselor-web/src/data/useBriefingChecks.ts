// 상담 전 브리핑 '확인할 사항' 체크(상담 중 확인한 것 표시) — 서버 값(API_CONTRACT 26절, 2026-11-11).
// 웹 사례 상세 브리핑과 상담사 앱 · 브리핑이 같이 쓴다. 전에는 기기마다 브라우저(localStorage 'ispot-brief-ticks:<회차 ID>')에만
// 기억했다 — 처음 열 때 그 값이 있으면 서버로 한 번 옮기고 지운다.
//
//  - 누르면 화면을 먼저 바꾸고(기다리지 않게) 서버에 한 줄씩 보낸다. 실패하면 되돌리고 안내한다.
//  - 서버가 돌려준 전체로 맞춘다(다른 기기에서 켠 것도 그때 보인다).

import { useCallback, useEffect, useRef, useState } from "react";

import { briefingChecks } from "../api/endpoints";
import { errorMessage } from "./useRemote";

const legacyKey = (sessionId: string) => `ispot-brief-ticks:${sessionId}`;

function readLegacy(sessionId: string): string[] {
  try {
    const saved = JSON.parse(window.localStorage.getItem(legacyKey(sessionId)) || "[]");

    return Array.isArray(saved) ? saved.filter((text): text is string => typeof text === "string" && text.trim() !== "") : [];
  } catch {
    return [];
  }
}

function dropLegacy(sessionId: string) {
  try {
    window.localStorage.removeItem(legacyKey(sessionId));
  } catch {
    // 저장소를 못 쓰는 브라우저
  }
}

export interface BriefingChecksState {
  ticks: Set<string>;
  toggle: (text: string) => void;
  error: string | null;
}

/** sessionId: 브리핑이 값을 가져온 회차(분석이 끝난 최근 회차). 없으면 아무것도 하지 않는다. */
export function useBriefingChecks(sessionId: string | null, enabled = true): BriefingChecksState {
  const [ticks, setTicksState] = useState<Set<string>>(() => new Set());
  // 지금 표시 — 누를 때 켤지 끌지를 바로 정하려고(상태 갱신 함수는 나중에 돌 수 있다).
  const ticksRef = useRef<Set<string>>(new Set());
  const setTicks = useCallback((next: Set<string>) => {
    ticksRef.current = next;
    setTicksState(next);
  }, []);
  const [error, setError] = useState<string | null>(null);
  const current = useRef<string | null>(sessionId);

  current.current = sessionId;

  useEffect(() => {
    setTicks(new Set());
    setError(null);
    if (!sessionId || !enabled) return undefined;

    let live = true;

    (async () => {
      try {
        let data = await briefingChecks.get(sessionId);
        const legacy = readLegacy(sessionId).filter((text) => !data.checked.includes(text));

        // 예전에 이 기기에만 기억한 체크를 서버로 옮긴다(한 번).
        for (const text of legacy) data = await briefingChecks.toggle(sessionId, text.trim(), true);
        dropLegacy(sessionId);
        if (live) setTicks(new Set(data.checked));
      } catch (caught) {
        if (live) setError(errorMessage(caught, "확인 표시를 불러오지 못했어요."));
      }
    })();

    return () => {
      live = false;
    };
  }, [sessionId, enabled, setTicks]);

  const toggle = useCallback(
    (text: string) => {
      if (!sessionId) return;

      const target = sessionId;
      const next = !ticksRef.current.has(text);
      const copy = new Set(ticksRef.current);

      if (next) copy.add(text);
      else copy.delete(text);
      setTicks(copy);
      setError(null);
      briefingChecks
        .toggle(target, text, next)
        .then((data) => {
          if (current.current === target) setTicks(new Set(data.checked));
        })
        .catch((caught) => {
          if (current.current !== target) return;
          // 되돌린다.
          const back = new Set(ticksRef.current);

          if (next) back.delete(text);
          else back.add(text);
          setTicks(back);
          setError(errorMessage(caught, "확인 표시를 저장하지 못했어요. 연결을 확인해 주세요."));
        });
    },
    [sessionId, setTicks],
  );

  return { ticks, toggle, error };
}
