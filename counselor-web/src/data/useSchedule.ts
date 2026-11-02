// 일정 훅(GET/POST/PATCH/DELETE /schedule/events, API_CONTRACT 20절, 2026-11-02).
//
// 보이는 달 앞뒤를 덮는 기간(range)의 일정과, 일정에 붙일 사례(진행 중 사례 · 별칭)를 함께 부른다.
// 쓰기(만들기 · 고치기 · 지우기)는 끝나면 조용히 다시 부른다(처리 기한 · 공유 일정까지 서버 값으로 맞춘다).
// 대상(로그인 · 기간)이 바뀌면 앞 대상의 오류 · 진행 표시를 푼다(useClosureSummary 와 같은 꼴).

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { cases, schedule } from "../api/endpoints";
import type { ScheduleEvent, ScheduleEventCreate, ScheduleEventUpdate } from "../api/types";
import type { AuthSession } from "./useAuthSession";
import { errorMessage, useRemote } from "./useRemote";

/**
 * 같은 탭의 다른 일정 훅(달력 · 알림 종 · 홈)에 '일정이 바뀌었다' 고 알리는 이벤트(민규 #131 교차검증 R4 — 달력에서 최초접수를
 * 만들거나 기한을 완료해도 열린 알림 종은 새로고침 전까지 그대로였다). 받은 훅은 조용히 다시 부른다.
 */
const SCHEDULE_CHANGED_EVENT = "ispot-schedule-changed";

/** 일정에 붙일 수 있는 사례 수(진행 중, 최근 등록순). Backend page_size 상한과 같다. */
export const SCHEDULE_CASE_LIMIT = 100;

export interface ScheduleCaseOption {
  id: string;
  alias: string;
}

export interface ScheduleData {
  events: ScheduleEvent[];
  cases: ScheduleCaseOption[];
}

export interface ScheduleState {
  data: ScheduleData | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  busy: boolean;
  actionError: string | null;
  create: (payload: ScheduleEventCreate) => Promise<ScheduleEvent | null>;
  update: (eventId: string, payload: ScheduleEventUpdate) => Promise<ScheduleEvent | null>;
  remove: (eventId: string) => Promise<boolean>;
}

async function loadSchedule(range: { from: string; to: string }, withCases: boolean): Promise<ScheduleData> {
  const [events, casePage] = await Promise.all([
    schedule.list(range),
    withCases ? cases.list({ status: "ACTIVE", page: 1, page_size: SCHEDULE_CASE_LIMIT }) : Promise.resolve(null),
  ]);

  return {
    events: events.items,
    cases: (casePage?.items ?? []).map((item) => ({ id: item.id, alias: item.child_alias.trim() || "—" })),
  };
}

/** range 는 YYYY-MM-DD 둘. withCases=false 면 사례 목록은 부르지 않는다(홈 · 알림 종). */
export function useSchedule(
  session: AuthSession,
  range: { from: string; to: string },
  { withCases = true }: { withCases?: boolean } = {},
): ScheduleState {
  const me = session.status === "signedIn" ? session.me : null;
  const key = me ? `${me.id}:schedule:${range.from}:${range.to}:${withCases ? "c" : ""}` : null;
  const remote = useRemote<ScheduleData>(
    key,
    () => loadSchedule(range, withCases),
    "일정을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  const refresh = remote.refresh;
  useEffect(() => {
    if (!key) return undefined;
    const onChanged = () => refresh();
    window.addEventListener(SCHEDULE_CHANGED_EVENT, onChanged);
    return () => window.removeEventListener(SCHEDULE_CHANGED_EVENT, onChanged);
  }, [key, refresh]);

  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setBusy(false);
  }

  const run = useCallback(
    async <T,>(call: () => Promise<T>, fallback: string): Promise<T | null> => {
      const ticket = remote.capture();

      if (!ticket || inFlight.current) return null;

      inFlight.current = true;
      setBusy(true);
      setActionError(null);

      try {
        const result = await call();
        remote.resync(ticket);
        window.dispatchEvent(new Event(SCHEDULE_CHANGED_EVENT));
        return result;
      } catch (caught) {
        if (remote.isCurrent(ticket) && !(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, fallback));
        }
        remote.resync(ticket);
        return null;
      } finally {
        if (remote.sameGeneration(ticket)) {
          inFlight.current = false;
          setBusy(false);
        }
      }
    },
    [remote.capture, remote.resync, remote.isCurrent, remote.sameGeneration],
  );

  const create = useCallback(
    (payload: ScheduleEventCreate) => run(() => schedule.create(payload), "일정을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."),
    [run],
  );
  const update = useCallback(
    (eventId: string, payload: ScheduleEventUpdate) =>
      run(() => schedule.update(eventId, payload), "일정을 고치지 못했습니다. 잠시 후 다시 시도해 주세요."),
    [run],
  );
  const remove = useCallback(
    async (eventId: string) =>
      (await run(async () => {
        await schedule.remove(eventId);
        return true;
      }, "일정을 지우지 못했습니다. 잠시 후 다시 시도해 주세요.")) === true,
    [run],
  );

  return {
    data: remote.data,
    loading: remote.loading,
    error: remote.error,
    reload: remote.reload,
    busy,
    actionError,
    create,
    update,
    remove,
  };
}
