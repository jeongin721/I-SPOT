// 사례 상세 탭 1(CaseDetail · 내담자 정보)과 탭 2(CaseHistory · 상담 이력) 화면 값. 둘 다 useCaseDetail 하나로 그린다.
//
// Backend 에 없는 값은 지어내지 않고 '—' 또는 준비 중으로 둔다(specs 대응표 '팀 결정 — 사례 · 개인정보 / AI 신호 · 검수').
//  - 실명 · 생년월일(출생연도만 있음) · 사례관리대상자 · 가족유형 · 신고접수일 · 사례연계일 · 아이 앱 · 다음 상담 일정
//  - 위험도 · 학대 유형 · 주요 키워드 · 사정결과, 서비스 이행, 기관 서식 진행, 종결 검토 등록
//  - 상담 유형(정기 · 방문), 회차별 신호 채택 · 보류 수, 누적 AI 요약 · 주제 비중 · 회차별 세부 신호
// 사례관리대상자는 보호자와 같은 뜻이 아니어서 보호자 유형(guardian_type)으로 채우지 않는다.
//
// 탭 1 의 '초기면접 내용' 카드는 디자인에 없는 칸이다(2026-10-20 추가). 사례 등록 ② 탭에서 고른 가정상황 · 아동 특성
// (서식 4 항목 이름)을 단어로 보이고, '수정' 을 누르면 사례 등록과 같은 고르기 단추로 고쳐 저장한다(PATCH /cases/{id}).
// 고친 항목은 상담 일지(noteWrite.ts)의 초기면접 항목에 그대로 보인다. ② 탭의 나머지 칸은 여전히 준비 중이라 여기에도 없다.

import { NOT_PROVIDED } from "../caseRows";
import type { CaseDetailState } from "../useCaseDetail";
import type { AuthSession } from "../useAuthSession";
import type { RemoteTicket } from "../useRemote";
import { NOT_READY, TONE_CHIP, notice, screenNotice, sidebarValues } from "./common";
import { COLUMN_OF, PROCESS_COLUMNS, continueLink } from "./flow";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS } from "./intakeItems";
import { intakeChoices, toggleItem } from "./intakePick";
import { screenHref } from "./links";

interface CaseScreenInput {
  session: AuthSession;
  detail: CaseDetailState;
  caseId: string | null;
}

/** 주소에 사례 ID 가 없을 때 안내. */
export const MISSING_CASE = notice("사례가 정해지지 않았습니다. 사례 관리에서 사례를 골라 주세요.", {
  href: "/CaseList",
  hrefLabel: "사례 관리로",
});

/** 사례 상세 탭 공통: 위치 표시 · 머리 · 탭 링크 · 녹취 올리기 링크. */
export function caseHeaderValues({ session, detail, caseId }: CaseScreenInput) {
  const info = detail.caseInfo;
  const ids = { caseId };

  return {
    ...sidebarValues(session),
    notice: screenNotice({
      session,
      missing: caseId ? null : MISSING_CASE,
      loading: detail.loading,
      error: detail.error,
      retry: detail.reload,
    }),
    crumb: info ? `${info.alias} ${info.caseNumber}` : "",
    title: info ? info.alias : "",
    sub: info ? info.birthYearLabel : "",
    riskChip: `위험도 ${NOT_PROVIDED}`,
    meta: info ? `${info.caseNumber} · 다음 상담 ${NOT_PROVIDED}` : "",
    uploadHref: screenHref("/UploadModal", ids),
    tabs: {
      detail: screenHref("/CaseDetail", ids),
      history: screenHref("/CaseHistory", ids),
      briefing: screenHref("/PreBriefing", ids),
      app: screenHref("/CaseApp", ids),
      docs: screenHref("/CaseDocs", ids),
    },
  };
}

const DOT_DONE = { background: "#F2EFE8", color: "#66625A" };
const DOT_CURRENT = { background: "#FFFFFF", border: "2px solid #2B2A26", color: "#2B2A26" };
const DOT_PENDING = { background: "#EAE7DF", color: "#7A776F" };

interface IntakeDraft {
  familySituations: string[];
  childTraits: string[];
}

/**
 * 탭 1 화면 상태(Logic.state). 고치는 초기면접 항목은 '수정' 을 누를 때의 대상 표(detail.capture())와 함께 두고,
 * 표가 지금 대상일 때만 쓴다(다른 사례로 옮기거나 다시 로그인하면 고치던 것을 버린다 — 일지 화면의 고친 일지와 같은 기준).
 */
export interface CaseDetailUiState {
  /** 고치는 중인 초기면접 항목. null 이면 보기만 한다. */
  intakeDraft: IntakeDraft | null;
  intakeFor: RemoteTicket | null;
}

export const INITIAL_CASE_DETAIL_STATE: CaseDetailUiState = { intakeDraft: null, intakeFor: null };

interface CaseDetailInput extends CaseScreenInput {
  state: CaseDetailUiState;
  setState: (patch: Partial<CaseDetailUiState> | ((current: CaseDetailUiState) => Partial<CaseDetailUiState>)) => void;
}

/** 순서는 보지 않고 같은 항목인가(뺐다가 다시 고른 항목은 뒤로 가지만 고친 것으로 보지 않는다). */
function sameItems(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((item) => b.includes(item));
}

/** 탭 1 '초기면접 내용' 카드. 보기(단어) · 고치기(고르기 단추) · 저장 · 취소. */
function intakeValues({ detail, state, setState }: CaseDetailInput) {
  const info = detail.caseInfo;
  const draft = state.intakeDraft && detail.isCurrent(state.intakeFor) ? state.intakeDraft : null;
  const saving = detail.savingIntake;
  const dirty =
    draft !== null &&
    info !== null &&
    !(sameItems(draft.familySituations, info.intakeFamilySituations) && sameItems(draft.childTraits, info.intakeChildTraits));

  // 서식 4 ② 순서(가정상황 → 아동 특성). 일지는 칸 순서대로 아동 특성이 먼저다.
  const rows = info
    ? [
        { label: "가정상황", words: info.intakeFamilySituations },
        { label: "아동 특성", words: info.intakeChildTraits },
      ].map(({ label, words }) => ({ label, text: words.length > 0 ? words.join(", ") : "고른 항목 없음", empty: words.length === 0 }))
    : [];

  /** 고치는 목록 하나를 바꾼다. 대상이 바뀐 뒤의 누름은 버린다. */
  const toggle = (key: keyof IntakeDraft) => (label: string) =>
    setState((current) =>
      current.intakeDraft && detail.isCurrent(current.intakeFor)
        ? { intakeDraft: { ...current.intakeDraft, [key]: toggleItem(current.intakeDraft[key], label) } }
        : {},
    );

  const close = () => setState({ intakeDraft: null, intakeFor: null });

  return {
    rows,
    editing: draft !== null,
    canEdit: info !== null && draft === null,
    startEdit: () => {
      const ticket = detail.capture();

      if (!ticket || !info) return;
      setState({
        intakeDraft: { familySituations: [...info.intakeFamilySituations], childTraits: [...info.intakeChildTraits] },
        intakeFor: ticket,
      });
    },
    homes: draft ? intakeChoices(INTAKE_HOME_ITEMS, draft.familySituations, saving, toggle("familySituations")) : [],
    traits: draft ? intakeChoices(INTAKE_CHILD_ITEMS, draft.childTraits, saving, toggle("childTraits")) : [],
    editNote: "서식 4 ② 의 항목에서 고릅니다. 저장하면 이 사례의 상담 일지에 초기면접 항목으로 보입니다.",
    // 고치는 동안에만 보인다(취소하고 닫으면 앞 실패 문구를 남기지 않는다).
    error: draft && detail.intakeError ? notice(detail.intakeError, { alert: true }) : null,
    saveLabel: saving ? "저장 중…" : "저장",
    saving,
    cancel: () => {
      if (!saving) close();
    },
    // 바꾼 것이 없으면 보내지 않고 닫는다.
    save: async () => {
      if (!draft || saving) return;
      if (!dirty) {
        close();
        return;
      }

      const sent = draft;
      const saved = await detail.saveIntake({ childTraits: sent.childTraits, familySituations: sent.familySituations });

      if (saved) setState((current) => (current.intakeDraft === sent ? { intakeDraft: null, intakeFor: null } : {}));
    },
    /** 저장하지 않은 수정이 있는가(useLeaveGuard 에 넘긴다). */
    unsaved: dirty,
  };
}

/** 탭 1 · 내담자 정보. */
export function caseDetailValues(input: CaseDetailInput) {
  const { detail } = input;
  const info = detail.caseInfo;
  const latest = detail.sessions[0] ?? null;
  const dash = NOT_PROVIDED;
  // 최근 상담일은 회차의 상담 일시(consulted_at)로만 센다. 사례의 last_session_at 은 상담일이 없으면
  // 회차 등록일로 채워지므로(backend case_service._last_session_at_subquery) 쓰지 않는다.
  const consulted = detail.sessions.map((row) => row.consultedDate).filter((date) => date !== NOT_PROVIDED);
  const lastConsulted = consulted.length > 0 ? [...consulted].sort().reverse()[0] : dash;

  const basics: { label: string; value: string; strong?: boolean }[] = info
    ? [
        { label: "개별사건번호", value: info.caseNumber },
        { label: "이름", value: `${info.alias} (${info.genderLabel})` },
        { label: "생년월일", value: info.birthYearLabel },
        { label: "사례관리대상자", value: dash },
        { label: "가족유형", value: dash },
        { label: "담당 상담원", value: info.counselorName },
        { label: "신고접수일", value: dash },
        { label: "사례연계일", value: dash },
        { label: "상담 회차", value: `${info.sessionCount}회`, strong: true },
        { label: "최근 상담", value: lastConsulted },
        { label: "아이 앱", value: dash },
      ]
    : [];

  // 현재 진행 상황: 가장 최근 회차가 어느 칸에 있는가.
  const column = latest ? COLUMN_OF[latest.step] : -1;
  const progress = PROCESS_COLUMNS.map((label, index) => {
    const done = latest !== null && index < column;
    const current = latest !== null && index === column && index < PROCESS_COLUMNS.length - 1;
    // '추가 확인 · 질문' 칸은 Backend 에 없어 늘 준비 중이다.
    const last = index === PROCESS_COLUMNS.length - 1;

    return {
      label,
      // 원래 화면처럼 '녹취 올림' 칸은 번호 없이, 나머지는 1 · 2 · 3 · 4.
      mark: done ? "✓" : index === 0 ? "↑" : String(index),
      dot: done ? DOT_DONE : current ? DOT_CURRENT : DOT_PENDING,
      done,
      current,
      pending: !done && !current,
      chip: current && latest ? latest.statusLabel : last ? NOT_READY : "",
    };
  });

  const next = latest ? continueLink(latest) : null;

  const intake = intakeValues(input);

  return {
    ...caseHeaderValues(input),
    basics,
    intake,
    unsaved: intake.unsaved,
    riskBy: dash,
    abuseTypes: [dash],
    keywords: [dash],
    assessment: dash,
    latestLabel: latest ? `${latest.numberLabel} · ${latest.statusLabel}` : info ? "회차 없음" : "",
    continueHref: next ? next.href : screenHref("/UploadModal", { caseId: input.caseId }),
    continueLabel: next ? next.label : "녹취 올려 시작하기",
    progress,
    services: [{ label: "서비스 계획 · 이행", value: dash }],
    nextSchedule: dash,
    briefingHref: screenHref("/PreBriefing", { caseId: input.caseId }),
    formsChip: NOT_READY,
    formsHref: screenHref("/CaseForm", { caseId: input.caseId }),
    notReady: NOT_READY,
  };
}

/**
 * 탭 2 · 상담 이력. 누적 요약 · 주제 비중 · 세부 신호는 Backend 에 없어 빈 목록과 준비 중 안내를 준다.
 * 회차 카드는 최근 3회차(recent)를 보이고, '전 회차 보기' 창(all)에는 불러온 회차를 모두 보인다.
 * 창이 열렸는지는 화면이 들고 있다가 historyOpen · setHistoryOpen 으로 넘긴다.
 */
export function caseHistoryValues(
  input: CaseScreenInput & { historyOpen?: boolean; setHistoryOpen?: (open: boolean) => void },
) {
  const { detail } = input;
  const open = Boolean(input.historyOpen);
  const dash = NOT_PROVIDED;

  const sessions = detail.sessions.map((row) => ({
    no: row.numberLabel,
    // 상담 일시를 넣지 않은 회차는 등록일을 '등록' 이라고 밝혀 보여 준다(상담일로 대신하지 않는다).
    date: row.consultedDate !== NOT_PROVIDED ? row.consultedDate : `${row.createdDate} 등록`,
    kind: `상담 유형 ${dash}`,
    kindShort: dash,
    status: row.statusLabel,
    st: TONE_CHIP[row.tone],
    sig: `신호 ${dash}`,
    href: screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.id }),
  }));

  // 세부 신호 행렬의 열(회차). 오래된 회차부터.
  const cols = [...detail.sessions].reverse().map((row) => ({
    label: `${row.sessionNumber}회`,
    href: screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.id }),
  }));

  let sessionsNote = "";
  if (detail.caseInfo && sessions.length === 0) sessionsNote = "회차가 없습니다. 녹취를 올리면 회차가 생깁니다.";
  else if (detail.sessionTotal !== null && detail.sessionTotal > sessions.length) {
    sessionsNote = `최근 ${sessions.length}회차만 보입니다(전체 ${detail.sessionTotal}회차).`;
  }

  return {
    ...caseHeaderValues(input),
    overviewChip: `AI 분석 · ${NOT_READY}`,
    overviewNote: `지금까지 상담의 누적 요약 · 주제 비중은 ${NOT_READY}입니다(서버에 아직 없는 기능).`,
    periods: [] as { range: string; title: string; note: string }[],
    topics: [] as { label: string; width: string; pct: string }[],
    insights: [] as { title: string; text: string; src: string }[],
    sessions,
    recent: sessions.slice(0, 3),
    all: sessions,
    total: detail.sessionTotal ?? sessions.length,
    shownCount: `${sessions.length}개`,
    open,
    toggleOpen: () => input.setHistoryOpen?.(!open),
    notReady: NOT_READY,
    sessionsNote,
    cols,
    mrows: [] as { type: string; name: string; cells: { v: string; tip: string; bg: string; fg: string; ring: string }[] }[],
    signalNote: `회차별 세부 신호는 ${NOT_READY}입니다(AI 위험 신호를 서버가 아직 주지 않음).`,
  };
}
