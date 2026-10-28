// 구간별 음성 참고 표시(VoiceMarks) → 원문 검수 화면의 줄별 표시(칩)와 요약 문장.
//
// 표시 규칙(API_CONTRACT 16절 · I-SPOT_DOCS/docs/PROPOSAL_voice_marks.md §4):
//  - flag 가 true 인 지표만 칩으로 보인다(아이콘 대신 글자 — 색만으로 구분하지 않는다). 기준값은 응답의 thresholds 에
//    들어 있고 flag 가 이미 그 기준으로 계산돼 있어 여기서 숫자를 다시 비교하지 않는다.
//  - "탐지 없음" 은 ANALYZED 이면서 flag 가 모두 false 인 것이라 줄에는 아무것도 안 보이고, UNDETERMINED(분석하지 못함)는
//    이유를 사람 말로 바꿔 작은 칩으로 보인다. 둘을 같은 모양으로 보이지 않는다.
//  - 결과의 speaker 는 분석 당시 값이라 참고만 하고, 줄이 아동인지는 지금 원문의 화자로 본다.
//  - 0~1 점수 · % · 위험도 같은 값은 만들지 않는다. "판정" 이라는 말도 쓰지 않는다.

import type { VoiceMarkMetric, VoiceMarkSegment, VoiceMarks } from "../api/types";

/** 지표 이름(줄의 칩에 쓴다). */
export const METRIC_LABELS = {
  tremor: "목소리 떨림",
  mumble: "웅얼거림",
  soft: "작게 말함",
} as const;

export type MetricKey = keyof typeof METRIC_LABELS;

const METRIC_KEYS: MetricKey[] = ["tremor", "mumble", "soft"];

/** UNDETERMINED 이유 코드 → 사람 말(stt/voice_marks.md 5절). 모르는 코드는 그대로 보인다. */
export const REASON_LABELS: Record<string, string> = {
  TOO_SHORT: "구간이 1초보다 짧음",
  NO_VOICED_FRAMES: "소리가 나는 부분이 없음",
  NOT_CHILD_SEGMENT: "분석 당시 아동 발화가 아니었음",
  TOO_FEW_CHILD_SEGMENTS: "비교할 아동 발화가 8개보다 적음",
  NO_REFERENCE: "값이 거의 같아 비교 기준을 만들 수 없음",
  INVALID_TIME_RANGE: "구간 시각이 맞지 않음",
  DECODE_FAILED: "이 음성 형식은 읽을 수 없음(wav · flac · ogg · mp3 만)",
  AUDIO_TOO_LONG: "음성이 60분을 넘음",
  ANALYSIS_ERROR: "분석 중 오류",
};

export function reasonLabel(reason: string | null): string {
  if (!reason) return "";

  return Object.prototype.hasOwnProperty.call(REASON_LABELS, reason) ? REASON_LABELS[reason] : reason;
}

/** 줄에 보이는 칩 하나. */
export interface VoiceCue {
  key: string;
  /** "목소리 떨림" 같은 이름. */
  name: string;
  /** 이 녹음의 아동 발화끼리 비교한 상대값("z +2.1"). 모르면 "". */
  num: string;
  /** 단추 설명(값 · 단위). */
  title: string;
}

export interface SegmentMarks {
  segmentId: string;
  status: VoiceMarkSegment["status"];
  reason: string | null;
  /** flag 가 true 인 지표의 칩. */
  cues: VoiceCue[];
  /** 분석 당시 구간 시각. 지금 원문의 시각과 다르면 '분석 당시 시각 기준' 안내에 쓴다. */
  startMs: number;
  endMs: number;
  /** 분석 당시 화자. */
  speaker: string;
}

function formatZ(z: number | null): string {
  if (z === null || !Number.isFinite(z)) return "";

  return `z ${z >= 0 ? "+" : "−"}${Math.abs(z).toFixed(1)}`;
}

function metricCue(key: MetricKey, metric: VoiceMarkMetric | null): VoiceCue | null {
  if (!metric || typeof metric !== "object" || metric.flag !== true) return null;

  const value =
    typeof metric.value === "number" && Number.isFinite(metric.value) ? `${metric.value.toFixed(1)} ${metric.unit}` : "";
  const num = formatZ(typeof metric.z === "number" ? metric.z : null);

  return {
    key,
    name: METRIC_LABELS[key],
    num,
    title: [METRIC_LABELS[key], value, num ? `이 녹음의 아동 발화 기준 ${num}` : ""].filter(Boolean).join(" · "),
  };
}

function isSegment(value: unknown): value is VoiceMarkSegment {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;

  return typeof item.segment_id === "string" && (item.status === "ANALYZED" || item.status === "UNDETERMINED");
}

/** 결과의 segments → 발화 ID 별 표시. 모양이 어긋난 항목은 건너뛴다(화면이 멈추지 않게). */
export function marksBySegment(marks: VoiceMarks | null): Map<string, SegmentMarks> {
  const map = new Map<string, SegmentMarks>();
  const segments = marks?.result?.segments;

  if (!Array.isArray(segments)) return map;

  for (const segment of segments) {
    if (!isSegment(segment) || map.has(segment.segment_id)) continue;

    const cues = METRIC_KEYS.map((key) => metricCue(key, segment[key])).filter((cue): cue is VoiceCue => cue !== null);

    map.set(segment.segment_id, {
      segmentId: segment.segment_id,
      status: segment.status,
      reason: typeof segment.reason === "string" ? segment.reason : null,
      cues,
      startMs: typeof segment.start_ms === "number" ? segment.start_ms : -1,
      endMs: typeof segment.end_ms === "number" ? segment.end_ms : -1,
      speaker: typeof segment.speaker === "string" ? segment.speaker : "",
    });
  }

  return map;
}

export interface VoiceMarksSummary {
  /** none 분석 전(결과 없음) · undetermined 녹음 전체가 분석 불가 · analyzed 분석됨. */
  kind: "none" | "undetermined" | "analyzed";
  /** 범례에 보이는 한 문장. */
  text: string;
  /** 결과의 원문 판이 지금 보는 원문 판과 다를 때의 안내. 같거나 모르면 "". */
  versionNote: string;
  /** 표시가 하나라도 있는 구간 수. */
  flagged: number;
}

/**
 * 범례 요약. 원문 판이 다르면(검수에서 고친 뒤 아직 재분석 전, 또는 재분석이 필요 없는 수정) 그 사실을 함께 적는다.
 * 한계 안내(상대 비교 · 문제가 없는 녹음에도 표시될 수 있음 · 떨림은 놓치는 경우가 많음)는 화면 범례의 고정 문장이다.
 */
export function voiceMarksSummary(
  marks: VoiceMarks | null,
  currentVersion: number | null,
  waiting: boolean,
): VoiceMarksSummary {
  if (marks === null) {
    return {
      kind: "none",
      text: waiting ? "분석 전입니다. 원문 변환이 끝난 뒤 곧 계산됩니다." : "분석 결과가 없습니다.",
      versionNote: "",
      flagged: 0,
    };
  }

  const result = marks.result;
  const versionNote =
    currentVersion !== null && marks.transcript_version !== null && marks.transcript_version !== currentVersion
      ? `원문 ${marks.transcript_version}판 기준입니다(지금 ${currentVersion}판). 화자 · 시각을 고쳐 확정하면 다시 계산합니다.`
      : "";

  if (!result || result.status !== "ANALYZED") {
    return {
      kind: "undetermined",
      text: `분석 불가 · ${reasonLabel(result?.reason ?? null) || "이유 없음"}`,
      versionNote,
      flagged: 0,
    };
  }

  const segments = Array.isArray(result.segments) ? result.segments : [];
  const flagged = segments.filter((segment) => segment && segment.flag_any === true).length;
  const total = result.reference?.child_segments_total ?? 0;
  const used = result.reference?.child_segments_used ?? 0;

  return {
    kind: "analyzed",
    text: `아동 발화 ${total}개 중 ${used}개를 비교해 ${flagged}곳에 표시했습니다.`,
    versionNote,
    flagged,
  };
}
