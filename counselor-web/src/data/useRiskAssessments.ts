// 상담원 위험도 판단 훅(GET /sessions/{id}/risk-assessments, PUT …/{abuse_type}).
//
// 회차 · 학대 유형마다 상담원이 상 · 중 · 하로 판단한 값을 불러오고 저장한다(API_CONTRACT 11절).
//  - AI 는 유형별 심각도(1~5)를 제안만 하고 판단은 상담원이 한다. aiLevel 은 '판단할 때 보였던 AI 제안' 기록이다.
//  - AI 단계와 상 · 중 · 하를 대응시키는 규칙, 사례 단위 위험도는 팀 결정 전이라 여기서 계산하지 않는다.
//  - 서버는 판단한 유형만 준다. 이 훅은 네 유형을 늘 같은 순서로 채워 돌려준다(판단 전이면 level 이 null).
//  - 원문 확정 뒤(STT_CONFIRMED · AI_REVIEW_REQUIRED · AI_FAILED · APPROVED)에만 저장된다. 그 밖에는 409 문구를 보여 준다.
//  - 저장해도 회차 상태는 바뀌지 않는다(sessionEvents 를 보내지 않는다).

import { useCallback, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { riskAssessments as riskApi } from "../api/endpoints";
import {
  ABUSE_TYPE_LABELS,
  ABUSE_TYPES,
  RISK_LEVEL_LABELS,
  type AbuseType,
  type RiskAssessment,
  type RiskLevel,
} from "../api/types";
import { toDateTime } from "./time";
import { errorMessage, useRemote } from "./useRemote";

/** Backend 제한(API_CONTRACT 11절). */
export const RISK_REASON_MAX = 1000;

export interface RiskAssessmentRow {
  abuseType: AbuseType;
  /** "신체학대" 등. */
  abuseTypeLabel: string;
  /** 상담원 판단. 아직 판단하지 않았으면 null. */
  level: RiskLevel | null;
  /** "상" · "중" · "하", 판단 전이면 빈 문자열. */
  levelLabel: string;
  /** 판단 이유. 없으면 빈 문자열. */
  reason: string;
  /** 판단할 때 보였던 AI 제안(1~5). 없거나 판단 전이면 null. */
  aiLevel: number | null;
  /** 마지막으로 저장한 시각. 판단 전이면 빈 문자열. */
  assessedAt: string;
  /** 판단을 저장한 적이 있는가. */
  assessed: boolean;
}

/** 서버 목록(판단한 유형만)을 네 유형 고정 순서의 줄로 채운다. */
export function toRiskAssessmentRows(items: RiskAssessment[]): RiskAssessmentRow[] {
  return ABUSE_TYPES.map((abuseType) => {
    const item = items.find((candidate) => candidate.abuse_type === abuseType);

    return {
      abuseType,
      abuseTypeLabel: ABUSE_TYPE_LABELS[abuseType],
      level: item?.counselor_level ?? null,
      levelLabel: item ? RISK_LEVEL_LABELS[item.counselor_level] : "",
      reason: item?.reason ?? "",
      aiLevel: item?.ai_level ?? null,
      assessedAt: item ? toDateTime(item.assessed_at) : "",
      assessed: Boolean(item),
    };
  });
}

/** 보내기 전에 걸러 낼 문제가 있으면 그 문장, 없으면 null. 서버가 최종으로 거절한다(422). */
export function checkRiskReason(reason: string | undefined): string | null {
  if (reason !== undefined && reason.length > RISK_REASON_MAX) {
    return `판단 이유는 ${RISK_REASON_MAX.toLocaleString()}자까지 쓸 수 있습니다.`;
  }

  return null;
}

export interface RiskAssessmentsOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface RiskAssessmentsState {
  /** 네 유형 고정 순서(신체 · 정서 · 성 · 방임). */
  rows: RiskAssessmentRow[];
  submitting: boolean;
  loading: boolean;
  error: string | null;
  /**
   * 한 유형의 판단을 저장한다(없으면 만들고 있으면 고침). 판단 전체를 바꾸므로 이유를 빼면 지워진다.
   * 성공하면 그 유형의 줄, 실패하면 null.
   */
  save: (abuseType: AbuseType, input: { level: RiskLevel; reason?: string }) => Promise<RiskAssessmentRow | null>;
  reload: () => void;
}

export function useRiskAssessments(
  sessionId: string | null | undefined,
  { enabled = true }: RiskAssessmentsOptions = {},
): RiskAssessmentsState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<RiskAssessment[]>(
    key,
    riskApi.list,
    "위험도 판단을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  );
  const [submitting, setSubmitting] = useState(false);
  // 요청 중인가. state 는 같은 순간의 두 번째 누름을 막지 못해 ref 로도 든다.
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState(key);

  if (errorKey !== key) {
    setErrorKey(key);
    setActionError(null);
  }

  const rows = useMemo(() => toRiskAssessmentRows(remote.data ?? []), [remote.data]);

  /**
   * 한 번에 하나만 보낸다(같은 순간 두 번 눌러도 두 번째는 null).
   * 요청한 뒤 다른 회차로 옮겼으면 결과를 지금 회차의 목록에 넣지 않는다(판단은 요청한 회차에 저장됐다).
   */
  const save = useCallback(
    async (abuseType: AbuseType, input: { level: RiskLevel; reason?: string }): Promise<RiskAssessmentRow | null> => {
      if (!key || inFlight.current) return null;

      const problem = checkRiskReason(input.reason);

      if (problem) {
        setActionError(problem);
        return null;
      }

      const forKey = key;
      const reason = input.reason?.trim() ? input.reason : null;

      inFlight.current = true;
      setSubmitting(true);
      setActionError(null);

      try {
        const result = await riskApi.save(forKey, abuseType, { counselor_level: input.level, reason });

        remote.setData(forKey, (current) => {
          const list = current ?? [];

          return list.some((item) => item.abuse_type === result.abuse_type)
            ? list.map((item) => (item.abuse_type === result.abuse_type ? result : item))
            : [...list, result];
        });

        return toRiskAssessmentRows([result]).find((row) => row.abuseType === abuseType) ?? null;
      } catch (caught) {
        if (remote.isCurrent(forKey) && !(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, "위험도 판단을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }

        // 다른 창에서 먼저 저장했을 수 있다(409 DUPLICATE_RESOURCE). 최신 목록을 다시 받는다.
        remote.refresh();

        return null;
      } finally {
        inFlight.current = false;
        setSubmitting(false);
      }
    },
    [key, remote.setData, remote.isCurrent, remote.refresh],
  );

  return {
    rows,
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    save,
    reload: remote.reload,
  };
}
