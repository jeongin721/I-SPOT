// 화면 주소 규칙. 화면 경로는 파일 이름 그대로 두고(App.jsx), 다루는 사례 · 회차는 쿼리로 넘긴다.
//
//   #/CaseDetail?case=<사례 ID>
//   #/SessionDetail?case=<사례 ID>&session=<회차 ID>
//
// ID 는 Backend 조회에 쓰는 UUID 다(화면에 보이는 사례번호 C-2026-0001 이 아니다).
// 회차 화면은 session 만 있어도 된다(사례는 회차 정보에서 찾는다). 링크를 만들 때는 아는 것을 모두 넣는다.
// 새 화면도 이 규칙을 따른다(counselor-web/README.md '화면 주소').

export const CASE_PARAM = "case";
export const SESSION_PARAM = "session";

export interface ScreenIds {
  caseId: string | null;
  sessionId: string | null;
}

/** 화면 주소의 쿼리(react-router 의 useSearchParams 결과나 '?case=…' 문자열)에서 사례 · 회차 ID 를 읽는다. */
export function readScreenIds(search: URLSearchParams | string): ScreenIds {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const read = (name: string) => params.get(name)?.trim() || null;

  return { caseId: read(CASE_PARAM), sessionId: read(SESSION_PARAM) };
}

/** '/SessionDetail' 같은 화면 경로에 사례 · 회차 ID 를 붙인다. 없는 ID 는 빼고, 둘 다 없으면 경로만. */
export function screenHref(page: string, ids: Partial<ScreenIds> = {}): string {
  const params = new URLSearchParams();

  if (ids.caseId) params.set(CASE_PARAM, ids.caseId);
  if (ids.sessionId) params.set(SESSION_PARAM, ids.sessionId);

  const query = params.toString();

  return query ? `${page}?${query}` : page;
}
