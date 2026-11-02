// 탭 5 › 기관 서식 작성(CaseForm) 화면 값. 머리는 useCaseDetail, 서식 기록은 useCaseForms(API_CONTRACT 22절)로 그린다.
//
// 서식은 사례 단위다. 화면 주소 ?case=<사례 ID>&form=A|B|C|D 로 서식을 고른다(디자인은 브라우저 저장소 ispot-form 을 쓰지만
// 앱은 주소 쿼리로 넘긴다 — 문서함 '작성' · 내담자 정보 '기관 서식 작성' 링크가 붙인다). 없으면 A(사정기록지).
//  - 열면 그 서식의 임시 저장 차수, 없으면 가장 최근 확정 차수의 칸을 보인다. 고친 칸은 저장 전까지 화면에만 있다(edits).
//  - '임시 저장': 임시 저장 차수가 있으면 그 차수를 고치고, 없으면 다음 차수를 만든다(확정 차수를 고쳤으면 다음 차수).
//  - '확정': 임시 저장 뒤 확정. 확정한 차수는 고칠 수 없고, 다시 고쳐 저장하면 다음 차수가 된다.
//  - 디자인의 'AI 제안' · 'AI 초안'(칸 옆 근거 · 소견 초안)은 서버에 없고 상담사 판단 칸이라 AI 가 채우지 않는다 — 보이지 않는다.
//    점수 합계 · 응답 수만 화면이 계산한다(군 판정 · 사정결과는 상담원이 고른다).

import type {
  CaseForm,
  CaseFormType,
  CaseFormValuesMap,
  FamilyScaleValues,
  FormLevel,
  FormYesNo,
  ManagementChecklistValues,
  RiskScaleValues,
  SafetyAssessmentValues,
} from "../../api/types";
import { NOT_PROVIDED } from "../caseRows";
import { toDateOnly } from "../time";
import { currentForm, lastConfirmed, type CaseFormsState } from "../useCaseForms";
import { caseHeaderValues, type CaseScreenInput } from "./caseDetail";
import { notice } from "./common";
import { screenHref } from "./links";

export type FormTab = "A" | "B" | "C" | "D";
export const FORM_PARAM = "form";

export const FORM_TYPES: Record<FormTab, CaseFormType> = {
  A: "SAFETY_ASSESSMENT",
  B: "MANAGEMENT_CHECKLIST",
  C: "RISK_SCALE",
  D: "FAMILY_SCALE",
};

const FORM_NAMES: Record<FormTab, string> = {
  A: "사정기록지 · 안전영역",
  B: "사례관리 점검표",
  C: "위험수준별 개입 사정 척도",
  D: "가족관계 척도",
};

/** 주소 쿼리 form 값. 모르는 값이면 A. */
export function readFormTab(value: string | null | undefined): FormTab {
  const tab = (value ?? "").trim().toUpperCase();
  return tab === "B" || tab === "C" || tab === "D" ? tab : "A";
}

/** 서식 화면 링크(문서함 · 내담자 정보). */
export function caseFormHref(caseId: string | null, tab: FormTab): string {
  const base = screenHref("/CaseForm", { caseId });
  return `${base}${base.includes("?") ? "&" : "?"}${FORM_PARAM}=${tab}`;
}

/**
 * 내담자 정보 '기관 서식' 카드(디자인: '점검표 3차 작성 전' 칩 + '기관 서식 작성' → 점검표).
 * 칩은 사례관리 점검표 기록으로 보인다: 기록 없음 '점검표 1차 작성 전', 임시 저장 'N차 임시 저장', 확정 'N차 확정 · 날짜'.
 */
export function formsCardValues(forms: CaseFormsState, caseId: string | null) {
  let chip = NOT_PROVIDED;
  if (forms.loadError) chip = "서식 기록을 불러오지 못함";
  else if (forms.loaded) {
    const row = currentForm(forms.items, FORM_TYPES.B);
    if (!row) chip = "점검표 1차 작성 전";
    else if (row.status === "DRAFT") chip = `점검표 ${row.round}차 임시 저장`;
    else chip = `점검표 ${row.round}차 확정 · ${toDateOnly(row.confirmed_at)}`;
  }
  return { chip, href: caseFormHref(caseId, "B") };
}

/**
 * 종결보고서 '가족관계척도' 줄(11/03): 가족관계 척도 가장 최근 기록(임시 저장 포함)의 평균 · 응답일 · 응답자,
 * 2차 이상이면 1차(초기) 평균도. 평균은 작성 화면과 같은 계산(응답 합 / 15).
 */
export function familyScaleLine(forms: CaseFormsState): { avg: string; sub: string } {
  if (forms.loadError) return { avg: "", sub: `${NOT_PROVIDED} · 가족관계 척도 기록을 불러오지 못함` };
  if (!forms.loaded) return { avg: "", sub: NOT_PROVIDED };
  const rows = forms.items.filter((item) => item.form_type === FORM_TYPES.D).sort((a, b) => b.round - a.round);
  const latest = currentForm(forms.items, FORM_TYPES.D);
  const avgOf = (row: CaseForm) => {
    const answered = normalize("FAMILY_SCALE", row.values as Record<string, unknown>).answers.filter((x): x is number => x !== null);
    return answered.length ? (answered.reduce((a, b) => a + b, 0) / 15).toFixed(2) : "";
  };
  const day = (row: CaseForm) => {
    const d = toDateOnly(row.confirmed_at ?? row.updated_at);
    return d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : NOT_PROVIDED;
  };
  if (!latest || !avgOf(latest)) return { avg: "", sub: `${NOT_PROVIDED} · 가족관계 척도 응답 기록 없음` };
  const who = RESPONDENTS.find(([, code]) => code === normalize("FAMILY_SCALE", latest.values as Record<string, unknown>).respondent)?.[0];
  const first = rows.find((row) => row.round === 1);
  const initial = first && first.id !== latest.id && avgOf(first) ? ` · 초기 ${day(first)} 응답 ${avgOf(first)}점` : "";
  const draft = latest.status === "DRAFT" ? " · 임시 저장" : "";
  return { avg: avgOf(latest), sub: `${day(latest)} 응답${who ? ` (${who})` : ""}${draft}${initial}` };
}

// ---------------------------------------------------------
// 서식 문항(디자인 · 매뉴얼 서식 그대로)
// ---------------------------------------------------------

/** 안전영역 (서식 6 · 서식 29 공통 문항) */
const SA: [string, string[]][] = [
  ["피해아동", ["아동의 위험상황 인지 및 대처능력", "아동의 연령, 장애 등 집중적 보호가 요구되는 특성 보유", "피해아동과 가족과의 관계 친밀성"]],
  [
    "가족구성원",
    [
      "가족구성원의 아동 안전 보호 및 양육 의지",
      "가정 내 가정폭력 문제",
      "아동보호전문기관의 개입에 대한 태도",
      "가족기능과 가정환경에 대한 평가",
      "주양육자의 양육역량",
    ],
  ],
  [
    "사례관리대상자",
    [
      "학대행위에 대한 잘못 인지 및 개선 의지",
      "스스로 자신을 통제하기 어려운 특성 (중독, 성격장애 등)",
      "가정 내 위기상황(실직, 가정폭력 등)으로 인한 만성적 스트레스",
    ],
  ],
];

/** 서식 27 점검표 */
const CK = [
  "사례관리 계획에 따라 서비스가 적절하게 제공되고 있는가?",
  "학대피해아동과 비공식적인 지지망 그리고 전문적 보호체계의 노력이 적절한가?",
  "학대피해아동 가정이 안전하며 학대 위험이 감소하고 있는가? (소견에 구체적 근거 작성)",
  "제공되는 서비스에 대해 학대피해아동과 가족이 만족하고 있는가?",
  "다른 서비스 욕구가 발생하였는가?",
  "사례관리 지속이 필요한가?",
  "재사정이 필요한가?",
  "사례관리 계획은 수정되어야 하는가?",
  "사례는 종결되어야 하는가?",
];

/** 참고자료 3 · 43문항 */
const Q = [
  "아동은 질환을 가지고 있다.",
  "아동은 인터넷(핸드폰) 과의존 상태이다.",
  "아동은 신체 및 정신장애를 가지고 있다.",
  "아동이 신체적 상흔이나 손상을 가지고 있다.",
  "아동은 또래에 비해 발달상태가 느리다.",
  "아동은 자해행위 또는 자살을 시도한 적이 있다.",
  "아동은 심리적인 어려움을 가지고 있다.",
  "아동은 다른 사람과의 관계에 어려움이 있다.",
  "아동은 의사소통이 어렵다.",
  "아동이 비행행동을 하였다.",
  "아동이 성과 관련된 문제행동을 보인다.",
  "아동이 청결하지 못한 상태이다.",
  "아동이 아동보호전문기관 등의 개입에 거부적이다.",
  "아동이 사회로부터 고립되어 있다.",
  "주거환경이 열악하거나 불안정하다.",
  "지역사회 내에 모니터링 체계가 없다.",
  "동거가족 중 112 등에 신고된 사람이 있다.",
  "가족이 스트레스 상황에 노출되어 있다.",
  "주양육자는 사례관리대상자의 치료나 변화에 개입할 의지가 없다.",
  "주양육자가 사례관리대상자를 옹호하려고 한다.",
  "주양육자는 사례관리대상자에 대한 의존도가 높다.",
  "주양육자는 아동 양육을 위한 적절한 지식을 가지고 있다.",
  "주양육자는 보호자로서 자신의 역할을 이해하고 있다.",
  "주양육자는 학대에 대해 민감하다.",
  "주양육자는 자신의 욕구보다 아동의 욕구를 우선한다.",
  "주양육자는 아동의 기본적인 욕구를 충족시킨다.",
  "주양육자는 상황에 맞게 감정을 조절할 수 있다.",
  "주양육자는 장애가 없다.",
  "주양육자는 질환이 없다.",
  "주양육자는 양육에 있어서 적극적이다.",
  "주양육자는 아이의 정서에 따라 반응할 수 있다.",
  "주양육자는 아동에게 너그럽다.",
  "주양육자와 아동은 정서적 유대를 가지고 상호 간에 애착을 형성하고 있다.",
  "주양육자는 아동에 대해 현실적인 기대를 가지고 있다.",
  "주양육자는 긍정적인 생각과 태도를 가지고 있다.",
  "주양육자를 지지해주는 가족이 있다.",
  "가족에게 비공식적인 사회적 지지체계가 있다.",
  "가족에게 공식적인 사회적 지지체계가 있다.",
  "주양육자는 주변에 도움을 적극적으로 요청한다.",
  "주양육자는 아동보호전문기관 등의 개입에 수용적이다.",
  "주양육자는 사례관리대상자로부터 아동을 보호할 수 있다.",
  "아동은 자기보호능력이 있어서 학대로부터 스스로를 보호할 수 있다.",
  "주양육자 외 가족 내 양육을 도와주는 사람이 있다.",
];
const LBL = ["매우 아니다", "아니다", "그렇다", "매우 그렇다"];

/** 참고자료 1 · 15문항 */
const F = [
  "우리 가족은 가족끼리 대화가 잘 된다",
  "우리 가족은 문제를 함께 잘 해결하려고 노력한다",
  "우리 가족은 서로에 대해 잘 알고 있다",
  "우리 가족은 각자의 장점에 대해 가족들에게 마음을 열고 허심탄회하게 이야기한다",
  "우리 가족은 도움이 필요할 때 언제든지 서로 도움을 청할 수 있다",
  "우리 가족은 여가시간을 함께 보내기를 좋아한다",
  "우리 가족은 서로 친밀하게 느낀다",
  "우리 가족은 솔직하고 정직하다",
  "우리 가족은 서로 지지해주고 격려해준다",
  "우리 가족은 서로에게 생각과 느낌을 표현할 수 있다",
  "가족의 일을 계획할 때 우리 가족 모두에게 발언권이 있다",
  "우리 가족은 서로를 있는 그대로 인정한다",
  "우리 가족은 각각 자신의 행동에 책임을 진다",
  "우리 가족은 가족들 간의 서로 다른 의견을 존중한다",
  "우리 가족은 서로의 강점을 존중한다",
];

const LEVELS: [string, FormLevel][] = [
  ["높음", "HIGH"],
  ["보통", "MEDIUM"],
  ["낮음", "LOW"],
];
const KEY_OPTS: [string, FormYesNo][] = [
  ["있음", "YES"],
  ["없음", "NO"],
];
const YES_NO: [string, FormYesNo][] = [
  ["예", "YES"],
  ["아니오", "NO"],
];
const RESULTS: [string, NonNullable<SafetyAssessmentValues["result"]>][] = [
  ["집중관리 사례", "INTENSIVE"],
  ["일반관리 사례", "GENERAL"],
  ["모니터링관리 사례", "MONITORING"],
];
const RESPONDENTS: [string, NonNullable<FamilyScaleValues["respondent"]>][] = [
  ["부", "FATHER"],
  ["모", "MOTHER"],
  ["아동", "CHILD"],
];
const SCORE_WHO = ["피해아동 응답", "가족구성원 응답", "사례관리대상자 응답"];

// ---------------------------------------------------------
// 칸 값
// ---------------------------------------------------------

type AnyValues = CaseFormValuesMap[CaseFormType];

const fixed = <T>(source: unknown, count: number, pick: (item: unknown) => T): T[] =>
  Array.from({ length: count }, (_, i) => pick(Array.isArray(source) ? source[i] : undefined));
const oneOf = <T extends string>(value: unknown, allowed: readonly T[]): T | null =>
  allowed.includes(value as T) ? (value as T) : null;
const intIn = (value: unknown, min: number, max: number): number | null =>
  typeof value === "number" && Number.isInteger(value) && value >= min && value <= max ? value : null;
const text = (value: unknown): string => (typeof value === "string" ? value : "");

/** 서버 값(또는 빈 값)을 서식 꼴로 맞춘다. 모르는 칸 · 맞지 않는 값은 빈 칸. */
function normalize(type: "SAFETY_ASSESSMENT", raw: Record<string, unknown> | null): SafetyAssessmentValues;
function normalize(type: "MANAGEMENT_CHECKLIST", raw: Record<string, unknown> | null): ManagementChecklistValues;
function normalize(type: "RISK_SCALE", raw: Record<string, unknown> | null): RiskScaleValues;
function normalize(type: "FAMILY_SCALE", raw: Record<string, unknown> | null): FamilyScaleValues;
function normalize(type: CaseFormType, raw: Record<string, unknown> | null): AnyValues;
function normalize(type: CaseFormType, raw: Record<string, unknown> | null): AnyValues {
  const v = raw ?? {};
  const levels = LEVELS.map(([, code]) => code);
  const yesNo: FormYesNo[] = ["YES", "NO"];

  if (type === "SAFETY_ASSESSMENT") {
    return {
      items: fixed(v.items, 11, (item) => oneOf(item, levels)),
      key_person: oneOf(v.key_person, yesNo),
      scores: fixed(v.scores, 3, (item) => {
        const row = (item ?? {}) as Record<string, unknown>;
        return { score: intIn(row.score, 1, 10), reason: text(row.reason) };
      }),
      opinion: text(v.opinion),
      result: oneOf(
        v.result,
        RESULTS.map(([, code]) => code),
      ),
    };
  }
  if (type === "MANAGEMENT_CHECKLIST") {
    return {
      place: text(v.place),
      checks: fixed(v.checks, 9, (item) => oneOf(item, yesNo)),
      opinion: text(v.opinion),
      plan: text(v.plan),
    };
  }
  if (type === "RISK_SCALE") return { scores: fixed(v.scores, 43, (item) => intIn(item, 0, 3)) };
  return {
    respondent: oneOf(
      v.respondent,
      RESPONDENTS.map(([, code]) => code),
    ),
    answers: fixed(v.answers, 15, (item) => intIn(item, 1, 5)),
  };
}

/** 화면에서 고친(아직 저장하지 않은) 서식 칸. 서식마다 고친 적이 없으면 없음. */
export type FormEdits = Partial<Record<FormTab, AnyValues>>;

export interface CaseFormUiState {
  /** 화면 안에서 고른 서식(척도 열기). 주소의 form 이 바뀌면 그 값을 따른다. */
  tab: FormTab | null;
  tabFor: string | null;
  edits: FormEdits;
  /** 고친 칸이 어느 사례 것인가. 다른 사례로 옮기면 버린다. */
  editsFor: string | null;
  /** 저장 결과 · 막은 이유 한 줄. */
  note: string;
}

export const INITIAL_CASE_FORM_STATE: CaseFormUiState = {
  tab: null,
  tabFor: null,
  edits: {},
  editsFor: null,
  note: "",
};

interface CaseFormInput extends CaseScreenInput {
  forms: CaseFormsState;
  formParam: string | null;
  state: CaseFormUiState;
  setState: (patch: Partial<CaseFormUiState>) => void;
}

const SEL = (on: boolean) => ({
  bg: on ? "#F1EADA" : "transparent",
  fg: on ? "#2B2A26" : "#66625A",
  fw: on ? 700 : 400,
  bd: on ? "inset 0 0 0 1px #2B2A26" : "none",
});

export function caseFormValues(input: CaseFormInput) {
  const { forms, state: s, setState, caseId } = input;
  const header = caseHeaderValues(input);
  const info = input.detail.caseInfo;
  const paramTab = readFormTab(input.formParam);
  const tab: FormTab = s.tab && s.tabFor === (input.formParam ?? "") ? s.tab : paramTab;
  const edits: FormEdits = s.editsFor === caseId ? s.edits : {};

  const recordOf = (k: FormTab) => currentForm(forms.items, FORM_TYPES[k]);
  const saved = (k: FormTab) => normalize(FORM_TYPES[k], (recordOf(k)?.values as Record<string, unknown>) ?? null);
  const valuesOf = <K extends FormTab>(k: K) => (edits[k] ?? saved(k)) as AnyValues;
  const A = valuesOf("A") as SafetyAssessmentValues;
  const B = valuesOf("B") as ManagementChecklistValues;
  const C = valuesOf("C") as RiskScaleValues;
  const D = valuesOf("D") as FamilyScaleValues;
  const edit = <K extends FormTab>(k: K, next: AnyValues) =>
    setState({ edits: { ...edits, [k]: next }, editsFor: caseId, note: "" });

  // 디자인: 선택 단추를 다시 누르면 고른 것을 푼다(안전영역 · 점검표 · 척도 · 사정결과).
  const toggle = <T>(cur: T | null, value: T) => (cur === value ? null : value);
  const pickList = <T>(list: (T | null)[], i: number, value: T) => list.map((x, j) => (j === i ? toggle(x, value) : x));

  // 안전영역
  let idx = 0;
  const safety = SA.map(([name, items]) => ({
    name,
    items: items.map((q) => {
      const k = idx++;
      return {
        q,
        ai: "",
        ev: "",
        // AI 제안 · 근거는 서버에 없다(상담사 판단 칸).
        hasEv: false,
        opts: LEVELS.map(([label, code]) => ({
          label,
          ...SEL(A.items[k] === code),
          pick: () => edit("A", { ...A, items: pickList(A.items, k, code) }),
        })),
      };
    }),
  }));
  const keyOpts = KEY_OPTS.map(([label, code]) => ({
    label,
    ...SEL(A.key_person === code),
    pick: () => edit("A", { ...A, key_person: code }),
  }));
  const scoreRows = SCORE_WHO.map((who, i) => ({
    who,
    score: A.scores[i].score === null ? "" : String(A.scores[i].score),
    reason: A.scores[i].reason,
    setScore: (raw: string) => {
      const n = Number.parseInt(raw, 10);
      const score = Number.isNaN(n) ? null : Math.min(10, Math.max(1, n));
      edit("A", { ...A, scores: A.scores.map((row, j) => (j === i ? { ...row, score } : row)) });
    },
    setReason: (reason: string) =>
      edit("A", { ...A, scores: A.scores.map((row, j) => (j === i ? { ...row, reason } : row)) }),
  }));
  const resultOpts = RESULTS.map(([label, code]) => ({
    label,
    ...SEL(A.result === code),
    pick: () => edit("A", { ...A, result: toggle(A.result, code) }),
  }));

  // 점검표
  const checks = CK.map((q, i) => ({
    q: `${i + 1}. ${q}`,
    opts: YES_NO.map(([label, code]) => ({
      label,
      ...SEL(B.checks[i] === code),
      pick: () => edit("B", { ...B, checks: pickList(B.checks, i, code) }),
    })),
  }));

  // 척도(합계는 화면이 계산한다)
  let rs = 0;
  let ps = 0;
  let filled = 0;
  const scale = Q.map((q, i) => {
    const n = i + 1;
    const v = C.scores[i];
    if (v !== null) {
      filled++;
      if (n <= 21) rs += v;
      else ps += v;
    }
    return {
      n,
      q,
      head: n === 1 || n === 22,
      hid: n === 1 ? "scale-risk" : "scale-prot",
      headLabel: n === 1 ? "위험요인 (1~21)" : "보호요인 (22~43)",
      // AI 제안은 서버에 없다(상담사 판단 칸).
      ev: "",
      opts: [0, 1, 2, 3].map((o) => ({
        label: LBL[o],
        ...SEL(v === o),
        pick: () => edit("C", { ...C, scores: pickList(C.scores, i, o) }),
      })),
    };
  });

  // 가족관계 척도
  let fs = 0;
  let fn = 0;
  const fam = F.map((q, i) => {
    const v = D.answers[i];
    if (v) {
      fs += v;
      fn++;
    }
    return {
      n: i + 1,
      q,
      opts: [1, 2, 3, 4, 5].map((o) => ({
        label: String(o),
        ...SEL(v === o),
        pick: () => edit("D", { ...D, answers: pickList(D.answers, i, o) }),
      })),
    };
  });
  const resp = RESPONDENTS.map(([label, code]) => ({
    label,
    ...SEL(D.respondent === code),
    pick: () => edit("D", { ...D, respondent: code }),
  }));

  // 서식의 차수: 임시 저장 차수, 확정 차수(고치지 않았으면 그 차수, 고쳤으면 다음 차수), 기록이 없으면 1차.
  const roundOf = (k: FormTab) => {
    const row: CaseForm | null = recordOf(k);
    const changed = edits[k] !== undefined;
    const next = row ? (row.status === "DRAFT" ? row.round : row.round + 1) : 1;
    const shownConfirmed = row !== null && row.status === "APPROVED" && !changed;
    return { row, changed, next, shown: shownConfirmed ? row.round : next, shownConfirmed };
  };
  const { row: record, changed: dirty, next: nextRound } = roundOf(tab);
  // 점검표 머리: 점검일은 확정한 날(작성 중이면 오늘), 이전 점검일은 보이는 차수 앞의 확정 차수.
  const check = roundOf("B");
  const prevCheck = lastConfirmed(forms.items, FORM_TYPES.B, check.shown);
  const checkDate = check.shownConfirmed ? toDateOnly(check.row?.confirmed_at) : toDateOnly(new Date().toISOString());

  let status = "";
  if (!forms.loaded) status = forms.loading ? "서식 기록을 불러오는 중…" : "";
  else if (!record) status = `작성 기록 없음 · 저장하면 1차로 남습니다.`;
  else if (record.status === "DRAFT") status = `${record.round}차 임시 저장 · ${toDateOnly(record.updated_at)}`;
  else if (dirty) status = `${record.round}차 확정 (${toDateOnly(record.confirmed_at)}) · 고친 칸은 ${nextRound}차로 저장됩니다.`;
  else status = `${record.round}차 확정 · ${toDateOnly(record.confirmed_at)}`;
  if (dirty && record?.status !== "APPROVED") status += " · 저장하지 않은 수정이 있습니다.";

  const busy = forms.submitting || !forms.loaded || !caseId || forms.loadError !== null;
  const run = async (confirm: boolean) => {
    if (busy) return;
    const change = edits[tab];
    if (change === undefined && record?.status !== "DRAFT") {
      setState({
        note:
          record?.status === "APPROVED"
            ? `이미 확정한 ${record.round}차입니다. 칸을 고치면 ${record.round + 1}차로 저장됩니다.`
            : "작성한 칸이 없습니다.",
      });
      return;
    }
    if (change === undefined && !confirm) {
      setState({ note: "바꾼 칸이 없습니다." });
      return;
    }
    if (confirm && !window.confirm(`${FORM_NAMES[tab]} ${nextRound}차를 확정할까요? 확정하면 이 차수는 고칠 수 없습니다.`)) {
      return;
    }
    const ok = await forms.save(FORM_TYPES[tab], change ?? saved(tab), confirm);
    if (ok) {
      const rest = { ...edits };
      delete rest[tab];
      setState({ edits: rest, editsFor: caseId, note: confirm ? `${nextRound}차를 확정했습니다.` : `${nextRound}차를 임시 저장했습니다.` });
    }
  };

  let formsNotice = header.notice;
  if (!formsNotice && forms.loadError) formsNotice = notice(forms.loadError, { alert: true, retry: forms.reload });

  return {
    ...header,
    notice: formsNotice,
    backHref: screenHref("/CaseDocs", { caseId }),
    tabs: header.tabs,
    tA: tab === "A",
    tB: tab === "B",
    tC: tab === "C",
    tD: tab === "D",
    goC: () => setState({ tab: "C", tabFor: input.formParam ?? "", note: "" }),
    safety,
    keyOpts,
    // Key Person 의 AI 제안 · 근거, 점검표 소견 · 계획의 'AI 초안' 은 서버에 없다(상담사 판단 칸).
    keyEv: "",
    aiDraft: false,
    scoreRows,
    opinionA: A.opinion,
    setOpinionA: (opinion: string) => edit("A", { ...A, opinion }),
    resultOpts,
    fhead: {
      name: header.title || NOT_PROVIDED,
      counselor: info?.counselorName || NOT_PROVIDED,
      birth: header.sub || NOT_PROVIDED,
      round: `${checkDate || NOT_PROVIDED} / ${check.shown}차`,
      prev: prevCheck ? toDateOnly(prevCheck.confirmed_at) : NOT_PROVIDED,
    },
    place: B.place,
    setPlace: (place: string) => edit("B", { ...B, place }),
    checks,
    opinionB: B.opinion,
    setOpinionB: (opinion: string) => edit("B", { ...B, opinion }),
    planB: B.plan,
    setPlanB: (plan: string) => edit("B", { ...B, plan }),
    scale,
    riskSum: rs,
    protSum: ps,
    filled,
    scrollRisk: (event: { preventDefault: () => void }) => {
      // 디자인의 href="#scale-risk" 는 해시 라우터 주소를 바꾸므로 그 자리로 스크롤만 한다.
      event.preventDefault();
      document.getElementById("scale-risk")?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    fam,
    resp,
    famAvg: fn ? (fs / 15).toFixed(2) : "—",
    famN: fn,
    statusNote: s.note || forms.error || status,
    statusAlert: Boolean(forms.error && !s.note),
    canSave: !busy,
    saveDraft: () => void run(false),
    confirm: () => void run(true),
    unsaved: Object.keys(edits).length > 0,
  };
}
