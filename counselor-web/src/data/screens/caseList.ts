// 통합 사례 관리(CaseList) 화면 값.
//  - 이름은 아동 실명(등록된 사례), 없으면 별칭이다(목록을 with_child_name=true 로 부름). 나이 대신 출생연도를 보여 준다.
//  - 신고접수일은 사례에 저장한 값, 위험도는 분석이 끝난 가장 최근 회차의 상담원 판단이다(사례 상세 칩과 같은 값). 없으면 '—'.
//  - 정렬(전체 · 신고접수일 · 위험도)은 서버가 한다(GET /cases?sort=). 전체는 등록 최신순.
//  - '실명 보기' 토글은 10/30 디자인에서 빠졌다(화면에는 이름을 그대로 보이고 인쇄 · 복사 때만 가린다).
//  - 검색은 서버가 한다: 제목 · 사례 ID · 별칭(부분)과 실명(공백 무시 정확히 같을 때). 실명 일부로는 찾지 않는다(암호화 저장).
//  - 이름 · 상세 링크는 사례 ID 를 넘긴다(#/CaseDetail?case=…).

import type { CaseListSort, RiskLevel } from "../../api/types";
import type { AuthSession } from "../useAuthSession";
import type { CaseListState } from "../useCaseList";
import { sidebarValues } from "./common";
import { screenHref } from "./links";

const RISK_CHIP: Record<RiskLevel, string> = { HIGH: "chip c-hi", MEDIUM: "chip c-mid", LOW: "chip c-lo" };

export function caseListValues(input: {
  session: AuthSession;
  list: CaseListState;
  search: string;
  setSearch: (value: string) => void;
  sort: CaseListSort | null;
  setSort: (value: CaseListSort | null) => void;
}) {
  const { session, list, search, setSearch, sort, setSort } = input;
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
  const filters = options.map(([key, label]) => ({ label, cls: key === sort ? "on" : "", pick: () => setSort(key) }));

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
    countLabel,
    search: { value: search, onChange: (e: { target: { value: string } }) => setSearch(e.target.value) },
    phase,
    errorText: sessionError ? session.error : list.error,
    retry: sessionError ? session.recheck : list.reload,
    emptyText: search.trim() ? "검색 결과가 없습니다. 이름은 전체 이름으로만 찾습니다(일부로는 찾지 않음)." : "사례가 없습니다.",
  };
}
