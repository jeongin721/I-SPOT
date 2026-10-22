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

/** 회차 하나를 다루는 화면. 이 화면으로 가는 링크에만 회차 ID 를 넘긴다. */
const SESSION_PAGES = new Set(["/SessionDetail", "/SttReview", "/SignalReview", "/NoteWrite", "/FollowupQ", "/RiskProfile"]);

/**
 * 지금 화면의 사례 · 회차 ID 를 다음 화면 링크에 넘긴다. 사례 ID 는 늘, 회차 ID 는 회차 화면으로 갈 때만 넘긴다.
 * 녹취 올리기(UploadModal)에 회차 ID 가 붙으면 '새 회차'가 아니라 '그 회차에 이어 올리기'가 되기 때문이다.
 */
export function carryScreenHref(page: string, ids: Partial<ScreenIds>): string {
  return screenHref(page, { caseId: ids.caseId, sessionId: SESSION_PAGES.has(page) ? ids.sessionId : null });
}

/**
 * 팝업 화면(녹취 · 자료 올리기, 새 사례 등록). 이 화면으로 가는 링크는 연 화면 주소를 back 쿼리로 넘기고, 팝업을 닫으면
 * 그 화면으로 돌아간다(10/21 디자인의 markBack — 디자인은 브라우저 저장소 ispot-back 을 쓰지만 앱은 주소 쿼리로 넘긴다).
 */
export const POPUP_PAGES = new Set(["/UploadModal", "/CaseRegister"]);
export const BACK_PARAM = "back";

/** href 에 돌아갈 화면 주소(from)를 붙인다. 이미 back 이 있으면 그대로 둔다. */
export function withBack(href: string, from: string): string {
  const [path, query = ""] = href.split("?");
  const params = new URLSearchParams(query);

  if (!params.has(BACK_PARAM)) params.set(BACK_PARAM, from);

  return `${path}?${params.toString()}`;
}

/** 주소의 back 쿼리가 앱 안 화면(팝업 · 로그인 제외)이면 그 주소를, 아니면 null. */
export function readBackHref(search: URLSearchParams | string): string | null {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const back = params.get(BACK_PARAM)?.trim() ?? "";

  if (!/^\/[A-Za-z]+(\?[^#]*)?$/.test(back)) return null;

  const page = back.split("?")[0];

  return POPUP_PAGES.has(page) || page === "/Login" ? null : back;
}
