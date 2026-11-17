// 사례 하나의 일정 훅(GET /schedule/events, API_CONTRACT 20절, 2026-11-04).
// 종결보고서 '종결 상담일' 제안(일정의 종결 상담)에 쓴다. 오늘 앞뒤 약 200일(서버 상한 400일)을 받아 이 사례 일정만 남긴다.

import { schedule } from "../api/endpoints";
import type { ScheduleEvent } from "../api/types";
import { useRemote } from "./useRemote";

const DAY = 86400000;
const iso = (time: number) => new Date(time).toISOString().slice(0, 10);

export interface CaseScheduleState {
  /** 이 사례 일정(날짜순). 받기 전 · 실패면 []. */
  events: ScheduleEvent[];
  loaded: boolean;
}

export function useCaseSchedule(
  caseId: string | null | undefined,
  { enabled = true }: { enabled?: boolean } = {},
): CaseScheduleState {
  const remote = useRemote<{ items: ScheduleEvent[] }>(
    enabled && caseId ? caseId : null,
    () => schedule.list({ from: iso(Date.now() - 200 * DAY), to: iso(Date.now() + 199 * DAY) }),
    "일정을 불러오지 못했습니다.",
    () => false,
  );

  return {
    events: (remote.data?.items ?? []).filter((event) => event.case_id === caseId).sort((a, b) => a.date.localeCompare(b.date)),
    loaded: remote.data !== null,
  };
}
