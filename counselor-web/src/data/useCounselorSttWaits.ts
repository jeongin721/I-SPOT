// 관리자 홈 · 상담원별 업무량의 'STT 검수 대기'(2026-11-25).
// 상담원마다 GET /tasks/summary?counselor_id= 를 한 번씩 불러 원문 검수(REVIEW_TRANSCRIPT) 업무 수를 센다 — 서버가 이미 상담원별로
// 거르는 요약이 있어 새 API 없이 센다. 상담원 수만큼 부르므로 동시에 4개까지만 보낸다(mapLimited).
// 관리자일 때만 부른다(adminKey). 못 받으면 칸은 '—' 이다.

import { tasks } from "../api/endpoints";
import { adminKey, type AdminAccess } from "./adminAccess";
import { mapLimited } from "./mapLimited";
import { useRemote, type RemoteState } from "./useRemote";

const CONCURRENCY = 4;

export function useCounselorSttWaits(access: AdminAccess, counselorIds: string[]): RemoteState<Map<string, number>> {
  const ids = [...counselorIds].sort();
  const key = ids.length ? adminKey(access, true, `stt-waits:${ids.join(",")}`) : null;

  return useRemote<Map<string, number>>(
    key,
    async () => {
      const counts = await mapLimited(ids, CONCURRENCY, async (id) => {
        const summary = await tasks.summary({ counselor_id: id });
        return [id, summary.by_type?.REVIEW_TRANSCRIPT ?? 0] as const;
      });
      return new Map(counts);
    },
    "STT 검수 대기를 세지 못했습니다.",
    () => false,
  );
}
