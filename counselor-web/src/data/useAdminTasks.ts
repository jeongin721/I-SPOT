// 업무 처리 현황 훅(GET /tasks, 관리자는 모든 상담사의 업무). 관리자 대시보드의 업무 표에 쓴다.
//
// 사람이 처리할 차례인 회차를 오래 기다린 순서로 받는다. 종류별 수(탭 숫자)는 useAdminDashboard 의 pendingTasks.byType 에 있다.
// Backend 는 종류를 하나만 거를 수 있다(task_type). 두 종류를 한 탭에 모으려면 화면이 종류별로 이 훅을 나눠 부른다.
//
// Backend 에 없는 것:
//  - 문서 승인 대기: 업무 종류에 없다(문서 승인은 상담사 검수다). 탭을 두려면 NOT_PROVIDED 로 둔다.
//  - '제출 시각': 업무에는 이 상태로 기다리기 시작한 시각(waiting_since)만 있다.
//  - 재처리(다시 변환 · 다시 분석) 요청은 이 훅에 넣지 않았다. 관리자가 상담사의 회차를 다시 돌리게 할지는 팀 결정이다
//    (요청 자체는 회차 훅 useSessionDetail · useTranscriptReview · useSessionAnalysis 에 있다).
//
// 같은 탭에서 회차 상태가 바뀌면(sessionEvents) 조용히 다시 부른다. 조건이 바뀌면 늦게 온 앞 조건의 응답은 버린다.

import { useMemo } from "react";

import { tasks } from "../api/endpoints";
import type { Paged, TaskItem, TaskType } from "../api/types";
import { adminKey, type AdminAccess, type AdminHookOptions } from "./adminAccess";
import { toTaskRow, type TaskRow } from "./adminRows";
import { useRemote } from "./useRemote";

/** 한 쪽에 받는 건수 기본값. Backend 상한은 100. */
export const TASK_PAGE_SIZE = 20;

export interface AdminTasksOptions extends AdminHookOptions {
  /** 이 종류만. 빼면 모든 종류. */
  taskType?: TaskType;
  /** 지연(서버 기준 시간 초과)만. */
  overdueOnly?: boolean;
  /** 이 상담사의 업무만. */
  counselorId?: string;
  /** 1부터. */
  page?: number;
  pageSize?: number;
}

export interface AdminTasksState {
  /** 오래 기다린 것부터. */
  rows: TaskRow[];
  /** 조건에 맞는 전체 건수. 아직 모르면 null. */
  total: number | null;
  totalPages: number;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useAdminTasks(
  access: AdminAccess,
  { enabled = true, taskType, overdueOnly = false, counselorId, page = 1, pageSize = TASK_PAGE_SIZE }: AdminTasksOptions = {},
): AdminTasksState {
  const query = useMemo(
    () => ({
      task_type: taskType,
      overdue_only: overdueOnly || undefined,
      counselor_id: counselorId || undefined,
      page,
      page_size: pageSize,
    }),
    [taskType, overdueOnly, counselorId, page, pageSize],
  );
  const remote = useRemote<Paged<TaskItem>>(
    adminKey(access, enabled, `tasks:${JSON.stringify(query)}`),
    () => tasks.list(query),
    "업무 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => true,
  );

  // 기다린 시간은 받은 시각 기준이다(조회할 때마다 다시 센다).
  const rows = useMemo(() => {
    const now = Date.now();

    return (remote.data?.items ?? []).map((item) => toTaskRow(item, now));
  }, [remote.data]);

  return {
    rows,
    total: remote.data ? remote.data.meta.total : null,
    totalPages: Math.max(1, remote.data?.meta.total_pages ?? 1),
    loading: remote.loading,
    error: remote.error,
    reload: remote.reload,
  };
}
