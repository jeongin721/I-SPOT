// 홈(대시보드) 훅. GET /cases(진행 중 건수만) + GET /tasks/summary + 업무 종류마다 GET /tasks?task_type=(가장 오래 기다린 1건과 건수).
// 10/30 디자인 '미처리 업무' 는 종류별 한 줄(칩 = 업무 이름 · '별칭 n회차 외' · 오른쪽 건수)이다. 오래 기다린 종류부터 HOME_TASK_COUNT 줄.
//
// 상담사는 담당 사례 · 업무만, 관리자는 전체 사례 · 모든 상담사의 업무가 온다(Backend 가 거른다).
// 관리자도 업무를 자기 것으로 좁히지 않는다(counselor_id) — 사례 목록에는 담당자로 거르는 조건이 없어,
// 한쪽만 좁히면 두 숫자의 범위가 어긋난다. 화면은 관리자일 때 '전체' 라고 밝혀 보인다.
//
// Backend 에 없는 것(화면이 '—' · 준비 중으로 둔다): 오늘 일정 · 다음 상담까지 남은 시간 · 아이 앱 긴급 응답.
// 업무는 회차 처리 대기(녹음 업로드 · 원문 변환 · 검수 · AI 분석 · 재시도)뿐이다. 상담일지 작성 · 앱 확인은 업무 종류에 없다.
//
// 같은 탭에서 회차 상태가 바뀌면(sessionEvents) 조용히 다시 부른다.
// 10/30 디자인: '진행 중 내담자' 카드 아래 사례 몇 건(최근 등록순 HOME_CASE_COUNT 건). 사례마다 **마지막 회차 하나**와 그 회차의
// 회차 전체 상담원 판단(11.1)만 부른다 — 사례 단위 위험도는 팀 결정 전이라 만들지 않고 'n회차 판단' 으로 밝혀 보인다.
// signal-history 는 분석 결과 · 전사본 화자까지 읽어 홈에 쓰기엔 무겁다(민규 #122 리뷰). 한 사례가 실패해도 그 줄만 값 없이 둔다.

import { cases, riskAssessments, tasks } from "../api/endpoints";
import { TASK_LABELS, type RiskLevel, type SessionStatus, type TaskSummary, type TaskType } from "../api/types";
import type { AuthSession } from "./useAuthSession";
import { toTaskRow, type TaskRow } from "./adminRows";
import { sessionStep, type SessionStep } from "./sessionRows";
import { useRemote } from "./useRemote";

/** 홈에 줄로 보이는 업무 종류 수. 나머지 종류는 건수만 보인다. */
export const HOME_TASK_COUNT = 3;

/** 업무 종류 한 줄. 행 값은 그 종류에서 가장 오래 기다린 회차다. */
export interface HomeTask extends TaskRow {
  /** 회차 처리 단계. 이어서 할 화면을 고르는 데 쓴다. */
  step: SessionStep;
  /** 이 종류의 업무 수. */
  count: number;
}

/** 홈 '진행 중 내담자' 카드에 줄로 보이는 사례 수. */
export const HOME_CASE_COUNT = 3;

export interface HomeCase {
  id: string;
  alias: string;
  /** 마지막 회차의 회차 전체 상담원 판단. 판단 전이거나 못 불렀으면 null. */
  level: RiskLevel | null;
  /** 마지막 회차 번호 · 상태. 회차가 없거나 이력을 못 불렀으면 null. */
  latest: { number: number; status: SessionStatus } | null;
}

export interface HomeDashboardData {
  /** 진행 중(ACTIVE) 사례 수. */
  activeCases: number;
  /** 최근 등록한 진행 중 사례 HOME_CASE_COUNT 건. */
  cases: HomeCase[];
  summary: TaskSummary;
  /** 업무가 있는 종류 전부(가장 오래 기다린 회차가 앞선 종류부터). 화면은 앞 HOME_TASK_COUNT 줄만 그린다. */
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
  const taskTypes = Object.keys(TASK_LABELS) as TaskType[];
  const [casePage, summary, typePages] = await Promise.all([
    cases.list({ status: "ACTIVE", page: 1, page_size: HOME_CASE_COUNT }),
    tasks.summary(),
    Promise.all(taskTypes.map((task_type) => tasks.list({ task_type, page: 1, page_size: 1 }))),
  ]);
  const now = Date.now();
  const homeCases = await Promise.all(
    casePage.items.map(async (item): Promise<HomeCase> => {
      const base = { id: item.id, alias: item.child_alias, level: null, latest: null };
      try {
        const page = await cases.listSessions(item.id, { page: 1, page_size: 1 });
        const last = page.items[0];
        if (!last) return base;
        const judged = await riskAssessments.getOverall(last.id).catch(() => null);
        return {
          ...base,
          level: judged?.counselor_level ?? null,
          latest: { number: last.session_number, status: last.status },
        };
      } catch {
        return base;
      }
    }),
  );

  return {
    activeCases: casePage.meta.total,
    cases: homeCases,
    summary,
    tasks: typePages
      .flatMap((page) =>
        page.items[0]
          ? [{ ...toTaskRow(page.items[0], now), step: sessionStep(page.items[0].session_status).step, count: page.meta.total }]
          : [],
      )
      .sort((a, b) => a.waitingSinceAt - b.waitingSinceAt),
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
