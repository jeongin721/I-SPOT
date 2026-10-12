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

/** 사용자 시간대의 날짜와 시각(YYYY-MM-DD HH:mm). 값이 없으면 빈 문자열. */
export function toDateTime(iso: string | null | undefined): string {
  if (!iso) return "";

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(0, 16).replace("T", " ");

  return `${toDateOnly(iso)} ${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
}

/**
 * 음성 안의 위치 · 길이(밀리초)를 "01:36" 이나 "1:02:05" 로 쓴다. 1시간이 안 되면 분:초, 넘으면 시:분:초.
 * 음수나 숫자가 아닌 값은 빈 문자열.
 */
export function formatClock(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms) || ms < 0) return "";

  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return hours > 0 ? `${hours}:${pad2(minutes)}:${pad2(seconds)}` : `${pad2(minutes)}:${pad2(seconds)}`;
}

/** 녹음 길이(밀리초)를 "24분" · "1시간 5분" · "40초" 로 쓴다. 값이 없으면 빈 문자열. */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms) || ms < 0) return "";

  const totalSeconds = Math.round(ms / 1000);

  if (totalSeconds < 60) return `${totalSeconds}초`;

  const totalMinutes = Math.round(totalSeconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) return `${minutes}분`;

  return minutes === 0 ? `${hours}시간` : `${hours}시간 ${minutes}분`;
}

/** 파일 크기를 "183 KB" · "12.4 MB" 로 쓴다. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
