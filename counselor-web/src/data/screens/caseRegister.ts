// 새 사례 등록(CaseRegister · 서식 4 초기면접지 팝업) 화면 값. useCaseRegister 로 서버가 받는 칸만 저장한다.
//
// 저장하는 칸: 사례 제목 · 아동 별칭(필수), 신고접수일 · 사례연계일 · 최초면접일(2026-10-30), 개별사건번호(비우면 자동) · 성별 · 출생연도 · 보호자 유형(기타면 보호자 메모) · 사례 메모,
// ② 초기면접 내용의 아동 특성 · 가정상황(서식 4 항목 고르기), 담당 상담원(관리자만 고름, 상담원은 본인).
// 실명 · 가족 칸(2026-10-30 팀 결정 — 서버가 암호화해 저장): 대상아동 이름 · 생년월일 · 사례관리대상자(이름 · 관계 · 생년월일) ·
// 면접대상자 / 관계, ② 가족관계 표 · 건강정도. 칸 값 · 확인은 personalFields.ts · personalInfo.ts, 사례와 한 요청(personal_info)으로 보낸다.
// 생년월일을 넣으면 출생연도 칸은 그 해를 읽기 전용으로 보인다(서버도 생년월일의 해로 맞춘다).
// 등록되면 새 사례의 상세(?case=새 ID)로 간다. 초기면접 아동 특성 · 가정상황은 사례 상세(caseDetail.ts, 등록 뒤 고치기도 여기서)와
// 상담 일지(noteWrite.ts)에 단어로 보인다.
// 서식 4 고르기 · 글 칸(2026-11-05, '준비 중' 칸 열기 — caseFormFields.ts): ① 조치결과 · 피해아동 / 사례관리대상자 · 위험도(우선) ·
// 사례연계 경위, ② 가족유형(하나) · 보호자와 아동과의 관계 · 문제력(현 상황 · 이유 인식) · 대상자 태도 · 물리적 환경 · 상담원 소견.
// 모두 비워도 등록된다(서버 선택 칸). 상담원이 고르고 적는 칸이라 미리 골라 두지 않는다(디자인의 기본값 '원가정보호' · '지속관찰' 은
// 옮기지 않았다 — 고르지 않은 칸이 고른 것처럼 저장되지 않게). 글 칸은 평문 저장이라 개인정보를 적지 말라고 안내한다.
// 사례관리대상자는 보호자와 같은 뜻이 아니어서 보호자 유형으로 채우지 않는다. 한 칸의 내용을 다른 칸에 옮겨 담지 않는다.

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
import { emptyPersonalInput, type PersonalInput } from "../personalInfo";
import { NOT_READY, notice, screenNotice } from "./common";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS } from "./intakeItems";
import { intakeChoices, singleChoices, toggleItem } from "./intakePick";
import { screenHref } from "./links";
import { personalFieldValues } from "./personalFields";
import { caseChoiceOptions, caseTextValues } from "../caseFormFields";

export interface RegisterUiState {
  tab: "A" | "B";
  form: CaseRegisterInput;
  /** 서식 4 실명 · 가족 칸. 화면 상태에만 두고 브라우저 저장소에 넣지 않는다. */
  personal: PersonalInput;
  /** ② 탭으로 넘어가려다 필수 칸이 비어 막혔는가(그때부터 빈 필수 칸을 표시한다 — 10/21 디자인). */
  tried: boolean;
}

export function initialRegisterState(): RegisterUiState {
  return { tab: "A", form: { ...EMPTY_CASE_INPUT }, personal: emptyPersonalInput(), tried: false };
}

/** ① 기본 정보의 필수 칸. 서버가 비울 수 없게 하는 칸만 센다(디자인이 필수로 둔 조치결과 · 사례연계 경위는 서버 선택 칸이라 뺀다). */
const REQUIRED: [TextKey, string][] = [
  ["title", "사례 제목"],
  ["alias", "아동 별칭"],
];

/** 빈 필수 칸 테두리(디자인 값). */
const INVALID_BORDER = "#A33B2E";

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
    const created = await register.submit(form, state.personal);
    if (created) go(screenHref("/CaseDetail", { caseId: created.id }));
  };

  return {
    notice: screenNotice({ session }),
    formError: register.error ? notice(register.error, { alert: true }) : null,
    savedNote:
      "실명 · 생년월일 · 사례관리대상자 · 면접대상자 · 가족관계 · 건강정도는 암호화해 저장하고 담당 상담원 · 관리자만 봅니다. " +
      "사례연계 경위 · 사례 메모 등 글 칸은 암호화하지 않으니 실명 · 연락처 · 주소를 적지 마세요. " +
      "조치결과 · 위험도는 상담원이 고르는 칸입니다(AI 가 고르지 않습니다).",
    tabNote:
      "가정상황 · 아동 특성은 상담 일지에서 초기면접 항목으로 보입니다. 가족관계 · 건강정도는 암호화해 저장합니다. " +
      "보호자와 아동과의 관계 · 문제력 · 태도 · 환경 · 소견 글은 암호화하지 않으니 실명 · 연락처 · 주소를 적지 마세요.",
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
    // ② 가족유형(하나만, 2026-11-05). 같은 단추를 다시 누르면 뺀다.
    fams: singleChoices(caseChoiceOptions("familyType"), form.familyType, submitting, (value) =>
      setState((current) => ({ form: { ...current.form, familyType: value } })),
    ),
    midLabel: state.tab === "A" ? "초기면접 내용 →" : "← 기본 정보",
    goB: () => goTab(state.tab === "A" ? "B" : "A"),
    title: { ...field("title"), max: CASE_TITLE_MAX },
    alias: { ...field("alias"), max: CASE_ALIAS_MAX },
    caseNumber: { ...field("caseNumber"), max: CASE_NUMBER_MAX },
    gender: field("gender"),
    // 생년월일을 넣으면 출생연도는 그 해로 정해진다(읽기 전용).
    birthYear: state.personal.childBirthDate
      ? { ...field("birthYear"), value: state.personal.childBirthDate.slice(0, 4), readOnly: true, max: new Date().getFullYear() }
      : { ...field("birthYear"), readOnly: false, max: new Date().getFullYear() },
    ...personalFieldValues(
      state.personal,
      (next) => setState((current) => ({ personal: next(current.personal) })),
      submitting,
    ),
    guardianType: field("guardianType"),
    guardianOptions,
    showGuardianNote: form.guardianType === "OTHER",
    guardianNote: { ...field("guardianNote"), max: GUARDIAN_NOTE_MAX },
    notes: { ...field("notes"), max: CASE_NOTES_MAX },
    // 서식 4 ① 날짜 셋(2026-10-30 저장 연결).
    reportDate: field("reportDate"),
    linkedDate: field("linkedDate"),
    firstInterviewDate: field("firstInterviewDate"),
    // 서식 4 고르기 · 글 칸(2026-11-05). 고르기는 '선택'(빈 값)이 처음 값이다.
    childAction: { ...field("childAction"), options: caseChoiceOptions("childAction") },
    targetAction: { ...field("targetAction"), options: caseChoiceOptions("targetAction") },
    riskLevel: { ...field("riskLevel"), options: caseChoiceOptions("riskLevel") },
    ...caseTextValues(field),
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
