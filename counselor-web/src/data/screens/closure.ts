// 종결 검토(Closure) 목록 화면 값(10/30 디자인). 내담자 정보 '종결 검토 등록'(POST /cases/{id}/closure-review)으로 등록한 사례만 보인다.
//
// 사례 기본정보 · 회차 수는 useCaseOverview(mode "counts", withNames), 등록일은 사례의 closure_review_at.
// 진행 단계 · 내역 검토 진행률은 사례마다 closure-summary(확인 체크 수, 11/20 점검): 요약 전 · 확인 중이면 '① 내역 검토',
// 모두 확인했으면 '② 종결보고서', 사례가 종결됐으면 '종결'. 못 받았으면 '① 내역 검토' · '—'.
// 이름은 아동 실명(등록된 사례), 없으면 별칭(useCaseOverview withNames), 나이 대신 출생연도, 학대 유형은 사례에 없어 보이지 않는다.
// '실명 보기' 토글은 10/30 디자인에서 빠졌다(CaseList 와 같음).
// 누르면 그 사례의 ① 전체 상담 내역 검토(?case=)로 간다.
// 검색어는 입력한 계정에 묶는다(data/useAccountSearch) — 앞 계정이 친 이름 · 사례 ID 가 다음 계정에 보이지 않게.
// 검색은 받은 목록 안에서 이름 · 별칭 · 사례 ID 의 일부로 찾는다(화면에 이미 보이는 값).

import { NOT_PROVIDED } from "../caseRows";
import type { AuthSession } from "../useAuthSession";
import type { ClosureSummaryRecord } from "../../api/types";
import type { CaseOverviewState } from "../useCaseOverview";
import { NOT_READY, screenNotice, sidebarValues } from "./common";
import { screenHref } from "./links";

interface ClosureInput {
  session: AuthSession;
  overview: CaseOverviewState;
  search: string;
  setSearch: (value: string) => void;
  /** 사례 ID → closure-summary. 받기 전 · 실패면 없음. */
  summaries?: Record<string, ClosureSummaryRecord | null> | null;
}

/** 종결 검토 진행: 단계 · 칩 · 내역 검토 진행률. */
export function closureProgress(record: ClosureSummaryRecord | null | undefined, closed: boolean) {
  if (closed) return { stage: "종결", stageCls: "chip c-check", review: record?.summary ? "확인 완료" : NOT_PROVIDED };
  if (record === undefined || record === null) return { stage: "① 내역 검토", stageCls: "chip c-ok", review: NOT_PROVIDED };
  const body = record.summary;
  if (!body) return { stage: "① 내역 검토", stageCls: "chip c-ok", review: "요약 만들기 전" };
  const keys = body.groups.flatMap((group) => group.items.map((item) => item.key));
  const ok = keys.filter((key) => record.checks?.[key]).length;
  if (keys.length > 0 && ok === keys.length) return { stage: "② 종결보고서", stageCls: "chip c-sky", review: `확인 ${ok} / ${keys.length}` };
  return { stage: "① 내역 검토", stageCls: "chip c-ok", review: `확인 ${ok} / ${keys.length}` };
}

export function closureValues(input: ClosureInput) {
  const { session, overview, search } = input;
  const query = search.trim().toLowerCase();
  const items = overview.data?.items ?? [];
  const registered = items
    .filter(({ caseRow }) => Boolean(caseRow.closureReviewDate))
    .sort((a, b) => b.caseRow.closureReviewDate.localeCompare(a.caseRow.closureReviewDate));
  const rows = registered
    .filter(
      ({ caseRow }) =>
        !query ||
        caseRow.name.toLowerCase().includes(query) ||
        caseRow.alias.toLowerCase().includes(query) ||
        caseRow.caseNumber.toLowerCase().includes(query),
    )
    .map(({ caseRow, createdDate, sessionTotal }) => ({
      ini: caseRow.initial,
      name: caseRow.name,
      age: caseRow.birthYearLabel,
      sub: [caseRow.caseNumber, `사례 ${caseRow.statusLabel}`, overview.wholeOrg ? caseRow.counselorName : ""]
        .filter(Boolean)
        .join(" · "),
      href: screenHref("/ClosureReview", { caseId: caseRow.id }),
      sessions: `${sessionTotal}회차`,
      date: caseRow.closureReviewDate || createdDate || NOT_PROVIDED,
      ...closureProgress(input.summaries?.[caseRow.id], caseRow.status === "CLOSED"),
    }));

  let countLabel = "";
  if (overview.data) {
    countLabel = `종결 검토 ${registered.length}건 · ${overview.wholeOrg ? "전체" : "담당"} 사례 ${overview.data.caseTotal}건 중`;
    if (overview.data.casesTruncated) countLabel += ` · 최근 등록한 ${items.length}건 표시`;
  }

  let emptyText = "";
  if (overview.data && rows.length === 0) {
    emptyText = query ? "검색 결과가 없습니다." : "종결 검토에 등록한 사례가 없습니다. 사례 상세(내담자 정보)에서 '종결 검토 등록' 을 눌러 주세요.";
  }

  return {
    ...sidebarValues(session),
    notice: screenNotice({ session, loading: overview.loading, error: overview.error, retry: overview.reload }),
    listNote: "내역 검토 진행률은 ① 전체 상담 내역 검토에서 확인 체크한 요약 수입니다.",
    countLabel,
    search: {
      value: search,
      onChange: (e: { target: { value: string } }) => input.setSearch(e.target.value),
      // 로그인이 확인된 계정이 있을 때만 입력을 받는다(data/useAccountSearch).
      disabled: session.status !== "signedIn",
    },
    rows,
    emptyText,
    notReady: NOT_READY,
  };
}
