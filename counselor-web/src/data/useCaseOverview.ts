// 사례 · 회차 모음 훅. 통계 · 일정 · 종결 검토 화면이 쓴다.
//
// 사례 단위 집계 API 는 없어서(specs 대응표 Stats · Schedule · Closure 줄 '보완: 기존 조회로 집계') 기존 조회를 모은다.
//  - GET /cases 를 쪽마다(100건씩) 불러 사례를 모두 모은다. 상담사는 담당 사례만, 관리자는 전체 사례가 온다(Backend 가 거른다).
//  - mode "sessions": 사례마다 GET /cases/{id}/sessions 를 쪽마다 불러 회차를 모두 모은다(통계의 상담일별 회차 수 · 일정 달력).
//  - mode "counts":   사례마다 회차 수만(page_size=1 의 meta.total) 부른다(종결 검토 목록의 회차 수).
// 요청이 사례 수만큼 늘어나서 한 번에 OVERVIEW_CONCURRENCY 사례씩 부르고, 사례 · 회차 수에 상한을 둔다(넘으면 truncated).
// withNames: 이름을 보이는 화면(종결 검토 · 일정)만 실명과 함께 부른다(쪽마다 서버에 목록 열람 기록). 통계는 부르지 않는다.
//
// 다른 계정으로 바뀌면 key 가 null 을 거쳐 바뀌므로 앞 계정의 값을 보이지 않는다(useRemote).
// 같은 탭에서 회차 상태가 바뀌면(sessionEvents) 조용히 다시 부른다.
//
// Backend 에 없는 값은 만들지 않는다: 신고접수일(사례 생성일 created_at 은 신고접수일이 아니다), 학대 판단 · 재신고 ·
// 행위자 · 서비스 실적, 개인 · 기관 일정, 종결 검토 등록 · 진행률.

import { cases } from "../api/endpoints";
import type { Paged } from "../api/types";
import { toCaseRow, type CaseRow } from "./caseRows";
import { mapLimited } from "./mapLimited";
import { toSessionRow, type SessionRow } from "./sessionRows";
import { toDateOnly } from "./time";
import type { AuthSession } from "./useAuthSession";
import { useRemote } from "./useRemote";

/** 한 쪽에 받는 건수. Backend 상한(page_size ≤ 100)과 같다. */
export const OVERVIEW_PAGE_SIZE = 100;
/** 한 번에 함께 부르는 사례 수. */
export const OVERVIEW_CONCURRENCY = 4;
/** 사례를 최대 몇 쪽까지 부르는가(100건 × 20쪽 = 2,000건). 넘으면 최근 등록한 사례까지만 모인다. */
export const MAX_CASE_PAGES = 20;
/** 한 사례의 회차를 최대 몇 쪽까지 부르는가(100회차 × 10쪽 = 1,000회차). 넘으면 최근 회차까지만 모인다. */
export const MAX_SESSION_PAGES = 10;

export type OverviewMode = "sessions" | "counts";

export interface CaseOverviewItem {
  caseRow: CaseRow;
  /** 사례를 등록한 날짜(YYYY-MM-DD, 사용자 시간대). 신고접수일이 아니다. */
  createdDate: string;
  /** 이 사례의 전체 회차 수(Backend 가 센 값). */
  sessionTotal: number;
  /** mode "sessions" 면 이 사례의 회차(최신부터), "counts" 면 빈 배열. */
  sessions: SessionRow[];
}

export interface CaseOverviewData {
  /** 최근 등록한 사례부터. */
  items: CaseOverviewItem[];
  /** 볼 수 있는 전체 사례 수(Backend 가 센 값). */
  caseTotal: number;
  /** 사례가 MAX_CASE_PAGES 쪽을 넘어 일부만 모았다. */
  casesTruncated: boolean;
  /** 회차가 MAX_SESSION_PAGES 쪽을 넘어 일부만 모은 사례가 있다. */
  sessionsTruncated: boolean;
}

export interface CaseOverviewState {
  data: CaseOverviewData | null;
  /** 관리자라 전체(모든 상담사) 사례인가. 아니면 담당 사례다. */
  wholeOrg: boolean;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * 1쪽을 먼저 받아 전체 쪽 수를 알고, 나머지 쪽(maxPages 까지)을 부른다.
 * 쪽 사이에 새 항목이 생기면 앞 쪽 항목이 뒤로 밀려 두 번 올 수 있어 id 로 한 번만 남긴다.
 */
async function loadPages<T extends { id: string }>(
  fetchPage: (page: number) => Promise<Paged<T>>,
  maxPages: number,
  concurrency: number,
): Promise<{ items: T[]; total: number; truncated: boolean }> {
  const first = await fetchPage(1);
  const total = first.meta.total;
  const needed = Math.ceil(total / OVERVIEW_PAGE_SIZE);
  const last = Math.min(needed, maxPages);
  const restPages = Array.from({ length: Math.max(0, last - 1) }, (_, index) => index + 2);
  const rest = await mapLimited(restPages, concurrency, fetchPage);
  const seen = new Set<string>();
  const items: T[] = [];

  for (const item of [first, ...rest].flatMap((page) => page.items)) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    items.push(item);
  }

  return { items, total, truncated: needed > maxPages };
}

async function loadCaseOverview(mode: OverviewMode, withNames: boolean): Promise<CaseOverviewData> {
  const caseList = await loadPages(
    (page) => cases.list({ page, page_size: OVERVIEW_PAGE_SIZE, ...(withNames ? { with_child_name: true } : {}) }),
    MAX_CASE_PAGES,
    OVERVIEW_CONCURRENCY,
  );
  let sessionsTruncated = false;

  const items = await mapLimited(caseList.items, OVERVIEW_CONCURRENCY, async (source): Promise<CaseOverviewItem> => {
    const base = { caseRow: toCaseRow(source), createdDate: toDateOnly(source.created_at) };

    if (mode === "counts") {
      const page = await cases.listSessions(source.id, { page: 1, page_size: 1 });

      return { ...base, sessionTotal: page.meta.total, sessions: [] };
    }

    // 한 사례 안의 쪽은 차례로 부른다(사례끼리 이미 함께 부르고 있어서).
    const sessionList = await loadPages(
      (page) => cases.listSessions(source.id, { page, page_size: OVERVIEW_PAGE_SIZE }),
      MAX_SESSION_PAGES,
      1,
    );
    if (sessionList.truncated) sessionsTruncated = true;

    return { ...base, sessionTotal: sessionList.total, sessions: sessionList.items.map(toSessionRow) };
  });

  return { items, caseTotal: caseList.total, casesTruncated: caseList.truncated, sessionsTruncated };
}

/** session 은 useAuthSession() 결과. 로그인이 확인된 뒤에만 부르고, 다른 계정으로 바뀌면 앞 계정의 값을 보이지 않는다. */
export function useCaseOverview(
  session: AuthSession,
  mode: OverviewMode,
  { withNames = false }: { withNames?: boolean } = {},
): CaseOverviewState {
  const me = session.status === "signedIn" ? session.me : null;
  const remote = useRemote(
    me ? `${me.id}:overview:${mode}:${withNames ? "names" : "plain"}` : null,
    () => loadCaseOverview(mode, withNames),
    "사례 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => true,
  );

  return {
    data: remote.data,
    wholeOrg: session.isAdmin,
    loading: remote.loading,
    error: remote.error,
    reload: remote.reload,
  };
}
