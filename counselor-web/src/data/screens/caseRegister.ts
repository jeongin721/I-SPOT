// 새 사례 등록(CaseRegister · 서식 4 초기면접지 팝업) 화면 값. useCaseRegister 로 서버가 받는 칸만 저장한다.
//
// 저장하는 칸: 사례 제목 · 아동 별칭(필수), 개별사건번호(비우면 자동) · 성별 · 출생연도 · 보호자 유형(기타면 보호자 메모) · 사례 메모,
// ② 초기면접 내용의 아동 특성 · 가정상황(서식 4 항목 고르기), 담당 상담원(관리자만 고름, 상담원은 본인).
// 등록되면 새 사례의 상세(?case=새 ID)로 간다. 초기면접 아동 특성 · 가정상황은 사례 상세(caseDetail.ts, 등록 뒤 고치기도 여기서)와
// 상담 일지(noteWrite.ts)에 단어로 보인다.
// 나머지 서식 4 칸은 개인정보 저장 범위가 팀 결정 전이라(specs 대응표 CaseRegister 줄) 입력을 막고 '준비 중' 으로 둔다:
//  - 실명 · 생년월일(출생연도만 저장) · 사례관리대상자(보호자와 같은 뜻이 아니어서 보호자 유형으로 채우지 않는다)
//  - 신고접수일 · 사례연계일 · 최초면접일 · 학대유형 · 조치결과 · 면접대상자 · 위험도 · 사례연계 경위
//  - ② 초기면접 내용 탭의 나머지(보호자와 아동과의 관계 · 가족유형 · 가족관계 · 문제력 · 태도 · 소견)
// 이 칸들의 내용을 사례 메모 등 다른 칸에 옮겨 담지 않는다.

import { GUARDIAN_LABELS, type GuardianType } from "../../api/types";
import type { AuthSession } from "../useAuthSession";
import {
  CASE_ALIAS_MAX,
  CASE_NOTES_MAX,
  CASE_NUMBER_MAX,
  CASE_TITLE_MAX,
  EMPTY_CASE_INPUT,
  GUARDIAN_NOTE_MAX,
  type CaseRegisterInput,
  type CaseRegisterState,
} from "../useCaseRegister";
import { NOT_READY, notice, screenNotice } from "./common";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS } from "./intakeItems";
import { intakeChoices, toggleItem } from "./intakePick";
import { screenHref } from "./links";

const FAM = [
  "일반가정",
  "부자가정",
  "모자가정",
  "미혼부 · 모 가정",
  "친부+계모",
  "친모+계부",
  "친인척보호",
  "친부+동거녀",
  "친모+동거남",
  "가정위탁",
  "입양가정",
  "시설보호",
  "기타",
];

export interface RegisterUiState {
  tab: "A" | "B";
  form: CaseRegisterInput;
  /** ② 탭으로 넘어가려다 필수 칸이 비어 막혔는가(그때부터 빈 필수 칸을 표시한다 — 10/21 디자인). */
  tried: boolean;
}

export function initialRegisterState(): RegisterUiState {
  return { tab: "A", form: { ...EMPTY_CASE_INPUT }, tried: false };
}

/** ① 기본 정보의 필수 칸. 서버가 받는 칸 중 비울 수 없는 것만 센다(준비 중 칸은 입력할 수 없어 뺀다). */
const REQUIRED: [TextKey, string][] = [
  ["title", "사례 제목"],
  ["alias", "아동 별칭"],
];

/** 빈 필수 칸 테두리(디자인 값). */
const INVALID_BORDER = "#A33B2E";

/** 고를 수 없는(준비 중) 선택 단추. 모양은 고르지 않은 단추다. */
const picker = (label: string) => ({ label, bg: "#FFFFFF", bd: "#DAD5C9", fg: "#2B2A26", fw: 400, mark: "+" });

type IntakeKey = "childTraits" | "familySituations";
type TextKey = Exclude<keyof CaseRegisterInput, IntakeKey>;

interface CaseRegisterInputs {
  session: AuthSession;
  register: CaseRegisterState;
  /** 주소의 back(이 팝업을 연 화면). 없으면 null — 닫기 · 취소는 사례 관리로 간다. */
  back: string | null;
  state: RegisterUiState;
  setState: (patch: Partial<RegisterUiState> | ((current: RegisterUiState) => Partial<RegisterUiState>)) => void;
  /** 등록 뒤 새 사례 상세로 옮긴다(useScreenGo — 그사이 화면을 떠났으면 옮기지 않는다). */
  go: (href: string) => void;
}

export function caseRegisterValues({ session, register, back, state, setState, go }: CaseRegisterInputs) {
  const form = state.form;
  const me = session.me;
  const isAdmin = session.isAdmin;
  const missing = REQUIRED.filter(([name]) => !String(form[name] ?? "").trim());

  /** 입력칸 하나의 값과 바꾸는 함수. 필수 칸이 비었는데 ② 탭으로 넘어가려 했으면 invalid 다. */
  const field = (name: TextKey) => {
    const invalid = state.tried && missing.some(([key]) => key === name);

    return {
      value: form[name],
      onChange: (event: { target: { value: string } }) => {
        const value = event.target.value;
        setState((current) => ({ form: { ...current.form, [name]: value } }));
      },
      invalid: invalid ? "true" : "false",
      border: invalid ? INVALID_BORDER : undefined,
    };
  };

  /** 탭 옮기기. ② 탭은 필수 칸을 다 채워야 열린다(10/21 디자인). */
  const goTab = (key: RegisterUiState["tab"]) => {
    if (key === "B" && missing.length > 0) setState({ tab: "A", tried: true });
    else setState({ tab: key });
  };

  const tabs = (
    [
      ["A", "① 기본 정보 (필수)"],
      ["B", "② 초기면접 내용"],
    ] as const
  ).map(([key, label]) => ({
    label,
    sel: state.tab === key ? "true" : "false",
    bd: state.tab === key ? "#C2A36B" : "transparent",
    fg: state.tab === key ? "#2B2A26" : "#66625A",
    fw: state.tab === key ? 700 : 400,
    go: () => goTab(key),
  }));

  const guardianOptions = (Object.keys(GUARDIAN_LABELS) as GuardianType[]).map((type) => ({
    value: type,
    label: GUARDIAN_LABELS[type],
  }));

  // 관리자: 담당 상담원을 고른다(목록을 못 받았으면 본인으로 등록된다는 안내). 상담원: 본인 이름만 보인다.
  let counselorNote = "";
  if (isAdmin && register.counselorsLoading) counselorNote = "담당 상담원 목록을 불러오는 중…";
  else if (isAdmin && register.counselorsError) counselorNote = `${register.counselorsError} 고르지 않으면 본인으로 등록됩니다.`;
  else if (!isAdmin) counselorNote = "담당 상담원은 관리자만 바꿀 수 있습니다.";

  const submitting = register.submitting || register.created !== null;

  /** 초기면접 아동 특성 · 가정상황 고르기 단추(눌러서 고르고 다시 눌러 뺀다). 등록 중에는 잠근다. */
  const intakePickers = (key: IntakeKey, options: string[]) =>
    intakeChoices(options, form[key], submitting, (label) =>
      setState((current) => ({ form: { ...current.form, [key]: toggleItem(current.form[key], label) } })),
    );

  const submit = async (event?: { preventDefault?: () => void }) => {
    if (event && event.preventDefault) event.preventDefault();
    const created = await register.submit(form);
    if (created) go(screenHref("/CaseDetail", { caseId: created.id }));
  };

  return {
    notice: screenNotice({ session }),
    formError: register.error ? notice(register.error, { alert: true }) : null,
    savedNote:
      "서버에 저장하는 칸: 사례 제목 · 아동 별칭 · 개별사건번호 · 성별 · 출생연도 · 보호자 유형 · 사례 메모 · 담당 상담원, " +
      "② 초기면접 내용의 가정상황 · 아동 특성. " +
      `'${NOT_READY}' 칸은 개인정보 저장 범위가 팀 결정 전이라 입력할 수 없습니다.`,
    tabNote:
      "가정상황 · 아동 특성은 서버에 저장하고 상담 일지에서 초기면접 항목으로 보입니다. " +
      `나머지 칸(관계 · 가족 · 문제력 · 태도 · 소견)은 ${NOT_READY}이라 입력할 수 없습니다.`,
    notReady: NOT_READY,
    tabs,
    isA: state.tab === "A",
    isB: state.tab === "B",
    missNote:
      state.tab === "A" && state.tried && missing.length > 0
        ? `기본 정보 필수 항목을 모두 입력해야 초기면접 내용으로 넘어갈 수 있어요 · 남은 항목: ${missing
            .map(([, label]) => label)
            .join(", ")}`
        : "",
    closeHref: back ?? "/CaseList",
    homes: intakePickers("familySituations", INTAKE_HOME_ITEMS),
    traits: intakePickers("childTraits", INTAKE_CHILD_ITEMS),
    fams: FAM.map(picker),
    famRows: [0, 1],
    midLabel: state.tab === "A" ? "초기면접 내용 →" : "← 기본 정보",
    goB: () => goTab(state.tab === "A" ? "B" : "A"),
    title: { ...field("title"), max: CASE_TITLE_MAX },
    alias: { ...field("alias"), max: CASE_ALIAS_MAX },
    caseNumber: { ...field("caseNumber"), max: CASE_NUMBER_MAX },
    gender: field("gender"),
    birthYear: { ...field("birthYear"), max: new Date().getFullYear() },
    guardianType: field("guardianType"),
    guardianOptions,
    showGuardianNote: form.guardianType === "OTHER",
    guardianNote: { ...field("guardianNote"), max: GUARDIAN_NOTE_MAX },
    notes: { ...field("notes"), max: CASE_NOTES_MAX },
    isAdmin,
    counselor: field("counselorId"),
    counselorOptions: register.counselors,
    counselorRetry: isAdmin && register.counselorsError ? register.reloadCounselors : null,
    meName: me ? me.name : "",
    counselorNote,
    submit,
    submitting,
    submitLabel: register.created ? "등록됨 · 이동 중…" : register.submitting ? "등록 중…" : "등록",
  };
}
