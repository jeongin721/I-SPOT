// 관리자 화면이 Backend 응답(계정 · 감사 로그 · 처리 대기 업무)을 화면 값으로 바꿀 때 쓰는 함수.
//
// ispotvscode/src/api/adminAdapters.ts 와 커밋 8aaf63e(관리자 대시보드 숫자 · 최근 접속)에서 옮겨 왔다.
// 화면 배치와 상관없이 쓸 수 있게 문자열 · 숫자만 만든다. 어느 칸에 어떻게 놓을지는 화면이 정한다.
//
// Backend 에 없는 값은 지어내지 않고 NOT_PROVIDED("—")로 둔다(specs 대응표 Admin 줄 — 팀 결정):
//  - 미배정 사례: 사례는 만들 때 늘 담당자가 있다. '미배정' 의 뜻(담당자 계정 정지 · 퇴사 등)이 정해지지 않았다.
//  - 문서 승인 대기 · 관리자 결재: 문서 승인은 상담사 검수이고 관리자 결재가 아니다. 집계 API 도 없다.
//  - 보안 이벤트 · 심각도 · 탐지(예: 외부 IP 반복 실패): 감사 로그는 있지만 심각도 · 탐지 규칙이 없다.

import type { AuditLog, Case, TaskItem, TaskSummary, TaskType, TemporaryPassword, User, UserRole } from "../api/types";
import { TASK_LABELS } from "../api/types";
import { NOT_PROVIDED } from "./caseRows";
import { ROLE_LABELS } from "./profile";
import { pad2, parseBackendTime, toDateTime } from "./time";

// =========================================================
// 날짜
// =========================================================

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** "10월 13일 (화)". 사용자 시간대의 그 날. */
export function toAdminDateLabel(now: Date): string {
  return `${now.getMonth() + 1}월 ${now.getDate()}일 (${WEEKDAYS[now.getDay()]})`;
}

/** "10-13 09:14". 사용자 시간대. 값이 없거나 읽지 못하면 빈 문자열. */
export function toShortDateTime(iso: string | null | undefined): string {
  if (!iso) return "";

  const at = parseBackendTime(iso);

  if (!at) return "";

  return `${pad2(at.getMonth() + 1)}-${pad2(at.getDate())} ${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
}

/** 기다린 시간 "40분" · "5시간" · "2일 3시간". 미래 시각이면 "0분". 읽지 못하면 빈 문자열. */
export function toWaitingFor(iso: string, now: number = Date.now()): string {
  const at = parseBackendTime(iso);

  if (!at) return "";

  const minutes = Math.max(0, Math.floor((now - at.getTime()) / 60000));

  if (minutes < 60) return `${minutes}분`;

  const hours = Math.floor(minutes / 60);

  if (hours < 24) return `${hours}시간`;

  const days = Math.floor(hours / 24);
  const restHours = hours % 24;

  return restHours === 0 ? `${days}일` : `${days}일 ${restHours}시간`;
}

// =========================================================
// 계정
// =========================================================

export type AccountTagTone = "red" | "amber" | "slate";

export interface AccountTag {
  label: string;
  tone: AccountTagTone;
}

/**
 * 활성 · 비활성 말고 따로 보여 줄 계정 상태. 넷은 뜻이 다르다(types.ts User 설명).
 *
 * 휴면은 dormant_at 으로만 본다. Backend 는 미접속 기간(기본 60일)이 지난 뒤 맞는 비밀번호로 로그인했을 때
 * dormant_at 을 채우므로, 그 전에는 휴면으로 보이지 않는다. 휴면 해제도 dormant_at 이 있을 때만 할 수 있다.
 */
export function accountStateTags(user: User): AccountTag[] {
  const tags: AccountTag[] = [];

  if (user.is_locked) tags.push({ label: "잠금", tone: "red" });
  if (user.dormant_at) tags.push({ label: "휴면", tone: "slate" });
  if (user.must_change_password) tags.push({ label: "임시 비밀번호", tone: "amber" });

  return tags;
}

/** 담당자별 사례 수(종결 포함). 담당자별 집계 API 가 없어 관리자가 받은 전체 사례로 센다. */
export function countCasesByCounselor(list: Pick<Case, "counselor_id">[]): Map<string, number> {
  const counts = new Map<string, number>();

  for (const item of list) {
    counts.set(item.counselor_id, (counts.get(item.counselor_id) ?? 0) + 1);
  }

  return counts;
}

/** 계정 한 줄에서 지금 할 수 있는 요청. 서버도 최종으로 막는다(마지막 관리자 · 자기 계정 강제 로그아웃은 409). */
export interface AccountAbilities {
  activate: boolean;
  /** 자기 계정은 막는다(바로 자기 로그인이 끊긴다). */
  deactivate: boolean;
  unlock: boolean;
  /** 휴면 해제 + 임시 비밀번호 발급. 휴면(dormant_at)일 때만. */
  reactivate: boolean;
  /** 자기 계정은 막는다(서버도 409). */
  logoutAll: boolean;
  /** 자기 계정은 막는다(바로 자기 로그인이 끊긴다. 본인은 설정의 비밀번호 변경을 쓴다). */
  resetPassword: boolean;
  /** 자기 역할은 바꾸지 않는다(역할을 바꾸면 그 계정 토큰이 모두 끊긴다). */
  changeRole: boolean;
}

export interface AccountRow {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  roleLabel: string;
  /** 지금 로그인한 관리자 자신의 계정인가. */
  isSelf: boolean;
  active: boolean;
  /** "활성" · "비활성". */
  activeLabel: string;
  /** 잠금 · 휴면 · 임시 비밀번호. */
  tags: AccountTag[];
  /** 시간 잠금일 때 풀리는 시각. 기본 설정(풀리지 않음)이면 빈 문자열. */
  lockedUntil: string;
  /** 최근 로그인 일시. 없으면 NOT_PROVIDED. */
  lastLoginAt: string;
  createdAt: string;
  /** 담당 사례 수(종결 포함). 세지 못했으면 null. */
  caseCount: number | null;
  /** caseCount 를 글자로. 세지 못했으면 NOT_PROVIDED. */
  caseCountLabel: string;
  can: AccountAbilities;
}

export function toAccountRow(user: User, meId: string | null, caseCounts: Map<string, number> | null): AccountRow {
  const isSelf = user.id === meId;
  const caseCount = caseCounts ? (caseCounts.get(user.id) ?? 0) : null;

  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    roleLabel: ROLE_LABELS[user.role] ?? user.role,
    isSelf,
    active: user.is_active,
    activeLabel: user.is_active ? "활성" : "비활성",
    tags: accountStateTags(user),
    lockedUntil: toDateTime(user.locked_until),
    lastLoginAt: toDateTime(user.last_login_at) || NOT_PROVIDED,
    createdAt: toDateTime(user.created_at),
    caseCount,
    caseCountLabel: caseCount === null ? NOT_PROVIDED : String(caseCount),
    can: {
      activate: !user.is_active,
      deactivate: user.is_active && !isSelf,
      unlock: Boolean(user.is_locked),
      reactivate: Boolean(user.dormant_at) && !isSelf,
      logoutAll: !isSelf,
      resetPassword: !isSelf,
      changeRole: !isSelf,
    },
  };
}

/** 임시 비밀번호. 이 응답에서 한 번만 온다. 훅은 들고 있지 않고 돌려주기만 한다(화면이 한 번 보여 주고 버린다). */
export interface TemporaryPasswordView {
  temporaryPassword: string;
  /** 사용 기한(YYYY-MM-DD HH:mm). 지나면 다시 초기화해야 한다. */
  expiresAt: string;
  mustChangePassword: boolean;
}

export function toTemporaryPasswordView(source: TemporaryPassword): TemporaryPasswordView {
  return {
    temporaryPassword: source.temporary_password,
    expiresAt: toDateTime(source.expires_at),
    mustChangePassword: source.must_change_password,
  };
}

/** 활성 상담사 수와 전체 상담사 수. 활성은 is_active 만 본다(잠김 · 휴면 · 임시 비밀번호 계정 포함). */
export function countCounselors(users: Pick<User, "role" | "is_active">[]): { active: number; total: number } {
  const counselors = users.filter((user) => user.role === "COUNSELOR");

  return { active: counselors.filter((user) => user.is_active).length, total: counselors.length };
}

// =========================================================
// 감사 로그(접속 기록)
// =========================================================

/** 로그인 실패 감사 로그의 error_code → 사유. 응답은 모두 같은 문구라도 감사 로그에는 실제 이유가 남는다. */
const LOGIN_FAILURE_REASONS: Record<string, string> = {
  INVALID_CREDENTIALS: "비밀번호 불일치 · 없는 계정",
  ACCOUNT_LOCKED: "잠긴 계정",
  INACTIVE_USER: "비활성 계정",
  ACCOUNT_DORMANT: "휴면 계정",
  TEMP_PASSWORD_EXPIRED: "임시 비밀번호 만료",
};

export function toFailureReason(code: string | null | undefined): string {
  if (!code) return "";

  return LOGIN_FAILURE_REASONS[code] ?? code;
}

/** 계정 관련 감사 동작의 한글 이름(backend/app/core/enums.py AuditAction). 없는 값은 서버 값 그대로. */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  LOGIN: "로그인",
  LOGOUT_ALL: "강제 로그아웃",
  PASSWORD_CHANGED: "비밀번호 변경",
  PASSWORD_RESET: "비밀번호 초기화",
  ACCOUNT_LOCKED: "계정 잠김",
  ACCOUNT_UNLOCKED: "잠금 해제",
  ACCOUNT_DORMANT: "휴면 전환",
  ACCOUNT_REACTIVATED: "휴면 해제",
  USER_CREATED: "계정 생성",
  USER_UPDATED: "계정 수정",
};

/** User-Agent 를 "Chrome 126" 처럼 줄인다. 모르는 값은 앞부분만(전체는 userAgent 로). */
export function toBrowserLabel(userAgent: string | null | undefined): string {
  if (!userAgent) return NOT_PROVIDED;

  const rules: [RegExp, string][] = [
    [/Edg\/(\d+)/, "Edge"],
    [/OPR\/(\d+)/, "Opera"],
    [/SamsungBrowser\/(\d+)/, "Samsung Internet"],
    [/Firefox\/(\d+)/, "Firefox"],
    [/Chrome\/(\d+)/, "Chrome"],
    [/Version\/(\d+)[^ ]* (?:Mobile\/\S+ )?Safari\//, "Safari"],
  ];

  for (const [pattern, name] of rules) {
    const match = userAgent.match(pattern);

    if (match) return `${name} ${match[1]}`;
  }

  return userAgent.length > 24 ? `${userAgent.slice(0, 24)}…` : userAgent;
}

export interface AuditRow {
  id: string;
  action: string;
  actionLabel: string;
  success: boolean;
  /** "성공" · "실패". */
  resultLabel: string;
  /** 실패 사유. 성공이거나 코드가 없으면 빈 문자열. */
  failureReason: string;
  /** YYYY-MM-DD HH:mm */
  at: string;
  /** MM-DD HH:mm */
  shortAt: string;
  /** 행동한 사람 이름. 없는 계정으로 로그인을 시도했으면 NOT_PROVIDED(knownActor 가 false). */
  actorName: string;
  knownActor: boolean;
  /** 그 사람의 지금 역할(그때 역할이 아니다). 모르면 NOT_PROVIDED. */
  actorRoleLabel: string;
  ip: string;
  browser: string;
  /** 전체 User-Agent. 없으면 빈 문자열. */
  userAgent: string;
}

/** roles 는 계정 ID → 지금 역할. 계정 목록을 받지 못했으면 빈 Map 을 넘긴다(역할 칸만 NOT_PROVIDED). */
export function toAuditRow(log: AuditLog, roles: Map<string, UserRole>): AuditRow {
  const success = log.status === "SUCCESS";
  const role = log.actor_id ? roles.get(log.actor_id) : undefined;

  return {
    id: log.id,
    action: log.action,
    actionLabel: AUDIT_ACTION_LABELS[log.action] ?? log.action,
    success,
    resultLabel: success ? "성공" : "실패",
    failureReason: success ? "" : toFailureReason(log.error_code),
    at: toDateTime(log.created_at),
    shortAt: toShortDateTime(log.created_at),
    actorName: log.actor_name ?? NOT_PROVIDED,
    knownActor: Boolean(log.actor_name),
    actorRoleLabel: role ? (ROLE_LABELS[role] ?? role) : NOT_PROVIDED,
    ip: log.ip_address ?? NOT_PROVIDED,
    browser: toBrowserLabel(log.user_agent),
    userAgent: log.user_agent ?? "",
  };
}

/**
 * 날짜 입력(YYYY-MM-DD, 사용자 시간대) → 감사 로그 since · until(UTC ISO).
 * 시작일은 그날 0시부터, 종료일은 그날 23:59:59.999 까지 포함한다(Backend 는 둘 다 경계 포함).
 * 비어 있거나 읽지 못하면 undefined(조건 없음).
 */
export function toAuditRange(startDate: string, endDate: string): { since?: string; until?: string } {
  const since = startDate ? new Date(`${startDate}T00:00:00`) : null;
  const until = endDate ? new Date(`${endDate}T23:59:59.999`) : null;

  return {
    since: since && !Number.isNaN(since.getTime()) ? since.toISOString() : undefined,
    until: until && !Number.isNaN(until.getTime()) ? until.toISOString() : undefined,
  };
}

// =========================================================
// 처리 대기 업무
// =========================================================

/**
 * 대시보드 '처리 대기 업무' 에 더하는 종류. 이 목록이 숫자의 정의다.
 *
 * 뺀 것: UPLOAD_AUDIO(상담 뒤 녹음을 올리는 차례 — 처리가 시작되지 않은 예정 업무라 밀린 업무로 세지 않는다).
 * 문서 승인 대기는 Backend 에 집계가 없어 넣을 수 없다.
 */
export const PENDING_TASK_TYPES: readonly TaskType[] = [
  "REQUEST_STT",
  "REVIEW_TRANSCRIPT",
  "RETRY_STT",
  "REQUEST_ANALYSIS",
  "REVIEW_ANALYSIS",
  "RETRY_ANALYSIS",
];

/** 화면 안내(툴팁 등)용: 무엇을 더했고 무엇을 뺐는지. */
export const PENDING_TASKS_NOTE =
  `더한 업무: ${PENDING_TASK_TYPES.map((type) => TASK_LABELS[type]).join(" · ")}\n` +
  `뺀 업무: ${TASK_LABELS.UPLOAD_AUDIO}(예정 업무), 문서 승인 대기(집계 API 없음)\n` +
  "지연은 서버가 정한 기준 시간(기본 48시간)을 넘긴 업무입니다.";

export interface PendingTasks {
  /** PENDING_TASK_TYPES 를 더한 수. */
  count: number;
  /** 그 가운데 지연. */
  overdue: number;
  /** 종류별 수(UPLOAD_AUDIO 포함 7종 모두). 업무 표의 탭 숫자에 쓴다. */
  byType: Record<TaskType, number>;
}

/**
 * 처리 대기 업무 수 = by_type 에서 PENDING_TASK_TYPES 만 더한 값.
 * 지연 수는 요약의 전체 지연(overdue)에서 뺀 종류(UPLOAD_AUDIO)의 지연을 뺀다.
 * 지연 여부는 서버 is_overdue 기준 그대로다(화면이 시간을 다시 계산하지 않는다).
 */
export function toPendingTasks(summary: TaskSummary, uploadAudioOverdue: number): PendingTasks {
  const count = PENDING_TASK_TYPES.reduce((sum, type) => sum + (summary.by_type[type] ?? 0), 0);

  // 두 요청 사이에 기준 시간을 넘기는 업무가 있으면 어긋날 수 있어 범위 안으로 맞춘다.
  const overdue = Math.min(count, Math.max(0, summary.overdue - uploadAudioOverdue));

  return { count, overdue, byType: { ...summary.by_type } };
}

export interface TaskRow {
  sessionId: string;
  caseId: string;
  /** 화면에 보이는 사례 ID(예: C-2026-0001). */
  caseNumber: string;
  /** 아동 별칭. 실명이 아니다(실명은 Backend 에 없다). */
  childAlias: string;
  counselorName: string;
  sessionNumber: number;
  /** 회차 제목. 없으면 빈 문자열. */
  sessionTitle: string;
  taskType: TaskType;
  /** 처리 단계(업무 이름). */
  stageLabel: string;
  /** 이 상태로 기다리기 시작한 시각 MM-DD HH:mm. 화면의 '제출 시각' 이 아니다 — 상태가 바뀐 시각이다. */
  waitingSince: string;
  /** YYYY-MM-DD HH:mm */
  waitingSinceFull: string;
  /** 기다린 시간("5시간"). 부른 시각 기준이라 다시 조회할 때 바뀐다. */
  waitingFor: string;
  /** 서버 기준 지연. 위험 신호가 아니므로 '긴급' 이라고 쓰지 않는다. */
  overdue: boolean;
  /** 재시도 업무(원문 변환 · AI 분석 실패)인가. */
  failed: boolean;
  /** 재시도 업무의 오류 코드. 없으면 빈 문자열. 문구는 회차 상세(useSessionDetail)에서 본다. */
  lastErrorCode: string;
}

export function toTaskRow(item: TaskItem, now: number = Date.now()): TaskRow {
  return {
    sessionId: item.session_id,
    caseId: item.case_id,
    caseNumber: item.case_number,
    childAlias: item.child_alias.trim() || NOT_PROVIDED,
    counselorName: item.counselor_name ?? NOT_PROVIDED,
    sessionNumber: item.session_number,
    sessionTitle: item.session_title ?? "",
    taskType: item.task_type,
    stageLabel: TASK_LABELS[item.task_type] ?? item.task_type,
    waitingSince: toShortDateTime(item.waiting_since),
    waitingSinceFull: toDateTime(item.waiting_since),
    waitingFor: toWaitingFor(item.waiting_since, now),
    overdue: item.is_overdue,
    failed: item.task_type === "RETRY_STT" || item.task_type === "RETRY_ANALYSIS",
    lastErrorCode: item.last_error_code ?? "",
  };
}
