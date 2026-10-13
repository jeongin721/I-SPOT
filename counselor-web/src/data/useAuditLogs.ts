// 접속 기록 · 감사 로그 훅(GET /auth/audit-logs, 관리자 전용). ispotvscode/src/admin/AdminApp.tsx 의 AccessLogView 에서 옮겨 왔다.
//
// 기본은 로그인 기록(action=LOGIN)이다. 계정 관리 기록(잠금 해제 · 강제 로그아웃 등)을 보려면 action 을 바꾼다(adminRows.AUDIT_ACTION_LABELS).
// 역할 칸은 계정 목록(GET /auth/users)의 지금 역할이다(그때 역할이 아니다). 계정 목록을 못 받으면 역할 칸만 NOT_PROVIDED.
//
// 보안 이벤트 화면의 심각도 · 탐지는 Backend 에 없다. 실패한 로그인만 모아 보려면 result: "FAILURE" 로 부르되,
// 심각도를 지어 붙이지 않는다(adminRows 머리말).
//
// 조건(결과 · 기간 · 쪽)이 바뀌면 앞 결과를 비우고 다시 부른다. 늦게 온 앞 조건의 응답은 버린다(useRemote).

import { useEffect, useMemo } from "react";

import { auth } from "../api/endpoints";
import type { AuditLog, AuditStatus, Paged, User, UserRole } from "../api/types";
import { adminKey, type AdminAccess, type AdminHookOptions } from "./adminAccess";
import { onAccountsChanged } from "./adminEvents";
import { toAuditRange, toAuditRow, type AuditRow } from "./adminRows";
import { useRemote } from "./useRemote";

/** 한 쪽에 받는 건수 기본값. Backend 상한은 100. */
export const AUDIT_PAGE_SIZE = 20;

export interface AuditLogsOptions extends AdminHookOptions {
  /** 감사 동작. 기본 "LOGIN". 빈 문자열이면 모든 동작. */
  action?: string;
  /** "ALL"(기본) · "SUCCESS" · "FAILURE". */
  result?: "ALL" | AuditStatus;
  /** 시작일(YYYY-MM-DD, 사용자 시간대, 그날 0시부터). 빈 문자열이면 조건 없음. */
  startDate?: string;
  /** 종료일(YYYY-MM-DD, 그날 끝까지). */
  endDate?: string;
  /** 1부터. */
  page?: number;
  pageSize?: number;
}

export interface AuditLogsState {
  /** 최신순. */
  rows: AuditRow[];
  /** 조건에 맞는 전체 건수. 아직 모르면 null. */
  total: number | null;
  /** 전체 쪽 수(최소 1). */
  totalPages: number;
  /** 시작일이 종료일보다 늦으면 그 문장(이때는 부르지 않는다). 없으면 null. */
  rangeError: string | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const loadUsers = () => auth.listUsers();

export function useAuditLogs(
  access: AdminAccess,
  {
    enabled = true,
    action = "LOGIN",
    result = "ALL",
    startDate = "",
    endDate = "",
    page = 1,
    pageSize = AUDIT_PAGE_SIZE,
  }: AuditLogsOptions = {},
): AuditLogsState {
  const rangeError = startDate && endDate && startDate > endDate ? "시작일이 종료일보다 늦습니다." : null;

  // 조건을 key 에 담는다. 조건이 바뀌면 useRemote 가 앞 결과를 비우고 늦은 응답을 버린다.
  const query = useMemo(
    () => ({
      action: action || undefined,
      status: result === "ALL" ? undefined : result,
      ...toAuditRange(startDate, endDate),
      page,
      page_size: pageSize,
    }),
    [action, result, startDate, endDate, page, pageSize],
  );
  const key = rangeError ? null : adminKey(access, enabled, `audit:${JSON.stringify(query)}`);

  const logs = useRemote<Paged<AuditLog>>(
    key,
    () => auth.auditLogs(query),
    "접속 기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );
  const users = useRemote<User[]>(adminKey(access, enabled, "audit:users"), loadUsers, "", () => false);

  // 계정 관리 훅의 요청도 감사 로그에 남는다. 같은 탭에서 바뀌면 조용히 다시 부른다.
  const refreshLogs = logs.refresh;
  const refreshUsers = users.refresh;

  useEffect(
    () =>
      onAccountsChanged(() => {
        refreshLogs();
        refreshUsers();
      }),
    [refreshLogs, refreshUsers],
  );

  const roles = useMemo(
    () => new Map<string, UserRole>((users.data ?? []).map((user) => [user.id, user.role])),
    [users.data],
  );
  const rows = useMemo(() => (logs.data?.items ?? []).map((log) => toAuditRow(log, roles)), [logs.data, roles]);

  return {
    rows,
    total: logs.data ? logs.data.meta.total : null,
    totalPages: Math.max(1, logs.data?.meta.total_pages ?? 1),
    rangeError,
    loading: logs.loading,
    error: logs.error,
    reload: logs.reload,
  };
}
