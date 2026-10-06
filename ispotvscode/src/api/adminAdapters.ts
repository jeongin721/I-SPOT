// 관리자 화면(src/admin)이 Backend 응답을 화면 값으로 바꿀 때 쓰는 함수.
//
// 시각은 adapters.parseBackendTime 규칙(시간대 표시가 없으면 UTC)으로 읽는다.

import { NOT_PROVIDED, pad2, parseBackendTime } from "./adapters";
import type { Case, User, UserRole } from "./types";

// =========================================================
// 계정
// =========================================================

export const ROLE_LABELS: Record<UserRole, string> = {
  ADMIN: "관리자",
  COUNSELOR: "상담사",
};

/** 사용자 시간대의 "YYYY-MM-DD HH:MM". 값이 없으면 "—". */
export function toLocalDateTime(iso: string | null | undefined): string {
  if (!iso) return NOT_PROVIDED;

  const at = parseBackendTime(iso);

  if (!at) return iso;

  return `${at.getFullYear()}-${pad2(at.getMonth() + 1)}-${pad2(at.getDate())} ${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
}

/**
 * 계정 상태 표시. 활성/비활성은 따로 보여 주고, 여기서는 그 밖의 상태만 고른다.
 *
 * 휴면은 dormant_at 으로만 본다. Backend 는 미접속 기간(기본 60일)이 지난 뒤 맞는 비밀번호로 로그인했을 때
 * dormant_at 을 채우므로, 그 전에는 휴면으로 보이지 않는다. 휴면 해제 단추도 dormant_at 이 있을 때만 쓸 수 있다.
 */
export function accountStateTags(user: User): { label: string; tone: "red" | "amber" | "slate" }[] {
  const tags: { label: string; tone: "red" | "amber" | "slate" }[] = [];

  if (user.is_locked) tags.push({ label: "잠금", tone: "red" });
  if (user.dormant_at) tags.push({ label: "휴면", tone: "slate" });
  if (user.must_change_password) tags.push({ label: "임시 비밀번호", tone: "amber" });

  return tags;
}

/**
 * 상담사별 담당 사례 수. 관리자는 GET /cases 가 전체 사례를 주므로 모든 페이지를 받아 센다.
 * (담당자별 집계 API 는 없다. 종결 사례도 함께 센다.)
 */
export function countCasesByCounselor(list: Pick<Case, "counselor_id">[]): Map<string, number> {
  const counts = new Map<string, number>();

  for (const item of list) {
    counts.set(item.counselor_id, (counts.get(item.counselor_id) ?? 0) + 1);
  }

  return counts;
}

// =========================================================
// 새 계정의 첫 비밀번호
// =========================================================
//
// POST /auth/users 는 관리자가 보낸 비밀번호를 그대로 쓰고 첫 로그인 때 변경을 강제하지 않는다.
// 그래서 화면은 아무도 모르는 임의 비밀번호로 계정을 만들고 곧바로 password-reset 으로 임시 비밀번호를
// 발급한다(변경 강제 · 만료 시각이 붙는다). 이 값은 어디에도 보여 주거나 저장하지 않는다.
//
// Backend 비밀번호 규칙(app/core/password_policy.py)을 통과하도록 만든다.
// - 길이는 규칙이 받는 최대(MAX_BYTES = 72바이트, ASCII 라 72자)로 만든다. 최소 길이 설정(PASSWORD_MIN_LENGTH)의
//   상한도 72 라서(app/core/config.py) 설정을 어떻게 바꿔도 짧다는 이유로 거절되지 않는다.
// - 글자 · 숫자 · 특수문자를 모두 넣는다.
// - 모음(a e i o u)과 치환 문자(@ 4 0 1 3 5 $ 7 — `P@ssw0rd` 를 password 로 되돌려 보는 것)를 쓰지 않는다.
//   금지 단어는 모두 모음이 들어 있어 이렇게 하면 들어갈 수 없다.
// - 같은 문자 4번 반복 · 연속 문자 4개(abcd · 1234 · qwer · 거꾸로 포함)를 거른다.
// 이메일 아이디 · 이름(4자 이상 조각)이 우연히 들어가면 서버가 422 WEAK_PASSWORD 로 거절하므로 호출부가 다시 만든다.

const LETTERS = "bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ";
const DIGITS = "2689";
const SYMBOLS = "!#%^&*-_=+?";
const PASSWORD_ALPHABET = LETTERS + DIGITS + SYMBOLS;
/** Backend 비밀번호 최대 길이(password_policy.MAX_BYTES). 이보다 길면 WEAK_PASSWORD 다. */
const INITIAL_PASSWORD_LENGTH = 72;

const SEQUENCES = [
  "abcdefghijklmnopqrstuvwxyz",
  "0123456789",
  "qwertyuiop",
  "asdfghjkl",
  "zxcvbnm",
  "1qaz2wsx",
  "1q2w3e4r5t6y7u8i9o0p",
  "q1w2e3r4t5y6u7i8o9p0",
];

function hasSequence(lowered: string): boolean {
  for (let index = 0; index + 4 <= lowered.length; index += 1) {
    const chunk = lowered.slice(index, index + 4);
    const reversed = chunk.split("").reverse().join("");

    if (SEQUENCES.some((sequence) => sequence.includes(chunk) || sequence.includes(reversed))) return true;
  }

  return false;
}

/** 규칙을 지키는지 화면에서 먼저 본다. 금지 단어 · 이메일 · 이름 검사는 서버에 맡긴다(위 설명). */
export function meetsInitialPasswordRules(candidate: string): boolean {
  const lowered = candidate.toLowerCase();

  return (
    [...candidate].some((c) => LETTERS.includes(c)) &&
    [...candidate].some((c) => DIGITS.includes(c)) &&
    [...candidate].some((c) => SYMBOLS.includes(c)) &&
    !/(.)\1{3,}/.test(lowered) &&
    !hasSequence(lowered)
  );
}

/** crypto.getRandomValues 로 고른 임의 비밀번호. 치우침이 없도록 알파벳 길이의 배수 밖 값은 버린다. */
export function generateInitialPassword(): string {
  const limit = 256 - (256 % PASSWORD_ALPHABET.length);

  for (let attempt = 0; attempt < 100; attempt += 1) {
    let candidate = "";

    while (candidate.length < INITIAL_PASSWORD_LENGTH) {
      const bytes = new Uint8Array(INITIAL_PASSWORD_LENGTH * 2);

      crypto.getRandomValues(bytes);

      for (const byte of bytes) {
        if (byte >= limit) continue;

        candidate += PASSWORD_ALPHABET[byte % PASSWORD_ALPHABET.length];

        if (candidate.length === INITIAL_PASSWORD_LENGTH) break;
      }
    }

    if (meetsInitialPasswordRules(candidate)) return candidate;
  }

  // 100번 연속으로 걸릴 일은 사실상 없다. 나면 서버 검사에 맡긴다(호출부가 오류를 보여 준다).
  throw new Error("규칙에 맞는 비밀번호를 만들지 못했습니다.");
}

// =========================================================
// 접속 기록(감사 로그 LOGIN)
// =========================================================

/** 로그인 실패 감사 로그의 error_code → 화면 사유. 응답은 모두 같은 문구라도 감사 로그에는 실제 이유가 남는다. */
const LOGIN_FAILURE_REASONS: Record<string, string> = {
  INVALID_CREDENTIALS: "비밀번호 불일치 · 없는 계정",
  ACCOUNT_LOCKED: "잠긴 계정",
  INACTIVE_USER: "비활성 계정",
  ACCOUNT_DORMANT: "휴면 계정",
  TEMP_PASSWORD_EXPIRED: "임시 비밀번호 만료",
};

export function toLoginFailureReason(code: string | null | undefined): string {
  if (!code) return "";

  return LOGIN_FAILURE_REASONS[code] ?? code;
}

/** User-Agent 를 "Chrome 126" 처럼 줄인다. 모르는 값은 앞부분만 보여 준다(전체는 title 로). */
export function toBrowserLabel(userAgent: string | null | undefined): string {
  if (!userAgent) return NOT_PROVIDED;

  const rules: [RegExp, string][] = [
    [/Edg\/(\d+)/, "Edge"],
    [/OPR\/(\d+)/, "Opera"],
    [/SamsungBrowser\/(\d+)/, "Samsung Internet"],
    [/Firefox\/(\d+)/, "Firefox"],
    [/Chrome\/(\d+)/, "Chrome"],
    [/Version\/(\d+)[^ ]* (?:Mobile\/\S+ )?Safari\//, "Safari"],
  ];

  for (const [pattern, name] of rules) {
    const match = userAgent.match(pattern);

    if (match) return `${name} ${match[1]}`;
  }

  return userAgent.length > 24 ? `${userAgent.slice(0, 24)}…` : userAgent;
}

/**
 * 날짜 입력(YYYY-MM-DD, 사용자 시간대) → 감사 로그 since · until(UTC ISO).
 * 시작일은 그날 0시부터, 종료일은 그날 23:59:59.999 까지 포함한다(Backend 는 둘 다 경계 포함).
 * 비어 있으면 undefined(조건 없음).
 */
export function toAuditRange(startDate: string, endDate: string): { since?: string; until?: string } {
  const since = startDate ? new Date(`${startDate}T00:00:00`) : null;
  const until = endDate ? new Date(`${endDate}T23:59:59.999`) : null;

  return {
    since: since && !Number.isNaN(since.getTime()) ? since.toISOString() : undefined,
    until: until && !Number.isNaN(until.getTime()) ? until.toISOString() : undefined,
  };
}
