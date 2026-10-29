// 회차 전체 상담원 위험도 판단 훅(GET/PUT /sessions/{id}/risk-assessment, API_CONTRACT 11.1절, 2026-10-29).
//
// 상담사가 유형별 심각도(AI 제안 1~5)를 보고 이 회차 전체를 상 · 중 · 하 **하나**로 판단한 값을 불러오고 저장한다.
//  - 유형별 판단(11.2절, 예전 useRiskAssessments)은 화면에서 더 쓰지 않는다. 서버 창구는 기록 · signal-history 용으로 남아 있다.
//  - AI 는 유형별 심각도(1~5)를 제안만 하고 판단은 상담원이 한다. aiLevel 은 '판단할 때 보였던 AI 제안 중 가장 높은 단계' 기록이다.
//    AI 단계와 상 · 중 · 하를 대응시키는 규칙, 사례 단위 위험도는 팀 결정 전이라 여기서 계산하지 않는다.
//  - 서버는 판단이 없으면 data 를 null 로 준다. useRemote 는 data 가 null 이면 '아직 못 받음' 으로 보므로 { assessment } 로 감싸 든다.
//  - 원문 확정 뒤(STT_CONFIRMED · AI_REVIEW_REQUIRED · AI_FAILED · APPROVED)에만 저장된다. 그 밖에는 409 문구를 보여 준다.
//  - 저장해도 회차 상태는 바뀌지 않는다(sessionEvents 를 보내지 않는다).
//  - 분석이 끝나 검수 중인 회차에 판단이 없으면 요약 · 일지 작성으로 넘어가지 못한다(needsJudgment). 유형별 위험도 화면은
//    다음 단추 · 단계 표시를 팝업으로 막고, 요약 · 일지 작성 화면은 유형별 위험도로 돌려보낸다(?ask=1, signalReview.ts).

import { useCallback, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { riskAssessments as riskApi } from "../api/endpoints";
import { RISK_LEVEL_LABELS, type OverallRiskAssessment, type RiskLevel, type SessionStatus } from "../api/types";
import { toDateTime } from "./time";
import { errorMessage, useRemote } from "./useRemote";

/** Backend 제한(API_CONTRACT 11절). */
export const RISK_REASON_MAX = 1000;

/** 상담원 판단을 저장할 수 있는 회차 상태(API_CONTRACT 11절). */
export const ASSESSABLE_STATUSES: readonly SessionStatus[] = ["STT_CONFIRMED", "AI_REVIEW_REQUIRED", "AI_FAILED", "APPROVED"];

export interface OverallRiskAssessmentRow {
  /** 상담원 판단. */
  level: RiskLevel;
  /** "상" · "중" · "하". */
  levelLabel: string;
  /** 판단 이유. 없으면 빈 문자열. */
  reason: string;
  /** 판단할 때 보였던 AI 제안 중 가장 높은 단계(1~5). 없으면 null. */
  aiLevel: number | null;
  /** 마지막으로 저장한 시각(YYYY-MM-DD HH:mm). */
  assessedAt: string;
}

export function toOverallRiskAssessmentRow(item: OverallRiskAssessment): OverallRiskAssessmentRow {
  return {
    level: item.counselor_level,
    levelLabel: RISK_LEVEL_LABELS[item.counselor_level],
    reason: item.reason ?? "",
    aiLevel: item.ai_level,
    assessedAt: toDateTime(item.assessed_at),
  };
}

/** 보내기 전에 걸러 낼 문제가 있으면 그 문장, 없으면 null. 서버가 최종으로 거절한다(422). */
export function checkRiskReason(reason: string | undefined): string | null {
  // 서버(파이썬 len)처럼 코드 포인트로 센다. reason.length 는 UTF-16 단위라 이모지 하나를 2 로 센다.
  if (reason !== undefined && Array.from(reason).length > RISK_REASON_MAX) {
    return `판단 이유는 ${RISK_REASON_MAX.toLocaleString()}자까지 쓸 수 있습니다.`;
  }

  return null;
}

export interface OverallRiskAssessmentOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface OverallRiskAssessmentState {
  /** 저장된 판단. 아직 판단하지 않았으면 null — loaded 가 true 이고 loadError 가 없을 때만 '판단 전' 으로 믿는다. */
  assessment: OverallRiskAssessmentRow | null;
  /**
   * 서버 값을 한 번이라도 받았는가. 받기 전(또는 받지 못한 채)에는 assessment 가 null 이어도 실제 판단이 있을 수 있으므로,
   * 화면은 이 값이 true 이고 loadError 가 없을 때만 저장 단추를 켠다. 그래야 서버에 있는 이유를 모른 채 PUT 으로
   * 덮어쓰지 않는다(PUT 은 판단 전체를 바꾼다 — 유형별 판단의 Codex #81 R1 과 같은 이유).
   */
  loaded: boolean;
  submitting: boolean;
  loading: boolean;
  /** 저장 실패 또는 조회 실패 문구. */
  error: string | null;
  /** 조회 실패 문구만. 저장 실패는 들어가지 않는다. reload() 로 다시 부른다. */
  loadError: string | null;
  /**
   * 판단을 저장한다(없으면 만들고 있으면 고침). 판단 전체를 바꾸므로 이유를 빼면 지워진다.
   * 성공하면 저장된 판단, 실패하면 null.
   */
  save: (input: { level: RiskLevel; reason?: string }) => Promise<OverallRiskAssessmentRow | null>;
  reload: () => void;
}

/**
 * 지금 판단 단추를 켤 수 있는가.
 * 회차 상태가 저장 가능하고, 요청 중이 아니고, **서버 값을 받은 뒤(loaded · 조회 오류 없음)** 여야 한다.
 * 값을 못 받은 채 저장하면 서버에 있던 판단 이유를 모른 채 PUT 으로 지운다. 오류를 보이는 것만으로는 부족해서 단추 자체를 끈다.
 */
export function canAssessNow(
  status: SessionStatus | null,
  state: Pick<OverallRiskAssessmentState, "loaded" | "loading" | "loadError" | "submitting">,
): boolean {
  return (
    status !== null &&
    ASSESSABLE_STATUSES.includes(status) &&
    state.loaded &&
    !state.loading &&
    state.loadError === null &&
    !state.submitting
  );
}

/**
 * 판단 없이는 다음 단계(요약 · 일지 작성)로 못 가는 회차인가(2026-10-29 사용자 결정 '위험도를 고르기 전에는 다음 페이지로 못 간다').
 * AI 분석이 끝나 검수 중(AI_REVIEW_REQUIRED)이고, 판단을 받아 봤는데(loaded · 조회 오류 없음) 없을 때다.
 *  - 승인 완료 회차는 막지 않는다(이미 끝난 흐름이고, 이 기능 전에 승인한 회차도 있다).
 *  - 값을 아직 못 받았거나 조회가 실패했으면 막지 않는다(막을 근거가 없다 — 화면이 오류 · 불러오는 중을 보인다).
 *  - 분석 전 · 분석 중 · 실패 회차는 다음 단추가 원래 잠겨 있어(canNext) 여기서 보지 않는다.
 */
export function needsJudgment(
  status: SessionStatus | null,
  state: Pick<OverallRiskAssessmentState, "loaded" | "loadError" | "assessment">,
): boolean {
  return status === "AI_REVIEW_REQUIRED" && state.loaded && state.loadError === null && state.assessment === null;
}

/**
 * 요약 · 일지 작성이 '들어올 때 한 번만' 돌려보낼지 정한다(2026-10-29 교차 검토).
 * 회차마다 상태와 판단을 처음 모두 받은 그리기에서 needsJudgment 를 판정해 기억하고, 그 뒤 같은 회차에서 상태가 바뀌어도
 * 다시 보내지 않는다 — 화면 안에서 '요약 수정' 으로 승인을 풀면 AI_REVIEW_REQUIRED 로 돌아오는데, 이 기능 전에 승인한 회차는
 * 판단이 없어 고치던 화면이 그 자리에서 튕기기 때문이다. 회차가 바뀌면 다시 판정한다.
 * 상태나 판단을 아직 못 받았거나 조회가 실패했으면 false(막을 근거가 없다).
 */
export function useJudgmentGate(
  sessionId: string | null | undefined,
  status: SessionStatus | null,
  state: Pick<OverallRiskAssessmentState, "loaded" | "loadError" | "assessment">,
): boolean {
  const decided = useRef<{ sessionId: string; redirect: boolean } | null>(null);

  if (decided.current !== null && decided.current.sessionId !== sessionId) decided.current = null;

  if (decided.current === null && sessionId && status !== null && state.loaded && state.loadError === null) {
    decided.current = { sessionId, redirect: needsJudgment(status, state) };
  }

  return decided.current !== null && decided.current.sessionId === sessionId && decided.current.redirect;
}

/** 서버의 null(판단 없음)을 useRemote 의 '못 받음'(null)과 구분하려고 감싼다. */
function loadOverall(sessionId: string): Promise<{ assessment: OverallRiskAssessment | null }> {
  return riskApi.getOverall(sessionId).then((assessment) => ({ assessment: assessment ?? null }));
}

export function useOverallRiskAssessment(
  sessionId: string | null | undefined,
  { enabled = true }: OverallRiskAssessmentOptions = {},
): OverallRiskAssessmentState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<{ assessment: OverallRiskAssessment | null }>(
    key,
    loadOverall,
    "위험도 판단을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  );
  const [submitting, setSubmitting] = useState(false);
  // 요청 중인가. state 는 같은 순간의 두 번째 누름을 막지 못해 ref 로도 든다.
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  // 대상 세대가 바뀌면(다른 회차, 로그아웃 · 다시 로그인, 다른 회차에 갔다 돌아옴) 앞 대상의 오류를 지우고,
  // 앞 대상에서 보낸 요청이 아직 안 끝났어도 새 대상에서는 저장할 수 있게 한다. 그 요청의 응답은 useRemote 의 표가
  // 버린다(같은 회차로 돌아와도 세대가 다르다).
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setSubmitting(false);
  }

  const assessment = useMemo(
    () => (remote.data?.assessment ? toOverallRiskAssessmentRow(remote.data.assessment) : null),
    [remote.data],
  );

  /**
   * 한 번에 하나만 보낸다(같은 순간 두 번 눌러도 두 번째는 null).
   * 요청한 뒤 대상이 바뀌었으면(다른 회차, 로그아웃 · 재로그인, 다른 회차에 갔다 돌아옴, 다른 탭에서 다시 로그인)
   * 결과를 반영하지 않고 null 을 돌려준다. 판단은 요청한 회차에 저장됐고, 지금 값은 그 뒤에 새로 불러온 값이다.
   */
  const save = useCallback(
    async (input: { level: RiskLevel; reason?: string }): Promise<OverallRiskAssessmentRow | null> => {
      const ticket = remote.capture();

      // 이 함수를 만든 그리기 뒤에 대상이 바뀌었으면 보내지 않는다.
      if (!ticket || ticket.key !== key || inFlight.current) return null;

      const problem = checkRiskReason(input.reason);

      if (problem) {
        setActionError(problem);
        return null;
      }

      const reason = input.reason?.trim() ? input.reason : null;

      inFlight.current = true;
      setSubmitting(true);
      setActionError(null);

      try {
        const result = await riskApi.saveOverall(ticket.key, { counselor_level: input.level, reason });

        if (!remote.setData(ticket, { assessment: result })) return null;

        return toOverallRiskAssessmentRow(result);
      } catch (caught) {
        // 대상이 바뀌었으면 오류 문구도 다시 조회도 하지 않는다(새로 부른 값을 건드리지 않게).
        if (!remote.isCurrent(ticket)) return null;

        if (!(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, "위험도 판단을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }

        // 다른 창에서 먼저 저장했을 수 있다(409 DUPLICATE_RESOURCE). 최신 값을 다시 받는다.
        remote.refresh();

        return null;
      } finally {
        // 대상 세대가 바뀌었으면 그때 이미 풀었다. 새 대상에서 보낸 요청의 표시를 끄지 않는다.
        if (remote.sameGeneration(ticket)) {
          inFlight.current = false;
          setSubmitting(false);
        }
      }
    },
    [key, remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.refresh],
  );

  return {
    assessment,
    loaded: remote.data !== null,
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    loadError: remote.error,
    save,
    reload: remote.reload,
  };
}
