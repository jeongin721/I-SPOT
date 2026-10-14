// 통합 사례 관리(CaseList) 화면 값.
//  - 이름은 아동 별칭이다(Backend 는 실명을 저장하지 않는다). 나이 대신 출생연도를 보여 준다.
//  - 신고접수일 · 위험도 · 실명 보기는 Backend 에 값이 없어 자리만 두고 '—' · 준비 중으로 둔다(팀 결정 대기).
//  - 이름 · 상세 링크는 사례 ID 를 넘긴다(#/CaseDetail?case=…).

import type { AuthSession } from "../useAuthSession";
import type { CaseListState } from "../useCaseList";
import { NOT_READY, sidebarValues } from "./common";
import { screenHref } from "./links";

export function caseListValues(input: {
  session: AuthSession;
  list: CaseListState;
  search: string;
  setSearch: (value: string) => void;
}) {
  const { session, list, search, setSearch } = input;
  const me = session.me;
  const rows = list.rows.map((r) => ({
    id: r.caseNumber,
    ini: r.initial,
    name: r.alias,
    age: r.birthYearLabel,
    date: r.reportDate,
    risk: r.riskLabel,
    cls: "note",
    href: screenHref("/CaseDetail", { caseId: r.id }),
  }));
  // 위험도는 사례 단위 값이 Backend 에 없다. '전체'만 고를 수 있다.
  const filters = [
    ["all", list.total == null ? "전체" : `전체 ${list.total}`],
    ["상", "상"],
    ["중", "중"],
    ["하", "하"],
  ].map(([k, label]) => ({ label, cls: k === "all" ? "on" : "", disabled: k !== "all" }));

  // 표 본문: 확인 · 불러오는 중 → 오류 → 빈 목록 → 행
  const sessionError = session.status === "error";
  let phase = "rows";
  if (session.status === "checking" || list.loading) phase = "loading";
  if (sessionError || (phase !== "loading" && list.error)) phase = "error";
  else if (phase === "rows" && rows.length === 0) phase = "empty";

  let countLabel = "";
  if (list.total != null) {
    countLabel = `${me && me.role === "ADMIN" ? "전체" : "담당"} 사례 ${list.total}건`;
    if (list.total > rows.length) countLabel += ` · 처음 ${rows.length}건 표시`;
  }

  return {
    ...sidebarValues(session),
    rows,
    filters,
    real: false,
    tgBg: "#DCD5C3",
    tgX: "2px",
    notReady: NOT_READY,
    countLabel,
    search: { value: search, onChange: (e: { target: { value: string } }) => setSearch(e.target.value) },
    phase,
    errorText: sessionError ? session.error : list.error,
    retry: sessionError ? session.recheck : list.reload,
    emptyText: search.trim() ? "검색 결과가 없습니다." : "사례가 없습니다.",
  };
}
