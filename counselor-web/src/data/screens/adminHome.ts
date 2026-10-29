// 관리자 홈(AdminHome) 값. 디자인 counselor-design/screens/AdminHome.dc.html '기관 현황'.
//
// 서버 값으로 채우는 것:
//  - 진행 중 사례: GET /cases?status=ACTIVE 의 전체 건수(useCaseList). 종결을 포함한 전체는 useAdminDashboard.caseTotal.
//  - 처리 대기 업무 · 지연: useAdminDashboard.pendingTasks(무엇을 세는지는 adminRows.PENDING_TASK_TYPES)
//  - 활성 상담사 / 전체 상담사 · 비활성 수: useAdminDashboard.counselors
//  - 업무 처리 현황 표: useAdminTasks 두 종류씩(admin.ts taskGroupValues). 새 디자인에는 없고 앱에 있던 구역이라
//    디자인의 '긴급 알림 현황' 자리에 둔다(팀 질문 D5 의 추천 — 앱의 기존 관리자 기능은 새 메뉴에서도 유지).
//  - 최근 접속 활동: useAdminDashboard.recentLogins(로그인 기록 최근 5건)
//  - 상담원별 업무량의 담당 사례(종결 포함): useAdminAccounts 의 계정별 사례 수
//
// 서버에 없어 '—' · 준비 중으로 두는 것(값을 지어내지 않는다):
//  - 긴급 알림(아이 연계 앱의 긴급 응답 · 상담원 확인 · '담당자에게 다시 알림'): 아이 앱 서버가 없다(팀 결정 A2). 표는 만들지 않는다.
//  - 접속 위치(기관 내부망 · 외부): 내부망 정의가 없다. 'OTP 실패' 구분: OTP 가 없다(D1). 실패한 시도의 계정 ID: 서버가 남기지 않는다.
//  - 업무량의 위험도 상 · 이번 주 상담 · STT 검수 대기 · 일지 미작성: 상담원별 집계 API 와 사례 단위 위험도 규칙이 없다.
//  - 재배정 필요 건수: 비활성 상담사의 '진행 중' 사례만 셀 방법이 없다(계정별 사례 수는 종결 포함).

import { PENDING_TASKS_NOTE } from "../adminRows";
import type { AdminAccountsState } from "../useAdminAccounts";
import type { AdminDashboardState, DashboardCell } from "../useAdminDashboard";
import type { AdminTasksState } from "../useAdminTasks";
import type { AuthSession } from "../useAuthSession";
import type { CaseListState } from "../useCaseList";
import { NOT_PROVIDED } from "../caseRows";
import { NOT_READY, notice } from "./common";
import {
  ADMIN_PAGES,
  fullDateLabel,
  initialOf,
  overdueTasksHref,
  scrollToId,
  staffDetailHref,
  tablePhase,
  taskGroupValues,
  type TaskGroupKey,
} from "./admin";

/** 관리자 홈의 업무 처리 현황 구역 id. 위 '처리 대기 업무' 카드가 이 구역으로 굴린다. */
export const HOME_TASKS_ID = "admin-home-tasks";

export interface AdminHomeInput {
  session: AuthSession;
  dashboard: AdminDashboardState;
  /** useCaseList({ status: "ACTIVE" }). 건수만 쓴다. */
  activeCases: CaseListState;
  /** 업무 표 묶음의 두 종류. */
  groupTasks: [AdminTasksState, AdminTasksState];
  accounts: AdminAccountsState;
  group: TaskGroupKey;
  setGroup: (key: TaskGroupKey) => void;
  /** 오늘(그릴 때). 시험에서 바꿔 넣는다. */
  now?: Date;
}

function cellText<T>(cell: DashboardCell<T>, show: (value: T) => string): string {
  if (cell.value !== null) return show(cell.value);

  return cell.loading ? "…" : NOT_PROVIDED;
}

export function adminHomeValues(input: AdminHomeInput) {
  const { dashboard, activeCases, groupTasks, accounts, group, setGroup } = input;
  const pending = dashboard.pendingTasks.value;
  const counselors = dashboard.counselors.value;

  // ---------------- 요약 카드 ----------------
  const someFailed =
    [dashboard.caseTotal, dashboard.pendingTasks, dashboard.counselors].some((cell) => cell.error) ||
    Boolean(activeCases.error);
  const kpis = {
    active: {
      value: activeCases.total !== null ? String(activeCases.total) : activeCases.loading ? "…" : NOT_PROVIDED,
      note:
        dashboard.caseTotal.value !== null ? `전체 ${dashboard.caseTotal.value}건 중(종결 포함)` : "",
    },
    pending: {
      value: cellText(dashboard.pendingTasks, (value) => String(value.count)),
      note: pending ? `지연 ${pending.overdue}건 · 아래 업무 처리 현황` : "아래 업무 처리 현황",
      title: PENDING_TASKS_NOTE,
      // 디자인의 '#urgent' 앵커 자리. 해시 앵커 대신 같은 화면의 구역으로 굴린다.
      go: scrollToId(HOME_TASKS_ID),
    },
    counselors: {
      value: cellText(dashboard.counselors, (value) => String(value.active)),
      total: counselors ? ` / ${counselors.total}` : "",
      note: counselors ? `비활성 ${counselors.total - counselors.active}명` : "",
      href: ADMIN_PAGES.accounts,
    },
    urgent: {
      value: NOT_PROVIDED,
      note: `${NOT_READY} · 아이 연계 앱 서버 없음`,
    },
  };

  // ---------------- 업무 처리 현황 ----------------
  const tasks = {
    ...taskGroupValues({ groupTasks, pending, group, setGroup }),
    moreHref: ADMIN_PAGES.tasks,
    // 앱의 옛 '즉시 확인 필요' 줄(기준 시간을 넘긴 업무 → 바로가기) 자리. 녹음 업로드를 포함한 전체 지연이다
    // (Backend 는 종류를 하나만 거를 수 있어 '지연만' 목록에서 녹음 업로드를 뺄 수 없다).
    overdueText: pending ? `기준 시간을 넘긴 업무 ${pending.overdueAll}건(녹음 업로드 포함)` : "",
    overdueHref: overdueTasksHref(),
  };

  // ---------------- 최근 접속 활동 ----------------
  const logins = dashboard.recentLogins;
  const recentRows = (logins.value ?? []).map((row) => ({
    key: row.id,
    at: row.shortAt || row.at || NOT_PROVIDED,
    atFull: row.at,
    // 없는 계정으로 시도한 로그인은 이름이 없다(서버가 시도한 이메일을 남기지 않는다).
    name: row.actorName,
    nameWeight: row.knownActor ? "500" : "700",
    role: row.knownActor ? row.actorRoleLabel : "",
    ev: row.success ? "로그인 성공" : "로그인 실패",
    evCls: row.success ? "chip c-ok" : "chip c-urgent",
    reason: row.failureReason,
    ip: row.ip,
    net: NOT_PROVIDED,
  }));
  const recent = {
    rows: recentRows,
    phase: tablePhase(logins.loading, logins.error, recentRows.length),
    emptyText: "접속 기록이 없습니다.",
    errorText: logins.error,
    retry: dashboard.reload,
    href: ADMIN_PAGES.security,
  };

  // ---------------- 상담원별 업무량 ----------------
  const counselorRows = accounts.rows.filter((row) => row.role === "COUNSELOR");
  const maxCases = Math.max(0, ...counselorRows.map((row) => row.caseCount ?? 0));
  const loadRows = counselorRows.map((row) => ({
    key: row.id,
    href: staffDetailHref(row.id),
    ini: initialOf(row.name),
    name: row.name,
    rank: row.active ? row.roleLabel : `${row.roleLabel} · 비활성`,
    // 비활성 상담사는 흐리게(+ 글자 '비활성'). 색 · 흐림만으로 나타내지 않는다.
    op: row.active ? 1 : 0.6,
    cases: row.caseCountLabel,
    w: row.caseCount !== null && maxCases > 0 ? `${Math.round((row.caseCount / maxCases) * 100)}%` : "0%",
    hi: NOT_PROVIDED,
    week: NOT_PROVIDED,
    stt: NOT_PROVIDED,
    note: NOT_PROVIDED,
  }));
  const load = {
    rows: loadRows,
    phase: tablePhase(accounts.loading, accounts.rows.length === 0 ? accounts.error : null, loadRows.length),
    emptyText: "상담원 계정이 없습니다.",
    errorText: accounts.error,
    retry: accounts.reload,
    // 이번 주 상담 · STT 검수 대기는 서버 조회(회차 목록 · GET /tasks/summary?counselor_id=)가 있지만 상담원마다 부르는 훅이 없다.
    // 위험도 상 · 일지 미작성은 사례 단위 위험도 규칙 · '미작성' 정의가 없다.
    note:
      `위험도 상 · 일지 미작성은 ${NOT_READY}입니다(사례 단위 기준이 정해지지 않음). ` +
      `이번 주 상담 · STT 검수 대기도 ${NOT_READY}입니다(상담원별로 세는 연결이 아직 없음).` +
      (accounts.caseCountError ? ` ${accounts.caseCountError} 담당 사례 칸은 ${NOT_PROVIDED} 로 둡니다.` : ""),
    href: ADMIN_PAGES.accounts,
  };

  return {
    dateLabel: fullDateLabel(input.now ?? new Date()),
    statsNotice: someFailed
      ? notice("일부 숫자를 불러오지 못했습니다.", {
          alert: true,
          retry: () => {
            dashboard.reload();
            activeCases.reload();
          },
        })
      : null,
    kpis,
    tasksId: HOME_TASKS_ID,
    tasks,
    recent,
    load,
    notReady: NOT_READY,
  };
}
