// 사례 목록 훅(GET /cases). 화면은 검색어만 넘기고 rows · total · 상태를 받아 그린다.
//
// 상담사는 담당 사례만, 관리자는 전체 사례가 온다(Backend 가 거른다).
// 검색은 제목 · 사례번호 · 아동 별칭(부분)과 아동 실명(정확히)에서 찾는다. 입력이 멈춘 뒤(SEARCH_DELAY_MS) 한 번만 부른다.
// withNames: 이름 칸에 실명을 보이는 화면(사례 목록 · 녹취 올리기)만 with_child_name=true 로 부른다(부를 때마다 서버에 목록
// 열람 기록 1줄). 건수만 쓰는 관리자 홈은 싣지 않는다.

import { useCallback, useEffect, useState } from "react";

import { ApiError, getToken } from "../api/client";
import { cases } from "../api/endpoints";
import type { CaseListOrder, CaseListSort, CaseStatus } from "../api/types";
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
  /** 이름 칸에 실명을 보이는 화면만 true(with_child_name=true, 서버가 목록 열람 기록을 남김). 기본 false. */
  withNames?: boolean;
  /** 서버 정렬(신고접수일 · 위험도). 없으면 등록 최신순. */
  sort?: CaseListSort;
  /** desc(신고접수일 최신 · 위험도 상부터) · asc(반대). sort 가 있을 때만 쓴다. */
  order?: CaseListOrder;
  /** 한 쪽 건수. 기본 CASE_PAGE_SIZE. */
  pageSize?: number;
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

export function useCaseList({
  search = "",
  status,
  page = 1,
  enabled = true,
  withNames = false,
  sort,
  order,
  pageSize = CASE_PAGE_SIZE,
}: CaseListOptions = {}): CaseListState {
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
    // 예약할 때의 로그인. 기다리는 사이 다른 탭에서 다른 계정으로 로그인했으면 앞 계정의 검색어(실명)를
    // 새 계정 토큰으로 보내지 않는다 — 응답만 버리면 이미 요청 주소에 실린다(Codex #130 재검수 N1).
    const token = getToken();

    setLoading(true);
    setError(null);

    // 검색어를 칠 때마다 부르지 않도록 잠깐 기다린다. 검색어가 없으면 바로 부른다.
    const timer = window.setTimeout(
      () => {
        if (getToken() !== token) return;

        cases
          .list({
            page,
            page_size: pageSize,
            status,
            search: query || undefined,
            sort,
            ...(sort && order ? { order } : {}),
            ...(withNames ? { with_child_name: true } : {}),
          })
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
  }, [enabled, query, status, page, pageSize, withNames, sort, order, reloadKey]);

  // 켜진 직후 첫 조회가 시작되기 전 한 번의 그리기에서도 '불러오는 중'으로 보이게 한다(빈 목록으로 깜빡이지 않게).
  const waitingFirst = enabled && total === null && error === null;

  return { rows, total, loading: loading || waitingFirst, error, reload };
}
