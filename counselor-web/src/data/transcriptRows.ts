// Backend 전사본 발화(TranscriptSegment) → 원문 검수 화면의 한 줄.
//
// 화자는 Backend 5종(API_CONTRACT 7절)만 쓴다. 새 화면의 '사례관리대상자' 는 Backend 에 없고
// 보호자(GUARDIAN)와 같은 뜻도 아니어서(specs 대응표 팀 결정 — 사례 · 개인정보) 어느 값으로도 바꾸지 않는다.
//
// 신뢰도 0.0 은 '공급자가 값을 주지 않음' 이다(0% 가 아니다). 저신뢰는 0 < 신뢰도 < 0.7 이고,
// 상담사가 고친 발화(edited_segment_ids)는 확인을 거쳤으므로 저신뢰 표시를 끈다(API_CONTRACT 7절).

import type { Speaker, TranscriptSegment } from "../api/types";
import { NOT_PROVIDED } from "./caseRows";
import { formatClock } from "./time";

export const SPEAKER_LABELS: Record<Speaker, string> = {
  CHILD: "아동",
  COUNSELOR: "상담원",
  GUARDIAN: "보호자",
  OTHER: "기타",
  UNKNOWN: "화자 미확인",
};

/** 화자 고르기 목록의 순서. */
export const SPEAKER_OPTIONS: Speaker[] = ["CHILD", "COUNSELOR", "GUARDIAN", "OTHER", "UNKNOWN"];

/** 저신뢰 기준(API_CONTRACT 7절). 이 값 미만이면서 0 보다 크면 저신뢰. */
export const LOW_CONFIDENCE_THRESHOLD = 0.7;

export function isLowConfidence(confidence: number): boolean {
  return confidence > 0 && confidence < LOW_CONFIDENCE_THRESHOLD;
}

/** "62%". 공급자가 값을 주지 않았으면(0.0) NOT_PROVIDED. */
export function confidenceLabel(confidence: number): string {
  return confidence > 0 ? `${Math.round(confidence * 100)}%` : NOT_PROVIDED;
}

export interface SegmentRow {
  segmentId: string;
  speaker: Speaker;
  speakerLabel: string;
  text: string;
  startMs: number;
  endMs: number;
  /** "01:36". */
  startLabel: string;
  endLabel: string;
  confidence: number;
  confidenceLabel: string;
  /** 저신뢰라 확인이 필요한가. 상담사가 고친 발화는 false. */
  lowConfidence: boolean;
  /** 화자가 UNKNOWN 이라 화자 확인이 필요한가. */
  speakerUnknown: boolean;
  /** 서버에 저장된 상담사 수정이 있는 발화인가. */
  edited: boolean;
  /** 아직 저장하지 않은 수정이 있는가(useTranscriptReview 의 고친 칸). */
  dirty: boolean;
  /** 저장하면 지워질 발화인가. */
  removed: boolean;
}

export function toSegmentRow(source: TranscriptSegment, edited: boolean): SegmentRow {
  return {
    segmentId: source.segment_id,
    speaker: source.speaker,
    speakerLabel: SPEAKER_LABELS[source.speaker] ?? source.speaker,
    text: source.text,
    startMs: source.start_ms,
    endMs: source.end_ms,
    startLabel: formatClock(source.start_ms),
    endLabel: formatClock(source.end_ms),
    confidence: source.confidence,
    confidenceLabel: confidenceLabel(source.confidence),
    lowConfidence: !edited && isLowConfidence(source.confidence),
    speakerUnknown: source.speaker === "UNKNOWN",
    edited,
    dirty: false,
    removed: false,
  };
}
