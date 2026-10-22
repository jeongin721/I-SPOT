// 사례 상세 · 초기면접지(CaseIntake · 문서함에서 여는 서식 4) 화면 값. 머리 · 탭은 caseHeaderValues, 저장은 useCaseDetail.saveCase.
//
// 10/22 디자인(counselor-design/screens/CaseIntake.dc.html): 문서함의 '초기면접지 (아동용)' 를 열면 팝업 대신 사례 상세 안에서
// 새 사례 등록과 같은 서식이 사례 값으로 채워져 열린다.
// 고칠 수 있는 칸은 사례에 저장된 칸뿐이다(사례 제목 · 아동 별칭 · 성별 · 출생연도 · 보호자 유형(기타면 관계 메모) · 사례 메모,
// ② 가정상황 · 아동 특성, 담당 상담원은 관리자만). 바꾼 칸만 보낸다(useCaseIntake 의 toCaseUpdateRequest).
// 개별사건번호는 수정 요청이 받지 않아 읽기만 한다.
// 나머지 서식 4 칸은 새 사례 등록(caseRegister.ts)과 같이 개인정보 저장 범위가 팀 결정 전이라 입력을 막고 '준비 중' 으로 둔다:
//  - 실명 · 생년월일(출생연도만 저장) · 사례관리대상자 · 신고접수일 · 사례연계일 · 최초면접일 · 조치결과 · 면접대상자 · 위험도 · 사례연계 경위
//  - ② 탭의 나머지(보호자와 아동과의 관계 · 가족유형 · 가족관계 · 문제력 · 태도 · 소견)
// 이 칸들의 내용을 사례 메모 등 다른 칸에 옮겨 담지 않고, AI 가 미리 고르거나 채우지 않는다.
// 디자인의 '임시 저장' · '확정' 은 서식의 작성 기록 · 확정 상태가 서버에 없어(문서함 기관 서식 줄과 같은 까닭) '저장' 하나로 둔다.
// 날짜 달력 · '기타' 직접 입력은 그 칸이 준비 중이거나 서버가 자유 글을 받지 않아 옮기지 않았다(새 사례 등록과 같음).
//
// 고친 칸은 처음 고칠 때의 대상 표(detail.capture())와 함께 두고, 표가 지금 대상일 때만 쓴다(다른 사례로 옮기거나 다시 로그인하면
// 고치던 것을 버린다 — 사례 상세 초기면접 수정과 같은 기준). 고치지 않은 칸은 늘 지금 서버 값을 보인다.

import { GUARDIAN_LABELS, type GuardianType } from "../../api/types";
import type { AuthSession } from "../useAuthSession";
import type { CaseDetailState } from "../useCaseDetail";
import {
  intakeFormOf,
  toCaseUpdateRequest,
  type IntakeCounselors,
  type IntakeField,
  type IntakeForm,
} from "../useCaseIntake";
import { CASE_ALIAS_MAX, CASE_NOTES_MAX, CASE_TITLE_MAX, GUARDIAN_NOTE_MAX } from "../useCaseRegister";
import type { RemoteTicket } from "../useRemote";
import { caseHeaderValues } from "./caseDetail";
import { NOT_READY, notice } from "./common";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS } from "./intakeItems";
import { intakeChoices, toggleItem } from "./intakePick";
import { screenHref } from "./links";

/** 가족유형 단추(준비 중이라 고를 수 없다). 이름은 새 사례 등록과 같은 서식 항목이다. */
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

/** 성별 고르기. 서버에 다른 글자가 적혀 있으면 그 값도 고를 수 있게 붙인다(지어내지 않고 그대로 보인다). */
const GENDERS = ["여", "남"];

/** 빈 필수 칸 테두리(디자인 값). */
const INVALID_BORDER = "#A33B2E";

type ListField = "childTraits" | "familySituations";
type TextField = Exclude<IntakeField, ListField>;

/** ① 기본 정보의 필수 칸. 서버가 비울 수 없게 하는 칸만 센다(준비 중 칸은 입력할 수 없어 뺀다). */
const REQUIRED: [TextField, string][] = [
  ["title", "사례 제목"],
  ["alias", "아동 별칭"],
];

/** 고를 수 없는(준비 중) 선택 단추. 모양은 고르지 않은 단추다. */
const picker = (label: string) => ({ label, bg: "#FFFFFF", bd: "#DAD5C9", fg: "#2B2A26", fw: 400, mark: "+" });

/** 화면 상태(Logic.state). */
export interface CaseIntakeUiState {
  tab: "A" | "B";
  /** 고친 칸만 든다. 고치지 않은 칸은 서버 값을 그대로 보인다. */
  edits: Partial<IntakeForm>;
  /** 처음 고칠 때의 대상 표. 지금 대상이 아니면 edits 를 쓰지 않는다. */
  editsFor: RemoteTicket | null;
  /** ② 탭으로 넘어가려다 필수 칸이 비어 막혔는가(그때부터 빈 필수 칸을 표시한다 — 디자인). */
  tried: boolean;
  /** '저장' 을 눌렀을 때 입력 확인에서 걸린 문구. 다시 고치면 지운다. */
  problem: string | null;
  /** 마지막으로 저장이 반영된 대상 표('저장했습니다' 안내를 그 대상에서만 보인다). */
  savedFor: RemoteTicket | null;
}

export const INITIAL_CASE_INTAKE_STATE: CaseIntakeUiState = {
  tab: "A",
  edits: {},
  editsFor: null,
  tried: false,
  problem: null,
  savedFor: null,
};

interface CaseIntakeInput {
  session: AuthSession;
  detail: CaseDetailState;
  counselors: IntakeCounselors;
  caseId: string | null;
  state: CaseIntakeUiState;
  setState: (patch: Partial<CaseIntakeUiState> | ((current: CaseIntakeUiState) => Partial<CaseIntakeUiState>)) => void;
}

export function caseIntakeValues(input: CaseIntakeInput) {
  const { session, detail, counselors, caseId, state, setState } = input;
  const header = caseHeaderValues(input);
  const info = detail.caseInfo;
  const isAdmin = session.isAdmin;
  const saving = detail.savingCase;
  const edits = detail.isCurrent(state.editsFor) ? state.edits : {};
  const saved = info ? intakeFormOf(info) : null;
  const form: IntakeForm | null = saved ? { ...saved, ...edits } : null;
  const checked = saved ? toCaseUpdateRequest(edits, saved, { isAdmin }) : { payload: null, problem: null };
  // 저장하지 않은 수정: 보낼 칸이 있거나, 고친 칸이 입력 확인에 걸린다(예: 사례 제목을 비움).
  const dirty = checked.payload !== null || checked.problem !== null;
  const missing = form ? REQUIRED.filter(([name]) => !form[name].trim()) : [];

  /**
   * 칸 하나를 고친다. next 는 그 칸의 지금 값(고친 값, 없으면 서버 값)을 받아 새 값을 준다.
   * 저장 중이거나 사례 정보가 없으면 무시한다. 대상이 바뀐 뒤의 첫 수정은 새 대상의 표로 다시 시작한다.
   */
  const edit = <K extends IntakeField>(name: K, next: (value: IntakeForm[K]) => IntakeForm[K]) =>
    setState((current) => {
      const now = detail.caseInfo;

      if (detail.savingCase || !now) return {};

      const keep = detail.isCurrent(current.editsFor);
      const ticket = keep ? current.editsFor : detail.capture();

      if (!ticket) return {};

      const edits: Partial<IntakeForm> = keep ? { ...current.edits } : {};
      const before = edits[name];
      edits[name] = next(before !== undefined ? (before as IntakeForm[K]) : intakeFormOf(now)[name]);

      return { edits, editsFor: ticket, problem: null, savedFor: null };
    });

  /** 입력칸 하나의 값과 바꾸는 함수. 필수 칸이 비었는데 ② 탭으로 넘어가려 했으면 invalid 다. */
  const field = (name: TextField) => {
    const invalid = state.tried && missing.some(([key]) => key === name);

    return {
      value: form ? form[name] : "",
      onChange: (event: { target: { value: string } }) => {
        const value = event.target.value;
        edit(name, () => value);
      },
      invalid: invalid ? "true" : "false",
      border: invalid ? INVALID_BORDER : undefined,
    };
  };

  /** 탭 옮기기. ② 탭은 필수 칸을 다 채워야 열린다(디자인 · 새 사례 등록과 같음). */
  const goTab = (key: CaseIntakeUiState["tab"]) => {
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

  /** 초기면접 아동 특성 · 가정상황 고르기 단추(새 사례 등록 · 사례 상세와 같은 모양). 저장 중에는 잠근다. */
  const intakePickers = (key: ListField, options: string[]) =>
    form ? intakeChoices(options, form[key], saving, (label) => edit(key, (list) => toggleItem(list, label))) : [];

  const guardianOptions = (Object.keys(GUARDIAN_LABELS) as GuardianType[]).map((type) => ({
    value: type,
    label: GUARDIAN_LABELS[type],
  }));

  const genderValue = form ? form.gender : "";
  const genderOptions = [...GENDERS];
  if (saved && saved.gender && !genderOptions.includes(saved.gender)) genderOptions.push(saved.gender);
  if (genderValue && !genderOptions.includes(genderValue)) genderOptions.push(genderValue);

  // 담당 상담원: 관리자는 활성 계정에서 고른다. 지금 담당자가 목록에 없으면(정지된 계정 · 목록을 못 받음) 그대로 붙인다.
  const counselorOptions = isAdmin ? [...counselors.options] : [];
  if (isAdmin && info && !counselorOptions.some((option) => option.id === info.counselorId)) {
    counselorOptions.unshift({ id: info.counselorId, label: `${info.counselorName} (지금 담당)` });
  }
  let counselorNote = "";
  if (isAdmin && counselors.loading) counselorNote = "담당 상담원 목록을 불러오는 중…";
  else if (isAdmin && counselors.error) counselorNote = counselors.error;
  else if (!isAdmin) counselorNote = "담당 상담원은 관리자만 바꿀 수 있습니다.";

  const save = async (event?: { preventDefault?: () => void }) => {
    if (event && event.preventDefault) event.preventDefault();
    if (!info || saving) return;
    if (checked.problem !== null) {
      setState({ problem: checked.problem });
      return;
    }
    if (checked.payload === null) return;

    const sent = state.edits;
    const sentFor = state.editsFor;
    const ok = await detail.saveCase(checked.payload);

    // 반영됐으면 고친 칸을 비운다(서버 값이 그 값이 됐다). 그사이 대상이 바뀌었으면 위 표 확인이 이미 고친 칸을 버린다.
    if (ok) {
      setState((current) =>
        current.edits === sent ? { edits: {}, editsFor: null, problem: null, savedFor: sentFor } : {},
      );
    }
  };

  const problem = detail.isCurrent(state.editsFor) && state.problem ? state.problem : null;
  const savedOk = !dirty && detail.isCurrent(state.savedFor);

  return {
    ...header,
    ready: info !== null,
    headNote: info ? `서식 4 · 사례 등록 ${info.createdDate}` : "서식 4",
    savedNote:
      "사례에 저장하는 칸: 사례 제목 · 아동 별칭 · 성별 · 출생연도 · 보호자 유형 · 사례 메모 · 담당 상담원(관리자), " +
      "② 초기면접 내용의 가정상황 · 아동 특성. 바꾼 칸만 저장합니다. 개별사건번호는 바꿀 수 없습니다. " +
      `'${NOT_READY}' 칸은 개인정보 저장 범위가 팀 결정 전이라 입력할 수 없습니다.`,
    tabNote:
      "가정상황 · 아동 특성은 사례에 저장되고 상담 일지에서 초기면접 항목으로 보입니다. " +
      `나머지 칸(관계 · 가족 · 문제력 · 태도 · 소견)은 ${NOT_READY}이라 입력할 수 없습니다.`,
    notReady: NOT_READY,
    formTabs: tabs,
    isA: state.tab === "A",
    isB: state.tab === "B",
    missNote:
      state.tab === "A" && state.tried && missing.length > 0
        ? `기본 정보 필수 항목을 모두 입력해야 초기면접 내용으로 넘어갈 수 있어요 · 남은 항목: ${missing
            .map(([, label]) => label)
            .join(", ")}`
        : "",
    midLabel: state.tab === "A" ? "초기면접 내용 →" : "← 기본 정보",
    goB: () => goTab(state.tab === "A" ? "B" : "A"),
    // 저장 중 · 사례 정보를 받기 전에는 고칠 수 없다.
    locked: saving || info === null,
    // 머리의 title(아동 별칭 제목)과 겹치지 않게 사례 제목 칸은 caseTitle 로 준다.
    caseTitle: { ...field("title"), max: CASE_TITLE_MAX },
    alias: { ...field("alias"), max: CASE_ALIAS_MAX },
    caseNumber: info ? info.caseNumber : "",
    gender: field("gender"),
    genderOptions,
    birthYear: { ...field("birthYear"), max: new Date().getFullYear() },
    guardianType: field("guardianType"),
    guardianOptions,
    showGuardianNote: form !== null && form.guardianType === "OTHER",
    guardianNote: { ...field("guardianNote"), max: GUARDIAN_NOTE_MAX },
    notes: { ...field("notes"), max: CASE_NOTES_MAX },
    isAdmin,
    counselor: field("counselorId"),
    counselorOptions,
    counselorName: info ? info.counselorName : "",
    counselorNote,
    counselorRetry: isAdmin && counselors.error ? counselors.reload : null,
    homes: intakePickers("familySituations", INTAKE_HOME_ITEMS),
    traits: intakePickers("childTraits", INTAKE_CHILD_ITEMS),
    fams: FAM.map(picker),
    famRows: [0, 1],
    formError: problem
      ? notice(problem, { alert: true })
      : detail.caseError
        ? notice(detail.caseError, { alert: true })
        : null,
    statusNote: savedOk ? "저장했습니다." : dirty ? "저장하지 않은 수정이 있습니다." : "",
    save,
    saving,
    canSave: info !== null && dirty && !saving,
    saveLabel: saving ? "저장 중…" : "저장",
    canReset: dirty && !saving,
    // 고친 칸을 버리고 서버 값으로 되돌린다.
    reset: () => {
      if (!detail.savingCase) setState({ edits: {}, editsFor: null, problem: null, tried: false });
    },
    /** 저장하지 않은 수정이 있는가(useLeaveGuard 에 넘긴다). */
    unsaved: dirty,
    backHref: screenHref("/CaseDocs", { caseId }),
  };
}
