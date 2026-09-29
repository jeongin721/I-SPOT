// Backend 응답 → 화면이 쓰는 형태로 변환.
//
// 화면(data/cases.ts, data/mockData.ts)의 타입은 mock 데이터 기준으로 먼저 만들어졌고,
// Backend Contract 와 모양이 다르다. 컴포넌트를 전부 고치는 대신 여기서 변환해서
// 기존 화면 코드가 그대로 동작하게 한다.
//
// ⚠️ Backend 에 아직 없는 값은 아래 MISSING 목록에 정리해 두었다.
//    임시값으로 채우되, 무엇이 가짜인지 분명히 표시한다.

import type { CaseRecord, RiskLevel } from "../data/cases";
import type { Session as UiSession } from "../data/mockData";
import { ApiError } from "./client";
import { GUARDIAN_LABELS, TASK_LABELS } from "./types";
import type { Case, Session, SessionStatus, Speaker, TaskItem, Transcript } from "./types";

// =========================================================
// Backend 가 아직 제공하지 않는 값
// =========================================================
//
//  화면 필드          | 상태
//  ------------------|---------------------------------------------------
//  abuseTypes        | 사례 단위로는 없음. AI 분석 결과(abuse_signals)에 있음
//  riskLevel/Score   | 사례 단위로는 없음. 회차별 AI 분석에서 집계해야 함
//  keywords          | Backend 에 없음
//  sessionCount      | 사례 목록 응답에는 없음. 사례 상세(session_count) 또는 회차 목록 meta.total
//
//  해결됨: counselor(이름) → counselor_name
//         guardian       → guardian_type / guardian_note
//
// 위 항목이 필요하면 Backend 에 필드 추가를 요청해야 한다.
// 지금은 화면이 깨지지 않도록 중립값을 넣는다.

/** Backend 가 값을 주지 않아 화면에서 임시로 채운 자리. */
export const NOT_PROVIDED = "—";

// =========================================================
// 사례
// =========================================================

function toAge(birthYear: number | null): number {
  if (!birthYear) return 0;

  return new Date().getFullYear() - birthYear;
}

/**
 * Backend 시각을 Date 로 읽는다.
 *
 * Backend 는 UTC 로 저장하는데, 사례 · 회기 시각은 `2026-09-29T07:04:56` 처럼 시간대 표시 없이
 * 오고(업무 목록의 waiting_since 만 Z 가 붙는다) 브라우저는 이런 문자열을 지역 시각으로 읽는다.
 * 그대로 두면 한국 시간 새벽에 등록한 회기가 전날로 보이므로, 표시가 없으면 UTC 로 본다.
 */
export function parseBackendTime(iso: string): Date | null {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const parsed = new Date(hasZone ? iso : `${iso}Z`);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/** 사용자 시간대의 날짜(YYYY-MM-DD). */
function toDateOnly(iso: string | null): string {
  if (!iso) return "";

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(0, 10);

  return `${at.getFullYear()}-${pad2(at.getMonth() + 1)}-${pad2(at.getDate())}`;
}

/**
 * 보호자를 화면에 보여줄 문자열로 바꾼다.
 * OTHER 는 상담사가 직접 적은 값(guardian_note)을 그대로 쓴다.
 */
export function toGuardianLabel(source: Case): string {
  if (!source.guardian_type) return NOT_PROVIDED;

  if (source.guardian_type === "OTHER") {
    return source.guardian_note || GUARDIAN_LABELS.OTHER;
  }

  return GUARDIAN_LABELS[source.guardian_type];
}

/** 사례 상태: Backend 는 ACTIVE/CLOSED 두 가지뿐이다. */
function toUiCaseStatus(status: Case["status"]): CaseRecord["status"] {
  return status === "CLOSED" ? "pending" : "active";
}

export interface CaseAdapterExtras {
  /** 회차 목록에서 얻은 총 회차 수. 없으면 0. */
  sessionCount?: number;
  /** Backend 의 counselor_name 을 덮어써야 할 때만 쓴다. */
  counselorName?: string;
  /** AI 분석에서 집계한 위험도. 없으면 표시하지 않는다. */
  riskLevel?: RiskLevel;
  riskScore?: number;
}

/**
 * Backend Case 를 화면의 CaseRecord 로 바꾼다.
 *
 * Backend 에 없는 값은 extras 로 채워 넣을 수 있고, 채우지 않으면 빈 값이 된다.
 * child_alias 는 실명이 아니라 별칭이다(Backend 는 아동 실명을 저장하지 않는다).
 */
export function toUiCase(source: Case, extras: CaseAdapterExtras = {}): CaseRecord {
  return {
    id: source.case_number,
    childName: source.child_alias,
    age: toAge(source.child_birth_year),
    guardian: toGuardianLabel(source),
    abuseTypes: [],
    riskLevel: extras.riskLevel ?? "low",
    riskScore: extras.riskScore ?? 0,
    lastSession: toDateOnly(source.last_session_at),
    sessionCount: extras.sessionCount ?? 0,
    counselor: extras.counselorName ?? source.counselor_name ?? NOT_PROVIDED,
    status: toUiCaseStatus(source.status),
    keywords: [],
  };
}

/** 화면에서 사례를 다시 조회할 때 필요한 실제 id(UUID)를 함께 들고 다니기 위한 형태. */
export interface CaseWithId extends CaseRecord {
  /** Backend 조회에 쓰는 UUID. 화면에 보이는 id(case_number)와 다르다. */
  backendId: string;
}

export function toUiCaseWithId(source: Case, extras: CaseAdapterExtras = {}): CaseWithId {
  return { ...toUiCase(source, extras), backendId: source.id };
}

// =========================================================
// 회차 상태
// =========================================================
//
// Backend 는 회차 상태를 하나로 관리하고, 화면은 STT/AI/기록 세 갈래로 나눠 보여준다.
// 하나의 Backend 상태에서 세 값을 유도한다.

type UiSttStatus = UiSession["sttStatus"];
type UiAiStatus = UiSession["aiStatus"];
type UiRecordStatus = UiSession["recordStatus"];

interface DerivedStatus {
  stt: UiSttStatus;
  ai: UiAiStatus;
  record: UiRecordStatus;
  /** 실패 상태인가. 화면 타입에는 실패 표현이 없어 별도로 알린다. */
  failed: boolean;
  /** 실패나 진행 상황을 사람에게 보여줄 문구. */
  label: string;
}

const STATUS_MAP: Record<SessionStatus, DerivedStatus> = {
  CREATED: {
    stt: "처리중", ai: "대기중", record: "미작성", failed: false, label: "음성 업로드 대기",
  },
  AUDIO_UPLOADED: {
    stt: "처리중", ai: "대기중", record: "미작성", failed: false, label: "STT 실행 대기",
  },
  STT_PROCESSING: {
    stt: "처리중", ai: "대기중", record: "미작성", failed: false, label: "받아쓰는 중",
  },
  STT_REVIEW_REQUIRED: {
    stt: "검수필요", ai: "대기중", record: "미작성", failed: false, label: "원문 검수 필요",
  },
  STT_CONFIRMED: {
    stt: "검수완료", ai: "대기중", record: "미작성", failed: false, label: "AI 분석 대기",
  },
  AI_PROCESSING: {
    stt: "검수완료", ai: "분석중", record: "미작성", failed: false, label: "AI 분석 중",
  },
  AI_REVIEW_REQUIRED: {
    stt: "검수완료", ai: "검토필요", record: "작성중", failed: false, label: "AI 결과 검수 필요",
  },
  APPROVED: {
    stt: "분석완료", ai: "상담사검토완료", record: "상담사검토완료", failed: false, label: "승인 완료",
  },
  STT_FAILED: {
    stt: "처리중", ai: "대기중", record: "미작성", failed: true, label: "STT 실패 — 재시도 필요",
  },
  AI_FAILED: {
    stt: "검수완료", ai: "대기중", record: "미작성", failed: true, label: "AI 분석 실패 — 재시도 필요",
  },
};

export function deriveStatus(status: SessionStatus): DerivedStatus {
  return STATUS_MAP[status];
}

/** 다음에 해야 할 행동. 버튼 활성화 판단에 쓴다. */
export function nextAction(status: SessionStatus): string {
  switch (status) {
    case "CREATED":
      return "음성 업로드";
    case "AUDIO_UPLOADED":
    case "STT_FAILED":
      return "STT 실행";
    case "STT_PROCESSING":
    case "AI_PROCESSING":
      return "처리 중";
    case "STT_REVIEW_REQUIRED":
      return "원문 검수";
    case "STT_CONFIRMED":
    case "AI_FAILED":
      return "AI 분석 실행";
    case "AI_REVIEW_REQUIRED":
      return "요약 검수";
    case "APPROVED":
      return "완료";
  }
}

// =========================================================
// 회차
// =========================================================

/** 사용자 시간대의 시각(HH:MM). */
function toTimePart(iso: string | null): string {
  if (!iso) return "";

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(11, 16);

  return `${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
}

export interface SessionAdapterExtras {
  counselorName?: string;
  /** 상담 유형은 Backend 에 없다. 화면 기본값을 쓴다. */
  type?: UiSession["type"];
  durationLabel?: string;
}

/** Backend Session 을 화면의 Session 으로 바꾼다. */
export function toUiSession(
  source: Session,
  caseNumber: string,
  extras: SessionAdapterExtras = {},
): UiSession {
  const derived = deriveStatus(source.status);
  const at = source.consulted_at ?? source.created_at;

  return {
    id: source.id,
    caseId: caseNumber,
    date: toDateOnly(at),
    time: toTimePart(at),
    sessionNumber: source.session_number,
    counselor: extras.counselorName ?? NOT_PROVIDED,
    duration: extras.durationLabel ?? NOT_PROVIDED,
    type: extras.type ?? "정기상담",
    location: source.location ?? NOT_PROVIDED,
    sttStatus: derived.stt,
    aiStatus: derived.ai,
    recordStatus: derived.record,
  };
}

// =========================================================
// ===== 사례 · 회기 화면 (갈래 A) =====
// =========================================================
//
// 사례 상세 · 회기 목록 · 회기 등록 화면이 함께 쓰는 변환.
// 회차 수(session_count)는 사례 상세(GET /cases/{id}) 응답에만 있어 여기서 채운다.
// 담당 상담사 이름은 toUiCase 가 counselor_name 에서 읽는다.

/** 사례 상세 응답을 화면의 CaseWithId 로 바꾼다. CaseDetail 을 그대로 넘기면 된다. */
export function toUiCaseDetail(source: Case & { session_count: number }): CaseWithId {
  return toUiCaseWithId(source, { sessionCount: source.session_count });
}

// =========================================================
// ===== 전사 검수 · 음성 업로드 =====
//
// TranscriptReviewView · UploadModal · STTCaseSelectorPage 가 쓰는 변환.

/**
 * 사례 · 회기 자체가 없거나 남의 것일 때의 오류 코드. 같은 403/404 라도 AUDIO_NOT_FOUND ·
 * TRANSCRIPT_NOT_FOUND 는 "음성이 없다" 같은 다른 뜻이라 서버 문구를 그대로 보여 준다.
 */
const MISSING_RESOURCE_CODES = new Set(["FORBIDDEN", "NOT_FOUND", "CASE_NOT_FOUND", "SESSION_NOT_FOUND"]);

/**
 * ApiError 를 화면 문구로 바꾼다.
 * 남의 자료거나 없는 자료(403/404)는 서버 문구 대신 한 가지 안내로 통일한다.
 */
export function describeApiError(
  caught: unknown,
  fallback: string,
  forbiddenMessage = "권한이 없거나 없는 사례입니다.",
): string {
  if (!(caught instanceof ApiError)) return fallback;

  if (caught.isForbidden && MISSING_RESOURCE_CODES.has(caught.code)) return forbiddenMessage;

  return caught.message;
}

/** 화자 코드 → 화면 이름. */
export const SPEAKER_LABELS: Record<Speaker, string> = {
  COUNSELOR: "상담사",
  CHILD: "아동",
  GUARDIAN: "보호자",
  OTHER: "기타",
  UNKNOWN: "미확인",
};

/** ms → "mm:ss". 한 시간을 넘으면 "h:mm:ss". */
export function toTimestamp(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const mmss = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

  return h > 0 ? `${h}:${mmss}` : mmss;
}

/**
 * Backend 가 전사본에 덧붙여 주는 아동 발화 인수인계 보기(child_handoff).
 *
 * types.ts 의 Transcript 와 API_CONTRACT.md 7절에는 아직 없는 필드라 여기서만 읽는다.
 * review_needed_segments 는 화자가 불확실해 사람이 확인해야 하는 발화다.
 */
interface ChildHandoffSegment {
  segment_id: string;
  text: string;
  start_ms: number;
  end_ms: number;
}

interface ChildHandoffReviewSegment extends ChildHandoffSegment {
  reason: string;
}

export interface ChildHandoff {
  child_analysis_text: string;
  confirmed_child_segments: ChildHandoffSegment[];
  review_needed_segments: ChildHandoffReviewSegment[];
}

type TranscriptWithHandoff = Transcript & { child_handoff?: ChildHandoff | null };

/** child_handoff 의 사유 코드 → 화면 문구. 모르는 코드는 그대로 보여 준다. */
const REVIEW_REASON_LABELS: Record<string, string> = {
  UNRESOLVED_SPEAKER: "화자 확인 필요",
};

/** 전사 검수 화면의 발화 한 줄. */
export interface UiTranscriptSegment {
  /** Backend 의 segment_id. 수정 요청에 그대로 쓴다. */
  id: string;
  speaker: Speaker;
  speakerLabel: string;
  /** "mm:ss" 로 표시한 시작 시각. */
  timestamp: string;
  startMs: number;
  endMs: number;
  text: string;
  confidence: number;
  /** 상담사가 이미 고친 발화인가(edited_segment_ids). */
  edited: boolean;
  /** child_handoff 가 사람 확인이 필요하다고 표시한 사유. 없으면 null. */
  reviewReason: string | null;
}

/** Backend Transcript 의 발화 목록을 화면 형태로 바꾼다. 순서는 시작 시각 순으로 맞춘다. */
export function toUiTranscriptSegments(source: Transcript): UiTranscriptSegment[] {
  const edited = new Set(source.edited_segment_ids);
  const reasons = new Map<string, string>();

  for (const item of (source as TranscriptWithHandoff).child_handoff?.review_needed_segments ?? []) {
    reasons.set(item.segment_id, REVIEW_REASON_LABELS[item.reason] ?? item.reason);
  }

  return [...source.segments]
    .sort((a, b) => a.start_ms - b.start_ms)
    .map((seg) => ({
      id: seg.segment_id,
      speaker: seg.speaker,
      speakerLabel: SPEAKER_LABELS[seg.speaker] ?? seg.speaker,
      timestamp: toTimestamp(seg.start_ms),
      startMs: seg.start_ms,
      endMs: seg.end_ms,
      text: seg.text,
      confidence: seg.confidence,
      edited: edited.has(seg.segment_id),
      reviewReason: reasons.get(seg.segment_id) ?? null,
    }));
}

/** 상담 자료 검수 목록(처리 대기 업무) 한 줄. */
export interface UiTaskRow {
  sessionId: string;
  /** Backend 사례 UUID. 주소에 쓴다. */
  caseId: string;
  /** 화면에 보이는 사례번호. */
  caseNumber: string;
  childName: string;
  sessionNumber: number;
  sessionTitle: string;
  /** 업무 이름(TASK_LABELS). */
  taskLabel: string;
  /** 회기 상태를 사람에게 보여줄 문구. */
  statusLabel: string;
  /** 기다리기 시작한 날짜(YYYY-MM-DD). */
  waitingSince: string;
  isOverdue: boolean;
  counselor: string;
}

export function toUiTaskRow(item: TaskItem): UiTaskRow {
  return {
    sessionId: item.session_id,
    caseId: item.case_id,
    caseNumber: item.case_number,
    childName: item.child_alias,
    sessionNumber: item.session_number,
    sessionTitle: item.session_title ?? "",
    taskLabel: TASK_LABELS[item.task_type],
    statusLabel: deriveStatus(item.session_status).label,
    waitingSince: toDateOnly(item.waiting_since),
    isOverdue: item.is_overdue,
    counselor: item.counselor_name ?? NOT_PROVIDED,
  };
}
