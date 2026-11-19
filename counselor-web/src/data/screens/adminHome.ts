// 관리자 홈(AdminHome) 값. 디자인 counselor-design/screens/AdminHome.dc.html '기관 현황'.
//
// 서버 값으로 채우는 것:
//  - 진행 중 사례: GET /cases?status=ACTIVE 의 전체 건수(useCaseList). 종결을 포함한 전체는 useAdminDashboard.caseTotal.
//  - 처리 대기 업무 · 지연: useAdminDashboard.pendingTasks(무엇을 세는지는 adminRows.PENDING_TASK_TYPES)
//  - 활성 상담사 / 전체 상담사 · 비활성 수: useAdminDashboard.counselors
//  - 긴급 알림 현황 표(11/19 연결): GET /child-app-alerts/recent — 오늘 · 어제 긴급 알림(확인한 것 포함)과 그 전에 남은 확인 전.
//    담당이 아닌 관리자라 '아이 응답' 칸은 내용 대신 이유 문구(CHILD_ALERT_TEXT)다.
//  - 업무 처리 현황 표: useAdminTasks 두 종류씩(admin.ts taskGroupValues). 새 디자인에는 없고 앱에 있던 구역이라
//    긴급 알림 현황 아래에 둔다(팀 질문 D5 의 추천 — 앱의 기존 관리자 기능은 새 메뉴에서도 유지).
//  - 최근 접속 활동: useAdminDashboard.recentLogins(로그인 기록 최근 5건)
//  - 상담원별 업무량의 담당 사례(종결 포함): useAdminAccounts 의 계정별 사례 수
//
// 서버에 없어 '—' · 준비 중으로 두는 것(값을 지어내지 않는다):
//  - 긴급 알림 표의 '담당자에게 다시 알림': 알림(푸시) 발송이 없어 단추를 준비 중으로 둔다.
//  - 접속 위치(기관 내부망 · 외부): 내부망 정의가 없다. 'OTP 실패' 구분: OTP 가 없다(D1). 실패한 시도의 계정 ID: 서버가 남기지 않는다.
//  - 업무량의 위험도 상 · 이번 주 상담 · STT 검수 대기 · 일지 미작성: 상담원별 집계 API 와 사례 단위 위험도 규칙이 없다.
//  - 재배정 필요 건수: 비활성 상담사의 '진행 중' 사례만 셀 방법이 없다(계정별 사례 수는 종결 포함).

import type { ChildOpenAlert, ChildRecentAlert } from "../../api/types";
import { CHILD_ALERT_TEXT } from "../useCaseChildApp";
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

/** 관리자 홈의 긴급 알림 현황 구역 id. 위 '긴급 알림 · 확인 전' 카드가 이 구역으로 굴린다. */
export const HOME_URGENT_ID = "urgent";

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
  /** 확인 안 한 콩콩 알림(관리자는 기관 전체). 꺼져 있거나 못 받았으면 null. */
  childAlerts?: ChildOpenAlert[] | null;
  /** 긴급 알림 현황(GET /child-app-alerts/recent). 아이 앱이 꺼져 있으면 null. */
  recentAlerts?: { data: ChildRecentAlert[] | null; loading: boolean; error: string | null; reload: () => void; off: boolean };
  /** 긴급 알림 표 거르기: 전체 · 확인 전. */
  urgentFilter?: "all" | "pending";
  setUrgentFilter?: (value: "all" | "pending") => void;
  group: TaskGroupKey;
  setGroup: (key: TaskGroupKey) => void;
  /** 오늘(그릴 때). 시험에서 바꿔 넣는다. */
  now?: Date;
}

const pad2 = (n: number) => String(n).padStart(2, "0");

/** '오늘 08:12' · '어제 21:40' · '10/13 22:31'(디자인 표 그대로). */
export function alertWhen(value: string, now: Date): string {
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return NOT_PROVIDED;
  const time = `${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((day(now) - day(at)) / 86_400_000);
  if (diff === 0) return `오늘 ${time}`;
  if (diff === 1) return `어제 ${time}`;
  return `${at.getMonth() + 1}/${at.getDate()} ${time}`;
}

/** 확인 전으로 지난 시간: '25분' · '1시간 50분' · '1일 11시간'. */
export function elapsedText(from: string, now: Date): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(from).getTime()) / 60_000));
  if (minutes < 60) return `${minutes}분`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간${minutes % 60 ? ` ${minutes % 60}분` : ""}`;
  return `${Math.floor(hours / 24)}일${hours % 24 ? ` ${hours % 24}시간` : ""}`;
}

function cellText<T>(cell: DashboardCell<T>, show: (value: T) => string): string {
  if (cell.value !== null) return show(cell.value);

  return cell.loading ? "…" : NOT_PROVIDED;
}

export function adminHomeValues(input: AdminHomeInput) {
  const { dashboard, activeCases, groupTasks, accounts, group, setGroup } = input;
  const now = input.now ?? new Date();
  const recentData = input.recentAlerts?.data ?? null;
  const isRecent = (r: ChildRecentAlert) => alertWhen(r.created_at, now).startsWith("오늘") || alertWhen(r.created_at, now).startsWith("어제");
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
    // 긴급 알림 · 확인 전(11/10 연결): 기관 전체의 확인 안 한 콩콩 긴급 알림 수. 아이 앱이 꺼져 있으면 '—'.
    // 11/19: 디자인대로 '오늘·어제 긴급 n건 중', 누르면 아래 긴급 알림 현황으로.
    urgent: input.childAlerts
      ? {
          value: String(input.childAlerts.filter((alert) => alert.urgent).length),
          note: recentData
            ? `오늘·어제 긴급 ${recentData.filter((r) => isRecent(r)).length}건 중`
            : `확인 필요 ${input.childAlerts.filter((alert) => !alert.urgent).length}건 · 아이 앱`,
        }
      : { value: NOT_PROVIDED, note: `${NOT_READY} · 아이 앱이 꺼져 있음` },
    urgentGo: scrollToId(HOME_URGENT_ID),
  };

  // ---------------- 긴급 알림 현황 ----------------
  const uf = input.urgentFilter ?? "all";
  const pendingRows = (recentData ?? []).filter((r) => !r.acknowledged_at);
  const urgentRows = (uf === "pending" ? pendingRows : recentData ?? []).map((r) => {
    const pendingRow = !r.acknowledged_at;
    const msg = CHILD_ALERT_TEXT[r.reason] ?? CHILD_ALERT_TEXT.NEEDS_CHECK;
    return {
      key: r.id,
      t: alertWhen(r.last_at ?? r.created_at, now),
      kid: r.child_alias,
      cid: r.case_number,
      msg: r.repeat_count ? `${msg} ${r.repeat_count}번 더 눌렀어요.` : msg,
      who: r.counselor_name ?? NOT_PROVIDED,
      pending: pendingRow,
      st: pendingRow
        ? `확인 전 · ${elapsedText(r.created_at, now)} 경과`
        : `${alertWhen(r.acknowledged_at as string, now)} 확인${r.acknowledged_by_name ? ` · ${r.acknowledged_by_name}` : ""}`,
      stCls: pendingRow ? "chip c-urgent" : "chip c-ok",
    };
  });
  const recentState = input.recentAlerts;
  const urgentTable = {
    id: HOME_URGENT_ID,
    rows: urgentRows,
    phase: recentState?.off
      ? ("empty" as const)
      : tablePhase(Boolean(recentState?.loading) && !recentData, recentState?.error ?? null, urgentRows.length),
    emptyText: recentState?.off
      ? "아이 앱 기능이 꺼져 있습니다."
      : uf === "pending"
        ? "확인 전인 긴급 알림이 없습니다."
        : "오늘 · 어제 긴급 알림이 없습니다.",
    errorText: recentState?.error ?? "",
    retry: recentState?.reload ?? (() => undefined),
    filters: (
      [
        ["all", `전체 ${(recentData ?? []).length}`],
        ["pending", `확인 전 ${pendingRows.length}`],
      ] as const
    ).map(([key, label]) => ({
      key,
      label,
      cls: uf === key ? "on" : "",
      pressed: uf === key ? "true" : "false",
      pick: () => input.setUrgentFilter?.(key),
    })),
    // 알림(푸시) 발송이 없어 '담당자에게 다시 알림' 은 준비 중이다.
    nudgeTitle: `${NOT_READY} · 푸시 알림을 연결한 뒤 쓸 수 있습니다`,
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
    dateLabel: fullDateLabel(now),
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
    urgent: urgentTable,
    tasksId: HOME_TASKS_ID,
    tasks,
    recent,
    load,
    notReady: NOT_READY,
  };
}
