// 사례 상세 탭들(내담자 정보 · 상담 이력 · 상담 전 브리핑 · 문서함)이 같이 쓰는 '가장 최근 분석 회차' 값.
//
// 사례에는 위험도 · 학대 유형 · 확인 메모가 따로 저장되지 않는다. 그래서 회차 목록(useCaseDetail, 최신 회차부터)에서
// AI 분석이 끝난 가장 최근 회차(결과 검수 중 · 승인 완료) 하나를 골라, 그 회차의 값을 기존 API 로 부른다(새 API 없음).
//  - 상담원 판단(상 · 중 · 하): GET /sessions/{id}/risk-assessments (useRiskAssessments)
//  - AI 관련 신호 · 근거 발화 · 확인 메모: GET /sessions/{id}/analysis (useSessionAnalysis · useRiskSignals)
// 그보다 새 회차가 아직 분석 전이어도 이 회차를 쓴다(화면은 session.numberLabel 로 어느 회차 값인지 밝힌다).
// 회차 목록은 최신 100개까지라(useCaseDetail), 그 안에 분석 끝난 회차가 없고 목록이 잘렸으면 truncated 로 알린다.
// 여러 회차를 모으는 값(회차별 추이 · 처음 나온 이야기)은 회차마다 부르게 되므로 여기서 하지 않는다(사례 단위 API 제안 중).

import { useMemo } from "react";

import { RISK_LEVEL_LABELS, type RiskLevel } from "../api/types";
import type { CaseDetailState } from "./useCaseDetail";
import { useRiskAssessments, type RiskAssessmentsState } from "./useRiskAssessments";
import { useRiskSignals, type RiskSignalsState } from "./useRiskSignals";
import { useSessionAnalysis, type SessionAnalysisState } from "./useSessionAnalysis";
import type { SessionRow } from "./sessionRows";

/** 분석 결과를 볼 수 있는 회차 상태. */
const ANALYZED = new Set(["AI_REVIEW_REQUIRED", "APPROVED"]);

/** 회차 목록(최신부터)에서 분석이 끝난 가장 최근 회차. 없으면 null. */
export function latestAnalyzedSession(sessions: SessionRow[]): SessionRow | null {
  return sessions.find((row) => ANALYZED.has(row.status)) ?? null;
}

const LEVEL_ORDER: RiskLevel[] = ["HIGH", "MEDIUM", "LOW"];

export interface CaseSignalsState {
  /** 값을 가져온 회차. 분석이 끝난 회차가 없으면 null. */
  session: SessionRow | null;
  analysis: SessionAnalysisState;
  risk: RiskAssessmentsState;
  signals: RiskSignalsState;
  /** 상담원이 고른 유형별 판단 중 가장 높은 것. 판단이 하나도 없으면 null. */
  topLevel: RiskLevel | null;
  /** "상" · "중" · "하" 또는 "". */
  topLevelLabel: string;
  /** 가장 높은 판단을 저장한 일시. 없으면 "". */
  topLevelAt: string;
  /** 분석 끝난 회차를 못 찾았는데 회차 목록이 잘렸는가(더 오래된 회차에 있을 수 있다). */
  truncated: boolean;
  /** 받은 회차 수(잘렸을 때 '최근 N회차' 문구용). */
  shownCount: number;
}

export function useCaseSignals(detail: CaseDetailState, { enabled = true }: { enabled?: boolean } = {}): CaseSignalsState {
  const session = latestAnalyzedSession(detail.sessions);
  const sessionId = session?.id ?? null;
  const analysis = useSessionAnalysis(sessionId, { enabled });
  const risk = useRiskAssessments(sessionId, { enabled });
  const signals = useRiskSignals(sessionId, analysis.analysis, { enabled });

  const top = useMemo(() => {
    for (const level of LEVEL_ORDER) {
      const row = risk.rows.find((item) => item.level === level);
      if (row) return { level, at: row.assessedAt };
    }

    return null;
  }, [risk.rows]);

  return {
    session,
    analysis,
    risk,
    signals,
    topLevel: top?.level ?? null,
    topLevelLabel: top ? RISK_LEVEL_LABELS[top.level] : "",
    topLevelAt: top?.at ?? "",
    truncated: session === null && detail.sessionTotal !== null && detail.sessionTotal > detail.sessions.length,
    shownCount: detail.sessions.length,
  };
}
