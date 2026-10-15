// 홈(대시보드) 훅. GET /cases(진행 중 건수만) + GET /tasks/summary + GET /tasks(오래 기다린 것부터 HOME_TASK_COUNT 건 — 디자인의 세 줄).
//
// 상담사는 담당 사례 · 업무만, 관리자는 전체 사례 · 모든 상담사의 업무가 온다(Backend 가 거른다).
// 관리자도 업무를 자기 것으로 좁히지 않는다(counselor_id) — 사례 목록에는 담당자로 거르는 조건이 없어,
// 한쪽만 좁히면 두 숫자의 범위가 어긋난다. 화면은 관리자일 때 '전체' 라고 밝혀 보인다.
//
// Backend 에 없는 것(화면이 '—' · 준비 중으로 둔다): 오늘 일정 · 다음 상담까지 남은 시간 · 아이 앱 긴급 응답.
// 업무는 회차 처리 대기(녹음 업로드 · 원문 변환 · 검수 · AI 분석 · 재시도)뿐이다. 상담일지 작성 · 앱 확인은 업무 종류에 없다.
//
// 같은 탭에서 회차 상태가 바뀌면(sessionEvents) 조용히 다시 부른다.

import { cases, tasks } from "../api/endpoints";
import type { TaskSummary } from "../api/types";
import type { AuthSession } from "./useAuthSession";
import { toTaskRow, type TaskRow } from "./adminRows";
import { sessionStep, type SessionStep } from "./sessionRows";
import { useRemote } from "./useRemote";

/** 홈에 줄로 보이는 업무 수. 나머지는 건수만 보인다. */
export const HOME_TASK_COUNT = 3;

export interface HomeTask extends TaskRow {
  /** 회차 처리 단계. 이어서 할 화면을 고르는 데 쓴다. */
  step: SessionStep;
}

export interface HomeDashboardData {
  /** 진행 중(ACTIVE) 사례 수. */
  activeCases: number;
  summary: TaskSummary;
  /** 오래 기다린 것부터 HOME_TASK_COUNT 건까지. */
  tasks: HomeTask[];
}

export interface HomeDashboardState {
  data: HomeDashboardData | null;
  /** 관리자라 전체(모든 상담사) 숫자인가. */
  wholeOrg: boolean;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

async function loadHomeDashboard(): Promise<HomeDashboardData> {
  const [casePage, summary, taskPage] = await Promise.all([
    cases.list({ status: "ACTIVE", page: 1, page_size: 1 }),
    tasks.summary(),
    tasks.list({ page: 1, page_size: HOME_TASK_COUNT }),
  ]);
  const now = Date.now();

  return {
    activeCases: casePage.meta.total,
    summary,
    tasks: taskPage.items.map((item) => ({ ...toTaskRow(item, now), step: sessionStep(item.session_status).step })),
  };
}

/** session 은 useAuthSession() 결과. 로그인이 확인된 뒤에만 부르고, 다른 계정으로 바뀌면 앞 계정의 값을 보이지 않는다. */
export function useHomeDashboard(session: AuthSession): HomeDashboardState {
  const me = session.status === "signedIn" ? session.me : null;
  const remote = useRemote(
    me ? `${me.id}:home` : null,
    loadHomeDashboard,
    "홈 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => true,
  );

  return {
    data: remote.data,
    wholeOrg: session.isAdmin,
    loading: remote.loading,
    error: remote.error,
    reload: remote.reload,
  };
}
