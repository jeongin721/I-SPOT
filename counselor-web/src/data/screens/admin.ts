// 관리자(Admin) 화면 값. 디자인(Admin.dc.html)은 대시보드 한 장이라, 왼쪽 메뉴의 업무 처리 현황 · 상담사 계정 관리 ·
// 접속 기록은 같은 화면의 다른 보기로 둔다(주소 #/Admin?view=tasks · accounts · audit). 보기는 디자인의 카드 · 표 · 칩을 그대로 쓴다.
//
//  - 관리자가 아니면 훅이 서버를 부르지 않는다(adminAccess). 화면은 권한 없음 안내만 보인다(Admin.jsx).
//  - Backend 에 없는 값(미배정 사례 · 문서 승인 대기 · 보안 경고 · 재처리 요청)은 지어내지 않고 '—' · 준비 중으로 둔다(adminRows 머리말).
//  - 임시 비밀번호는 이 화면 상태에만 한 번 들고 있다가 '닫기' 를 누르면 버린다. 다른 관리자로 바뀌면 보이지 않는다(forAdmin).
//  - '아동명' 칸은 아동 별칭이다(실명은 Backend 에 없다). '제출 시각' 은 Backend 에 없어 '대기 시작'(이 단계로 바뀐 시각)을 보인다.

import type { TaskType, UserRole } from "../../api/types";
import { TASK_LABELS } from "../../api/types";
import { AUDIT_ACTION_LABELS, PENDING_TASKS_NOTE, type AccountRow, type TaskRow, type TemporaryPasswordView } from "../adminRows";
import type { AdminAccountsState } from "../useAdminAccounts";
import type { AdminDashboardState, DashboardCell } from "../useAdminDashboard";
import type { AdminTasksState } from "../useAdminTasks";
import type { AuditLogsState } from "../useAuditLogs";
import type { AuthSession } from "../useAuthSession";
import { NOT_PROVIDED } from "../caseRows";
import { NOT_READY, notice, screenNotice, sidebarValues, type ScreenNotice } from "./common";
import { screenHref } from "./links";

// =========================================================
// 보기와 주소
// =========================================================

export type AdminView = "dashboard" | "tasks" | "accounts" | "audit";

export const VIEW_PARAM = "view";

const VIEWS: readonly AdminView[] = ["dashboard", "tasks", "accounts", "audit"];

/** 주소의 view 쿼리 → 보기. 없거나 모르는 값이면 대시보드. */
export function readAdminView(search: URLSearchParams | string): AdminView {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const value = params.get(VIEW_PARAM)?.trim() as AdminView | undefined;

  return value && VIEWS.includes(value) ? value : "dashboard";
}

export function adminHref(view: AdminView): string {
  return view === "dashboard" ? "/Admin" : `/Admin?${VIEW_PARAM}=${view}`;
}

// =========================================================
// 훅에 넘기는 조건(화면 함수의 useState)
// =========================================================

/** 대시보드 업무 표의 탭. Backend 는 종류를 하나만 거를 수 있어 탭마다 두 종류를 따로 불러 합친다. */
export type TaskGroupKey = "stt" | "review" | "analysis";

export const TASK_GROUPS: readonly { key: TaskGroupKey; label: string; types: readonly [TaskType, TaskType] }[] = [
  { key: "stt", label: "원문 변환 대기", types: ["REQUEST_STT", "RETRY_STT"] },
  { key: "review", label: "상담사 검토 대기", types: ["REVIEW_TRANSCRIPT", "REVIEW_ANALYSIS"] },
  { key: "analysis", label: "AI 분석 대기", types: ["REQUEST_ANALYSIS", "RETRY_ANALYSIS"] },
];

/** 대시보드 업무 표에 보이는 줄 수(탭의 두 종류를 이만큼씩 받아 오래 기다린 순서로 합친다). */
export const DASHBOARD_TASK_ROWS = 5;

export function taskGroupTypes(key: TaskGroupKey): readonly [TaskType, TaskType] {
  return (TASK_GROUPS.find((group) => group.key === key) ?? TASK_GROUPS[0]).types;
}

export type AuditResultFilter = "ALL" | "SUCCESS" | "FAILURE";

export interface AdminQuery {
  /** 대시보드 업무 표의 탭. */
  group: TaskGroupKey;
  /** 업무 처리 현황 보기: 이 종류만. 빈 문자열이면 모든 종류. */
  taskType: TaskType | "";
  overdueOnly: boolean;
  taskPage: number;
  /** 접속 기록 보기: 감사 동작. 기본 LOGIN, 빈 문자열이면 모든 동작. */
  auditAction: string;
  auditResult: AuditResultFilter;
  auditStart: string;
  auditEnd: string;
  auditPage: number;
}

export const INITIAL_ADMIN_QUERY: AdminQuery = {
  group: "stt",
  taskType: "",
  overdueOnly: false,
  taskPage: 1,
  auditAction: "LOGIN",
  auditResult: "ALL",
  auditStart: "",
  auditEnd: "",
  auditPage: 1,
};

// =========================================================
// 화면 상태(Logic.state)
// =========================================================

/** 한 번 더 묻는 요청. 임시 비밀번호가 새로 나오거나 그 계정의 로그인이 끊기는 것들이다. */
export type AccountAsk = "resetPassword" | "reactivate" | "deactivate" | "logoutAll";

export interface IssuedPassword extends TemporaryPasswordView {
  /** 이 값을 받은 관리자. 다른 관리자로 바뀌면 보이지 않는다. */
  forAdmin: string;
  name: string;
  email: string;
  /** "새 계정" · "비밀번호 초기화" · "휴면 해제". */
  reason: string;
}

export interface AdminUiState {
  form: { email: string; name: string; role: UserRole };
  /** 방금 받은 임시 비밀번호. '닫기' 를 누르면 null. */
  issued: IssuedPassword | null;
  ask: { userId: string; kind: AccountAsk; forAdmin: string } | null;
  /** 마지막 요청이 성공했다는 안내. */
  done: { text: string; forAdmin: string } | null;
  copied: boolean;
}

export const INITIAL_ADMIN_STATE: AdminUiState = {
  form: { email: "", name: "", role: "COUNSELOR" },
  issued: null,
  ask: null,
  done: null,
  copied: false,
};

// =========================================================
// 값
// =========================================================

export interface AdminScreenInput {
  session: AuthSession;
  view: AdminView;
  dashboard: AdminDashboardState;
  /** 대시보드 탭의 두 종류. */
  groupTasks: [AdminTasksState, AdminTasksState];
  /** 업무 처리 현황 보기. */
  taskList: AdminTasksState;
  accounts: AdminAccountsState;
  audit: AuditLogsState;
  query: AdminQuery;
  setQuery: (patch: Partial<AdminQuery>) => void;
  state: AdminUiState;
  setState: (patch: Partial<AdminUiState> | ((current: AdminUiState) => Partial<AdminUiState>)) => void;
}

type Change = { target: { value: string } };

const ASK_TEXT: Record<AccountAsk, { label: string; question: (name: string) => string }> = {
  resetPassword: {
    label: "비밀번호 초기화",
    question: (name) => `${name} 계정의 비밀번호를 초기화할까요? 임시 비밀번호가 새로 나오고 그 계정의 로그인은 모두 끊깁니다.`,
  },
  reactivate: {
    label: "휴면 해제",
    question: (name) => `${name} 계정의 휴면을 풀까요? 임시 비밀번호가 새로 나옵니다.`,
  },
  deactivate: {
    label: "비활성화",
    question: (name) => `${name} 계정을 비활성화할까요? 그 계정의 로그인이 모두 끊기고 다시 활성화하기 전에는 로그인할 수 없습니다.`,
  },
  logoutAll: {
    label: "강제 로그아웃",
    question: (name) => `${name} 계정의 모든 기기 로그인을 끊을까요? 비밀번호는 그대로입니다.`,
  },
};

function cellText<T>(cell: DashboardCell<T>, show: (value: T) => string): string {
  if (cell.value !== null) return show(cell.value);

  return cell.loading ? "…" : NOT_PROVIDED;
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

/** 표 본문 단계: 불러오는 중 → 오류 → 빈 목록 → 행. */
function tablePhase(loading: boolean, error: string | null, count: number): "loading" | "error" | "empty" | "rows" {
  if (error) return "error";
  if (loading) return "loading";

  return count === 0 ? "empty" : "rows";
}

function pager(page: number, totalPages: number, total: number | null, go: (page: number) => void) {
  return {
    label: total === null ? "" : `전체 ${total}건 · ${page} / ${totalPages}쪽`,
    canPrev: page > 1,
    canNext: page < totalPages,
    prev: () => go(Math.max(1, page - 1)),
    next: () => go(Math.min(totalPages, page + 1)),
  };
}

export function adminValues(input: AdminScreenInput) {
  const { session, view, dashboard, groupTasks, taskList, accounts, audit, query, setQuery, state, setState } = input;
  const adminId = session.me?.id ?? "";
  const pending = dashboard.pendingTasks.value;

  // ---------------- 왼쪽 메뉴 ----------------
  const nav = (target: AdminView) => ({ href: adminHref(target), cls: view === target ? "on" : undefined });
  const menu = {
    dashboard: nav("dashboard"),
    tasks: nav("tasks"),
    accounts: nav("accounts"),
    audit: nav("audit"),
    // 메뉴 옆 숫자는 처리 대기 업무 수(대시보드와 같은 값). 모르면 보이지 않는다. 보안 이벤트 숫자는 Backend 에 없어 넣지 않는다.
    taskBadge: pending && pending.count > 0 ? String(pending.count) : "",
  };

  // ---------------- 대시보드 ----------------
  const counselors = dashboard.counselors;
  const someFailed = [dashboard.caseTotal, dashboard.pendingTasks, dashboard.counselors, dashboard.recentLogins].some(
    (cell) => cell.error,
  );
  const stats = {
    caseTotal: cellText(dashboard.caseTotal, String),
    pending: cellText(dashboard.pendingTasks, (value) => String(value.count)),
    pendingNote: pending ? `지연 ${pending.overdue}건` : "",
    pendingTitle: PENDING_TASKS_NOTE,
    activeCounselors: cellText(counselors, (value) => String(value.active)),
    totalCounselors: counselors.value ? ` / ${counselors.value.total}` : "",
    unassigned: dashboard.unassignedCases,
  };

  const goOverdue = () => setQuery({ taskType: "", overdueOnly: true, taskPage: 1 });
  // 즉시 확인 필요: 디자인의 네 줄(보안 · 사례 · 승인 · 배정) 자리. 서버에 있는 것은 지연 업무뿐이다.
  const alerts = [
    { chip: "보안", cls: "chip c-urgent", text: `보안 경고 ${dashboard.securityAlerts}`, href: "", onClick: undefined, note: NOT_READY },
    {
      chip: "업무",
      cls: "chip c-check",
      text: `기준 시간을 넘긴 처리 대기 업무 ${pending ? `${pending.overdue}건` : cellText(dashboard.pendingTasks, String)}`,
      href: adminHref("tasks"),
      onClick: goOverdue,
      note: "",
    },
    { chip: "승인", cls: "chip c-ing", text: `문서 승인 대기 ${dashboard.documentApprovals}`, href: "", onClick: undefined, note: NOT_READY },
    { chip: "배정", cls: "chip c-type", text: `미배정 사례 ${dashboard.unassignedCases}`, href: "", onClick: undefined, note: NOT_READY },
  ];

  const logins = dashboard.recentLogins;
  const recent = (logins.value ?? []).map((row) => ({
    key: row.id,
    name: row.actorName,
    weight: row.knownActor ? "500" : "700",
    meta: `${row.shortAt} · ${row.ip}`,
    result: row.resultLabel,
    resultCls: row.success ? "chip c-ok" : "chip c-check",
    reason: row.failureReason,
  }));
  const recentText = logins.loading ? "불러오는 중…" : logins.error ? logins.error : recent.length === 0 ? "접속 기록이 없습니다." : "";

  const groupTabs = TASK_GROUPS.map((group) => {
    const count = pending ? group.types.reduce((sum, type) => sum + (pending.byType[type] ?? 0), 0) : null;
    const on = group.key === query.group;

    return {
      key: group.key,
      label: count === null ? group.label : `${group.label} ${count}`,
      cls: on ? "pill on" : "pill",
      selected: on ? "true" : "false",
      title: group.types.map((type) => TASK_LABELS[type]).join(" · "),
      pick: () => setQuery({ group: group.key }),
    };
  });
  const [first, second] = groupTasks;
  const groupRows = [...first.rows, ...second.rows]
    .sort((a, b) => a.waitingSinceFull.localeCompare(b.waitingSinceFull))
    .slice(0, DASHBOARD_TASK_ROWS)
    .map(taskRowValues);
  const groupTotal = first.total !== null && second.total !== null ? first.total + second.total : null;
  const groupError = first.error ?? second.error;
  const dashTasks = {
    tabs: groupTabs,
    rows: groupRows,
    phase: tablePhase(first.loading || second.loading, groupError, groupRows.length),
    errorText: groupError,
    retry: () => {
      first.reload();
      second.reload();
    },
    more: groupTotal !== null && groupTotal > groupRows.length ? `오래 기다린 ${groupRows.length}건만 보입니다(전체 ${groupTotal}건).` : "",
  };

  // ---------------- 업무 처리 현황 ----------------
  const typeOptions = [
    { value: "", label: "모든 종류" },
    ...(Object.keys(TASK_LABELS) as TaskType[]).map((type) => ({
      value: type,
      label: pending ? `${TASK_LABELS[type]} ${pending.byType[type] ?? 0}` : TASK_LABELS[type],
    })),
  ];
  const tasks = {
    typeOptions,
    type: {
      value: query.taskType,
      onChange: (e: Change) => setQuery({ taskType: e.target.value as TaskType | "", taskPage: 1 }),
    },
    overdue: { checked: query.overdueOnly, onChange: () => setQuery({ overdueOnly: !query.overdueOnly, taskPage: 1 }) },
    rows: taskList.rows.map(taskRowValues),
    phase: tablePhase(taskList.loading, taskList.error, taskList.rows.length),
    errorText: taskList.error,
    retry: taskList.reload,
    emptyText: query.overdueOnly ? "지연된 업무가 없습니다." : "처리 대기 업무가 없습니다.",
    pager: pager(query.taskPage, taskList.totalPages, taskList.total, (page) => setQuery({ taskPage: page })),
  };

  // ---------------- 상담사 계정 관리 ----------------
  const form = state.form;
  const asking = state.ask && state.ask.forAdmin === adminId ? state.ask : null;
  const busy = accounts.submitting;
  const issue = (source: TemporaryPasswordView | null, row: Pick<AccountRow, "name" | "email">, reason: string) => {
    if (!source) return;
    setState({ issued: { ...source, forAdmin: adminId, name: row.name, email: row.email, reason }, copied: false });
  };
  const finish = (text: string) => setState({ ask: null, done: { text, forAdmin: adminId } });

  const run = async (row: AccountRow, kind: AccountAsk | "unlock" | "activate") => {
    setState({ done: null });

    if (kind === "resetPassword") {
      const result = await accounts.resetPassword(row.id);
      if (result) {
        issue(result, row, "비밀번호 초기화");
        finish(`${row.name} 계정의 비밀번호를 초기화했습니다.`);
      }
    } else if (kind === "reactivate") {
      const result = await accounts.reactivate(row.id);
      if (result) {
        issue(result, row, "휴면 해제");
        finish(`${row.name} 계정의 휴면을 풀었습니다.`);
      }
    } else if (kind === "deactivate") {
      if (await accounts.setActive(row.id, false)) finish(`${row.name} 계정을 비활성화했습니다.`);
    } else if (kind === "logoutAll") {
      if (await accounts.logoutAll(row.id)) finish(`${row.name} 계정의 로그인을 모두 끊었습니다.`);
    } else if (kind === "unlock") {
      if (await accounts.unlock(row.id)) finish(`${row.name} 계정의 잠금을 풀었습니다.`);
    } else if (await accounts.setActive(row.id, true)) {
      finish(`${row.name} 계정을 다시 활성화했습니다.`);
    }
  };

  const accountRows = accounts.rows.map((row) => {
    const ask = (kind: AccountAsk) => () => setState({ ask: { userId: row.id, kind, forAdmin: adminId }, done: null });
    const actions = [
      row.can.resetPassword ? { label: "비밀번호 초기화", cls: "btn btn-s btn-sm", onClick: ask("resetPassword") } : null,
      row.can.unlock ? { label: "잠금 해제", cls: "btn btn-s btn-sm", onClick: () => run(row, "unlock") } : null,
      row.can.reactivate ? { label: "휴면 해제", cls: "btn btn-s btn-sm", onClick: ask("reactivate") } : null,
      row.can.activate ? { label: "다시 활성화", cls: "btn btn-s btn-sm", onClick: () => run(row, "activate") } : null,
      row.can.deactivate ? { label: "비활성화", cls: "btn btn-s btn-sm", onClick: ask("deactivate") } : null,
      row.can.logoutAll ? { label: "강제 로그아웃", cls: "btn btn-s btn-sm", onClick: ask("logoutAll") } : null,
    ].filter((action): action is { label: string; cls: string; onClick: () => void } => action !== null);
    const thisAsk = asking && asking.userId === row.id ? asking.kind : null;

    return {
      key: row.id,
      name: row.name,
      self: row.isSelf ? "(나)" : "",
      email: row.email,
      role: row.roleLabel,
      active: row.activeLabel,
      activeCls: row.active ? "chip c-ok" : "chip c-type",
      tags: row.tags.map((tag) => ({
        label: tag.label,
        cls: tag.tone === "red" ? "chip c-check" : tag.tone === "amber" ? "chip c-ing" : "chip c-type",
      })),
      lockedUntil: row.lockedUntil ? `${row.lockedUntil}에 풀림` : "",
      cases: row.caseCountLabel,
      lastLogin: row.lastLoginAt,
      actions,
      noActions: actions.length === 0 ? (row.isSelf ? "자기 계정" : "") : "",
      asking: thisAsk !== null,
      askText: thisAsk ? ASK_TEXT[thisAsk].question(row.name) : "",
      askLabel: thisAsk ? ASK_TEXT[thisAsk].label : "",
      confirm: () => {
        if (thisAsk) void run(row, thisAsk);
      },
    };
  });

  const issued = state.issued && state.issued.forAdmin === adminId ? state.issued : null;
  const done = state.done && state.done.forAdmin === adminId ? state.done.text : "";
  const field = (key: "email" | "name") => ({
    value: form[key],
    onChange: (e: Change) => setState((current) => ({ form: { ...current.form, [key]: e.target.value } })),
  });

  const accountsView = {
    email: field("email"),
    name: field("name"),
    role: {
      value: form.role,
      onChange: (e: Change) => setState((current) => ({ form: { ...current.form, role: e.target.value as UserRole } })),
    },
    busy,
    createLabel: busy && accounts.busyId === null ? "만드는 중…" : "계정 만들기",
    create: async (e: { preventDefault: () => void }) => {
      e.preventDefault();
      setState({ done: null, ask: null });

      const created = await accounts.create({ email: form.email, name: form.name, role: form.role });

      if (!created) return;

      setState({ form: INITIAL_ADMIN_STATE.form });
      issue(created.temporaryPassword, created.account, "새 계정");
      if (created.temporaryPassword) setState({ done: { text: `${created.account.name} 계정을 만들었습니다.`, forAdmin: adminId } });
    },
    issued: issued
      ? {
          who: `${issued.name} (${issued.email})`,
          reason: issued.reason,
          password: issued.temporaryPassword,
          expiresAt: issued.expiresAt || NOT_PROVIDED,
          copied: state.copied,
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
        }
      : null,
    done,
    error: accounts.error,
    caseCountError: accounts.caseCountError,
    rows: accountRows,
    phase: tablePhase(accounts.loading, accounts.rows.length === 0 ? accounts.error : null, accountRows.length),
    retry: accounts.reload,
    busyRow: accounts.busyId,
    cancelAsk: () => setState({ ask: null }),
  };

  // ---------------- 접속 기록 ----------------
  const actionOptions = [
    { value: "", label: "모든 동작" },
    ...Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => ({ value, label })),
  ];
  const auditView = {
    actionOptions,
    action: { value: query.auditAction, onChange: (e: Change) => setQuery({ auditAction: e.target.value, auditPage: 1 }) },
    result: {
      value: query.auditResult,
      onChange: (e: Change) => setQuery({ auditResult: e.target.value as AuditResultFilter, auditPage: 1 }),
    },
    start: { value: query.auditStart, onChange: (e: Change) => setQuery({ auditStart: e.target.value, auditPage: 1 }) },
    end: { value: query.auditEnd, onChange: (e: Change) => setQuery({ auditEnd: e.target.value, auditPage: 1 }) },
    rangeError: audit.rangeError,
    rows: audit.rows.map((row) => ({
      key: row.id,
      at: row.at,
      name: row.actorName,
      role: row.actorRoleLabel,
      action: row.actionLabel,
      result: row.resultLabel,
      resultCls: row.success ? "chip c-ok" : "chip c-check",
      reason: row.failureReason,
      ip: row.ip,
      browser: row.browser,
      userAgent: row.userAgent,
    })),
    phase: tablePhase(audit.loading, audit.error, audit.rows.length),
    // 기간이 거꾸로면 부르지 않는다(rangeError 를 위에 보인다).
    emptyText: audit.rangeError ? "기간을 고쳐 주세요." : "조건에 맞는 기록이 없습니다.",
    errorText: audit.error,
    retry: audit.reload,
    pager: pager(query.auditPage, audit.totalPages, audit.total, (page) => setQuery({ auditPage: page })),
  };

  const titles: Record<AdminView, string> = {
    dashboard: "관리자 대시보드",
    tasks: "업무 처리 현황",
    accounts: "상담사 계정 관리",
    audit: "접속 기록",
  };

  return {
    ...sidebarValues(session),
    menu,
    title: titles[view],
    isDashboard: view === "dashboard",
    isTasks: view === "tasks",
    isAccounts: view === "accounts",
    isAudit: view === "audit",
    dateLabel: dashboard.dateLabel,
    notReady: NOT_READY,
    stats,
    statsNotice: someFailed ? notice("일부 숫자를 불러오지 못했습니다.", { alert: true, retry: dashboard.reload }) : null,
    alerts,
    recent,
    recentText,
    recentAlert: Boolean(logins.error),
    dashTasks,
    tasks,
    accounts: accountsView,
    audit: auditView,
  };
}

/** 관리자가 아니거나 로그인을 확인하지 못했을 때 보여 줄 안내. 서버는 부르지 않는다. */
export function adminBlockedNotice(session: AuthSession): ScreenNotice {
  return (
    screenNotice({ session }) ??
    notice("관리자 계정만 볼 수 있는 화면입니다.", { href: "/Main", hrefLabel: "홈으로" })
  );
}
