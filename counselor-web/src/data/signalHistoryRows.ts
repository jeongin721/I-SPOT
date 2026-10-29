// 사례 단위 신호 이력(useSignalHistory) → 화면 칸 값. 유형별 위험도 '회차별 추이' 와 상담 이력 '회차 카드 · 세부 신호 행렬' 이 같이 쓴다.
//
//  - 칸 값: AI 심각도(1~5, ai_level)가 있으면 그 숫자, 없는데 관련 신호(detected)가 있으면 '확인 필요', 둘 다 없으면 '–'.
//    분석이 끝나지 않은 회차는 '분석 중' · '분석 전'. 모두 AI 제안이다(판정 아님).
//  - '위험도 (상담원)' 줄: 그 회차에서 상담원이 고른 유형별 판단(상 · 중 · 하) 중 가장 높은 것. AI 값으로 채우지 않는다.

import { RISK_LEVEL_LABELS, type AbuseType, type RiskLevel, type SignalHistorySession } from "../api/types";

/** 10/27 디자인 '회차별 추이' 의 줄 순서(신체 · 정서 · 방임 · 성). */
export const TREND_TYPES: AbuseType[] = ["PHYSICAL", "EMOTIONAL", "NEGLECT", "SEXUAL"];

export const TYPE_SHORT: Record<AbuseType, string> = { PHYSICAL: "신체", EMOTIONAL: "정서", SEXUAL: "성", NEGLECT: "방임" };

const LEVEL_ORDER: RiskLevel[] = ["HIGH", "MEDIUM", "LOW"];

export const DASH = "–";

export interface HistoryCell {
  text: string;
  /** 값이 없는 칸(–, 분석 전)이라 흐리게 보인다. */
  muted: boolean;
  /** AI 심각도 숫자(없으면 null) — 행렬 칸 색을 정한다. */
  level: number | null;
  /** 관련 신호가 있는가. */
  detected: boolean;
}

/** 분석이 끝나지 않아 값이 없는 회차의 칸 문구. 없으면 ''(값이 있는 회차). */
export function pendingLabel(session: SignalHistorySession): string {
  if (session.types.length > 0) return "";
  if (session.analysis_status === "PROCESSING") return "분석 중";
  if (session.analysis_status === "FAILED") return "분석 실패";
  return "분석 전";
}

export function historyCell(session: SignalHistorySession, type: AbuseType): HistoryCell {
  const pending = pendingLabel(session);
  if (pending) return { text: pending, muted: true, level: null, detected: false };

  const row = session.types.find((item) => item.abuse_type === type);
  const level = typeof row?.ai_level === "number" ? row.ai_level : null;
  const detected = row?.detected === true;

  if (level !== null) return { text: String(level), muted: false, level, detected };
  if (detected) return { text: "확인 필요", muted: true, level: null, detected };
  return { text: DASH, muted: true, level: null, detected: false };
}

/**
 * 그 회차의 상담원 판단. 회차 전체 판단(회차 줄 counselor_level, 11.1절 — #119 부터 화면은 이것만 저장)을 먼저 보고,
 * 없으면 예전 회차의 유형별 판단(types[].counselor_level, 11.2절) 가운데 가장 높은 것. 둘 다 없으면 null.
 */
export function counselorTop(session: SignalHistorySession): RiskLevel | null {
  if (session.counselor_level) return session.counselor_level;

  for (const level of LEVEL_ORDER) {
    if (session.types.some((item) => item.counselor_level === level)) return level;
  }

  return null;
}

export function counselorTopLabel(session: SignalHistorySession): string {
  const top = counselorTop(session);
  return top ? RISK_LEVEL_LABELS[top] : DASH;
}

/**
 * 관련 신호를 '없음' 으로 단정할 수 있는가 — detected 가 하나라도 false 이고 true 는 없을 때.
 * 전부 null(근거 없어 서버가 뺀 유형 · 검출 미확인)이면 false — 화면은 '검출 여부 미확인' 으로 쓴다(유형별 위험도와 같은 규칙).
 */
export function signalsClearlyAbsent(session: SignalHistorySession): boolean {
  return session.types.some((item) => item.detected === false) && !session.types.some((item) => item.detected === true);
}

/** 관련 신호(AI)가 있는 유형의 짧은 이름. 줄 순서는 TREND_TYPES. */
export function detectedTypeLabels(session: SignalHistorySession): string[] {
  return TREND_TYPES.filter((type) => session.types.some((item) => item.abuse_type === type && item.detected === true)).map(
    (type) => TYPE_SHORT[type],
  );
}
