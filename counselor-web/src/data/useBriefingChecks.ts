// 상담 전 브리핑 '확인할 사항' 체크(상담 중 확인한 것 표시) — 서버 값(API_CONTRACT 26절, 2026-11-11).
// 웹 사례 상세 브리핑과 상담사 앱 · 브리핑이 같이 쓴다.
//
//  - 누르면 화면을 먼저 바꾸고 서버에 한 줄씩 보낸다(지금 보이는 문장 목록도 같이 — 서버가 목록을 고쳐 사라진 옛 문장의 체크를
//    지운다, 민규 #176 1). 서버가 돌려준 전체로 맞춘다(다른 기기에서 켠 것도 그때 보인다).
//  - 연결이 없거나 서버가 잠시 답하지 않으면(0 · 5xx) 체크는 그대로 두고 이 기기에 맡겨 둔다('ispot-brief-pending:<회차 ID>').
//    연결이 돌아오면(online) · 다시 열면 보낸다 — 방문 상담 중 연결이 약해도 쓸 수 있게(민규 #176 3). 4xx 면 되돌리고 알린다.
//  - 예전 판은 체크를 기기에만 기억했다('ispot-brief-ticks:<회차 ID>'). 처음 열 때 서버로 옮긴다 — 한 건씩, 실패한 건은 넘기고
//    (300자 넘는 문장 등 4xx 는 버리고, 연결 문제면 다음에 다시), 서버 값은 늘 화면에 넣는다(민규 #176 2).

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { briefingChecks } from "../api/endpoints";
import type { BriefingChecks } from "../api/types";
import { errorMessage } from "./useRemote";

const TEXT_MAX = 300;
const legacyKey = (sessionId: string) => `ispot-brief-ticks:${sessionId}`;
const pendingKey = (sessionId: string) => `ispot-brief-pending:${sessionId}`;

type Pending = Record<string, boolean>;

function readJson<T>(key: string, fallback: T): T {
  try {
    const value = JSON.parse(window.localStorage.getItem(key) || "null");

    return value ?? fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // 저장소를 못 쓰는 브라우저 — 이 화면에서만 기억한다.
  }
}

/** 연결 문제(다시 보내면 될 수 있음)인가. */
const transient = (caught: unknown) => !(caught instanceof ApiError) || caught.status === 0 || caught.status >= 500;

function readLegacy(sessionId: string): string[] {
  const saved = readJson<unknown>(legacyKey(sessionId), []);

  return Array.isArray(saved) ? saved.filter((text): text is string => typeof text === "string" && text.trim() !== "") : [];
}

function readPending(sessionId: string): Pending {
  const saved = readJson<unknown>(pendingKey(sessionId), {});

  return saved && typeof saved === "object" && !Array.isArray(saved) ? (saved as Pending) : {};
}

/** 서버 값 위에 맡겨 둔 바뀜을 얹는다. */
function overlay(server: string[], pending: Pending): Set<string> {
  const set = new Set(server);

  Object.entries(pending).forEach(([text, checked]) => (checked ? set.add(text) : set.delete(text)));

  return set;
}

export interface BriefingChecksState {
  ticks: Set<string>;
  toggle: (text: string) => void;
  error: string | null;
  /** 연결이 없어 이 기기에 맡겨 둔 체크가 있는가(연결되면 보낸다). */
  waiting: boolean;
}

/**
 * sessionId: 브리핑이 값을 가져온 회차(분석이 끝난 최근 회차). 없으면 아무것도 하지 않는다.
 * visible: 지금 화면에 보이는 확인 사항 문장들(서버가 사라진 옛 문장의 체크를 지우는 데 쓴다).
 */
export function useBriefingChecks(sessionId: string | null, enabled = true, visible: string[] = []): BriefingChecksState {
  const [ticks, setTicksState] = useState<Set<string>>(() => new Set());
  const [error, setError] = useState<string | null>(null);
  const [waiting, setWaiting] = useState(false);
  // 지금 표시 — 누를 때 켤지 끌지를 바로 정하려고(상태 갱신 함수는 나중에 돌 수 있다).
  const ticksRef = useRef<Set<string>>(new Set());
  const current = useRef<string | null>(sessionId);
  const visibleRef = useRef<string[]>(visible);
  const flushing = useRef(false);

  current.current = sessionId;
  visibleRef.current = visible;

  const setTicks = useCallback((next: Set<string>) => {
    ticksRef.current = next;
    setTicksState(next);
  }, []);

  /** 서버 값으로 맞춘다(맡겨 둔 바뀜은 그 위에). */
  const apply = useCallback(
    (target: string, data: BriefingChecks) => {
      if (current.current !== target) return;

      const pending = readPending(target);

      setTicks(overlay(data.checked, pending));
      setWaiting(Object.keys(pending).length > 0);
    },
    [setTicks],
  );

  const send = useCallback(
    (target: string, text: string, checked: boolean) =>
      briefingChecks.toggle(target, text, checked, visibleRef.current.length > 0 ? visibleRef.current : undefined),
    [],
  );

  /** 맡겨 둔 바뀜을 차례로 보낸다. 연결 문제면 남은 것은 다음에. */
  const flush = useCallback(
    async (target: string) => {
      if (flushing.current) return;

      flushing.current = true;
      try {
        let data: BriefingChecks | null = null;

        for (const [text, checked] of Object.entries(readPending(target))) {
          try {
            data = await send(target, text, checked);
          } catch (caught) {
            if (transient(caught)) break;
            // 받을 수 없는 값(4xx)은 버린다.
          }
          const left = readPending(target);

          delete left[text];
          writeJson(pendingKey(target), Object.keys(left).length > 0 ? left : null);
        }
        apply(target, data ?? (await briefingChecks.get(target)));
      } catch {
        // 아직 연결이 없다 — 그대로 둔다.
      } finally {
        flushing.current = false;
      }
    },
    [apply, send],
  );

  useEffect(() => {
    setTicks(new Set());
    setError(null);
    setWaiting(false);
    if (!sessionId || !enabled) return undefined;

    let live = true;
    const target = sessionId;

    // 맡겨 둔 것이 있으면 서버 값을 받기 전에도 먼저 보인다(연결이 없을 때).
    const pending = readPending(target);

    if (Object.keys(pending).length > 0) {
      setTicks(overlay([], pending));
      setWaiting(true);
    }

    (async () => {
      let data: BriefingChecks;

      try {
        data = await briefingChecks.get(target);
      } catch (caught) {
        if (live && !transient(caught)) setError(errorMessage(caught, "확인 표시를 불러오지 못했어요."));
        return;
      }

      // 예전 기기 값 옮기기 — 한 건씩, 실패는 넘기고, 서버 값은 늘 화면에.
      const legacy = readLegacy(target).filter((text) => !data.checked.includes(text.trim()));
      let keepLegacy = false;

      for (const raw of legacy) {
        const text = raw.trim();

        if (text.length > TEXT_MAX) continue;
        try {
          data = await briefingChecks.toggle(target, text, true);
        } catch (caught) {
          if (transient(caught)) {
            keepLegacy = true;
            break;
          }
        }
      }
      if (!keepLegacy) writeJson(legacyKey(target), null);
      if (live) apply(target, data);
      if (live && Object.keys(readPending(target)).length > 0) void flush(target);
    })();

    const onOnline = () => void flush(target);

    window.addEventListener("online", onOnline);

    return () => {
      live = false;
      window.removeEventListener("online", onOnline);
    };
  }, [sessionId, enabled, setTicks, apply, flush]);

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

      // 앞서 맡겨 둔 것이 있으면 순서를 지키려고 이것도 맡긴 뒤 한꺼번에 보낸다.
      if (Object.keys(readPending(target)).length > 0) {
        writeJson(pendingKey(target), { ...readPending(target), [text]: next });
        setWaiting(true);
        void flush(target);
        return;
      }

      send(target, text, next)
        .then((data) => apply(target, data))
        .catch((caught) => {
          if (current.current !== target) return;
          if (transient(caught)) {
            // 연결이 없다 — 체크는 그대로 두고 맡겨 둔다.
            writeJson(pendingKey(target), { ...readPending(target), [text]: next });
            setWaiting(true);
            return;
          }
          const back = new Set(ticksRef.current);

          if (next) back.delete(text);
          else back.add(text);
          setTicks(back);
          setError(errorMessage(caught, "확인 표시를 저장하지 못했어요."));
        });
    },
    [sessionId, setTicks, apply, flush, send],
  );

  return { ticks, toggle, error, waiting };
}
