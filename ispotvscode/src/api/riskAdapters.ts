// AI 결과의 위험 관련 항목(risk_utterances · abuse_signals · risk_factors)을 화면 형태로 바꾼다.
//
// AI 분석 검토 화면과 사례 관리의 분석 탭이 같은 결과를 같은 모양으로 보여 주도록 한 곳에 둔다.
// 세 필드의 항목 구조는 아직 팀 합의 전이라(PROPOSAL_risk_fields.md §7) Backend 는 객체를 그대로
// 넘긴다. 그래서 필드를 하나씩 확인하며 읽고, 합의되면 이 파일만 고친다.
// types.ts 는 abuse_signals · risk_factors 를 string[] 로 적어 두었지만 실제로는 객체 배열이다.
//
// ⚠️ AI 결과는 판정이 아니라 참고정보다. "관련 신호", "추가 확인 필요" 로만 쓴다.
// ⚠️ 근거 발화 번호가 없는 항목은 보여 주지 않는다(05_RULES.md "근거 없는 위험 신호를 생성하지 않는다").

import type { UiTranscriptSegment } from "./adapters";
import type { AnalysisResult } from "./types";

type LooseItem = Record<string, unknown>;

function asItems(value: unknown): LooseItem[] {
  if (!Array.isArray(value)) return [];

  return value.filter((item): item is LooseItem => typeof item === "object" && item !== null && !Array.isArray(item));
}

function readString(item: LooseItem, key: string): string | null {
  const value = item[key];

  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** 항목이 근거로 든 발화 번호. segment_id(단수)와 segment_ids(복수)를 모두 보고 겹치는 번호는 뺀다. */
export function readSegmentIds(item: LooseItem): string[] {
  const ids: string[] = [];

  for (const key of ["segment_id", "segment_ids"]) {
    const value = item[key];
    const candidates = Array.isArray(value) ? value : [value];

    for (const id of candidates) {
      if (typeof id === "string" && id && !ids.includes(id)) ids.push(id);
    }
  }

  return ids;
}

/** 학대유형 대분류 → 화면 이름. Contract 는 영문 대문자로 오고 한글은 화면에서만 쓴다. */
const ABUSE_TYPE_LABELS: Record<string, string> = {
  PHYSICAL: "신체",
  EMOTIONAL: "정서",
  SEXUAL: "성",
  NEGLECT: "방임",
};

function toAbuseTypeLabel(value: unknown): string | null {
  if (typeof value !== "string" || !value) return null;

  return ABUSE_TYPE_LABELS[value] ?? value;
}

/** 추가 확인이 필요하다고 AI 가 표시한 발화 하나. 한 항목이 여러 발화를 들면 발화마다 한 줄이다. */
export interface UiRiskUtterance {
  segmentId: string;
  /** AI 가 든 발화 문장. 없으면 전사본의 같은 발화 문장. */
  text: string;
  /** AI 가 든 사유. 없으면 빈 문자열. */
  reason: string;
  /** 전사본에서 찾은 시작 시각. 전사본을 넘기지 않았거나 없는 번호면 빈 문자열. */
  timestamp: string;
  /** 학대유형 대분류가 있으면 화면 이름(예: "신체"). */
  typeLabel: string | null;
}

export function toUiRiskUtterances(
  result: AnalysisResult | null,
  segments: UiTranscriptSegment[] = [],
): UiRiskUtterance[] {
  if (!result) return [];

  const byId = new Map(segments.map((seg) => [seg.id, seg]));
  const rows: UiRiskUtterance[] = [];

  for (const item of asItems(result.risk_utterances)) {
    for (const segmentId of readSegmentIds(item)) {
      const seg = byId.get(segmentId);

      rows.push({
        segmentId,
        text: readString(item, "text") ?? seg?.text ?? "",
        reason: readString(item, "reason") ?? "",
        timestamp: seg?.timestamp ?? "",
        typeLabel: toAbuseTypeLabel(item.abuse_type),
      });
    }
  }

  return rows;
}

/** abuse_signals · risk_factors 한 줄. 판정이 아니라 추가 확인이 필요한 참고정보다. */
export interface UiReferenceSignal {
  key: string;
  /** 신호는 "신체 관련 신호", 위험 요인은 요인 이름. */
  label: string;
  kind: "관련 신호" | "위험 요인";
  segmentIds: string[];
}

/**
 * abuse_signals · risk_factors 를 한 목록으로 바꾼다.
 *
 * - abuse_signals 중 detected 가 명시적으로 false 인 항목은 신호가 아니므로 뺀다.
 * - 근거 발화 번호가 없는 항목도 뺀다.
 */
export function toUiReferenceSignals(result: AnalysisResult | null): UiReferenceSignal[] {
  if (!result) return [];

  const rows: UiReferenceSignal[] = [];

  asItems(result.abuse_signals).forEach((item, index) => {
    if (item.detected === false) return;

    const segmentIds = readSegmentIds(item);

    if (segmentIds.length === 0) return;

    const typeLabel = toAbuseTypeLabel(item.abuse_type);
    const label = typeLabel ? `${typeLabel} 관련 신호` : readString(item, "label") ?? "관련 신호";

    rows.push({ key: `signal-${index}`, label, kind: "관련 신호", segmentIds });
  });

  asItems(result.risk_factors).forEach((item, index) => {
    const segmentIds = readSegmentIds(item);

    if (segmentIds.length === 0) return;

    const label = readString(item, "label") ?? readString(item, "code") ?? "위험 요인";

    rows.push({ key: `factor-${index}`, label, kind: "위험 요인", segmentIds });
  });

  return rows;
}

/** 강조해서 보여 줄 발화 번호(위험 관련 발화로 표시된 것). */
export function riskSegmentIdSet(utterances: UiRiskUtterance[]): Set<string> {
  return new Set(utterances.map((item) => item.segmentId));
}
