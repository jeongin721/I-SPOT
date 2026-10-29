// AI 결과의 위험 관련 항목(risk_utterances · abuse_signals, PROPOSAL_risk_fields.md §7-0 · API_CONTRACT 8절 "위험 3필드 항목 구조")
// → 유형별 위험도 화면의 근거 발화와 유형별 칩.
//
//  - Contract 값은 영문 대문자(abuse_type · evidence_strength · detection_source)이고 한글 이름은 여기서만 붙인다
//    (02_ARCHITECTURE §7). 넷 밖의 유형명이 오면 "기타(값)" 으로 보인다.
//  - 모두 AI 참고정보다. 판정이 아니므로 "관련 신호" · "추가 확인 필요" 로만 쓴다(05_RULES §1, README "지켜야 할 원칙").
//  - 서버는 근거 발화(segment_ids)가 없거나 원문에 없는 항목을 저장 전에 뺀다. 그래서 여기 오는 발화는 모두 근거가 있고,
//    모델이 검출했는데 근거가 없던 유형은 abuse_signals 에서도 빠져 있다(warnings 에 건수만 남는다).
//  - 근거 위치(몇 분 · 누구)는 원문(GET …/transcript)의 발화로 찾는다(README 원칙 3). 원문을 못 받았으면 번호만 보인다.
//  - 채택 · 보류 · 제외 기록은 서버에 없다(팀 결정 전). 이 모듈은 읽기 전용 표시만 만든다.

import type { AbuseSignal, RiskUtterance, TranscriptSegment } from "../api/types";
import { formatClock } from "./time";
import { SPEAKER_LABELS } from "./transcriptRows";

/** 학대 유형 대분류 → 화면 이름. Contract 는 영문 대문자로 온다. */
export const ABUSE_TYPE_LABELS: Record<string, string> = {
  PHYSICAL: "신체학대",
  EMOTIONAL: "정서학대",
  SEXUAL: "성학대",
  NEGLECT: "방임",
};

/** 유형별 줄의 고정 순서. 서버도 이 네 유형을 모두 준다. */
export const ABUSE_TYPE_ORDER = ["PHYSICAL", "EMOTIONAL", "SEXUAL", "NEGLECT"];

/** 근거의 직접성(확률이 아니다). */
export const STRENGTH_LABELS: Record<string, string> = {
  HIGH: "높음",
  MEDIUM: "중간",
  LOW: "낮음",
};

/**
 * 표에 선언한 값만 읽는다. `table[key]` 는 "__proto__" · "constructor" · "toString" 같은 이름에서 Object 의 상속 속성을
 * 돌려주고, 그 값(객체 · 함수)이 화면에 들어가면 React 가 그리기를 멈춘다(Codex R1). 서버는 항목 키를 검증하지 않고
 * 변환기는 모르는 유형명을 보존하므로 어떤 문자열이 와도 문자열 fallback 으로 떨어져야 한다.
 */
function lookup(table: Record<string, string>, key: string): string | null {
  return Object.prototype.hasOwnProperty.call(table, key) ? table[key] : null;
}

export function abuseTypeLabel(abuseType: unknown): string {
  if (typeof abuseType !== "string" || !abuseType) return "유형 미확인";

  return lookup(ABUSE_TYPE_LABELS, abuseType) ?? `기타(${abuseType})`;
}

export function strengthLabel(strength: unknown): string {
  if (typeof strength !== "string" || !strength) return "미확인";

  return lookup(STRENGTH_LABELS, strength) ?? `미확인(${strength})`;
}

/** 근거 발화 한 줄. 원문에서 찾았으면 위치 · 화자 · 문장이 있고, 못 찾았으면(원문 미수신 · 없는 번호) 번호만 있다. */
export interface SignalEvidence {
  segmentId: string;
  found: boolean;
  /** "01:36" 같은 음성 안 위치. */
  startLabel: string;
  speakerLabel: string;
  text: string;
}

/** 위험 신호 카드 하나(= risk_utterances 한 항목). */
export interface SignalCard {
  key: string;
  abuseType: string;
  typeLabel: string;
  /** 2차 세부유형명(한글). 없으면 "". */
  subtype: string;
  strength: string;
  strengthLabel: string;
  /** AI 가 든 발화 문장. */
  quote: string;
  /** AI 가 그 강도로 본 이유. 없으면 "". */
  reason: string;
  /** 인용문이 원문과 맞는지 AI 가 대조한 결과. */
  verified: boolean;
  evidence: SignalEvidence[];
  /** 근거 위치 요약. "01:36 아동" 처럼 첫 근거부터 ' · ' 로 잇는다. 원문이 없으면 "발화 seg_002". */
  positionLabel: string;
}

function evidenceOf(segmentId: string, segments: Map<string, TranscriptSegment> | null): SignalEvidence {
  const segment = segments?.get(segmentId);

  if (!segment) return { segmentId, found: false, startLabel: "", speakerLabel: "", text: "" };

  return {
    segmentId,
    found: true,
    startLabel: formatClock(segment.start_ms),
    speakerLabel: SPEAKER_LABELS[segment.speaker] ?? segment.speaker,
    text: segment.text,
  };
}

function readIds(value: unknown): string[] {
  if (!Array.isArray(value)) return [];

  const ids: string[] = [];

  for (const id of value) {
    if (typeof id === "string" && id && !ids.includes(id)) ids.push(id);
  }

  return ids;
}

function readText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** 근거 위치 요약 문구. */
export function positionLabel(evidence: SignalEvidence[]): string {
  if (evidence.length === 0) return "";

  return evidence
    .map((item) => (item.found ? [item.startLabel, item.speakerLabel].filter(Boolean).join(" ") : `발화 ${item.segmentId}`))
    .join(" · ");
}

/**
 * 아무 항목의 segment_ids(보호요인 · 확인 메모 등) → 근거 줄. 원문을 못 받았으면(segments 가 null) 번호만 남는다.
 * 위험 신호 카드와 같은 규칙(중복 · 빈 값 · 문자열 아닌 값은 뺀다)이다.
 */
export function locateEvidence(ids: unknown, segments: TranscriptSegment[] | null): SignalEvidence[] {
  const byId = segments ? new Map(segments.map((segment) => [segment.segment_id, segment])) : null;

  return readIds(ids).map((segmentId) => evidenceOf(segmentId, byId));
}

/**
 * risk_utterances → 카드 목록. 순서는 서버가 준 그대로다(2차 분석 근거 순).
 * segments 가 null 이면(원문을 아직 못 받음) 근거는 번호만 남는다 — '없음' 이 아니라 '모름' 이다.
 */
export function toSignalCards(utterances: RiskUtterance[], segments: TranscriptSegment[] | null): SignalCard[] {
  const byId = segments ? new Map(segments.map((segment) => [segment.segment_id, segment])) : null;

  return utterances.map((item, index) => {
    const evidence = readIds(item.segment_ids).map((segmentId) => evidenceOf(segmentId, byId));
    const abuseType = typeof item.abuse_type === "string" ? item.abuse_type : "";

    return {
      key: `${abuseType || "unknown"}-${index}`,
      abuseType,
      typeLabel: abuseTypeLabel(abuseType),
      subtype: readText(item.subtype),
      strength: typeof item.evidence_strength === "string" ? item.evidence_strength : "",
      strengthLabel: strengthLabel(item.evidence_strength),
      quote: readText(item.text),
      reason: readText(item.reason),
      verified: item.evidence_verified === true,
      evidence,
      positionLabel: positionLabel(evidence),
    };
  });
}

/**
 * 유형별 줄의 상태.
 *  - signal: 관련 신호가 있고 근거 발화가 연결돼 있다(추가 확인 필요).
 *  - filtered: 모델은 짚었으나 아동이 명확히 부정한 발화라 신호로 내지 않았다(detected=false, FILTERED).
 *  - none: 관련 신호 없음(detected 가 분명히 false).
 *  - unknown: detected 가 없거나 참/거짓이 아니다. 서버는 이런 항목을 근거가 맞을 때만 남기므로(API_CONTRACT 8절)
 *    '없음' 으로 단정하지 않고 확인 필요로 둔다(Codex R2). 검출로 바꿔 쓰지도 않는다.
 *  - missing: 응답에 그 유형이 없다 — 근거 발화가 없는 신호를 서버가 뺀 경우다(warnings 에 건수가 남는다).
 */
export type TypeSignalState = "signal" | "filtered" | "none" | "unknown" | "missing";

export interface TypeSignal {
  abuseType: string;
  typeLabel: string;
  state: TypeSignalState;
  stateLabel: string;
  /** 이 유형의 카드(근거 발화) 수. */
  count: number;
  /** FILTERED 일 때 서버가 준 사유. */
  filteredReason: string;
}

export const TYPE_STATE_LABELS: Record<TypeSignalState, string> = {
  signal: "관련 신호 · 추가 확인 필요",
  filtered: "관련 신호 없음 · 아동이 명확히 부정한 발화는 신호에서 뺌",
  none: "관련 신호 없음",
  unknown: "검출 여부 미확인 · 근거 발화를 직접 확인",
  missing: "응답에 없음 · 근거 발화가 없는 신호는 서버가 뺌",
};

/** abuse_signals + risk_utterances → 네 유형 고정 순서의 줄. 넷 밖의 유형이 응답에 있으면 뒤에 붙는다. */
export function toTypeSignals(signals: AbuseSignal[], utterances: RiskUtterance[]): TypeSignal[] {
  const counts = new Map<string, number>();

  for (const item of utterances) {
    const abuseType = typeof item.abuse_type === "string" ? item.abuse_type : "";
    counts.set(abuseType, (counts.get(abuseType) ?? 0) + 1);
  }

  const byType = new Map<string, AbuseSignal>();

  for (const signal of signals) {
    if (typeof signal.abuse_type === "string" && signal.abuse_type && !byType.has(signal.abuse_type)) {
      byType.set(signal.abuse_type, signal);
    }
  }

  const order = [...ABUSE_TYPE_ORDER, ...[...byType.keys()].filter((type) => !ABUSE_TYPE_ORDER.includes(type))];

  return order.map((abuseType) => {
    const signal = byType.get(abuseType);
    const count = counts.get(abuseType) ?? 0;
    let state: TypeSignalState;

    if (!signal) state = "missing";
    else if (signal.detected === true) state = "signal";
    else if (signal.detected === false) state = signal.detection_source === "FILTERED" ? "filtered" : "none";
    else state = "unknown";

    return {
      abuseType,
      typeLabel: abuseTypeLabel(abuseType),
      state,
      stateLabel: TYPE_STATE_LABELS[state],
      count,
      filteredReason: state === "filtered" ? readText(signal?.filtered_reason) : "",
    };
  });
}
