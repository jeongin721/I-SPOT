// 다음 상담 체크리스트 훅(GET · POST /sessions/{id}/followup-suggestions, API_CONTRACT 18절).
//
// Backend 가 AI 분석을 저장한 직후 같은 백그라운드 작업에서 만든다. 만드는 중(PROCESSING)이면 되풀이 조회하고,
// AI 분석이 진행 중인 동안에도(watch) 되풀이 조회해 분석이 끝나자마자 생기는 행을 받는다. 분석이 끝난 그리기에서 한 번 더 받는다.
// 결과는 AI 초안(공식 근거를 찾아 쓴 확인 사항 · 질문)이며 판정이 아니다. 상담원이 확인 · 승인한다.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { followupSuggestions as followupApi } from "../api/endpoints";
import type { AnalysisStatus, FollowupSuggestion, FollowupSuggestionResult } from "../api/types";
import { toDateTime } from "./time";
import { errorMessage, usePolling, useRemote } from "./useRemote";

export const FOLLOWUP_STATUS_LABELS: Record<AnalysisStatus, string> = {
  PROCESSING: "만드는 중",
  COMPLETED: "완료",
  FAILED: "실패",
};

export interface FollowupView {
  status: AnalysisStatus;
  statusLabel: string;
  /** 완료됐을 때만 있다. 칸 모양은 API_CONTRACT 18절 그대로다. */
  result: FollowupSuggestionResult | null;
  /** 실패 문구(서버 고정 문구). */
  errorMessage: string | null;
  provider: string | null;
  createdAt: string;
  completedAt: string;
}

export interface FollowupSuggestionsOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
  /** 행이 곧 생길 수 있어 되풀이 조회할 때(AI 분석 중). 이 값이 true → false 로 바뀌면 한 번 더 받는다. */
  watch?: boolean;
}

export interface FollowupSuggestionsState {
  /** 가장 최근 행. 아직 만들기 전이면 null. */
  view: FollowupView | null;
  processing: boolean;
  submitting: boolean;
  loading: boolean;
  error: string | null;
  /** 다시 만들기. 대상이 바뀌어 반영하지 못했거나 실패하면 false. */
  run: () => Promise<boolean>;
  reload: () => void;
}

export function useFollowupSuggestions(
  sessionId: string | null | undefined,
  { enabled = true, watch = false }: FollowupSuggestionsOptions = {},
): FollowupSuggestionsState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<FollowupSuggestion | null>(
    key,
    followupApi.get,
    "다음 상담 체크리스트를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  );
  const [submitting, setSubmitting] = useState(false);
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setSubmitting(false);
  }

  const row = remote.data;
  const processing = row?.status === "PROCESSING";

  usePolling(processing || (watch && key !== null), remote.refresh, remote.settled);

  // AI 분석이 끝난 그리기에서 한 번 더 받는다(마지막 되풀이 조회가 행이 생기기 직전이었을 수 있다).
  const watched = useRef(watch);
  const refresh = remote.refresh;
  useEffect(() => {
    if (watched.current && !watch) refresh();
    watched.current = watch;
  }, [watch, refresh]);

  const run = useCallback(async () => {
    const ticket = remote.capture();

    if (!ticket || ticket.key !== key || inFlight.current) return false;

    inFlight.current = true;
    setSubmitting(true);
    setActionError(null);

    try {
      const started = await followupApi.run(ticket.key);

      return remote.setData(ticket, started);
    } catch (caught) {
      if (!remote.isCurrent(ticket)) return false;

      if (!(caught instanceof ApiError && caught.isUnauthorized)) {
        setActionError(errorMessage(caught, "다음 상담 체크리스트를 만들지 못했습니다. 잠시 후 다시 시도해 주세요."));
      }

      remote.refresh();

      return false;
    } finally {
      if (remote.sameGeneration(ticket)) {
        inFlight.current = false;
        setSubmitting(false);
      }
    }
  }, [key, remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.refresh]);

  return {
    view: row
      ? {
          status: row.status,
          statusLabel: FOLLOWUP_STATUS_LABELS[row.status],
          result: row.status === "COMPLETED" ? row.result : null,
          errorMessage: row.error?.message ?? null,
          provider: row.provider,
          createdAt: toDateTime(row.created_at),
          completedAt: toDateTime(row.completed_at),
        }
      : null,
    processing,
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    run,
    reload: remote.reload,
  };
}
