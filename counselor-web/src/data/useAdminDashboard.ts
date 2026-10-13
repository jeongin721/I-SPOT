// 관리자 대시보드 숫자 훅. 커밋 8aaf63e(옛 앱 관리자 대시보드를 실제 데이터로)에서 옮겨 왔다.
//
//  - 전체 관리 사례: GET /cases 의 meta.total(관리자는 전체 사례, 종결 포함)
//  - 처리 대기 업무 · 지연 · 종류별 수: GET /tasks/summary + GET /tasks?task_type=UPLOAD_AUDIO&overdue_only=true
//    (정의는 adminRows.PENDING_TASK_TYPES)
//  - 활성 상담사 / 전체 상담사: GET /auth/users
//  - 최근 접속 활동 5건: GET /auth/audit-logs?action=LOGIN
// 칸마다 따로 부른다. 한 칸이 실패해도 나머지는 보인다.
//
// 미배정 사례 · 문서 승인 대기 · 보안 경고는 Backend 에 값이 없어 NOT_PROVIDED("—")로 둔다(adminRows 머리말).

import { useCallback, useEffect, useMemo } from "react";

import { auth, cases, tasks } from "../api/endpoints";
import type { AuditLog, TaskSummary, User } from "../api/types";
import { adminKey, type AdminAccess, type AdminHookOptions } from "./adminAccess";
import { onAccountsChanged } from "./adminEvents";
import {
  countCounselors,
  toAdminDateLabel,
  toAuditRow,
  toPendingTasks,
  type AuditRow,
  type PendingTasks,
} from "./adminRows";
import { NOT_PROVIDED } from "./caseRows";
import { ROLE_LABELS } from "./profile";
import { useRemote, type RemoteState } from "./useRemote";

/** 최근 접속 활동에 보여 주는 건수. */
export const RECENT_LOGIN_COUNT = 5;

/** 칸 하나. 불러오는 중이면 value 가 null 이고 loading, 실패하면 value 가 null 이고 error 에 문구. */
export interface DashboardCell<T> {
  value: T | null;
  loading: boolean;
  error: string | null;
}

export interface AdminDashboardState {
  /** "10월 13일 (화)". 그릴 때의 오늘. */
  dateLabel: string;
  /** 로그인한 관리자 이름 · 역할. 관리자가 아니면 빈 문자열. */
  adminName: string;
  adminRoleLabel: string;
  /** 전체 관리 사례(종결 포함). */
  caseTotal: DashboardCell<number>;
  /** 처리 대기 업무 수 · 지연 · 종류별 수. */
  pendingTasks: DashboardCell<PendingTasks>;
  /** 활성 상담사 / 전체 상담사(관리자 계정은 세지 않는다). */
  counselors: DashboardCell<{ active: number; total: number }>;
  /** 최근 로그인 시도(성공 · 실패) 최신순. */
  recentLogins: DashboardCell<AuditRow[]>;
  /** Backend 에 없는 값. 팀 결정 전까지 항상 NOT_PROVIDED. */
  unassignedCases: string;
  /** Backend 에 없는 값. 팀 결정 전까지 항상 NOT_PROVIDED. */
  documentApprovals: string;
  /** Backend 에 없는 값(보안 이벤트 심각도 · 탐지). 팀 결정 전까지 항상 NOT_PROVIDED. */
  securityAlerts: string;
  /** 모든 칸을 다시 부른다. */
  reload: () => void;
}

const FALLBACK = "불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";

function toCell<S, T>(remote: RemoteState<S>, map: (value: S) => T): DashboardCell<T> {
  return {
    value: remote.data === null ? null : map(remote.data),
    loading: remote.loading,
    error: remote.error,
  };
}

const loadCaseTotal = () => cases.list({ page_size: 1 }).then((page) => page.meta.total);

const loadPending = () =>
  Promise.all([
    tasks.summary(),
    tasks.list({ task_type: "UPLOAD_AUDIO", overdue_only: true, page_size: 1 }),
  ]).then(([summary, uploadAudio]): [TaskSummary, number] => [summary, uploadAudio.meta.total]);

const loadUsers = () => auth.listUsers();

const loadRecentLogins = () =>
  auth.auditLogs({ action: "LOGIN", page_size: RECENT_LOGIN_COUNT }).then((page) => page.items);

export function useAdminDashboard(access: AdminAccess, { enabled = true }: AdminHookOptions = {}): AdminDashboardState {
  const caseTotal = useRemote<number>(adminKey(access, enabled, "dashboard:cases"), loadCaseTotal, FALLBACK, () => false);
  // 같은 탭에서 회차 상태가 바뀌면(sessionEvents) 업무 수도 바뀐다.
  const pending = useRemote<[TaskSummary, number]>(
    adminKey(access, enabled, "dashboard:tasks"),
    loadPending,
    FALLBACK,
    () => true,
  );
  const users = useRemote<User[]>(adminKey(access, enabled, "dashboard:users"), loadUsers, FALLBACK, () => false);
  const logins = useRemote<AuditLog[]>(
    adminKey(access, enabled, "dashboard:logins"),
    loadRecentLogins,
    FALLBACK,
    () => false,
  );

  // 계정 관리 훅이 계정을 바꾸면 상담사 수를 다시 센다.
  const refreshUsers = users.refresh;

  useEffect(() => onAccountsChanged(refreshUsers), [refreshUsers]);

  const roles = useMemo(() => new Map((users.data ?? []).map((user) => [user.id, user.role])), [users.data]);

  const reload = useCallback(() => {
    caseTotal.reload();
    pending.reload();
    users.reload();
    logins.reload();
  }, [caseTotal.reload, pending.reload, users.reload, logins.reload]);

  const admin = access.isAdmin ? access.me : null;

  return {
    dateLabel: toAdminDateLabel(new Date()),
    adminName: admin ? admin.name : "",
    adminRoleLabel: admin ? ROLE_LABELS[admin.role] : "",
    caseTotal: toCell(caseTotal, (total) => total),
    pendingTasks: toCell(pending, ([summary, uploadAudioOverdue]) => toPendingTasks(summary, uploadAudioOverdue)),
    counselors: toCell(users, countCounselors),
    recentLogins: toCell(logins, (items) => items.map((log) => toAuditRow(log, roles))),
    unassignedCases: NOT_PROVIDED,
    documentApprovals: NOT_PROVIDED,
    securityAlerts: NOT_PROVIDED,
    reload,
  };
}
