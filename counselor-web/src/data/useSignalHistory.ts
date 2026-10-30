// 사례 단위 신호 이력 훅(GET /cases/{id}/signal-history, API_CONTRACT 4절, 2026-10-28 #99).
// 회차마다 analysis · risk-assessments 를 부르지 않고 한 번에 받는다. 회차는 전부 · 회차 번호 오름차순이고,
// 분석 전 회차도 자리가 있다(types 가 빈 배열).
//  - detected · ai_level 은 AI 제안이고, 위험도는 counselor_level(상담원 판단)만 쓴다(05_RULES §1).
//  - 이 사례의 회차가 바뀌면(분석 끝남 · 판단 저장 — sessionEvents) 다시 부른다.

import { cases } from "../api/endpoints";
import type { SignalHistory, SignalHistorySession } from "../api/types";
import { useRemote } from "./useRemote";

export interface SignalHistoryState {
  /** 회차 번호 오름차순. 아직 못 받았으면 빈 배열. */
  sessions: SignalHistorySession[];
  loaded: boolean;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useSignalHistory(
  caseId: string | null | undefined,
  { enabled = true }: { enabled?: boolean } = {},
): SignalHistoryState {
  const remote = useRemote<SignalHistory>(
    enabled && caseId ? caseId : null,
    cases.signalHistory,
    "회차별 신호 이력을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    (change, current, data) =>
      change.caseId === current || Boolean(data?.sessions.some((row) => row.session_id === change.sessionId)),
  );

  return {
    sessions: remote.data?.sessions ?? [],
    loaded: remote.data !== null,
    loading: remote.loading,
    error: remote.error,
    reload: remote.reload,
  };
}
