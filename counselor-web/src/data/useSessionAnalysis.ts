// AI 분석 훅(POST · GET /sessions/{id}/analysis). 원문을 확정한 뒤 분석을 요청하고, 끝날 때까지 되풀이 조회한다.
//
// 분석 결과는 'AI 분석 참고정보' 다. 판정이 아니다(05_RULES §1, API_CONTRACT 8절 표현 주의).
// 상담사가 고치고 승인하는 것은 요약(useSummaryReview)이고, 여기 값은 AI 원본이다.
//
// 위험 관련 배열(risk_utterances · abuse_signals · risk_factors)은 내보내지 않는다. 항목 구조가 팀 합의 전이고
// (PROPOSAL_risk_fields.md §7) 지금은 mock · pipeline · langgraph 모두 빈 배열이다. 신호 검토 화면은
// 팀 결정(specs 대응표 'AI 신호 · 검수') 뒤에 따로 만든다.

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { analysis as analysisApi } from "../api/endpoints";
import type { AnalysisEnvelope, AnalysisStatus, SessionStatus } from "../api/types";
import { notifySessionChanged } from "./sessionEvents";
import { canRequestAnalysis, isProcessing } from "./sessionRows";
import { toDateTime } from "./time";
import { errorMessage, usePolling, useRemote } from "./useRemote";

export const ANALYSIS_STATUS_LABELS: Record<AnalysisStatus, string> = {
  PROCESSING: "AI 분석 중",
  COMPLETED: "AI 분석 완료",
  FAILED: "AI 분석 실패",
};

export interface AnalysisView {
  status: AnalysisStatus;
  statusLabel: string;
  /** AI 원본 요약. 결과가 없으면(분석 중 · 실패) 빈 문자열. */
  overview: string;
  /** AI 원본 요약 항목. */
  keyPoints: string[];
  /** AI 가 남긴 '추가 확인 필요' 같은 안내. */
  warnings: string[];
  /** 분석에 쓴 원문 버전. */
  transcriptVersion: number | null;
  provider: string | null;
  model: string | null;
  requestedAt: string;
  /** 끝난 일시. 아직이면 빈 문자열. */
  completedAt: string;
}

export interface SessionAnalysisOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface SessionAnalysisState {
  sessionStatus: SessionStatus | null;
  /** 가장 최근 분석. 요청한 적이 없으면 null. 재분석을 요청하면 이전 결과는 더 볼 수 없다(API_CONTRACT 8절). */
  analysis: AnalysisView | null;
  /** 분석 실패 문구. */
  sessionError: string | null;
  /** 분석을 (다시) 요청할 수 있는가(원문 확정 · 실패 · 결과 검수 중). */
  canRequest: boolean;
  /** 분석 중이라 되풀이 조회하고 있는가. */
  processing: boolean;
  submitting: boolean;
  loading: boolean;
  error: string | null;
  /**
   * 첫 분석 · 실패 뒤 재시도 · 재분석. 상담사가 고친 요약은 재분석이 덮어쓰지 않는다.
   * 요청한 뒤 대상이 바뀌어(다른 회차, 갔다 돌아옴, 다시 로그인, 화면을 떠남) 반영하지 못했으면 false.
   */
  run: () => Promise<boolean>;
  reload: () => void;
}

export function useSessionAnalysis(
  sessionId: string | null | undefined,
  { enabled = true }: SessionAnalysisOptions = {},
): SessionAnalysisState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<AnalysisEnvelope>(key, analysisApi.get, "AI 분석 결과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
  const [submitting, setSubmitting] = useState(false);
  // 요청 중인가. state 는 같은 순간의 두 번째 누름을 막지 못해 ref 로도 든다.
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  // 대상 세대가 바뀌면(다른 회차, 로그아웃 · 다시 로그인, 다른 회차에 갔다 돌아옴) 앞 대상의 오류를 지우고,
  // 앞 대상에서 보낸 요청이 아직 안 끝났어도 새 대상에서는 보낼 수 있게 한다(그 요청의 응답은 반영하지 않는다).
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setSubmitting(false);
  }

  const envelope = remote.data;
  const sessionStatus = envelope?.session_status ?? null;
  const processing = sessionStatus !== null && isProcessing(sessionStatus);

  usePolling(processing, remote.refresh, remote.settled);

  const run = useCallback(async () => {
    const ticket = remote.capture();

    // 이 함수를 만든 그리기 뒤에 대상이 바뀌었으면 보내지 않는다.
    if (!ticket || ticket.key !== key || inFlight.current) return false;

    inFlight.current = true;
    setSubmitting(true);
    setActionError(null);

    try {
      const requested = await analysisApi.run(ticket.key);

      // 요청 응답의 'AI 분석 중' 을 바로 반영한다. 이어지는 조회가 한 번 실패해도 되풀이 조회가 시작되게.
      // 재분석을 요청하면 이전 결과는 API 로 더 볼 수 없으므로(API_CONTRACT 8절) 이전 결과도 내린다.
      // 대상이 바뀌었으면(갔다 돌아옴, 다시 로그인) 그 뒤에 새로 받은 결과를 내리지 않는다.
      const applied = remote.setData(ticket, (current) => ({
        ...current,
        session_id: ticket.key,
        session_status: requested.session_status,
        analysis: null,
        error: null,
      }));
      // 이 훅과 같은 회차를 보는 훅(요약 · 원문 · 회차 상세)도 'AI 분석 중' 을 받아 간다.
      notifySessionChanged({ sessionId: ticket.key });

      return applied;
    } catch (caught) {
      // 대상이 바뀌었으면 오류 문구도 다시 조회도 하지 않는다.
      if (!remote.isCurrent(ticket)) return false;

      if (!(caught instanceof ApiError && caught.isUnauthorized)) {
        setActionError(errorMessage(caught, "AI 분석을 요청하지 못했습니다. 잠시 후 다시 시도해 주세요."));
      }

      // 이미 분석 중이거나(409) 상태가 어긋났을 수 있다. 최신 상태를 다시 받는다.
      remote.refresh();

      return false;
    } finally {
      // 대상 세대가 바뀌었으면 그때 이미 풀었다. 새 대상에서 보낸 요청의 표시를 끄지 않는다.
      if (remote.sameGeneration(ticket)) {
        inFlight.current = false;
        setSubmitting(false);
      }
    }
  }, [key, remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.refresh]);

  const source = envelope?.analysis ?? null;

  return {
    sessionStatus,
    analysis: source
      ? {
          status: source.status,
          statusLabel: ANALYSIS_STATUS_LABELS[source.status],
          overview: source.result?.summary.overview ?? "",
          keyPoints: source.result?.summary.key_points ?? [],
          warnings: source.result?.warnings ?? [],
          transcriptVersion: source.transcript_version,
          provider: source.provider,
          model: source.model,
          requestedAt: toDateTime(source.created_at),
          completedAt: toDateTime(source.completed_at),
        }
      : null,
    sessionError: envelope?.error?.message ?? source?.error?.message ?? null,
    canRequest: sessionStatus !== null && canRequestAnalysis(sessionStatus),
    processing,
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    run,
    reload: remote.reload,
  };
}
