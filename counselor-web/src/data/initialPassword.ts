// 새 계정의 첫 비밀번호. ispotvscode/src/api/adminAdapters.ts 의 같은 함수를 옮겨 왔다.
//
// POST /auth/users 는 관리자가 보낸 비밀번호를 그대로 쓰고 첫 로그인 때 변경을 강제하지 않는다.
// 그래서 useAdminAccounts 는 아무도 모르는 임의 비밀번호로 계정을 만들고 곧바로 password-reset 으로 임시 비밀번호를
// 발급한다(변경 강제 · 만료 시각이 붙는다). 이 값은 어디에도 보여 주거나 저장하지 않는다.
//
// Backend 비밀번호 규칙(backend/app/core/password_policy.py)을 통과하도록 만든다.
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
