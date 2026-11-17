// 홈 '미처리 업무' 줄을 누르면 옆에 뜨는 작은 창(2026-11-11 경진님): 그 업무 종류에 걸린 회차를 오래 기다린 순으로 보여 주고,
// 상담사가 아동을 골라 그 회차 화면으로 간다. 줄을 누르기 전에는 부르지 않는다(taskType 이 null).
// 상담사는 담당 사례 업무만, 관리자는 모든 상담사의 업무가 온다(Backend 가 거른다 — 홈 숫자와 같은 범위).

import { tasks } from "../api/endpoints";
import type { TaskType } from "../api/types";
import { toTaskRow, type TaskRow } from "./adminRows";
import { homeTaskHref } from "./screens/main";
import { sessionStep } from "./sessionRows";
import { useRemote } from "./useRemote";

/** 창에 보이는 회차 수(서버 page_size 상한 100). 넘치면 '외 n건' 으로 알린다. */
export const TASK_PICK_SIZE = 50;

export interface TaskPickRow extends TaskRow {
  /** 이 회차의 이어서 할 화면. */
  href: string;
}

export interface TaskPickData {
  total: number;
  rows: TaskPickRow[];
}

async function loadTaskPick(taskType: string): Promise<TaskPickData> {
  const page = await tasks.list({ task_type: taskType as TaskType, page: 1, page_size: TASK_PICK_SIZE });
  const now = Date.now();
  const rows = page.items
    .map((item) => ({
      ...toTaskRow(item, now),
      href: homeTaskHref({ step: sessionStep(item.session_status).step, caseId: item.case_id, sessionId: item.session_id }),
    }))
    .sort((a, b) => a.waitingSinceAt - b.waitingSinceAt);
  return { total: page.meta.total, rows };
}

export function useTaskPick(taskType: TaskType | null) {
  return useRemote(taskType, loadTaskPick, "업무 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.", () => true);
}
