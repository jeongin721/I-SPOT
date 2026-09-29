// AI 분석 흐름 화면(사례 선택 · 분석 목록 · 분석 결과 검토)이 쓰는 변환.
//
// adapters.ts 의 공용 변환(deriveStatus · toUiCaseWithId · toUiTranscriptSegments)을 가져다 쓰고,
// AI 분석 화면에만 필요한 것만 여기에 둔다.
//
// ⚠️ AI 결과는 판정이 아니라 참고정보다. 화면 문구는 "관련 신호", "추가 확인 필요",
//    "근거 발화", "상담사 검토 필요" 로 쓰고 "확정" · "판정" 표현을 쓰지 않는다.

import { NOT_PROVIDED, deriveStatus, toUiCaseWithId, type CaseWithId, type UiTranscriptSegment } from "./adapters";
import type {
  AnalysisResult,
  Case,
  Session,
  SessionStatus,
  Summary,
  SummaryEvidenceItem,
  SummaryUpdateRequest,
  TaskItem,
  TaskType,
} from "./types";

// =========================================================
// 시각
// =========================================================

// adapters.ts 의 parseBackendTime 과 같은 규칙이다(그 함수는 내보내지 않아 여기 따로 둔다).
// 사례 · 회기 시각은 시간대 표시 없이 UTC 로 오므로, 표시가 없으면 UTC 로 읽는다.
function parseBackendTime(iso: string): Date | null {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const parsed = new Date(hasZone ? iso : `${iso}Z`);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/** 사용자 시간대의 날짜(YYYY-MM-DD). 값이 없으면 NOT_PROVIDED. */
export function toLocalDate(iso: string | null): string {
  if (!iso) return NOT_PROVIDED;

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(0, 10);

  return `${at.getFullYear()}-${pad2(at.getMonth() + 1)}-${pad2(at.getDate())}`;
}

/** 사용자 시간대의 날짜와 시각(YYYY-MM-DD HH:MM). 값이 없으면 NOT_PROVIDED. */
export function toLocalDateTime(iso: string | null): string {
  if (!iso) return NOT_PROVIDED;

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(0, 16).replace("T", " ");

  return `${toLocalDate(iso)} ${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
}

// =========================================================
// 사례 선택 (AIAnalysisSelectorPage)
// =========================================================

/** AI 분석 화면에서 처리할 업무. 분석 요청 · 결과 검토 · 실패 뒤 재요청. */
export const AI_TASK_TYPES: TaskType[] = ["REQUEST_ANALYSIS", "REVIEW_ANALYSIS", "RETRY_ANALYSIS"];

/** 사례 하나에 걸린 AI 분석 대기 업무 수. */
export interface AiPendingCount {
  /** 분석 요청 대기(STT 확정 뒤). */
  request: number;
  /** 결과 검토 대기. */
  review: number;
  /** 분석 실패 — 다시 요청 필요. */
  retry: number;
  total: number;
  /** 가장 오래 기다린 업무의 시작 시각(UTC). 없으면 null. */
  oldestWaiting: string | null;
}

const EMPTY_PENDING: AiPendingCount = { request: 0, review: 0, retry: 0, total: 0, oldestWaiting: null };

/** 처리 대기 업무를 사례별로 센다. AI 분석 업무가 아닌 것은 건너뛴다. */
export function countAiTasksByCase(items: TaskItem[]): Map<string, AiPendingCount> {
  const counts = new Map<string, AiPendingCount>();

  for (const item of items) {
    if (!AI_TASK_TYPES.includes(item.task_type)) continue;

    const current = { ...(counts.get(item.case_id) ?? EMPTY_PENDING) };

    if (item.task_type === "REQUEST_ANALYSIS") current.request += 1;
    else if (item.task_type === "REVIEW_ANALYSIS") current.review += 1;
    else current.retry += 1;

    current.total += 1;

    // waiting_since 는 항상 Z 로 끝나는 같은 형식이라 문자열 비교로 순서를 정할 수 있다.
    if (current.oldestWaiting === null || item.waiting_since < current.oldestWaiting) {
      current.oldestWaiting = item.waiting_since;
    }

    counts.set(item.case_id, current);
  }

  return counts;
}

/** 대기 업무 수를 한 줄로 풀어 쓴 것. 배지의 설명(title)에 쓴다. */
export function describePending(pending: AiPendingCount): string {
  const parts: string[] = [];

  if (pending.review > 0) parts.push(`결과 검토 ${pending.review}`);
  if (pending.request > 0) parts.push(`분석 요청 ${pending.request}`);
  if (pending.retry > 0) parts.push(`재요청 ${pending.retry}`);

  return parts.join(" · ");
}

/** AI 분석 사례 선택 목록의 한 줄. */
export interface UiAiCaseRow extends CaseWithId {
  pending: AiPendingCount;
}

/**
 * 사례 목록과 처리 대기 업무를 합쳐 사례 선택 목록을 만든다.
 * 대기 업무가 많은 사례가 먼저, 같으면 가장 오래 기다린 업무가 있는 사례가 먼저 온다.
 */
export function toUiAiCaseRows(caseItems: Case[], taskItems: TaskItem[]): UiAiCaseRow[] {
  const counts = countAiTasksByCase(taskItems);

  const rows = caseItems.map((source) => ({
    ...toUiCaseWithId(source),
    pending: counts.get(source.id) ?? EMPTY_PENDING,
  }));

  return rows.sort((a, b) => {
    if (b.pending.total !== a.pending.total) return b.pending.total - a.pending.total;

    const aWait = a.pending.oldestWaiting;
    const bWait = b.pending.oldestWaiting;

    if (aWait && bWait) return aWait.localeCompare(bWait);

    return 0;
  });
}

// =========================================================
// 분석 목록 (AIAnalysisListPage)
// =========================================================

/** 회기 하나의 AI 분석 상태 한 줄. AI 분석은 회기당 하나라 회기 목록을 그대로 쓴다. */
export interface UiAnalysisRow {
  /** Backend 회기 UUID. 분석 검토 주소의 analysisId 자리에 쓴다. */
  sessionId: string;
  sessionNumber: number;
  sessionTitle: string;
  /** AI 분석이 끝난 날짜(없으면 시작한 날짜). 분석 전이면 NOT_PROVIDED. */
  analysisDate: string;
  /** 분석 상태 배지 문구(adapters.deriveStatus 의 ai). 분석 실패는 따로 표시한다. */
  aiLabel: string;
  /** 회기 진행 상황을 사람에게 보여줄 문구. */
  statusLabel: string;
  failed: boolean;
}

export function toUiAnalysisRow(source: Session): UiAnalysisRow {
  const derived = deriveStatus(source.status);

  return {
    sessionId: source.id,
    sessionNumber: source.session_number,
    sessionTitle: source.title ?? "",
    analysisDate: toLocalDate(source.ai_completed_at ?? source.ai_started_at),
    aiLabel: source.status === "AI_FAILED" ? "분석 실패" : derived.ai,
    statusLabel: derived.label,
    failed: derived.failed,
  };
}

// =========================================================
// 분석 결과 검토 (AIReviewView)
// =========================================================

/**
 * 회기 상태별로 검토 화면이 보여 줄 단계.
 *
 * - beforeStt: 전사 검수를 마치기 전(STT 실패 포함) — 전사 검수 화면으로 안내
 * - ready: 전사본 확정, 분석 요청 전 — "AI 분석 요청" 버튼
 * - processing: 분석 중 — 2초 간격으로 다시 확인
 * - failed: 분석 실패 — 오류 문구와 다시 요청
 * - review: 결과 검토 · 수정 · 승인
 * - approved: 승인 완료 — 읽기 전용
 */
export type ReviewStage = "beforeStt" | "ready" | "processing" | "failed" | "review" | "approved";

export function toReviewStage(status: SessionStatus): ReviewStage {
  switch (status) {
    case "STT_CONFIRMED":
      return "ready";
    case "AI_PROCESSING":
      return "processing";
    case "AI_FAILED":
      return "failed";
    case "AI_REVIEW_REQUIRED":
      return "review";
    case "APPROVED":
      return "approved";
    default:
      return "beforeStt";
  }
}

/**
 * AI 결과의 위험 관련 항목 하나.
 *
 * risk_utterances · abuse_signals · risk_factors 의 항목 구조는 아직 팀 합의 전이라
 * (PROPOSAL_risk_fields.md §7) Backend 는 객체를 그대로 넘긴다. 그래서 필드를 하나씩 확인하며 읽는다.
 * types.ts 는 abuse_signals · risk_factors 를 string[] 로 적어 두었지만 실제로는 객체 배열이다.
 */
type LooseItem = Record<string, unknown>;

function asItems(value: unknown): LooseItem[] {
  if (!Array.isArray(value)) return [];

  return value.filter((item): item is LooseItem => typeof item === "object" && item !== null);
}

function readString(item: LooseItem, key: string): string | null {
  const value = item[key];

  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** 항목이 근거로 든 발화 번호. segment_id(단수)와 segment_ids(복수)를 모두 본다. */
function readSegmentIds(item: LooseItem): string[] {
  const ids: string[] = [];
  const single = item.segment_id;
  const many = item.segment_ids;

  if (typeof single === "string" && single) ids.push(single);

  if (Array.isArray(many)) {
    for (const id of many) {
      if (typeof id === "string" && id && !ids.includes(id)) ids.push(id);
    }
  }

  return ids;
}

/** 추가 확인이 필요하다고 AI 가 표시한 발화 하나. */
export interface UiRiskUtterance {
  segmentId: string;
  /** AI 가 든 발화 문장. 없으면 전사본의 같은 발화 문장. */
  text: string;
  /** AI 가 든 사유. 없으면 빈 문자열. */
  reason: string;
  /** 전사본에서 찾은 시작 시각. 전사본에 없는 번호면 빈 문자열. */
  timestamp: string;
}

/**
 * risk_utterances 를 화면 형태로 바꾼다. 근거 발화 번호가 없는 항목은 보여 주지 않는다
 * (05_RULES.md "근거 없는 위험 신호를 생성하지 않는다").
 */
export function toUiRiskUtterances(
  result: AnalysisResult | null,
  segments: UiTranscriptSegment[],
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
      });
    }
  }

  return rows;
}

/** 학대유형 대분류 → 화면 이름. Contract 는 영문 대문자로 오고 한글은 화면에서만 쓴다. */
const ABUSE_TYPE_LABELS: Record<string, string> = {
  PHYSICAL: "신체적 위해",
  EMOTIONAL: "정서적 위해",
  SEXUAL: "성적 위해",
  NEGLECT: "방임",
};

/** abuse_signals · risk_factors 한 줄. 판정이 아니라 추가 확인이 필요한 참고정보다. */
export interface UiReferenceSignal {
  key: string;
  label: string;
  segmentIds: string[];
}

/**
 * abuse_signals · risk_factors 를 화면에 보여 줄 참고정보 목록으로 바꾼다.
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

    const type = readString(item, "abuse_type");
    const typeLabel = type ? ABUSE_TYPE_LABELS[type] ?? type : "학대유형 미표기";

    rows.push({ key: `signal-${index}`, label: `${typeLabel} 관련 신호`, segmentIds });
  });

  asItems(result.risk_factors).forEach((item, index) => {
    const segmentIds = readSegmentIds(item);

    if (segmentIds.length === 0) return;

    const label = readString(item, "label") ?? readString(item, "code") ?? "위험요인";

    rows.push({ key: `factor-${index}`, label: `위험요인: ${label}`, segmentIds });
  });

  return rows;
}

/** 강조해서 보여 줄 발화 번호(위험 관련 발화로 표시된 것). */
export function riskSegmentIdSet(utterances: UiRiskUtterance[]): Set<string> {
  return new Set(utterances.map((item) => item.segmentId));
}

/** 요약 항목과 근거 발화. 근거 발화는 시작 시각과 화자로 보여 준다. */
export interface UiEvidence {
  key: string;
  keyPoint: string;
  segmentIds: string[];
  /** "00:08 아동" 같은 짧은 표시. 전사본에 없는 번호는 번호 그대로. */
  refs: string[];
}

export function toUiEvidence(
  evidence: SummaryEvidenceItem[],
  segments: UiTranscriptSegment[],
): UiEvidence[] {
  const byId = new Map(segments.map((seg) => [seg.id, seg]));

  return evidence
    .filter((item) => item.segment_ids.length > 0)
    .map((item, index) => ({
      key: `evidence-${index}`,
      keyPoint: item.key_point,
      segmentIds: item.segment_ids,
      refs: item.segment_ids.map((id) => {
        const seg = byId.get(id);

        return seg ? `${seg.timestamp} ${seg.speakerLabel}` : id;
      }),
    }));
}

// =========================================================
// 요약 편집
// =========================================================

/** 요약 편집 칸의 값. key_points 는 한 줄에 하나씩 적는다. */
export interface SummaryDraft {
  overview: string;
  keyPointsText: string;
  counselorNote: string;
}

export function toSummaryDraft(source: Summary | null): SummaryDraft {
  return {
    overview: source?.overview ?? "",
    keyPointsText: (source?.key_points ?? []).join("\n"),
    counselorNote: source?.counselor_note ?? "",
  };
}

/** 한 줄에 하나씩 적은 주요 내용을 배열로 바꾼다. 빈 줄은 뺀다. */
export function toKeyPoints(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

/**
 * 원래 요약과 편집 칸을 비교해 바뀐 필드만 담은 수정 요청을 만든다.
 * 바뀐 것이 없으면 null(Backend 는 빈 요청을 422 로 거절한다).
 */
export function toSummaryUpdate(source: Summary, draft: SummaryDraft): SummaryUpdateRequest | null {
  const payload: SummaryUpdateRequest = {};

  if (draft.overview !== source.overview) payload.overview = draft.overview;

  const keyPoints = toKeyPoints(draft.keyPointsText);

  if (keyPoints.join("\n") !== source.key_points.join("\n")) payload.key_points = keyPoints;

  if (draft.counselorNote !== (source.counselor_note ?? "")) payload.counselor_note = draft.counselorNote;

  return Object.keys(payload).length > 0 ? payload : null;
}
