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

const WEEK = ["일", "월", "화", "수", "목", "금", "토"];

/**
 * 이 사례의 다음 상담 일시(일정의 상담 일정 중 지금 뒤로 가장 가까운 것, 11/20 점검).
 * 사례 머리 '다음 상담' · 상담 전 브리핑 '상담 일시' 에 쓴다. 없거나 못 받았으면 null.
 */
export function useNextConsult(
  caseId: string | null | undefined,
  { enabled = true }: { enabled?: boolean } = {},
): string | null {
  const remote = useRemote<{ items: ScheduleEvent[] }>(
    enabled && caseId ? `next:${caseId}` : null,
    () => schedule.list({ from: iso(Date.now()), to: iso(Date.now() + 180 * DAY) }),
    "일정을 불러오지 못했습니다.",
    () => false,
  );
  const items = remote.data?.items ?? [];
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const hm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const next = items
    .filter((event) => event.case_id === caseId && event.kind === "CONSULT")
    .filter((event) => event.date > today || (event.date === today && (event.time === null || event.time >= hm)))
    .sort((a, b) => (a.date + (a.time ?? "")).localeCompare(b.date + (b.time ?? "")))[0];
  if (!next) return null;
  const [y, m, d] = next.date.split("-").map(Number);
  const day = WEEK[new Date(y, m - 1, d).getDay()];
  return `${m}/${d}(${day})${next.time ? ` ${next.time}` : ""}`;
}
