// 관리자 · 아이 연계 앱 관리(AdminApp) 화면 값. 11/17 디자인 counselor-design/screens/AdminApp.dc.html.
//
// 서버 값(11/19 연결):
//  - 앱 연결 현황 · 요약 카드: GET /child-app-cases(관리자는 진행 중 사례 전체) — 연결 상태 · 연결일 · 최근 응답 · 담당 상담사.
//  - 장기 무응답: 연결됨이고 마지막 응답(없으면 연결) 뒤 LONG_SILENT_DAYS 일 넘은 아이. 안부 연락 처리는
//    POST /cases/{id}/child-app/welfare-checks(DONE · OPEN, 처리 내용 200자)로 저장하고, 목록은 마지막 응답 뒤 가장 최근 기록을 보인다.
//
// 디자인과 다른 것:
//  - '초대 코드 보내기': 초대 코드는 담당 상담사만 만든다(관리자가 다시 만들면 상담사가 준 코드가 무효가 됨) — 단추는 준비 중으로 둔다.
//  - '연락 완료로 표시' 를 누르면 처리 내용(선택)을 적는 작은 창을 거친다. 디자인 표의 '처리 내용' 칸을 채울 곳이 없어서다.
//  - 아이 이름은 별칭(사례 목록과 같은 값)이다.

import type { ChildAppCaseRow } from "../../api/types";
import { NOT_PROVIDED } from "../caseRows";
import { NOT_READY } from "./common";
import { tablePhase } from "./admin";
import { alertWhen } from "./adminHome";

/** 이만큼(일) 응답이 없으면 장기 무응답(디자인 '7일 이상'). */
export const LONG_SILENT_DAYS = 7;
/** 이만큼 넘으면 무응답 일수를 붉게(디자인 14일). */
const WARN_DAYS = 14;

export type ConnFilter = "all" | "on" | "wait" | "off";
export type SilentFilter = "all" | "open";

export interface AdminAppInput {
  rows: ChildAppCaseRow[] | null;
  loading: boolean;
  error: string | null;
  off: boolean;
  reload: () => void;
  cf: ConnFilter;
  sf: SilentFilter;
  setCf: (value: ConnFilter) => void;
  setSf: (value: SilentFilter) => void;
  /** 처리 중인 사례 ID(단추를 막는다). */
  busy: string | null;
  /** 연락 완료 창을 연다(사례 ID) · 미처리로 되돌린다. */
  openDone: (caseId: string) => void;
  undo: (caseId: string) => void;
  now?: Date;
}

const ST: Record<ChildAppCaseRow["status"], [ConnFilter, string, string]> = {
  LINKED: ["on", "연결됨", "chip c-ok"],
  INVITED: ["wait", "초대 대기", "chip c-sand"],
  NOT_LINKED: ["off", "미연결", "chip c-check"],
};

const pct = (n: number, total: number) => (total ? Math.round((n / total) * 100) : 0);

function md(value: string | null): string {
  if (!value) return NOT_PROVIDED;
  const at = new Date(value);
  return Number.isNaN(at.getTime()) ? NOT_PROVIDED : `${at.getMonth() + 1}/${String(at.getDate()).padStart(2, "0")}`;
}

/** 마지막 응답(없으면 연결) 뒤 지난 날 수. 연결 전이면 null. */
export function silentDays(row: ChildAppCaseRow, now: Date): number | null {
  if (row.status !== "LINKED") return null;
  const since = row.last_response_at ?? row.linked_at;
  if (!since) return null;
  return Math.floor((now.getTime() - new Date(since).getTime()) / 86_400_000);
}

export function adminAppValues(input: AdminAppInput) {
  const now = input.now ?? new Date();
  const rows = input.rows ?? [];
  const total = rows.length;
  const on = rows.filter((r) => r.status === "LINKED").length;
  const wait = rows.filter((r) => r.status === "INVITED").length;
  const off = total - on - wait;

  const segOf = <K extends string>(cur: K, opts: [K, string][], pick: (k: K) => void) =>
    opts.map(([key, label]) => ({ key, label, cls: cur === key ? "on" : "", pressed: cur === key ? "true" : "false", pick: () => pick(key) }));

  const conn = rows
    .filter((r) => input.cf === "all" || ST[r.status][0] === input.cf)
    .map((r) => ({
      key: r.case_id,
      kid: r.child_alias,
      cid: r.case_number,
      who: r.counselor_name ?? NOT_PROVIDED,
      st: ST[r.status][1],
      stCls: ST[r.status][2],
      since: r.status === "LINKED" ? md(r.linked_at) : NOT_PROVIDED,
      last: r.last_response_at ? alertWhen(r.last_response_at, now) : NOT_PROVIDED,
      canInvite: r.status !== "LINKED",
      invLabel: r.status === "INVITED" ? "초대 코드 다시 보내기" : "초대 코드 보내기",
    }));

  const silentAll = rows
    .map((r) => ({ r, days: silentDays(r, now) }))
    .filter((x): x is { r: ChildAppCaseRow; days: number } => x.days !== null && x.days >= LONG_SILENT_DAYS)
    .sort((a, b) => b.days - a.days)
    .map(({ r, days }) => {
      const done = r.welfare_status === "DONE";
      const tried = r.welfare_status === "TRIED";
      return {
        key: r.case_id,
        kid: r.child_alias,
        cid: r.case_number,
        who: r.counselor_name ?? NOT_PROVIDED,
        last: r.last_response_at ? md(r.last_response_at) : "응답 없음",
        days,
        dCls: days >= WARN_DAYS ? "warn" : "",
        open: !done,
        st: done ? "연락 완료" : tried ? "연락 시도" : "미처리",
        stCls: done ? "chip c-ok" : tried ? "chip c-sand" : "chip c-urgent",
        memo: r.welfare_note ? `${md(r.welfare_at)} · ${r.welfare_note}` : done && r.welfare_at ? md(r.welfare_at) : NOT_PROVIDED,
        btnLabel: done ? "미처리로 되돌리기" : "연락 완료로 표시",
        btnCls: done ? "btn-s" : "btn-p",
        busy: input.busy === r.case_id,
        toggle: () => (done ? input.undo(r.case_id) : input.openDone(r.case_id)),
      };
    });
  const silentOpen = silentAll.filter((r) => r.open).length;
  const silent = input.sf === "open" ? silentAll.filter((r) => r.open) : silentAll;

  const phase = (count: number) => (input.off ? ("empty" as const) : tablePhase(input.loading && !input.rows, input.error, count));
  const offText = "아이 앱 기능이 꺼져 있습니다.";

  return {
    kpis: {
      total: input.rows ? String(total) : NOT_PROVIDED,
      on: input.rows ? String(on) : NOT_PROVIDED,
      onNote: `연결률 ${pct(on, total)}%`,
      notOn: input.rows ? String(off + wait) : NOT_PROVIDED,
      notOnNote: `미연결 ${off} · 초대 대기 ${wait}`,
      silent: input.rows ? String(silentAll.length) : NOT_PROVIDED,
      silentNote: `안부 연락 미처리 ${silentOpen}명`,
    },
    stack: {
      label: `연결됨 ${on}명, 초대 대기 ${wait}명, 미연결 ${off}명`,
      on: `${total ? (on / total) * 100 : 0}%`,
      wait: `${total ? (wait / total) * 100 : 0}%`,
      off: `${total ? (off / total) * 100 : 0}%`,
      legend: [
        ["#C2A36B", `연결됨 ${on}명 · ${pct(on, total)}%`],
        ["#DAD5C9", `초대 대기 ${wait}명 · ${pct(wait, total)}%`],
        ["#7A776F", `미연결 ${off}명 · ${pct(off, total)}%`],
      ] as const,
    },
    cFilters: segOf(input.cf, [["all", "전체"], ["on", "연결됨"], ["wait", "초대 대기"], ["off", "미연결"]], input.setCf),
    sFilters: segOf(input.sf, [["all", "전체"], ["open", "미처리"]], input.setSf),
    conn: {
      rows: conn,
      phase: phase(conn.length),
      emptyText: input.off ? offText : "해당하는 아이가 없습니다.",
      errorText: input.error ?? "",
      retry: input.reload,
    },
    silent: {
      rows: silent,
      phase: phase(silent.length),
      emptyText: input.off ? offText : `${LONG_SILENT_DAYS}일 넘게 응답이 없는 아이가 없습니다.`,
      errorText: input.error ?? "",
      retry: input.reload,
    },
    inviteTitle: `${NOT_READY} · 초대 코드는 담당 상담사가 아이 상세에서 만듭니다`,
  };
}
