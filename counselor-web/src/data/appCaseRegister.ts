// 상담사 앱(폰) · 사례 목록의 '새 사례 등록' 창(2026-11-20 디자인 AppCases.dc.html)에서 쓰는 값 확인 · 보낼 값 만들기.
//
// 창에서 받는 칸은 디자인 그대로 아동 이름 · 생년월일 · 성별(남 / 여) 셋뿐이다. 보낼 값은 웹 새 사례 등록과 같은 함수
// (useCaseRegister.ts toCaseCreateRequest)로 만든다 — 실명 · 생년월일은 personal_info(서버가 암호화해 저장),
// 성별은 사례의 child_gender, 출생연도는 생년월일의 해(서버도 같은 해로 맞춘다). 이 폰에 저장하지 않는다.
//
// 제목 · 아동 별칭(민규 11/24 제안, #197 로 main 머지 11/25): 앱 창에는 그 칸이 없다(디자인). 실명이나 실명 일부를 별칭에 넣으면
// 실명이 평문 칸으로 새므로 넣지 않는다. 두 칸을 **빼고** 보내면 서버가 사례번호로 채운다(별칭 '아동_0031', 제목 'C-2026-0031 사례').
// 서버 규칙(#197)이 main 에 들어가 앱 '+ 새 사례 등록' 단추를 켠다(APP_CASE_REGISTER_ENABLED, 11/25). '미입력' 같은 표시 글자는 보내지 않는다.

import type { CaseCreateRequest } from "../api/types";
import { emptyPersonalInput, todayKst } from "./personalInfo";
import { EMPTY_CASE_INPUT, toCaseCreateRequest } from "./useCaseRegister";

/** 디자인 이름 칸 최대 글자 수(setRgName 의 slice(0, 10)). */
export const APP_CASE_NAME_MAX = 10;
/** 앱 '+ 새 사례 등록' 을 보일지. 서버가 제목 · 별칭을 빼고 받는 #197 이 main 에 들어가 켬(11/25). */
export const APP_CASE_REGISTER_ENABLED = true;
/** 앱 등록 요청: 제목 · 별칭을 뺀 POST /cases(서버가 사례번호로 채움). */
export type AppCaseCreateRequest = Omit<CaseCreateRequest, "title" | "child_alias">;
export const APP_CASE_SEXES = ["남", "여"] as const;

export const BIRTH_FORMAT_ERROR = "생년월일은 YYYY-MM-DD 형식의 올바른 날짜로 입력하십시오";
export const REGISTER_MISSING_ERROR = "이름 · 생년월일 · 성별을 모두 입력하십시오";

/**
 * 입력 중인 생년월일 숫자(최대 8자리)가 아직 올바른 날짜가 될 수 있는가(디자인 bdOk 그대로).
 * 1900년 이전 · 미래(오늘 = 한국 날짜, 서버와 같음) · 없는 날짜로 이어질 수밖에 없으면 false.
 */
export function birthDigitsOk(dg: string, today: string = todayKst()): boolean {
  const cy = Number(today.slice(0, 4));
  const cm = Number(today.slice(5, 7));
  const cd = Number(today.slice(8, 10));
  const L = dg.length;
  if (!L) return true;
  const ys = dg.slice(0, 4);
  if (L < 4) {
    const lo = Number(ys.padEnd(4, "0"));
    const hi = Number(ys.padEnd(4, "9"));
    return lo <= cy && hi >= 1900;
  }
  const y = Number(ys);
  if (y < 1900 || y > cy) return false;
  if (L === 4) return true;
  const ms = dg.slice(4, 6);
  const mOk = (mm: number) => String(mm).padStart(2, "0").startsWith(ms) && (y < cy || mm <= cm);
  const months: number[] = [];
  for (let mm = 1; mm <= 12; mm++) if (mOk(mm)) months.push(mm);
  if (!months.length) return false;
  if (L <= 6) return true;
  const m = Number(ms);
  const ds = dg.slice(6, 8);
  const dim = new Date(y, m, 0).getDate();
  for (let dd = 1; dd <= dim; dd++) {
    if (String(dd).padStart(2, "0").startsWith(ds) && (y < cy || m < cm || dd <= cd)) return true;
  }
  return false;
}

/** 숫자를 YYYY-MM-DD 모양으로(디자인 bdFmt). */
export function formatBirthDigits(dg: string): string {
  return dg.slice(0, 4) + (dg.length > 4 ? "-" + dg.slice(4, 6) : "") + (dg.length > 6 ? "-" + dg.slice(6, 8) : "");
}

/**
 * 생년월일 칸에 새로 들어온 글자를 받아 들일지(디자인 setRgBirth). 숫자 · '-' 밖의 글자, 8자리 넘음, 될 수 없는 날짜면
 * { ok: false }(앞 값 그대로 두고 오류 문구), 아니면 YYYY-MM-DD 모양으로 바꾼 값.
 */
export function nextBirthValue(raw: string): { ok: true; value: string } | { ok: false } {
  const all = raw.replace(/[^0-9]/g, "");
  const dg = all.slice(0, 8);
  if (/[^0-9-]/.test(raw) || all.length > 8 || !birthDigitsOk(dg)) return { ok: false };
  return { ok: true, value: formatBirthDigits(dg) };
}

export interface AppCaseRegisterInput {
  name: string;
  birth: string;
  sex: string;
}

/** 세 칸이 다 찼는가(디자인 rgDis 의 반대). */
export function appRegisterReady(r: AppCaseRegisterInput | null): boolean {
  return !!(r && r.name.trim() && /^\d{4}-\d{2}-\d{2}$/.test(r.birth) && r.sex);
}

/** 보낼 값(POST /cases). 문제가 있으면 화면에 보일 문장. 담당 상담사는 보내지 않는다(서버가 요청자 본인으로 둔다). */
export function toAppCaseCreateRequest(
  r: AppCaseRegisterInput,
  meId: string | null,
): { payload: AppCaseCreateRequest; problem: null } | { payload: null; problem: string } {
  if (!appRegisterReady(r)) return { payload: null, problem: REGISTER_MISSING_ERROR };
  // 웹 등록과 같은 함수로 확인 · 변환한 뒤 제목 · 별칭만 뺀다(함수가 두 칸을 필수로 확인해 자리 글자를 잠깐 넣는다 — 보내지 않는다).
  const checked = toCaseCreateRequest(
    { ...EMPTY_CASE_INPUT, title: "-", alias: "-", gender: r.sex },
    {
      isAdmin: false,
      meId,
      personal: { ...emptyPersonalInput(), childName: r.name.trim(), childBirthDate: r.birth },
    },
  );
  if (checked.payload === null) return checked;
  const { title: _title, child_alias: _alias, ...payload } = checked.payload;
  return { payload, problem: null };
}
