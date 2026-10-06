// 대시보드 · 사례 관리 · 후속 관리 · 메뉴 배지가 쓰는 변환.
//
// 공통 변환(adapters.ts)은 가져다 쓰기만 하고, 이 화면들에만 필요한 것은 여기에 둔다.
// Backend 에 없는 값은 NOT_PROVIDED("—")로 두고 그럴듯한 기본값을 만들지 않는다.
// (adapters.toUiSession 은 상담 유형을 "정기상담" 으로 채우므로 이 화면들에서는 쓰지 않는다.
//  확인하지 않은 상담 유형이 "정기상담" 으로 보이기 때문이다.
//  adapters.toUiCase 의 위험도는 서버 값이 없으면 비워 두고, RiskBadge 가 "—" 로 그린다.)

import { NOT_PROVIDED, deriveStatus, toGuardianLabel, toUiTaskRow, toUiTranscriptSegments, pad2, parseBackendTime } from "./adapters";
import type { UiTaskRow, UiTranscriptSegment } from "./adapters";
import type {
  AnalysisResult,
  Case,
  Session,
  SessionStatus,
  Summary,
  TaskItem,
  TaskSummary,
  TaskType,
  Transcript,
} from "./types";

// =========================================================
// 시각
// =========================================================
//
// 시간대 규칙은 adapters.parseBackendTime 하나를 쓴다.
// Backend 는 UTC 로 저장하는데 사례 · 회기 시각은 시간대 표시 없이 온다(업무의 waiting_since 만 Z).
// 표시가 없으면 UTC 로 읽어야 한국 시간 새벽 기록이 전날로 보이지 않는다.

/** 사용자 시간대의 날짜(YYYY-MM-DD). 값이 없으면 빈 문자열. */
export function toLocalDate(iso: string | null): string {
  if (!iso) return "";

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(0, 10);

  return `${at.getFullYear()}-${pad2(at.getMonth() + 1)}-${pad2(at.getDate())}`;
}

/** 사용자 시간대의 시각(HH:MM). 값이 없으면 빈 문자열. */
export function toLocalTime(iso: string | null): string {
  if (!iso) return "";

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(11, 16);

  return `${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
}

/** 정렬용 숫자. 값이 없으면 가장 오래된 것으로 본다. */
function toSortTime(iso: string | null): number {
  if (!iso) return 0;

  return parseBackendTime(iso)?.getTime() ?? 0;
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** 대시보드 제목 아래 날짜. 예: "2026년 9월 29일 화요일" */
export function toKoreanDateHeading(now: Date): string {
  return `${now.getFullYear()}년 ${now.getMonth() + 1}월 ${now.getDate()}일 ${WEEKDAYS[now.getDay()]}요일`;
}

// =========================================================
// 로그인 사용자
// =========================================================

/** 로그인 화면이 저장해 둔 이름 · 역할(client.SESSION_INFO_KEY). 역할 값은 "counselor" | "admin". */
export interface SignedInUser {
  name: string;
  isAdmin: boolean;
}

export function readSignedInUser(raw: string | null): SignedInUser {
  try {
    const parsed = JSON.parse(raw ?? "{}") as { name?: string; role?: string };

    return { name: parsed.name ?? "", isAdmin: parsed.role === "admin" };
  } catch {
    return { name: "", isAdmin: false };
  }
}

// =========================================================
// 처리 대기 업무
// =========================================================

/**
 * 업무 종류별로 처리할 화면 주소. 주소의 사례 · 회기는 Backend UUID 다.
 * AI 분석은 회기당 하나라 분석 화면 주소의 analysisId 자리에 회기 UUID 를 쓴다.
 * 원문 변환 요청 · 재시도는 전사 검수 화면의 "원문 변환 (다시) 요청" 버튼으로 처리한다.
 * 녹음 업로드는 음성을 올릴 수 있는 업로드 창이 상담 자료 검수(상담 자료 업로드)에만 있어서 그리로 보낸다
 * (사례 상세의 업로드 창은 문서용이다).
 */
export function toTaskLink(item: Pick<TaskItem, "task_type" | "case_id" | "session_id">): string {
  switch (item.task_type) {
    case "REVIEW_TRANSCRIPT":
    case "REQUEST_STT":
    case "RETRY_STT":
      return `/cases/${item.case_id}/sessions/${item.session_id}/transcript`;
    case "REQUEST_ANALYSIS":
    case "REVIEW_ANALYSIS":
    case "RETRY_ANALYSIS":
      return `/cases/${item.case_id}/analyses/${item.session_id}`;
    case "UPLOAD_AUDIO":
      return "/stt-cases";
  }
}

/** 대시보드 · 후속 관리의 업무 한 줄. 검수 목록과 같은 모양에 이동할 주소만 더했다. */
export interface DashboardTaskRow extends UiTaskRow {
  taskType: TaskType;
  link: string;
}

export function toDashboardTaskRow(item: TaskItem): DashboardTaskRow {
  return { ...toUiTaskRow(item), taskType: item.task_type, link: toTaskLink(item) };
}

// =========================================================
// 메뉴 배지
// =========================================================

/**
 * 메뉴별로 세는 업무 종류. 여기 없는 메뉴(보고서 생성 등)는 대응하는 업무가 Backend 에 없어 배지를 띄우지 않는다.
 *
 * - 상담 자료 검수: 원문 검수 대기(검수 목록 화면이 task_type=REVIEW_TRANSCRIPT 로 불러오는 것과 같다)
 * - 사례 관리: AI 분석 단계에서 사람이 할 일(분석 요청 · 결과 검토 · 실패 재시도)
 */
/** 메뉴별로 세는 업무. 사례 관리 탭 배지(CaseManagementPage 의 NEEDS_ACTION_STATUSES)와 같은 대상이다. */
export const MENU_BADGE_TASKS: Record<string, TaskType[]> = {
  "/stt-cases": ["REVIEW_TRANSCRIPT"],
  "/case-management": ["REQUEST_ANALYSIS", "REVIEW_ANALYSIS", "RETRY_ANALYSIS"],
};

/** 메뉴 주소 → 배지 숫자. */
export function toMenuBadges(summary: TaskSummary): Record<string, number> {
  const badges: Record<string, number> = {};

  for (const [path, types] of Object.entries(MENU_BADGE_TASKS)) {
    badges[path] = types.reduce((sum, type) => sum + (summary.by_type[type] ?? 0), 0);
  }

  return badges;
}

// =========================================================
// 사례
// =========================================================

/**
 * 사례 관리 · 대시보드가 쓰는 사례 한 줄.
 * 위험도 · 학대유형 · 회차 수는 사례 목록 응답에 없어 담지 않는다(화면에서 "—").
 */
export interface ManagedCase {
  /** Backend 조회 · 주소에 쓰는 UUID. */
  backendId: string;
  /** 화면에 보이는 사례번호. */
  caseNumber: string;
  /** 실명이 아닌 별칭. */
  childName: string;
  /** "9세" 형태. 출생연도가 없으면 "—". */
  ageLabel: string;
  guardian: string;
  status: Case["status"];
  statusLabel: string;
  /** 최근 상담일(YYYY-MM-DD). 회기가 없으면 빈 문자열. */
  lastSession: string;
  /** 최근 상담순 정렬용. */
  lastSessionTime: number;
  counselor: string;
}

export const CASE_STATUS_LABELS: Record<Case["status"], string> = {
  ACTIVE: "진행중",
  CLOSED: "종결",
};

export function toManagedCase(source: Case): ManagedCase {
  const age = source.child_birth_year ? new Date().getFullYear() - source.child_birth_year : null;

  return {
    backendId: source.id,
    caseNumber: source.case_number,
    childName: source.child_alias,
    ageLabel: age !== null ? `${age}세` : NOT_PROVIDED,
    guardian: toGuardianLabel(source),
    status: source.status,
    statusLabel: CASE_STATUS_LABELS[source.status],
    lastSession: toLocalDate(source.last_session_at),
    lastSessionTime: toSortTime(source.last_session_at),
    counselor: source.counselor_name ?? NOT_PROVIDED,
  };
}

/** 최근 상담이 늦은 순. 상담이 없는 사례는 뒤로 간다. */
export function sortByRecentSession(list: ManagedCase[]): ManagedCase[] {
  return [...list].sort((a, b) => b.lastSessionTime - a.lastSessionTime);
}

// =========================================================
// 대시보드 숫자
// =========================================================

export interface DashboardStat {
  label: string;
  value: string;
  note: string;
  /** 서버에서 채우는 칸인가. 불러오는 동안 "…" 표시에 쓴다. */
  fromServer: boolean;
}

export interface DashboardStatInput {
  isAdmin: boolean;
  /** 불러오는 중이면 null. */
  summary: TaskSummary | null;
  caseTotal: number | null;
  activeCaseTotal: number | null;
}

/** 서버에 없는 숫자의 안내 문구. */
const NOT_SERVED_NOTE = "아직 서버에 없음";

/**
 * 상단 숫자 5칸. tasks.summary 와 사례 목록 total 로 채울 수 있는 것만 채운다.
 * 오늘 예정 상담 · 작성 대기 문서는 Backend 에 조회가 없어 "—".
 */
export function toDashboardStats(input: DashboardStatInput): DashboardStat[] {
  const { summary, caseTotal, activeCaseTotal } = input;

  const caseNote =
    caseTotal !== null && activeCaseTotal !== null
      ? `진행 ${activeCaseTotal} · 종결 ${caseTotal - activeCaseTotal}`
      : "";

  return [
    {
      label: input.isAdmin ? "전체 사례" : "전체 담당 사례",
      value: caseTotal !== null ? String(caseTotal) : NOT_PROVIDED,
      note: caseNote,
      fromServer: true,
    },
    { label: "오늘 예정 상담", value: NOT_PROVIDED, note: NOT_SERVED_NOTE, fromServer: false },
    { label: "작성 대기 문서", value: NOT_PROVIDED, note: NOT_SERVED_NOTE, fromServer: false },
    {
      label: "미처리 업무",
      value: summary ? String(summary.total) : NOT_PROVIDED,
      note: summary ? `지연 ${summary.overdue}건 포함` : "",
      fromServer: true,
    },
    {
      label: "지연 업무",
      value: summary ? String(summary.overdue) : NOT_PROVIDED,
      note: summary ? "기준 시간 넘게 기다린 업무" : "",
      fromServer: true,
    },
  ];
}

// =========================================================
// 후속 관리 숫자
// =========================================================

/** 상담사가 직접 확인해야 하는 업무. 회기 상태 중 사람이 개입하는 두 지점(원문 검수 · AI 결과 검토)이다. */
export const HUMAN_REVIEW_TASKS: TaskType[] = ["REVIEW_TRANSCRIPT", "REVIEW_ANALYSIS"];

export interface FollowUpStat {
  label: string;
  value: string;
  color: string;
  /** 서버에서 채우는 칸인가. 불러오는 동안 "…" 표시에 쓴다. */
  fromServer: boolean;
}

/**
 * 후속 관리 상단 숫자 5칸. "상담사 확인 필요" 만 tasks.summary 로 채운다.
 * 오늘 상담 · 기록 작성 대기 · 승인 반려 · 후속상담 예정은 Backend 에 조회가 없어 "—".
 */
export function toFollowUpStats(summary: TaskSummary | null): FollowUpStat[] {
  const review = summary
    ? String(HUMAN_REVIEW_TASKS.reduce((sum, type) => sum + (summary.by_type[type] ?? 0), 0))
    : NOT_PROVIDED;

  return [
    { label: "오늘 상담", value: NOT_PROVIDED, color: "#2563EB", fromServer: false },
    { label: "기록 작성 대기", value: NOT_PROVIDED, color: "#D97706", fromServer: false },
    { label: "상담사 확인 필요", value: review, color: "#7C3AED", fromServer: true },
    { label: "승인 반려", value: NOT_PROVIDED, color: "#DC2626", fromServer: false },
    { label: "후속상담 예정", value: NOT_PROVIDED, color: "#0891B2", fromServer: false },
  ];
}

// =========================================================
// 회기 (사례 관리 — 이전 상담)
// =========================================================

export interface HistoryRow {
  id: string;
  sessionNumber: number;
  title: string;
  status: SessionStatus;
  /** 상담일(없으면 등록일). YYYY-MM-DD */
  date: string;
  time: string;
  /** 상담 유형 · 소요 시간은 Backend 에 없다. */
  type: string;
  location: string;
  duration: string;
  sttLabel: string;
  aiLabel: string;
}

export function toHistoryRow(source: Session): HistoryRow {
  const derived = deriveStatus(source.status);
  const at = source.consulted_at ?? source.created_at;

  return {
    id: source.id,
    sessionNumber: source.session_number,
    title: source.title ?? "",
    status: source.status,
    date: toLocalDate(at),
    time: toLocalTime(at),
    type: NOT_PROVIDED,
    location: source.location ?? NOT_PROVIDED,
    duration: NOT_PROVIDED,
    // 대기 · 실패 상태는 화면 타입에 표현이 없어 adapters.deriveStatus 의 칸 문구를 쓴다.
    sttLabel: derived.sttLabel,
    aiLabel: derived.aiLabel,
  };
}

/** 회기 번호가 큰 것(최근)부터. */
export function sortSessionsLatestFirst<T extends { session_number: number }>(list: T[]): T[] {
  return [...list].sort((a, b) => b.session_number - a.session_number);
}

// =========================================================
// AI 분석 (사례 관리 — 분석 결과 검토, 읽기 전용)
// =========================================================

/**
 * AI 분석 단계의 회기 상태. 분석 결과 검토 탭은 이 회기들을 보여 준다.
 * 검수가 끝나 분석을 기다리는 회기(STT_CONFIRMED)도 넣는다. 메뉴 배지가 분석 요청 대기를 함께 세므로,
 * 배지를 보고 들어온 상담사가 이 탭에서 해당 회기를 찾을 수 있어야 한다(요청은 AI 분석 화면에서 한다).
 */
export const ANALYSED_SESSION_STATUSES: SessionStatus[] = [
  "STT_CONFIRMED",
  "AI_PROCESSING",
  "AI_REVIEW_REQUIRED",
  "APPROVED",
  "AI_FAILED",
];

/** 분석 결과 검토 탭의 상태 표시. 판정처럼 읽히지 않게 검토 진행 상황만 적는다. */
export function toAnalysisStatusLabel(status: SessionStatus, summary: Summary | null): string {
  switch (status) {
    case "STT_CONFIRMED":
      return "분석 요청 대기";
    case "AI_PROCESSING":
      return "분석 중";
    case "AI_FAILED":
      return "분석 실패";
    case "APPROVED":
      return "상담사 검토 완료";
    case "AI_REVIEW_REQUIRED":
      return summary?.is_edited ? "수정됨" : "검토 필요";
    default:
      return deriveStatus(status).label;
  }
}

// 위험 관련 항목 변환은 AI 분석 검토 화면과 함께 쓰도록 riskAdapters.ts 에 둔다.
export {
  riskSegmentIdSet,
  toUiReferenceSignals,
  toUiRiskUtterances,
  type UiReferenceSignal,
  type UiRiskUtterance,
} from "./riskAdapters";

/** segment_id → 발화. 근거 발화의 시각 · 화자를 찾는 데 쓴다. 전사본이 없으면 빈 Map. */
export function indexSegments(source: Transcript | null): Map<string, UiTranscriptSegment> {
  const map = new Map<string, UiTranscriptSegment>();

  if (!source) return map;

  for (const seg of toUiTranscriptSegments(source)) map.set(seg.id, seg);

  return map;
}

/** 근거 발화 앞뒤 한 줄씩. "원문 위치 보기" 에 쓴다. */
export function segmentContext(source: Transcript | null, segmentId: string): UiTranscriptSegment[] {
  if (!source) return [];

  const ordered = toUiTranscriptSegments(source);
  const index = ordered.findIndex((seg) => seg.id === segmentId);

  if (index < 0) return [];

  return ordered.slice(Math.max(0, index - 1), index + 2);
}
