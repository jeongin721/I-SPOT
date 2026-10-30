// 종결 검토(Closure) 목록 화면 값(10/30 디자인). 내담자 정보 '종결 검토 등록'(POST /cases/{id}/closure-review)으로 등록한 사례만 보인다.
//
// 사례 기본정보 · 회차 수는 useCaseOverview(mode "counts"), 등록일은 사례의 closure_review_at.
// 진행 단계는 등록하면 '① 내역 검토' 다. 내역 검토 진행률(확인한 요약 수)과 '요약 만드는 중' 은 종결 요약 AI · 저장이 아직 없어 '—'.
// 이름은 아동 별칭(실명 없음), 나이 대신 출생연도, 학대 유형은 사례에 없어 보이지 않는다.
// '실명 보기' 토글은 10/30 디자인에서 빠졌다(CaseList 와 같음).
// 누르면 그 사례의 ① 전체 상담 내역 검토(?case=)로 간다.
// 검색어는 입력한 계정에 묶는다(useAccountSearch) — 앞 계정이 친 별칭 · 사례 ID 가 다음 계정에 보이지 않게.

import { useCallback, useEffect, useState } from "react";

import { NOT_PROVIDED } from "../caseRows";
import type { AuthSession } from "../useAuthSession";
import type { CaseOverviewState } from "../useCaseOverview";
import { NOT_READY, screenNotice, sidebarValues } from "./common";
import { screenHref } from "./links";

/**
 * 계정에 묶인 검색어. 로그인 확인 중이거나 다른 계정으로 바뀌면 바뀐 첫 그리기부터 빈 검색어로 보이고
 * 들고 있던 검색어도 버린다(같은 계정으로 다시 확인돼도 비운다). 로그인이 확인되기 전에 친 글자는 받지 않는다.
 */
export function useAccountSearch(session: AuthSession): [string, (value: string) => void] {
  const owner = session.status === "signedIn" && session.me ? session.me.id : null;
  const [held, setHeld] = useState<{ owner: string | null; value: string }>({ owner: null, value: "" });

  useEffect(() => {
    setHeld((current) => (current.owner === owner ? current : { owner, value: "" }));
  }, [owner]);

  const setSearch = useCallback((value: string) => {
    if (owner !== null) setHeld({ owner, value });
  }, [owner]);

  return [owner !== null && held.owner === owner ? held.value : "", setSearch];
}

interface ClosureInput {
  session: AuthSession;
  overview: CaseOverviewState;
  search: string;
  setSearch: (value: string) => void;
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
        !query || caseRow.alias.toLowerCase().includes(query) || caseRow.caseNumber.toLowerCase().includes(query),
    )
    .map(({ caseRow, createdDate, sessionTotal }) => ({
      ini: caseRow.initial,
      name: caseRow.alias,
      age: caseRow.birthYearLabel,
      sub: [caseRow.caseNumber, `사례 ${caseRow.statusLabel}`, overview.wholeOrg ? caseRow.counselorName : ""]
        .filter(Boolean)
        .join(" · "),
      href: screenHref("/ClosureReview", { caseId: caseRow.id }),
      sessions: `${sessionTotal}회차`,
      date: caseRow.closureReviewDate || createdDate || NOT_PROVIDED,
      stage: "① 내역 검토",
      stageCls: "chip c-ok",
      review: NOT_PROVIDED,
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
    listNote: `내역 검토 진행률은 ${NOT_READY}입니다(종결 요약 AI 가 아직 없음).`,
    countLabel,
    search: {
      value: search,
      onChange: (e: { target: { value: string } }) => input.setSearch(e.target.value),
      // 로그인이 확인된 계정이 있을 때만 입력을 받는다(useAccountSearch).
      disabled: session.status !== "signedIn",
    },
    rows,
    emptyText,
    notReady: NOT_READY,
  };
}
