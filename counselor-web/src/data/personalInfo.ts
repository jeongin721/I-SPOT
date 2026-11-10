// 서식 4 의 실명 · 생년월일 · 사례관리대상자 · 면접대상자 · 가족관계 표 · 건강정도 입력(새 사례 등록 · 초기면접지가 같이 쓴다).
//
// 화면 입력(문자열) ↔ 서버 값(PersonalInfoRequest, API_CONTRACT 4절 '개인 식별 정보'). 서버는 칸마다 암호화해 저장한다.
// 값은 화면 상태에만 두고 브라우저 저장소(localStorage · sessionStorage)에 넣지 않는다. 계정이 바뀌면 화면이 새로 만든다.
// 길이 · 범위 제한은 backend/app/schemas/case_personal_info.py 와 같다(서버가 최종으로 거절한다 — 422, 문구에 값 없음).
//
// 건강정도는 서버가 항목마다 '유 · 무' 와 세부 글 하나(200자)만 받는다. 디자인의 세부 칸(장애 정도 · 병원치료 횟수 · 입원/통원 ·
// 기간 · 약물복용 등)은 세부 글 한 칸에 적는다(서버에 칸이 없어 지어 나누지 않는다).

import {
  PERSONAL_HEALTH_KINDS,
  type PersonalFamilyMember,
  type PersonalHealth,
  type PersonalHealthItem,
  type PersonalHealthKind,
  type PersonalInfo,
  type PersonalInfoRequest,
} from "../api/types";

export const PERSON_NAME_MAX = 50;
/** 관계 · 종교 · 학력. */
export const PERSON_SHORT_MAX = 30;
export const PERSON_JOB_MAX = 50;
export const PERSON_AGE_MAX = 150;
export const HEALTH_DETAIL_MAX = 200;
export const FAMILY_MAX_ROWS = 30;
export const BIRTH_DATE_MIN = "1900-01-01";

export type LivingInput = "" | "동거" | "비동거";
export type PresentInput = "" | "유" | "무";

export interface FamilyRowInput {
  name: string;
  relation: string;
  age: string;
  religion: string;
  education: string;
  job: string;
  living: LivingInput;
}

export interface HealthRowInput {
  present: PresentInput;
  detail: string;
}

export interface PersonalInput {
  childName: string;
  /** YYYY-MM-DD 또는 "". */
  childBirthDate: string;
  targetName: string;
  targetRelation: string;
  targetBirthDate: string;
  intervieweeName: string;
  intervieweeRelation: string;
  family: FamilyRowInput[];
  healthSubject: string;
  health: Record<PersonalHealthKind, HealthRowInput>;
}

export type PersonalTextKey = Exclude<keyof PersonalInput, "family" | "health">;

export const EMPTY_FAMILY_ROW: FamilyRowInput = {
  name: "",
  relation: "",
  age: "",
  religion: "",
  education: "",
  job: "",
  living: "",
};

/** 건강정도 항목별 세부 글 자리 안내(디자인의 세부 칸 이름). */
export const HEALTH_DETAIL_HINTS: Record<PersonalHealthKind, string> = {
  질병: "질병명",
  장애: "장애명 · 심한/심하지 않은",
  병원치료: "횟수 · 입원/통원 · 기간",
  "정신과 진단": "진단명 · 약물복용 · 기간",
  "타기관 상담": "상담사유 · 횟수 · 기간",
};

function emptyHealth(): Record<PersonalHealthKind, HealthRowInput> {
  return Object.fromEntries(PERSONAL_HEALTH_KINDS.map((kind) => [kind, { present: "", detail: "" }])) as Record<
    PersonalHealthKind,
    HealthRowInput
  >;
}

export function emptyPersonalInput(): PersonalInput {
  return {
    childName: "",
    childBirthDate: "",
    targetName: "",
    targetRelation: "",
    targetBirthDate: "",
    intervieweeName: "",
    intervieweeRelation: "",
    family: [{ ...EMPTY_FAMILY_ROW }, { ...EMPTY_FAMILY_ROW }],
    healthSubject: "",
    health: emptyHealth(),
  };
}

const text = (value: string | null | undefined) => value ?? "";

/** 서버 값으로 입력칸을 채운다. 가족 표는 적어도 두 줄(빈 줄)을 보인다. */
export function personalInputOf(info: PersonalInfo | null): PersonalInput {
  const input = emptyPersonalInput();

  if (!info) return input;

  const health = emptyHealth();
  for (const item of info.health?.items ?? []) {
    health[item.kind] = {
      present: item.present === true ? "유" : item.present === false ? "무" : "",
      detail: text(item.detail),
    };
  }

  const family: FamilyRowInput[] = info.family_members.map((member) => ({
    name: member.name,
    relation: text(member.relation),
    age: member.age === null ? "" : String(member.age),
    religion: text(member.religion),
    education: text(member.education),
    job: text(member.job),
    living: member.living_together === true ? "동거" : member.living_together === false ? "비동거" : "",
  }));
  while (family.length < 2) family.push({ ...EMPTY_FAMILY_ROW });

  return {
    childName: text(info.child_name),
    childBirthDate: text(info.child_birth_date),
    targetName: text(info.target_person?.name),
    targetRelation: text(info.target_person?.relation),
    targetBirthDate: text(info.target_person?.birth_date),
    intervieweeName: text(info.interviewee?.name),
    intervieweeRelation: text(info.interviewee?.relation),
    family,
    healthSubject: text(info.health?.subject_name),
    health,
  };
}

/** 오늘(한국 날짜, YYYY-MM-DD). 서버도 한국 날짜로 생년월일 범위를 본다. */
export function todayKst(now: number = Date.now()): string {
  return new Date(now + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

const isBlankRow = (row: FamilyRowInput) =>
  !row.name.trim() &&
  !row.relation.trim() &&
  !row.age.trim() &&
  !row.religion.trim() &&
  !row.education.trim() &&
  !row.job.trim() &&
  !row.living;

/** 입력 확인에 걸린 문장. toPersonalInfoRequest 안에서만 던지고 받는다. */
class InputProblem extends Error {}

function need(ok: boolean, problem: string): void {
  if (!ok) throw new InputProblem(problem);
}

/** 칸 이름 뒤 조사(은 · 는). 마지막 글자에 받침이 있으면 '은'. */
function topic(label: string): string {
  const code = label.charCodeAt(label.length - 1) - 0xac00;
  return `${label}${code >= 0 && code < 11172 && code % 28 !== 0 ? "은" : "는"}`;
}

/** 글자 수. 서버(Python len)처럼 코드 포인트로 센다 — 확장 한자 · 이모지가 2 로 세여 맞는 값을 거절하지 않게(Codex #129 R5). */
export function charCount(text: string): number {
  return [...text].length;
}

/** 이름 칸: 앞뒤 공백을 떼고 50자까지, 비었으면 null. */
function nameOf(value: string, label: string): string | null {
  const trimmed = value.trim();
  need(charCount(trimmed) <= PERSON_NAME_MAX, `${topic(label)} ${PERSON_NAME_MAX}자까지 쓸 수 있습니다.`);
  return trimmed || null;
}

/** 짧은 글 칸(관계 · 종교 · 학력 · 직업): 비었으면 null. */
function shortOf(value: string, label: string, max = PERSON_SHORT_MAX): string | null {
  const trimmed = value.trim();
  need(charCount(trimmed) <= max, `${topic(label)} ${max}자까지 쓸 수 있습니다.`);
  return trimmed || null;
}

/** 생년월일 칸: YYYY-MM-DD, 1900-01-01 ~ 오늘(today). 비었으면 null. */
function dateOf(value: string, label: string, today: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  need(
    // 없는 날짜(2015-02-29 등)는 Date 가 다음 달로 넘기므로, 다시 글자로 바꿔 같은지 본다.
    /^\d{4}-\d{2}-\d{2}$/.test(trimmed) &&
      !Number.isNaN(Date.parse(`${trimmed}T00:00:00Z`)) &&
      new Date(`${trimmed}T00:00:00Z`).toISOString().slice(0, 10) === trimmed,
    `${topic(label)} YYYY-MM-DD 로 입력해 주세요.`,
  );
  need(trimmed >= BIRTH_DATE_MIN && trimmed <= today, `${topic(label)} ${BIRTH_DATE_MIN} 부터 오늘까지 입력할 수 있습니다.`);
  return trimmed;
}

function familyOf(rows: FamilyRowInput[]): PersonalFamilyMember[] {
  // 문구의 줄 번호는 화면 표의 줄 번호다(빈 줄을 빼기 전).
  const filled = rows.map((row, index) => ({ row, index })).filter(({ row }) => !isBlankRow(row));
  need(filled.length <= FAMILY_MAX_ROWS, `가족관계는 ${FAMILY_MAX_ROWS}줄까지 적을 수 있습니다.`);

  return filled.map(({ row, index }) => {
    const at = `가족관계 ${index + 1}번째 줄`;
    const name = nameOf(row.name, `${at}의 성명`);
    need(name !== null, `${at}의 성명을 입력해 주세요(성명이 없는 줄은 저장할 수 없습니다).`);
    const age = row.age.trim();
    need(
      !age || (/^\d{1,3}$/.test(age) && Number(age) <= PERSON_AGE_MAX),
      `${at}의 나이는 0~${PERSON_AGE_MAX} 사이 숫자로 입력해 주세요.`,
    );

    return {
      name: name as string,
      relation: shortOf(row.relation, `${at}의 관계`),
      age: age ? Number(age) : null,
      religion: shortOf(row.religion, `${at}의 종교`),
      education: shortOf(row.education, `${at}의 학력`),
      job: shortOf(row.job, `${at}의 직업`, PERSON_JOB_MAX),
      living_together: row.living === "동거" ? true : row.living === "비동거" ? false : null,
    };
  });
}

function healthOf(input: PersonalInput): PersonalHealth | null {
  const subject = nameOf(input.healthSubject, "건강정도 대상자 이름");
  const items: PersonalHealthItem[] = [];

  for (const kind of PERSONAL_HEALTH_KINDS) {
    const row = input.health[kind];
    const detail = shortOf(row.detail, `건강정도 ${kind}의 세부 내용`, HEALTH_DETAIL_MAX);
    if (!row.present && detail === null) continue;
    items.push({ kind, present: row.present === "유" ? true : row.present === "무" ? false : null, detail });
  }

  return subject || items.length ? { subject_name: subject, items } : null;
}

/**
 * 보낼 값으로 바꾼다. 문제가 있으면 { problem } 에 화면에 보일 문장(입력한 값은 문장에 넣지 않는다).
 * 빈 줄 · 빈 묶음은 빼고, 모든 칸이 비었으면 빈 값(registered=false 와 같은 모양)이 된다.
 */
export function toPersonalInfoRequest(
  input: PersonalInput,
  { today = todayKst() }: { today?: string } = {},
): { payload: PersonalInfoRequest; problem: null } | { payload: null; problem: string } {
  try {
    const targetName = nameOf(input.targetName, "사례관리대상자 이름");
    const targetRelation = shortOf(input.targetRelation, "사례관리대상자 관계");
    const targetBirth = dateOf(input.targetBirthDate, "사례관리대상자 생년월일", today);
    const intervieweeName = nameOf(input.intervieweeName, "면접대상자 이름");
    const intervieweeRelation = shortOf(input.intervieweeRelation, "면접대상자 관계");

    const payload: PersonalInfoRequest = {
      child_name: nameOf(input.childName, "대상아동 이름"),
      child_birth_date: dateOf(input.childBirthDate, "생년월일", today),
      target_person:
        targetName || targetRelation || targetBirth
          ? { name: targetName, relation: targetRelation, birth_date: targetBirth }
          : null,
      interviewee: intervieweeName || intervieweeRelation ? { name: intervieweeName, relation: intervieweeRelation } : null,
      family_members: familyOf(input.family),
      health: healthOf(input),
    };

    return { payload, problem: null };
  } catch (caught) {
    if (caught instanceof InputProblem) return { payload: null, problem: caught.message };
    throw caught;
  }
}

/** 모든 칸이 비었는가(새 사례 등록에서 보낼지 · 저장 전 사례인지). */
export function isBlankPersonalRequest(request: PersonalInfoRequest): boolean {
  return (
    request.child_name === null &&
    request.child_birth_date === null &&
    request.target_person === null &&
    request.interviewee === null &&
    request.family_members.length === 0 &&
    request.health === null
  );
}

/** 서버 값(응답)을 보낼 값 모양으로(바뀐 것이 있는지 견줄 때). */
export function requestOf(info: PersonalInfo | null): PersonalInfoRequest | null {
  // 서버 값은 같은 규칙을 이미 지났다. 날짜 상한만 풀어 둔다(서버와 화면의 '오늘' 이 하루 어긋나도 걸리지 않게).
  return toPersonalInfoRequest(personalInputOf(info), { today: "9999-12-31" }).payload;
}

/** 같은 내용인가(칸 순서 무관하게 JSON 으로 견준다 — 두 값 모두 toPersonalInfoRequest 가 같은 순서로 만든다). */
export function samePersonalRequest(a: PersonalInfoRequest, b: PersonalInfoRequest): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/**
 * 인쇄 · 복사 때 가릴 이름 — 아동 · 사례관리대상자 · 면접대상자 · 가족 · 건강정도 대상자(겹친 이름은 하나).
 * extra 에 별칭 등을 더한다. 화면 상태에서만 쓰고 저장하지 않는다.
 */
export function personalNames(info: PersonalInfoRequest | null, extra: string[] = []): string[] {
  const names = info
    ? [
        info.child_name,
        info.target_person?.name,
        info.interviewee?.name,
        ...info.family_members.map((member) => member.name),
        info.health?.subject_name,
      ]
    : [];
  return [...new Set([...names, ...extra].map((value) => (value ?? "").trim()).filter(Boolean))];
}
