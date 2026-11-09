// 통합 사례 관리(CaseList) 화면 값.
//  - 이름은 아동 실명(등록된 사례), 없으면 별칭이다(목록을 with_child_name=true 로 부름). 나이 대신 출생연도를 보여 준다.
//  - 신고접수일은 사례에 저장한 값, 위험도는 분석이 끝난 가장 최근 회차의 상담원 판단, 판단 전이면 서식 4 위험도(우선)이다. 없으면 '—'.
//  - 정렬(전체 · 신고접수일 · 위험도)은 서버가 한다(GET /cases?sort=&order=). 전체는 등록 최신순. 같은 단추를 다시 누르면 ↑ · ↓ 가 바뀐다(11/09 디자인).
//  - 쪽 번호도 서버가 나눈다(한 쪽 10건, 번호는 4개씩).
//  - '실명 보기' 토글은 10/30 디자인에서 빠졌다(화면에는 이름을 그대로 보이고 인쇄 · 복사 때만 가린다).
//  - 검색은 서버가 한다: 제목 · 사례 ID · 별칭(부분)과 실명(공백 무시 정확히 같을 때). 실명 일부로는 찾지 않는다(암호화 저장).
//  - 이름 · 상세 링크는 사례 ID 를 넘긴다(#/CaseDetail?case=…).

import type { CaseListOrder, CaseListSort, RiskLevel } from "../../api/types";
import type { AuthSession } from "../useAuthSession";
import type { CaseListState } from "../useCaseList";
import { sidebarValues } from "./common";
import { screenHref } from "./links";

/** 한 쪽 건수(디자인). */
export const CASE_LIST_PER_PAGE = 10;
const PAGE_BLOCK = 4;

const RISK_CHIP: Record<RiskLevel, string> = { HIGH: "chip c-hi", MEDIUM: "chip c-mid", LOW: "chip c-lo" };

export function caseListValues(input: {
  session: AuthSession;
  list: CaseListState;
  search: string;
  setSearch: (value: string) => void;
  sort: CaseListSort | null;
  order: CaseListOrder;
  /** 정렬을 바꾸면 1쪽으로 돌아간다(CaseList). */
  setSort: (value: CaseListSort | null, order: CaseListOrder) => void;
  page: number;
  setPage: (value: number) => void;
}) {
  const { session, list, search, setSearch, sort, order, setSort, page, setPage } = input;
  const me = session.me;
  const rows = list.rows.map((r) => ({
    id: r.caseNumber,
    ini: r.initial,
    name: r.name,
    age: r.birthYearLabel,
    date: r.reportDate,
    risk: r.riskLabel,
    cls: r.riskLevel ? RISK_CHIP[r.riskLevel] : "note",
    href: screenHref("/CaseDetail", { caseId: r.id }),
  }));
  // 정렬 단추(디자인: 전체 · 신고접수일 · 위험도).
  const options: [CaseListSort | null, string][] = [
    [null, "전체"],
    ["report_date", "신고접수일"],
    ["risk", "위험도"],
  ];
  const arrow = (key: CaseListSort | null) => (key && key === sort ? (order === "desc" ? " ↑" : " ↓") : "");
  const press = (key: CaseListSort | null) => () => {
    if (key && key === sort) setSort(key, order === "desc" ? "asc" : "desc");
    else setSort(key, "desc");
  };
  const filters = options.map(([key, label]) => ({ label: label + arrow(key), cls: key === sort ? "on" : "", pick: press(key) }));

  // 쪽 번호(디자인: 4개씩, 앞뒤 묶음은 '…').
  const totalPages = Math.max(1, Math.ceil((list.total ?? 0) / CASE_LIST_PER_PAGE));
  const current = Math.min(Math.max(1, page), totalPages);
  const go = (n: number) => () => setPage(Math.min(Math.max(1, n), totalPages));
  const blockStart = Math.floor((current - 1) / PAGE_BLOCK) * PAGE_BLOCK + 1;
  const blockEnd = Math.min(blockStart + PAGE_BLOCK - 1, totalPages);
  const pages: { label: string; cls: string; go: () => void; aria: string; cur?: "page" }[] = [];
  if (blockStart > 1) pages.push({ label: "…", cls: "pg-n pg-gap", go: go(blockStart - 1), aria: `${blockStart - 1}쪽` });
  for (let n = blockStart; n <= blockEnd; n++) {
    pages.push({ label: String(n), cls: n === current ? "pg-n on" : "pg-n", go: go(n), aria: `${n}쪽`, cur: n === current ? "page" : undefined });
  }
  if (blockEnd < totalPages) pages.push({ label: "…", cls: "pg-n pg-gap", go: go(blockEnd + 1), aria: `${blockEnd + 1}쪽` });
  const pager = {
    show: (list.total ?? 0) > 0,
    pages,
    first: go(1),
    prev: go(current - 1),
    next: go(current + 1),
    last: go(totalPages),
    atStart: current === 1,
    atEnd: current === totalPages,
  };

  // 표 본문: 확인 · 불러오는 중 → 오류 → 빈 목록 → 행
  const sessionError = session.status === "error";
  let phase = "rows";
  if (session.status === "checking" || list.loading) phase = "loading";
  if (sessionError || (phase !== "loading" && list.error)) phase = "error";
  else if (phase === "rows" && rows.length === 0) phase = "empty";

  let countLabel = "";
  if (list.total != null) {
    countLabel = `${me && me.role === "ADMIN" ? "전체" : "담당"} 사례 ${list.total}건`;
  }

  return {
    ...sidebarValues(session),
    rows,
    filters,
    pager,
    countLabel,
    search: { value: search, onChange: (e: { target: { value: string } }) => setSearch(e.target.value) },
    phase,
    errorText: sessionError ? session.error : list.error,
    retry: sessionError ? session.recheck : list.reload,
    emptyText: search.trim() ? "검색 결과가 없습니다. 이름은 전체 이름으로만 찾습니다(일부로는 찾지 않음)." : "사례가 없습니다.",
  };
}
