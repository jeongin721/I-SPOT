// 사례 목록 훅(GET /cases). 화면은 검색어만 넘기고 rows · total · 상태를 받아 그린다.
//
// 상담사는 담당 사례만, 관리자는 전체 사례가 온다(Backend 가 거른다).
// 검색은 제목 · 사례번호 · 아동 별칭에서 찾는다. 입력이 멈춘 뒤(SEARCH_DELAY_MS) 한 번만 부른다.

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { cases } from "../api/endpoints";
import type { CaseStatus } from "../api/types";
import { toCaseRow, type CaseRow } from "./caseRows";

/** 한 번에 받는 최대 건수. Backend 상한(page_size ≤ 100)과 같다. */
export const CASE_PAGE_SIZE = 100;

const SEARCH_DELAY_MS = 300;

export interface CaseListOptions {
  search?: string;
  status?: CaseStatus;
  page?: number;
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface CaseListState {
  rows: CaseRow[];
  /** 조건에 맞는 전체 건수. 아직 모르면 null. rows.length 보다 크면 다음 페이지가 있다. */
  total: number | null;
  /** 처음 불러오는 중이거나 조건이 바뀌어 다시 불러오는 중. */
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useCaseList({ search = "", status, page = 1, enabled = true }: CaseListOptions = {}): CaseListState {
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);
  const query = search.trim();

  useEffect(() => {
    if (!enabled) {
      // 로그아웃 · 다른 계정으로 바뀌는 중이면 앞 계정의 목록을 버린다(다시 켜질 때 앞 목록이 보이지 않게).
      setRows([]);
      setTotal(null);
      setError(null);
      setLoading(false);
      return;
    }

    // 조건이 바뀌었거나 화면을 떠났으면 늦게 온 응답은 버린다.
    let cancelled = false;

    setLoading(true);
    setError(null);

    // 검색어를 칠 때마다 부르지 않도록 잠깐 기다린다. 검색어가 없으면 바로 부른다.
    const timer = window.setTimeout(
      () => {
        cases
          .list({ page, page_size: CASE_PAGE_SIZE, status, search: query || undefined })
          .then((result) => {
            if (cancelled) return;

            setRows(result.items.map(toCaseRow));
            setTotal(result.meta.total);
            setLoading(false);
          })
          .catch((caught) => {
            if (cancelled) return;

            setRows([]);
            setTotal(null);
            setLoading(false);
            // 401 · 403 PASSWORD_CHANGE_REQUIRED 는 client 가 이벤트로 알리고, 화면은 useAuthSession 상태로 움직인다.
            setError(
              caught instanceof ApiError ? caught.message : "사례 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
            );
          });
      },
      query ? SEARCH_DELAY_MS : 0,
    );

    return () => {
      window.clearTimeout(timer);
      cancelled = true;
    };
  }, [enabled, query, status, page, reloadKey]);

  // 켜진 직후 첫 조회가 시작되기 전 한 번의 그리기에서도 '불러오는 중'으로 보이게 한다(빈 목록으로 깜빡이지 않게).
  const waitingFirst = enabled && total === null && error === null;

  return { rows, total, loading: loading || waitingFirst, error, reload };
}
