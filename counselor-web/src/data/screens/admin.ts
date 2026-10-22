// 관리자 화면 공통 값. 10/21 새 디자인(다솔 님 counselor-design 의 Admin*.dc.html)은 관리자 화면을 7장으로 나눴다.
// 앱은 서버가 있는 화면만 따로 둔다(화면 경로 = 파일 이름, App.jsx):
//
//   #/AdminHome                      홈 · 기관 현황(adminHome.ts)
//   #/AdminAccounts                  상담사 계정 관리(adminAccounts.ts)
//   #/AdminStaffDetail?user=<계정 ID> 상담사 상세(adminStaffDetail.ts)
//   #/AdminSecurity                  접속 기록 · 보안 이벤트(adminSecurity.ts)
//   #/AdminStats                     통계 · 보고(adminStats.ts)
//   #/AdminTasks(?overdue=1)         업무 처리 현황 — 새 디자인에는 없고 앱에 있던 보기라 그대로 둔다(이 파일의 adminTasksValues)
//
// 아이 연계 앱 관리(AdminApp) · 열람 기록(AdminViewLog)은 서버가 없어(팀 결정 A2 · B2 대기) 화면을 만들지 않고
// 관리자 메뉴(components/AdminSidebar.jsx)에 '준비 중' 으로만 둔다.
// 옛 주소 #/Admin?view=tasks · accounts · audit 는 Admin.jsx 가 위 새 주소로 옮긴다(adminRedirectHref).
//
//  - 관리자가 아니면 훅이 서버를 부르지 않는다(adminAccess). 화면은 권한 없음 안내만 보인다(AdminSidebar.jsx 의 AdminBlocked).
//  - Backend 에 없는 값은 지어내지 않고 '—'(NOT_PROVIDED) · 준비 중(NOT_READY)으로 둔다(adminRows 머리말). 디자인의 예시 숫자는 옮기지 않는다.
//  - 임시 비밀번호는 그 화면 상태에만 한 번 들고 있다가 '닫기' 를 누르면 버린다. 다른 관리자로 바뀌면 보이지 않는다(forAdmin).
//  - 2단계 인증(OTP)은 Backend 에 없고 팀 결정(D1) 전이라 어느 관리자 화면에도 보이지 않는다.

import type { TaskType } from "../../api/types";
import { TASK_LABELS } from "../../api/types";
import type { AccountRow, PendingTasks, TaskRow, TemporaryPasswordView } from "../adminRows";
import type { AdminTasksState } from "../useAdminTasks";
import type { AuthSession } from "../useAuthSession";
import { NOT_PROVIDED } from "../caseRows";
import { NOT_READY, notice, screenNotice, type ScreenNotice } from "./common";
import { screenHref } from "./links";

// =========================================================
// 화면 주소
// =========================================================

/** 관리자 화면 주소. 파일 이름 그대로다. */
export const ADMIN_PAGES = {
  home: "/AdminHome",
  tasks: "/AdminTasks",
  accounts: "/AdminAccounts",
  staff: "/AdminStaffDetail",
  security: "/AdminSecurity",
  stats: "/AdminStats",
} as const;

/** 옛 한 장짜리 관리자 화면(#/Admin)의 보기. 옛 링크를 새 화면으로 옮기는 데만 쓴다. */
export type AdminView = "dashboard" | "tasks" | "accounts" | "audit";

export const VIEW_PARAM = "view";

const VIEW_PAGES: Record<AdminView, string> = {
  dashboard: ADMIN_PAGES.home,
  tasks: ADMIN_PAGES.tasks,
  accounts: ADMIN_PAGES.accounts,
  audit: ADMIN_PAGES.security,
};

/** 주소의 view 쿼리 → 보기. 없거나 모르는 값이면 대시보드. */
export function readAdminView(search: URLSearchParams | string): AdminView {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const value = params.get(VIEW_PARAM)?.trim() ?? "";

  // 'toString' 같은 객체 기본 속성 이름이 보기로 읽히지 않게 자기 키만 본다.
  return Object.prototype.hasOwnProperty.call(VIEW_PAGES, value) ? (value as AdminView) : "dashboard";
}

/** 옛 보기 이름 → 새 화면 주소. */
export function adminHref(view: AdminView): string {
  return VIEW_PAGES[view];
}

/** 옛 주소 #/Admin(?view=…)를 옮길 새 주소. 보기가 없거나 모르는 값이면 관리자 홈. */
export function adminRedirectHref(search: URLSearchParams | string): string {
  return adminHref(readAdminView(search));
}

/** 상담사 상세가 다루는 계정. 디자인은 브라우저 저장소(ispot-staff)로 넘기지만 앱은 주소 쿼리로 넘긴다. */
export const USER_PARAM = "user";

export function staffDetailHref(userId: string): string {
  return `${ADMIN_PAGES.staff}?${new URLSearchParams({ [USER_PARAM]: userId }).toString()}`;
}

/** 주소의 user 쿼리(계정 ID). 없으면 null. */
export function readStaffId(search: URLSearchParams | string): string | null {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;

  return params.get(USER_PARAM)?.trim() || null;
}

/** 업무 처리 현황을 '지연된 업무만' 으로 열 때 붙이는 쿼리(관리자 홈의 '지연된 업무 보기'). */
export const OVERDUE_PARAM = "overdue";

export function overdueTasksHref(): string {
  return `${ADMIN_PAGES.tasks}?${OVERDUE_PARAM}=1`;
}

export function readOverdueOnly(search: URLSearchParams | string): boolean {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;

  return params.get(OVERDUE_PARAM) === "1";
}

// =========================================================
// 권한
// =========================================================

/** 관리자가 아니거나 로그인을 확인하지 못했을 때 보여 줄 안내. 서버는 부르지 않는다. */
export function adminBlockedNotice(session: AuthSession): ScreenNotice {
  return (
    screenNotice({ session }) ??
    notice("관리자 계정만 볼 수 있는 화면입니다.", { href: "/Main", hrefLabel: "홈으로" })
  );
}

/**
 * 관리자 훅이 아닌 공용 훅(useCaseOverview 처럼 enabled 조건이 없는 것)에 넘기는 로그인 상태.
 * 관리자가 아니면 '확인 중' 으로 넘겨 서버를 부르지 않게 한다(관리자 화면은 그때 권한 없음 안내만 보인다).
 */
export function adminOnly(session: AuthSession): AuthSession {
  return session.isAdmin ? session : { ...session, status: "checking", me: null };
}

// =========================================================
// 화면 조각
// =========================================================

export type TablePhase = "loading" | "error" | "empty" | "rows";

/** 표 본문 단계: 오류 → 불러오는 중 → 빈 목록 → 행. */
export function tablePhase(loading: boolean, error: string | null, count: number): TablePhase {
  if (error) return "error";
  if (loading) return "loading";

  return count === 0 ? "empty" : "rows";
}

export function pager(page: number, totalPages: number, total: number | null, go: (page: number) => void) {
  return {
    label: total === null ? "" : `전체 ${total}건 · ${page} / ${totalPages}쪽`,
    canPrev: page > 1,
    canNext: page < totalPages,
    prev: () => go(Math.max(1, page - 1)),
    next: () => go(Math.min(totalPages, page + 1)),
  };
}

/** 디자인의 .seg 묶음 단추(role="group" + aria-pressed). */
export interface SegButton {
  key: string;
  label: string;
  cls: string;
  pressed: "true" | "false";
  title: string;
  pick: () => void;
}

export function segButton(key: string, label: string, on: boolean, pick: () => void, title = ""): SegButton {
  return { key, label, cls: on ? "on" : "", pressed: on ? "true" : "false", title, pick };
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** "2026년 10월 22일 수요일". 사용자 시간대의 그 날(디자인 dateLabel). */
export function fullDateLabel(now: Date): string {
  return `${now.getFullYear()}년 ${now.getMonth() + 1}월 ${now.getDate()}일 ${WEEKDAYS[now.getDay()]}요일`;
}

/** 사용자 시간대의 그 날(YYYY-MM-DD). */
export function localDate(now: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");

  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * 같은 화면의 구역으로 굴린다. 디자인의 해시 앵커(href="#urgent")는 앱이 HashRouter 라 화면 이동으로 읽혀
 * 홈으로 튕기므로, 단추 + scrollIntoView 로 바꿨다.
 */
export function scrollToId(id: string): () => void {
  return () => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** 아바타 첫 글자. */
export function initialOf(name: string): string {
  return name && name !== NOT_PROVIDED ? Array.from(name)[0] : "?";
}

/** 계정 상태 칩: 활성/비활성 + 잠금 · 휴면 · 임시 비밀번호. 색만으로 나타내지 않도록 칩 글자가 상태 이름이다. */
export function accountChips(row: AccountRow): { label: string; cls: string }[] {
  return [
    { label: row.activeLabel, cls: row.active ? "chip c-ok" : "chip c-check" },
    ...row.tags.map((tag) => ({
      label: tag.label,
      cls: tag.tone === "red" ? "chip c-urgent" : tag.tone === "amber" ? "chip c-mid" : "chip c-normal",
    })),
  ];
}

// =========================================================
// 임시 비밀번호(계정 만들기 · 비밀번호 초기화 · 휴면 해제)
// =========================================================

export interface IssuedPassword extends TemporaryPasswordView {
  /** 이 값을 받은 관리자. 다른 관리자로 바뀌면 보이지 않는다. */
  forAdmin: string;
  /** 임시 비밀번호를 받은 계정. */
  userId: string;
  name: string;
  email: string;
  /** "새 계정" · "비밀번호 초기화" · "휴면 해제". */
  reason: string;
}

/** 방금 받은 임시 비밀번호를 한 번 보여 줄 값. 받은 관리자가 아니면 null. copied · setState 는 그 화면의 상태다. */
export function issuedPasswordValues(
  issued: IssuedPassword | null,
  adminId: string,
  copied: boolean,
  setState: (patch: { issued?: IssuedPassword | null; copied?: boolean }) => void,
) {
  if (!issued || issued.forAdmin !== adminId) return null;

  return {
    who: `${issued.name} (${issued.email})`,
    reason: issued.reason,
    password: issued.temporaryPassword,
    expiresAt: issued.expiresAt || NOT_PROVIDED,
    copied,
    copy: () => {
      try {
        void navigator.clipboard
          .writeText(issued.temporaryPassword)
          .then(() => setState({ copied: true }))
          .catch(() => undefined);
      } catch {
        // 복사를 못 하는 브라우저면 화면의 값을 직접 옮겨 적는다.
      }
    },
    close: () => setState({ issued: null, copied: false }),
  };
}

// =========================================================
// 업무 처리 현황(관리자 홈의 업무 표 · AdminTasks 화면)
// =========================================================

/** 관리자 홈 업무 표의 묶음. Backend 는 종류를 하나만 거를 수 있어 묶음마다 두 종류를 따로 불러 합친다. */
export type TaskGroupKey = "stt" | "review" | "analysis";

export const TASK_GROUPS: readonly { key: TaskGroupKey; label: string; types: readonly [TaskType, TaskType] }[] = [
  { key: "stt", label: "원문 변환 대기", types: ["REQUEST_STT", "RETRY_STT"] },
  { key: "review", label: "상담사 검토 대기", types: ["REVIEW_TRANSCRIPT", "REVIEW_ANALYSIS"] },
  { key: "analysis", label: "AI 분석 대기", types: ["REQUEST_ANALYSIS", "RETRY_ANALYSIS"] },
];

/** 관리자 홈 업무 표에 보이는 줄 수(묶음의 두 종류를 이만큼씩 받아 오래 기다린 순서로 합친다). */
export const DASHBOARD_TASK_ROWS = 5;

export function taskGroupTypes(key: TaskGroupKey): readonly [TaskType, TaskType] {
  return (TASK_GROUPS.find((group) => group.key === key) ?? TASK_GROUPS[0]).types;
}

function stageChip(row: TaskRow): string {
  if (row.failed) return "chip c-check";
  if (row.taskType === "REVIEW_TRANSCRIPT" || row.taskType === "REVIEW_ANALYSIS") return "chip c-ing";

  return "chip c-normal";
}

function taskRowValues(row: TaskRow) {
  return {
    key: `${row.sessionId}:${row.taskType}`,
    caseNumber: row.caseNumber,
    child: row.childAlias,
    counselor: row.counselorName,
    since: row.waitingSince || NOT_PROVIDED,
    sinceFull: row.waitingSinceFull,
    waiting: row.waitingFor || NOT_PROVIDED,
    // 지연은 글자로도 적는다(굵기 · 색만으로 나타내지 않는다). 위험 신호가 아니라서 '긴급' 이라고 쓰지 않는다.
    overdueText: row.overdue ? "지연" : "",
    waitWeight: row.overdue ? "700" : "400",
    stage: row.stageLabel,
    stageCls: stageChip(row),
    href: screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.sessionId }),
  };
}

/** 관리자 홈의 업무 표: 묶음 단추(.seg) + 오래 기다린 DASHBOARD_TASK_ROWS 줄. */
export function taskGroupValues(input: {
  groupTasks: [AdminTasksState, AdminTasksState];
  pending: PendingTasks | null;
  group: TaskGroupKey;
  setGroup: (key: TaskGroupKey) => void;
}) {
  const { groupTasks, pending, group, setGroup } = input;
  const tabs = TASK_GROUPS.map((item) => {
    const count = pending ? item.types.reduce((sum, type) => sum + (pending.byType[type] ?? 0), 0) : null;

    return segButton(
      item.key,
      count === null ? item.label : `${item.label} ${count}`,
      item.key === group,
      () => setGroup(item.key),
      item.types.map((type) => TASK_LABELS[type]).join(" · "),
    );
  });
  const [first, second] = groupTasks;
  const rows = [...first.rows, ...second.rows]
    .sort((a, b) => a.waitingSinceAt - b.waitingSinceAt)
    .slice(0, DASHBOARD_TASK_ROWS)
    .map(taskRowValues);
  const total = first.total !== null && second.total !== null ? first.total + second.total : null;
  const error = first.error ?? second.error;

  return {
    tabs,
    rows,
    phase: tablePhase(first.loading || second.loading, error, rows.length),
    errorText: error,
    emptyText: "처리 대기 업무가 없습니다.",
    retry: () => {
      first.reload();
      second.reload();
    },
    more: total !== null && total > rows.length ? `오래 기다린 ${rows.length}건만 보입니다(전체 ${total}건).` : "",
  };
}

/** 업무 처리 현황 화면(AdminTasks)의 조건. 화면 함수의 useState 로 들고 훅에 넘긴다. */
export interface AdminTasksQuery {
  /** 이 종류만. 빈 문자열이면 모든 종류. */
  taskType: TaskType | "";
  overdueOnly: boolean;
  page: number;
}

export function initialTasksQuery(overdueOnly: boolean): AdminTasksQuery {
  return { taskType: "", overdueOnly, page: 1 };
}

type Change = { target: { value: string } };

export function adminTasksValues(input: {
  /** 종류별 수(선택 목록 옆 숫자). 모르면 null. */
  pending: PendingTasks | null;
  taskList: AdminTasksState;
  query: AdminTasksQuery;
  setQuery: (patch: Partial<AdminTasksQuery>) => void;
}) {
  const { pending, taskList, query, setQuery } = input;

  return {
    typeOptions: [
      { value: "", label: "모든 종류" },
      ...(Object.keys(TASK_LABELS) as TaskType[]).map((type) => ({
        value: type,
        label: pending ? `${TASK_LABELS[type]} ${pending.byType[type] ?? 0}` : TASK_LABELS[type],
      })),
    ],
    type: {
      value: query.taskType,
      onChange: (e: Change) => setQuery({ taskType: e.target.value as TaskType | "", page: 1 }),
    },
    overdue: { checked: query.overdueOnly, onChange: () => setQuery({ overdueOnly: !query.overdueOnly, page: 1 }) },
    summary: pending ? `처리 대기 ${pending.count}건 · 지연 ${pending.overdue}건` : "",
    rows: taskList.rows.map(taskRowValues),
    phase: tablePhase(taskList.loading, taskList.error, taskList.rows.length),
    errorText: taskList.error,
    retry: taskList.reload,
    emptyText: query.overdueOnly ? "지연된 업무가 없습니다." : "처리 대기 업무가 없습니다.",
    pager: pager(query.page, taskList.totalPages, taskList.total, (page) => setQuery({ page })),
    notReady: NOT_READY,
  };
}
