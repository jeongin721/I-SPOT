// 관리자 · 사례 목록(AdminCases) 화면 값(10/30 디자인 counselor-design/screens/AdminCases.dc.html).
//
// 서버 연결: useAdminCases(GET /cases 전체 쪽 + GET /auth/users). 검색 · 상담원 거르기는 받은 목록에서 한다.
//
// Backend 에 없는 값은 다른 값으로 대신 채우지 않는다(caseRows.ts 와 같은 규칙).
//  - 위험도 · 신고접수일 · 관리 기간(신고접수일부터 셈): 사례 단위 값이 없어 '—'. 위험도 거르기 · 정렬 단추는 준비 중.
//  - 최근 상담: 사례의 last_session_at 은 상담 일시를 넣지 않은 회차를 등록일로 채워 셈하므로 최근 상담일로 보이지 않는다.
//  - 진행 단계(초기 조사 · 종결 검토): 없다. 사례 상태(진행 · 종결)만 보인다.
//  - 재배정 필요(디자인: 담당 상담원 비활성): 진행 중 사례의 담당 계정이 비활성이거나 지워졌으면 그렇게 보인다.
//    계정 목록을 받지 못하면 비활성은 알 수 없어 지워진 계정만 센다.
// 이름은 아동 별칭이다(Backend 는 실명을 저장하지 않는다). 디자인처럼 이름은 링크가 아니고, 담당 상담원은 상담사 상세로 간다.

import type { User } from "../../api/types";
import { NOT_PROVIDED, toCaseRow, type CaseRow } from "../caseRows";
import type { AdminCasesState } from "../useAdminCases";
import type { AuthSession } from "../useAuthSession";
import { staffDetailHref } from "./admin";
import { NOT_READY, screenNotice, sidebarValues } from "./common";

/** 상담원 거르기. ALL_STAFF 이면 전체, 아니면 담당 계정 ID. */
export const ALL_STAFF = "all";

export interface AdminCasesUiState {
  who: string;
  q: string;
}

export function initialAdminCasesState(): AdminCasesUiState {
  return { who: ALL_STAFF, q: "" };
}

interface AdminCasesInput {
  session: AuthSession;
  list: AdminCasesState;
  state: AdminCasesUiState;
  setState: (patch: Partial<AdminCasesUiState>) => void;
}

interface Staff {
  id: string;
  name: string;
  count: number;
}

/** 진행 중 사례인데 담당 계정이 지워졌거나(이름 없음) 비활성인가. users 가 없으면 비활성은 모른다(지워진 것만). */
export function needsReassign(row: CaseRow, counselorId: string, users: Map<string, User> | null): boolean {
  if (row.status !== "ACTIVE") return false;
  if (row.counselorName === NOT_PROVIDED) return true;
  const user = users?.get(counselorId);
  return Boolean(users && (!user || !user.is_active));
}

/**
 * 상담원 거르기 단추. 계정 목록이 있으면 상담원 계정 전부(사례 0건 포함)와 사례를 가진 다른 계정,
 * 없으면 사례에 적힌 담당자만. 이름순.
 */
function staffList(counts: Map<string, { name: string; count: number }>, users: User[] | null): Staff[] {
  const staff = new Map<string, Staff>();
  for (const user of users ?? []) {
    if (user.role === "COUNSELOR" || counts.has(user.id)) staff.set(user.id, { id: user.id, name: user.name, count: 0 });
  }
  for (const [id, { name, count }] of counts) {
    const known = staff.get(id);
    staff.set(id, { id, name: known?.name ?? name, count });
  }
  return [...staff.values()].sort((a, b) => a.name.localeCompare(b.name, "ko"));
}

export function adminCasesValues(input: AdminCasesInput) {
  const { session, list, state, setState } = input;
  const all = (list.cases ?? []).map((source) => ({ source, row: toCaseRow(source) }));
  const users = list.users ? new Map(list.users.map((user) => [user.id, user])) : null;

  const counts = new Map<string, { name: string; count: number }>();
  for (const { source, row } of all) {
    const current = counts.get(source.counselor_id);
    counts.set(source.counselor_id, { name: row.counselorName, count: (current?.count ?? 0) + 1 });
  }
  const staff = staffList(counts, list.users);
  // 고른 상담원이 목록에서 사라졌으면(다른 관리자 계정으로 바뀜 등) 전체로 본다.
  const who = staff.some((s) => s.id === state.who) ? state.who : ALL_STAFF;

  const q = state.q.trim().toLowerCase();
  const rows = all
    .filter(({ source }) => who === ALL_STAFF || source.counselor_id === who)
    .filter(({ row }) => !q || row.alias.toLowerCase().includes(q) || row.caseNumber.toLowerCase().includes(q))
    .map(({ source, row }) => {
      const reassign = needsReassign(row, source.counselor_id, users);
      return {
        key: row.id,
        id: row.caseNumber,
        name: row.alias,
        ini: row.initial,
        age: row.birthYearLabel,
        who: row.counselorName,
        // 지워진 계정은 상세가 없다.
        whoHref: row.counselorName === NOT_PROVIDED ? null : staffDetailHref(source.counselor_id),
        risk: row.riskLabel,
        date: row.reportDate,
        period: NOT_PROVIDED,
        last: NOT_PROVIDED,
        stage: reassign ? "재배정 필요" : `사례 ${row.statusLabel}`,
        stCls: reassign ? "chip c-urgent" : row.status === "CLOSED" ? "chip c-check" : "chip c-normal",
      };
    });

  // 위험도 거르기(디자인: 전체 · 상 · 중 · 하). 사례 단위 위험도가 Backend 에 없어 '전체' 만 고를 수 있다(CaseList 와 같음).
  const riskF = [
    ["all", "전체"],
    ["상", "상"],
    ["중", "중"],
    ["하", "하"],
  ].map(([key, label]) => ({ key, label, cls: key === "all" ? "on" : "", pressed: key === "all", disabled: key !== "all" }));
  // 정렬(디자인: 최근 접수 · 위험도 · 관리 기간)은 모두 Backend 에 없는 값으로 해서 고를 수 없다. 목록은 사례 등록 최신순이다.
  const sortF = [
    ["date", "최근 접수"],
    ["risk", "위험도"],
    ["long", "관리 기간"],
  ].map(([key, label]) => ({ key, label, cls: "", pressed: false, disabled: true }));
  const staffF = [{ id: ALL_STAFF, name: "전체", count: all.length }, ...staff].map((s) => ({
    key: s.id,
    label: `${s.name} ${s.count}`,
    cls: who === s.id ? "on" : "",
    pressed: who === s.id,
    disabled: false,
    pick: () => setState({ who: s.id }),
  }));

  const casesLoaded = list.cases !== null;
  const reassignCount = all.filter(({ source, row }) => needsReassign(row, source.counselor_id, users)).length;
  const activeStaff = staff.filter((s) => s.count > 0).length;

  return {
    ...sidebarValues(session),
    notice: screenNotice({ session, loading: list.loading, error: list.error, retry: list.reload }),
    kpis: [
      {
        label: "전체 사례",
        v: casesLoaded ? `${all.length}건` : NOT_PROVIDED,
        note: casesLoaded ? `상담원 ${activeStaff}명 담당` : "",
      },
      { label: "위험도 상", v: NOT_PROVIDED, note: NOT_READY },
      { label: "종결 검토", v: NOT_PROVIDED, note: NOT_READY },
      {
        label: "재배정 필요",
        v: casesLoaded ? `${reassignCount}건` : NOT_PROVIDED,
        note: list.users ? "담당 상담원 비활성 · 계정 없음" : "상담원 목록을 받지 못해 지워진 계정만 셈",
      },
    ],
    q: state.q,
    setQ: (e: { target: { value: string } }) => setState({ q: e.target.value }),
    riskF,
    sortF,
    staffF,
    notReady: NOT_READY,
    rows,
    empty: casesLoaded && rows.length === 0,
    countLabel: casesLoaded ? `사례 ${rows.length}건 표시 · 사례 등록 최신순` : "",
    dataNote:
      `위험도 · 신고접수일 · 관리 기간 · 최근 상담 · 진행 단계(초기 조사 · 종결 검토)는 ${NOT_READY}입니다(서버에 아직 없는 값). ` +
      "진행 단계 칸에는 사례 상태(진행 · 종결)를 보입니다.",
    usersError: list.usersError,
  };
}
