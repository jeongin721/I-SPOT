// Backend 시각을 화면에 보여 줄 문자열로 바꾼다. ispotvscode/src/api/adapters.ts 의 같은 함수를 옮겨 왔다.

/**
 * Backend 시각을 Date 로 읽는다.
 *
 * Backend 는 UTC 로 저장하는데, 사례 · 회기 시각은 `2026-09-29T07:04:56` 처럼 시간대 표시 없이
 * 오고(업무 목록의 waiting_since 만 Z 가 붙는다) 브라우저는 이런 문자열을 지역 시각으로 읽는다.
 * 그대로 두면 한국 시간 새벽에 등록한 회기가 전날로 보이므로, 표시가 없으면 UTC 로 본다.
 */
export function parseBackendTime(iso: string): Date | null {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const parsed = new Date(hasZone ? iso : `${iso}Z`);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/** 사용자 시간대의 날짜(YYYY-MM-DD). 값이 없으면 빈 문자열. */
export function toDateOnly(iso: string | null | undefined): string {
  if (!iso) return "";

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(0, 10);

  return `${at.getFullYear()}-${pad2(at.getMonth() + 1)}-${pad2(at.getDate())}`;
}
