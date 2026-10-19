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
  // 서버(파이썬 len)처럼 코드 포인트로 센다. reason.length 는 UTF-16 단위라 이모지 하나를 2 로 센다.
  if (reason !== undefined && Array.from(reason).length > RISK_REASON_MAX) {
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

  const rows = useMemo(() => toRiskAssessmentRows(remote.data ?? []), [remote.data]);

  /**
   * 한 번에 하나만 보낸다(같은 순간 두 번 눌러도 두 번째는 null).
   * 요청한 뒤 대상이 바뀌었으면(다른 회차, 로그아웃 · 재로그인, 다른 회차에 갔다 돌아옴, 다른 탭에서 다시 로그인)
   * 결과를 반영하지 않고 null 을 돌려준다. 판단은 요청한 회차에 저장됐고, 지금 목록은 그 뒤에 새로 불러온 값이다.
   */
  const save = useCallback(
    async (abuseType: AbuseType, input: { level: RiskLevel; reason?: string }): Promise<RiskAssessmentRow | null> => {
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
        const result = await riskApi.save(ticket.key, abuseType, { counselor_level: input.level, reason });

        const applied = remote.setData(ticket, (current) => {
          const list = current ?? [];

          return list.some((item) => item.abuse_type === result.abuse_type)
            ? list.map((item) => (item.abuse_type === result.abuse_type ? result : item))
            : [...list, result];
        });

        if (!applied) return null;

        return toRiskAssessmentRows([result]).find((row) => row.abuseType === abuseType) ?? null;
      } catch (caught) {
        // 대상이 바뀌었으면 오류 문구도 다시 조회도 하지 않는다(새로 부른 목록을 건드리지 않게).
        if (!remote.isCurrent(ticket)) return null;

        if (!(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, "위험도 판단을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }

        // 다른 창에서 먼저 저장했을 수 있다(409 DUPLICATE_RESOURCE). 최신 목록을 다시 받는다.
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
    rows,
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    save,
    reload: remote.reload,
  };
}
