// 서식 4 의 고르기 · 글 칸(2026-11-05, '준비 중' 칸 열기) — 새 사례 등록 · 초기면접지 · 사례 상세가 같이 쓴다.
//
// ① 조치결과 · 피해아동 / 사례관리대상자 · 위험도(우선) · 사례연계 경위, ② 가족유형(하나, 21개) · 보호자와 아동과의 관계 · 문제력(한 칸) ·
// 대상자 태도 · 물리적 환경 · 상담원 소견 및 향후 계획 — 11/03 디자인(CaseRegister · CaseIntake 같음). 서버 칸 이름 · 규칙은
// API_CONTRACT 4절 'POST /cases'.
// 모두 상담원이 고르거나 적는다 — AI 가 미리 고르거나 채우지 않는다. 위험도(우선)는 상담원이 고른 사례 위험도로,
// 회차 AI 심각도(1~5) · 회차 위험도 판단과 맞추지 않는다.
// 글 칸은 평문 저장이다. 디자인 안내 글이 있는 칸(사례연계 경위 · 문제력)은 그 글을, 없는 칸은 '실명 · 연락처 · 주소 등 개인정보는
// 적지 마세요' 를 입력칸에 보이고, 화면 안내문에도 개인정보를 적지 말라고 적는다(사례 메모와 같음).

import {
  CHILD_ACTION_LABELS,
  FAMILY_TYPE_LABELS,
  RISK_LEVEL_LABELS,
  TARGET_ACTION_LABELS,
  type CaseFormFields,
} from "../api/types";

/** 글 칸 하나의 길이 제한(backend app/schemas/case.py CASE_FORM_TEXT_MAX). */
export const CASE_FORM_TEXT_MAX = 2000;

/** 글 칸 입력칸에 보일 안내(사례 메모와 같은 문구). 디자인 안내 글이 있는 칸은 caseTextPlaceholder 가 그 글을 준다. */
export const CASE_FORM_TEXT_PLACEHOLDER = "실명 · 연락처 · 주소 등 개인정보는 적지 마세요";

/** 11/03 디자인의 입력칸 안내 글. */
const DESIGN_PLACEHOLDERS: Partial<Record<string, string>> = {
  linkedBackground: "신고 경위 · 신고자 유형 · 연계 내용",
  problem: "피해아동/사례관리대상자/비가해보호자/가족구성원 등이 생각하는 현 상황, 현 상황이 초래된 이유 등에 대한 기재",
};

/** 글 칸의 입력칸 안내. 디자인 글이 있으면 그것, 없으면 개인정보 안내. */
export function caseTextPlaceholder(key: string): string {
  return DESIGN_PLACEHOLDERS[key] ?? CASE_FORM_TEXT_PLACEHOLDER;
}

/** 고르기 칸: 입력 키 · 서버 키 · 화면 이름 · 고를 값(서버 코드 → 화면 글자, 서식 순서). */
export const CASE_CHOICE_FIELDS = [
  { key: "childAction", api: "child_action_result", label: "조치결과 · 피해아동", labels: CHILD_ACTION_LABELS },
  { key: "targetAction", api: "target_action_result", label: "조치결과 · 사례관리대상자", labels: TARGET_ACTION_LABELS },
  { key: "riskLevel", api: "counselor_risk_level", label: "위험도 (우선)", labels: RISK_LEVEL_LABELS },
  { key: "familyType", api: "intake_family_type", label: "가족유형", labels: FAMILY_TYPE_LABELS },
] as const;

/** 글 칸: 입력 키 · 서버 키 · 화면 이름. */
export const CASE_TEXT_FIELDS = [
  { key: "linkedBackground", api: "linked_background", label: "사례연계 경위" },
  { key: "guardianRelation", api: "intake_guardian_relation", label: "보호자와 아동과의 관계" },
  { key: "problem", api: "intake_problem", label: "문제력" },
  { key: "attitude", api: "intake_attitude", label: "대상자 태도" },
  { key: "environment", api: "intake_environment", label: "물리적 환경" },
  { key: "opinion", api: "intake_opinion", label: "상담원 소견 및 향후 계획" },
] as const;

export const CASE_FORM_FIELDS = [...CASE_CHOICE_FIELDS, ...CASE_TEXT_FIELDS] as const;

export type CaseChoiceKey = (typeof CASE_CHOICE_FIELDS)[number]["key"];
export type CaseTextKey = (typeof CASE_TEXT_FIELDS)[number]["key"];
export type CaseFormKey = CaseChoiceKey | CaseTextKey;
type CaseFormField = (typeof CASE_FORM_FIELDS)[number];
type CaseFormApi = CaseFormField["api"];

/** 화면 입력 그대로(문자열). 고르기 칸은 서버 코드 또는 "", 글 칸은 적은 글. */
export type CaseFormInput = Record<CaseFormKey, string>;

export const EMPTY_CASE_FORM: CaseFormInput = Object.fromEntries(
  CASE_FORM_FIELDS.map((field) => [field.key, ""]),
) as CaseFormInput;

/** 서버 값으로 입력칸을 채운다(없으면 ""). */
export function caseFormInputOf(source: CaseFormFields): CaseFormInput {
  return Object.fromEntries(
    CASE_FORM_FIELDS.map((field) => [field.key, (source[field.api] as string | null | undefined) ?? ""]),
  ) as CaseFormInput;
}

/** 칸 하나의 보낼 값. 비었으면 null, 목록에 없는 값 · 너무 긴 글이면 problem. */
export function checkCaseFormField(field: CaseFormField, raw: string): { value: string | null; problem: string | null } {
  const text = raw.trim();

  if (!text) return { value: null, problem: null };
  if ("labels" in field) {
    return Object.prototype.hasOwnProperty.call(field.labels, text)
      ? { value: text, problem: null }
      : { value: null, problem: `${field.label}: 목록에서 다시 골라 주세요.` };
  }
  if (text.length > CASE_FORM_TEXT_MAX) {
    return { value: null, problem: `${field.label}: ${CASE_FORM_TEXT_MAX.toLocaleString()}자까지 쓸 수 있습니다.` };
  }
  return { value: text, problem: null };
}

/** 요청 본문에 칸 하나를 넣는다(칸마다 값 형식이 달라 한곳에서만 바꿔 넣는다 — 값은 checkCaseFormField 로 확인한 것). */
export function putCaseFormValue(payload: CaseFormFields, api: CaseFormApi, value: string | null): void {
  (payload as unknown as Record<CaseFormApi, string | null>)[api] = value;
}

/** 고르기 칸의 화면 글자. 비었거나 모르는 값이면 "". */
export function caseChoiceLabel(key: CaseChoiceKey, value: string): string {
  const field = CASE_CHOICE_FIELDS.find((item) => item.key === key);
  if (!field || !value) return "";
  return (field.labels as Record<string, string>)[value] ?? "";
}

/**
 * 글 칸 화면 값(새 사례 등록 · 초기면접지). field 는 화면마다의 칸 값 함수(value · onChange 등).
 * 길이 제한과 입력칸 안내(caseTextPlaceholder)를 붙인다. 키는 CASE_TEXT_FIELDS 의 key 와 같다.
 */
export function caseTextValues<T extends object>(field: (name: CaseTextKey) => T) {
  return Object.fromEntries(
    CASE_TEXT_FIELDS.map(({ key }) => [key, { ...field(key), max: CASE_FORM_TEXT_MAX, placeholder: caseTextPlaceholder(key) }]),
  ) as Record<CaseTextKey, T & { max: number; placeholder: string }>;
}

/** 고르기 칸의 선택지(서식 순서). */
export function caseChoiceOptions(key: CaseChoiceKey): { value: string; label: string }[] {
  const field = CASE_CHOICE_FIELDS.find((item) => item.key === key);
  return field ? Object.entries(field.labels as Record<string, string>).map(([value, label]) => ({ value, label })) : [];
}
