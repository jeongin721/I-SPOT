// 새 사례 등록(CaseRegister · 서식 4 초기면접지 팝업) 화면 값. useCaseRegister 로 서버가 받는 칸만 저장한다.
//
// 저장하는 칸: 사례 제목 · 아동 별칭(필수), 개별사건번호(비우면 자동) · 성별 · 출생연도 · 보호자 유형(기타면 보호자 메모) · 사례 메모,
// 담당 상담원(관리자만 고름, 상담원은 본인). 등록되면 새 사례의 상세(?case=새 ID)로 간다.
// 나머지 서식 4 칸은 개인정보 저장 범위가 팀 결정 전이라(specs 대응표 CaseRegister 줄) 입력을 막고 '준비 중' 으로 둔다:
//  - 실명 · 생년월일(출생연도만 저장) · 사례관리대상자(보호자와 같은 뜻이 아니어서 보호자 유형으로 채우지 않는다)
//  - 신고접수일 · 사례연계일 · 최초면접일 · 학대유형 · 조치결과 · 면접대상자 · 위험도 · 사례연계 경위
//  - ② 초기면접 내용 탭 전체(가정상황 · 가족유형 · 가족관계 · 아동 특성 · 문제력 · 태도 · 소견)
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
import { screenHref } from "./links";

const TY = ["방임", "신체학대", "정서학대", "성학대"];
const HM = [
  "성격 및 기질 문제",
  "어릴적 학대경험",
  "알콜남용",
  "약물남용",
  "신체질환 및 장애",
  "정신질환 및 장애",
  "원치않은 아동",
  "부적절한 양육태도",
  "양육지식 및 기술부족",
  "부부 및 가족갈등",
  "성문제",
  "스트레스",
  "사회적 고립",
  "경제적 어려움",
  "배우자폭력",
  "존속학대",
  "전과력",
  "종교문제",
  "도박 · 게임중독",
  "특성없음",
  "기타",
];
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
const TR = [
  "거짓말",
  "반항 · 충동 · 공격성",
  "도벽",
  "가출",
  "약물",
  "흡연",
  "음주",
  "인터넷(게임)중독",
  "성문제",
  "주의산만",
  "과잉행동",
  "늦은귀가",
  "불건전한 또래관계",
  "대인관계 기피",
  "학교부적응",
  "잦은결석",
  "학교폭력 가해자",
  "학교폭력 피해자",
  "불안",
  "애착문제",
  "무력감",
  "우울",
  "낮은자존감",
  "신체발달지연",
  "언어문제",
  "학습문제",
  "대소변문제",
  "성격 및 기질문제",
  "위생문제",
  "틱",
  "급(만)성질병",
  "영양결핍",
  "탐식 및 결식",
  "특성없음",
  "기타",
];

export interface RegisterUiState {
  tab: "A" | "B";
  form: CaseRegisterInput;
}

export function initialRegisterState(): RegisterUiState {
  return { tab: "A", form: { ...EMPTY_CASE_INPUT } };
}

/** 고를 수 없는(준비 중) 선택 단추. 모양은 고르지 않은 단추다. */
const picker = (label: string) => ({ label, bg: "#FFFFFF", bd: "#DAD5C9", fg: "#2B2A26", fw: 400, mark: "+" });

interface CaseRegisterInputs {
  session: AuthSession;
  register: CaseRegisterState;
  state: RegisterUiState;
  setState: (patch: Partial<RegisterUiState> | ((current: RegisterUiState) => Partial<RegisterUiState>)) => void;
  /** 등록 뒤 새 사례 상세로 옮긴다(useScreenGo — 그사이 화면을 떠났으면 옮기지 않는다). */
  go: (href: string) => void;
}

export function caseRegisterValues({ session, register, state, setState, go }: CaseRegisterInputs) {
  const form = state.form;
  const me = session.me;
  const isAdmin = session.isAdmin;

  /** 입력칸 하나의 값과 바꾸는 함수. */
  const field = (name: keyof CaseRegisterInput) => ({
    value: form[name],
    onChange: (event: { target: { value: string } }) => {
      const value = event.target.value;
      setState((current) => ({ form: { ...current.form, [name]: value } }));
    },
  });

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
    go: () => setState({ tab: key }),
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

  const submit = async (event?: { preventDefault?: () => void }) => {
    if (event && event.preventDefault) event.preventDefault();
    const created = await register.submit(form);
    if (created) go(screenHref("/CaseDetail", { caseId: created.id }));
  };

  return {
    notice: screenNotice({ session }),
    formError: register.error ? notice(register.error, { alert: true }) : null,
    savedNote:
      "서버에 저장하는 칸: 사례 제목 · 아동 별칭 · 개별사건번호 · 성별 · 출생연도 · 보호자 유형 · 사례 메모 · 담당 상담원. " +
      `'${NOT_READY}' 칸은 개인정보 저장 범위가 팀 결정 전이라 입력할 수 없습니다.`,
    tabNote: `초기면접 내용은 ${NOT_READY}입니다. 저장 범위 · 서식 구조가 팀 결정 전이라 입력할 수 없습니다.`,
    notReady: NOT_READY,
    tabs,
    isA: state.tab === "A",
    isB: state.tab === "B",
    types: TY.map(picker),
    homes: HM.map(picker),
    traits: TR.map(picker),
    fams: FAM.map(picker),
    famRows: [0, 1],
    midLabel: state.tab === "A" ? "초기면접 내용 →" : "← 기본 정보",
    goB: () => setState({ tab: state.tab === "A" ? "B" : "A" }),
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
