// 접속 기록 · 보안 이벤트(AdminSecurity) 값. 디자인 counselor-design/screens/AdminSecurity.dc.html.
//
// 서버 연결: useAuditLogs(GET /auth/audit-logs) — 목록 하나 + 오늘 로그인 실패 수(같은 훅, 한 쪽 1건으로 전체 건수만),
// useAdminAccounts — 지금 잠긴 계정 수와 잠금 해제(POST /auth/users/{id}/unlock).
//  - 요약 카드는 디자인처럼 누르면 목록을 거르는 단추다. 로그인 실패는 디자인의 '24시간' 대신 '오늘(0시부터)' 이다
//    (훅의 기간 조건이 날짜 단위다). 잠긴 계정 카드를 누르면 '계정 잠김' 기록과 지금 잠긴 계정(잠금 해제 단추)을 보인다.
//  - 앱에 있던 자세한 조건(동작 · 결과 · 시작일 · 종료일 · 쪽)은 그대로 둔다. 디자인의 검색 칸은 서버 검색이 없어 두지 않는다.
// 서버에 없어 '—' · 준비 중: 외부 IP 접속 · 접속 위치(기관 내부망 정의 없음), 보안 이벤트 심각도 · 탐지, IP 차단 목록,
// 실패한 시도의 계정 ID(서버가 남기지 않음). OTP 실패 카드 · 거르기는 OTP 가 없어(D1) 두지 않는다.

import type { AuditLogsOptions, AuditLogsState } from "../useAuditLogs";
import type { AdminAccountsState } from "../useAdminAccounts";
import type { AuthSession } from "../useAuthSession";
import { AUDIT_ACTION_LABELS } from "../adminRows";
import { NOT_PROVIDED } from "../caseRows";
import { NOT_READY } from "./common";
import { localDate, pager, segButton, staffDetailHref, tablePhase } from "./admin";

export type AuditResultFilter = "ALL" | "SUCCESS" | "FAILURE";

/** 목록 조건. 화면 함수의 useState 로 들고 useAuditLogs 에 넘긴다. */
export interface SecurityQuery {
  /** 감사 동작. 기본 LOGIN, 빈 문자열이면 모든 동작. */
  action: string;
  result: AuditResultFilter;
  start: string;
  end: string;
  page: number;
}

export const INITIAL_SECURITY_QUERY: SecurityQuery = { action: "LOGIN", result: "ALL", start: "", end: "", page: 1 };

/** 오늘(사용자 시간대 0시부터) 로그인 실패 수를 세는 useAuditLogs 조건. 한 쪽 1건만 받고 전체 건수를 쓴다. */
export function todayFailureOptions(now: Date): AuditLogsOptions {
  const today = localDate(now);

  return { action: "LOGIN", result: "FAILURE", startDate: today, endDate: today, pageSize: 1 };
}

/** 화면 상태(Logic.state): 잠금 해제 결과 안내. */
export interface SecurityUiState {
  done: { text: string; forAdmin: string } | null;
}

export const INITIAL_SECURITY_UI: SecurityUiState = { done: null };

type Quick = "all" | "fail" | "lock";

const QUICK_QUERY: Record<Quick, Pick<SecurityQuery, "action" | "result">> = {
  all: { action: "LOGIN", result: "ALL" },
  fail: { action: "LOGIN", result: "FAILURE" },
  lock: { action: "ACCOUNT_LOCKED", result: "ALL" },
};

type Change = { target: { value: string } };

export function adminSecurityValues(input: {
  session: AuthSession;
  audit: AuditLogsState;
  /** todayFailureOptions 로 부른 useAuditLogs. */
  todayFailures: AuditLogsState;
  accounts: AdminAccountsState;
  query: SecurityQuery;
  setQuery: (patch: Partial<SecurityQuery>) => void;
  state: SecurityUiState;
  setState: (patch: Partial<SecurityUiState>) => void;
}) {
  const { session, audit, todayFailures, accounts, query, setQuery, state, setState } = input;
  const adminId = session.me?.id ?? "";

  // 지금 조건이 빠른 거르기 셋 가운데 무엇인가(자세한 조건으로 바꿨으면 없음).
  const quick = (Object.keys(QUICK_QUERY) as Quick[]).find(
    (key) => QUICK_QUERY[key].action === query.action && QUICK_QUERY[key].result === query.result,
  );
  const pickQuick = (key: Quick) => setQuery({ ...QUICK_QUERY[key], page: 1 });
  // 요약 카드는 다시 누르면 전체 접속 기록으로 돌아간다(디자인 kb).
  const toggleQuick = (key: Quick) => () => pickQuick(quick === key ? "all" : key);

  // ---------------- 요약 카드 ----------------
  const locked = accounts.rows.filter((row) => row.can.unlock);
  const lockedCount =
    accounts.rows.length > 0 ? String(locked.length) : accounts.loading ? "…" : accounts.error ? NOT_PROVIDED : "0";
  const kpis = {
    fail: {
      value:
        todayFailures.total !== null
          ? String(todayFailures.total)
          : todayFailures.loading
            ? "…"
            : NOT_PROVIDED,
      note: todayFailures.error ? "불러오지 못했습니다" : "오늘 0시부터 · 로그인 기록 기준",
      cls: quick === "fail" ? "card kpi kb on" : "card kpi kb",
      pressed: quick === "fail" ? "true" : "false",
      pick: toggleQuick("fail"),
    },
    external: {
      value: NOT_PROVIDED,
      note: `${NOT_READY} · 기관 내부망 정의 없음`,
    },
    lock: {
      value: lockedCount,
      note: "로그인 실패가 이어지면 서버가 잠급니다",
      cls: quick === "lock" ? "card kpi kb on" : "card kpi kb",
      pressed: quick === "lock" ? "true" : "false",
      pick: toggleQuick("lock"),
    },
  };

  const quickSeg = [
    segButton("all", "전체 접속 기록", quick === "all", () => pickQuick("all")),
    segButton("fail", "로그인 실패", quick === "fail", () => pickQuick("fail")),
    segButton("lock", "계정 잠김", quick === "lock", () => pickQuick("lock")),
  ];

  // ---------------- 지금 잠긴 계정(잠긴 계정 카드를 눌렀을 때) ----------------
  const unlock = async (userId: string, name: string) => {
    setState({ done: null });
    if (await accounts.unlock(userId)) setState({ done: { text: `${name} 계정의 잠금을 풀었습니다.`, forAdmin: adminId } });
  };
  const lockedList = {
    show: quick === "lock",
    rows: locked.map((row) => ({
      key: row.id,
      name: row.name,
      email: row.email,
      href: staffDetailHref(row.id),
      lockedUntil: row.lockedUntil ? `${row.lockedUntil}에 풀림` : "풀어 줄 때까지 잠김",
      unlock: () => void unlock(row.id, row.name),
    })),
    emptyText: accounts.loading ? "불러오는 중…" : "지금 잠긴 계정이 없습니다.",
    busy: accounts.submitting,
    busyRow: accounts.busyId,
  };

  // ---------------- 자세한 조건 · 목록 ----------------
  const rows = audit.rows.map((row) => ({
    key: row.id,
    at: row.at || NOT_PROVIDED,
    name: row.actorName,
    nameWeight: row.knownActor ? "500" : "700",
    role: row.knownActor ? row.actorRoleLabel : "",
    ev: row.actionLabel,
    result: row.resultLabel,
    resultCls: row.success ? "chip c-ok" : "chip c-urgent",
    reason: row.failureReason,
    ip: row.ip,
    net: NOT_PROVIDED,
    browser: row.browser,
    userAgent: row.userAgent,
  }));

  return {
    notReady: NOT_READY,
    kpis,
    quickSeg,
    lockedList,
    done: state.done && state.done.forAdmin === adminId ? state.done.text : "",
    actionError: accounts.error,
    actionOptions: [
      { value: "", label: "모든 동작" },
      ...Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => ({ value, label })),
    ],
    action: { value: query.action, onChange: (e: Change) => setQuery({ action: e.target.value, page: 1 }) },
    result: {
      value: query.result,
      onChange: (e: Change) => setQuery({ result: e.target.value as AuditResultFilter, page: 1 }),
    },
    start: { value: query.start, onChange: (e: Change) => setQuery({ start: e.target.value, page: 1 }) },
    end: { value: query.end, onChange: (e: Change) => setQuery({ end: e.target.value, page: 1 }) },
    rangeError: audit.rangeError,
    rows,
    phase: tablePhase(audit.loading, audit.error, rows.length),
    // 기간이 거꾸로면 부르지 않는다(rangeError 를 위에 보인다).
    emptyText: audit.rangeError ? "기간을 고쳐 주세요." : "조건에 맞는 기록이 없습니다.",
    errorText: audit.error,
    retry: audit.reload,
    pager: pager(query.page, audit.totalPages, audit.total, (page) => setQuery({ page })),
  };
}
