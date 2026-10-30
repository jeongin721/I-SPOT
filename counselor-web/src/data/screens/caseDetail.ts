// 사례 상세 탭 1(CaseDetail · 내담자 정보)과 탭 2(CaseHistory · 상담 이력) 화면 값. 둘 다 useCaseDetail 하나로 그린다.
//
// Backend 에 없는 값은 지어내지 않고 '—' 또는 준비 중으로 둔다(specs 대응표 '팀 결정 — 사례 · 개인정보 / AI 신호 · 검수').
//  - 실명 · 생년월일(출생연도만 있음) · 사례관리대상자 · 가족유형 · 신고접수일 · 사례연계일 · 아이 앱 · 다음 상담 일정
//  - 기관 서식 진행, 종결 검토 등록
//    (10/21 디자인은 사정결과 줄과 서비스 이행 · 다음 일정 상자를 뺐다)
//  - 상담 유형(정기 · 방문), 회차별 신호 채택 · 보류 수, 누적 AI 요약(주제 비중 · 세부 신호는 2026-10-28 · 29 연결)
// 사례관리대상자는 보호자와 같은 뜻이 아니어서 보호자 유형(guardian_type)으로 채우지 않는다.
//
// 위험도 · 학대 유형 · 주요 키워드(2026-10-27): 사례에 따로 저장된 값이 없어, 분석이 끝난 가장 최근 회차(useCaseSignals)의
// 값으로 채운다 — 새 API 없음.
//  - 머리 · 카드의 '위험도': 그 회차에서 상담원이 고른 회차 전체 판단(상 · 중 · 하 하나, 2026-10-29 — useOverallRiskAssessment).
//    'AI 판단' 이 아니다. 판단이 없으면 '—'. '상담사 지정 · 일시' 는 그 판단을 저장한 일시와 회차.
//  - 학대 유형: AI 관련 신호가 있는 유형에 '(확인 중)' 을 붙인다(10/27 디자인의 '방임 (확인 중)'). 2026-10-29 부터 상담원 판단은
//    유형별이 아니라 회차 전체 하나라 유형을 확정하는 기록이 없다. AI 신호를 판정처럼 보이지 않게 한다(05_RULES §1).
//  - 주요 키워드: 그 회차 위험 관련 발화의 세부 유형 이름(예: #직접 신체 가해). 디자인의 자유 키워드(#체벌)를 만드는
//    서버 값은 없어 새로 생성하지 않는다. 키워드마다 첫 근거 위치('N회차 01:08 아동')를 붙이고 누르면 STT 검수의 그 발화로
//    간다(README 원칙 3 '모든 제안에는 근거 위치', 2026-10-28 민규 리뷰).
//  - 회차 목록은 최신 100개까지만 온다(useCaseDetail). 그 안에 분석 끝난 회차가 없는데 목록이 잘렸으면 '최근 N회차 안에'
//    라고 밝힌다(사례 단위 signal-history API 가 생기면 그쪽을 쓴다).
//  - '(확인 중)' 유형과 주요 키워드는 AI 결과라 그 줄 옆에 'AI 제안' 칩과 안내를 붙인다(README 원칙 2 — 상담원 판단인
//    '상담사 지정' 과 섞여 보이지 않게, 2026-10-28 민규 리뷰).
//
// 탭 1 의 '초기면접 내용' 카드는 디자인에 없는 칸이다(2026-10-20 추가). 사례 등록 ② 탭에서 고른 가정상황 · 아동 특성
// (서식 4 항목 이름)을 단어로 보이고, '수정' 을 누르면 사례 등록과 같은 고르기 단추로 고쳐 저장한다(PATCH /cases/{id}).
// 고친 항목은 상담 일지(noteWrite.ts)의 초기면접 항목에 그대로 보인다. ② 탭의 나머지 칸은 여전히 준비 중이라 여기에도 없다.

import { NOT_PROVIDED } from "../caseRows";
import { ABUSE_TYPES, RISK_LEVEL_LABELS, type RiskLevel } from "../../api/types";
import type { CaseDetailState } from "../useCaseDetail";
import type { CaseSignalsState } from "../useCaseSignals";
import type { SignalHistoryState } from "../useSignalHistory";
import { MAX_APPROVED, type ApprovedSummariesState } from "../useApprovedSummaries";
import { formatClock, toDateOnly } from "../time";
import {
  TREND_TYPES,
  TYPE_SHORT,
  counselorTop,
  detectedTypeLabels,
  firstMentions,
  pendingLabel,
  signalsClearlyAbsent,
  taggedSessions,
  topicShares,
  untaggedAnalyzed,
} from "../signalHistoryRows";
import type { FollowupQuestionsState } from "../useFollowupQuestions";
import type { AuthSession } from "../useAuthSession";
import type { RemoteTicket } from "../useRemote";
import { NOT_READY, TONE_CHIP, notice, screenNotice, sidebarValues } from "./common";
import { COLUMN_OF, PROCESS_COLUMNS, continueLink } from "./flow";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS } from "./intakeItems";
import { intakeChoices, toggleItem } from "./intakePick";
import { screenHref } from "./links";
import { segmentHref } from "./sttReview";
import { uploadTargets } from "./uploadModal";

interface CaseScreenInput {
  session: AuthSession;
  detail: CaseDetailState;
  caseId: string | null;
  /** 분석이 끝난 가장 최근 회차의 값(useCaseSignals). 없으면 위험도는 '—'. */
  signals?: CaseSignalsState;
  /** 가장 최근 회차(sessions[0])의 승인한 추가 질문(18절). '추가 확인 · 질문' 칸 칩에 쓴다. */
  questions?: FollowupQuestionsState;
}

/** 위험도 칩 색(10/27 디자인: 상 c-hi · 중 c-mid · 하 c-lo). 판단 전은 c-normal. */
const RISK_CHIP: Record<RiskLevel, string> = { HIGH: "c-hi", MEDIUM: "c-mid", LOW: "c-lo" };


/** 키워드 칩 최대 개수. */
const MAX_KEYWORDS = 5;

/** 주요 키워드 칩 하나. where · href 는 첫 근거 발화(없으면 빈 값 · null). */
export interface RiskKeyword {
  text: string;
  where: string;
  href: string | null;
}

/** 주요 위험 요인 카드 값. 분석이 끝난 회차가 없거나 값을 받기 전이면 '—'. */
export function riskCardValues(signals: CaseSignalsState | undefined) {
  const dash = NOT_PROVIDED;
  const none: RiskKeyword[] = [{ text: dash, where: "", href: null }];

  if (!signals || !signals.session) {
    return {
      riskBy: signals?.truncated ? `최근 ${signals.shownCount}회차 안에 분석 끝난 회차가 없습니다` : dash,
      abuseTypes: [dash],
      keywords: none,
      riskNote: "",
      typesAi: false,
      keywordsAi: false,
      aiNote: "",
    };
  }

  const { session, risk } = signals;
  // 상담원 판단은 회차 전체 하나라 유형을 확정하는 기록이 없다. AI 관련 신호가 있는 유형만 '(확인 중)' 으로 보인다(AI 제안).
  const flagged = new Set(
    signals.signals.types.filter((row) => row.state === "signal").map((row) => row.abuseType),
  );
  const abuseTypes = ABUSE_TYPES.flatMap((type) => (flagged.has(type) ? [`${TYPE_SHORT[type]} (확인 중)`] : []));

  const ids = { caseId: session.caseId, sessionId: session.id };
  const keywords: RiskKeyword[] = [];
  for (const card of signals.signals.cards) {
    const tag = card.subtype ? `#${card.subtype}` : "";
    if (!tag || keywords.some((k) => k.text === tag)) continue;
    const first = card.evidence[0] ?? null;
    keywords.push({
      text: tag,
      where: card.positionLabel ? `${session.numberLabel} ${card.positionLabel.split(" · ")[0]}` : "",
      href: first ? segmentHref(ids, first.segmentId) : null,
    });
    if (keywords.length >= MAX_KEYWORDS) break;
  }

  let riskBy = `${session.numberLabel} · 판단 전`;
  if (signals.topLevelAt) riskBy = `${signals.topLevelAt} · ${session.numberLabel}`;

  let riskNote = "";
  if (risk.loadError) riskNote = risk.loadError;
  else if (signals.analysis.error) riskNote = signals.analysis.error;

  const typesAi = abuseTypes.length > 0;
  const keywordsAi = keywords.length > 0;

  return {
    riskBy,
    abuseTypes: abuseTypes.length > 0 ? abuseTypes : [dash],
    keywords: keywords.length > 0 ? keywords : none,
    riskNote,
    typesAi,
    keywordsAi,
    aiNote: `'(확인 중)' 유형과 주요 키워드는 ${session.numberLabel} AI 분석 결과입니다. 판정이 아니며, 위험도(회차 전체 상 · 중 · 하) · 상담사 지정은 상담원 판단입니다.`,
  };
}

/** 주소에 사례 ID 가 없을 때 안내. */
export const MISSING_CASE = notice("사례가 정해지지 않았습니다. 사례 관리에서 사례를 골라 주세요.", {
  href: "/CaseList",
  hrefLabel: "사례 관리로",
});

/** 사례 상세 '현재 진행 상황' 칸(PROCESS_COLUMNS 순서)마다 가는 화면. 0(녹취 올림)은 따로 정한다. */
const STEP_PAGES = ["/UploadModal", "/SttReview", "/SignalReview", "/NoteWrite", "/FollowupQ"];

/** 사례 상세 탭 공통: 위치 표시 · 머리 · 탭 링크 · 녹취 올리기 링크. */
export function caseHeaderValues(input: CaseScreenInput) {
  const { session, detail, caseId } = input;
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
    riskChip: `위험도 ${input.signals?.topLevelLabel || NOT_PROVIDED}`,
    riskCls: input.signals?.topLevel ? RISK_CHIP[input.signals.topLevel] : "c-normal",
    meta: info ? `${info.caseNumber} · 다음 상담 ${NOT_PROVIDED}` : "",
    uploadHref: screenHref("/UploadModal", ids),
    // 녹음하기 창(사례 상세 · 상담 이력 · 문서함, 10/29 디자인).
    recordCase: info ? `${info.alias} · ${info.caseNumber}` : "",
    recordTargets: uploadTargets(detail.sessions).filter((target) => target.uploadable),
    canRecord: Boolean(info && caseId),
    tabs: {
      detail: screenHref("/CaseDetail", ids),
      history: screenHref("/CaseHistory", ids),
      // 10/29 디자인: 상담 전 브리핑은 탭이 아니라 내담자 정보 탭 안(#brief). HashRouter 라 주소 # 대신 view=brief 로 연다.
      briefing: briefingHref(ids.caseId ?? null),
      app: screenHref("/CaseApp", ids),
      docs: screenHref("/CaseDocs", ids),
    },
  };
}

/** 내담자 정보 탭의 상담 전 브리핑 자리로 가는 주소(CaseDetail 이 view=brief 면 그 자리로 스크롤한다). */
export function briefingHref(caseId: string | null): string {
  const href = screenHref("/CaseDetail", { caseId });
  return `${href}${href.includes("?") ? "&" : "?"}view=brief`;
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
        { label: "조치결과", value: dash },
        { label: "담당 상담원", value: info.counselorName },
        { label: "신고접수일", value: dash },
        { label: "사례연계일", value: dash },
        { label: "최초면접일", value: dash },
        { label: "상담 회차", value: `${info.sessionCount}회`, strong: true },
        { label: "최근 상담", value: lastConsulted },
        { label: "아이 앱", value: dash },
      ]
    : [];

  // 현재 진행 상황: 가장 최근 회차가 어느 칸에 있는가. 칸을 누르면 그 회차의 그 단계 화면으로 간다(10/21 디자인).
  const column = latest ? COLUMN_OF[latest.step] : -1;
  const latestIds = latest ? { caseId: latest.caseId, sessionId: latest.id } : null;
  const progress = PROCESS_COLUMNS.map((label, index) => {
    const done = latest !== null && index < column;
    const current = latest !== null && index === column && index < PROCESS_COLUMNS.length - 1;
    // '추가 확인 · 질문' 칸: 회차 상태에 '질문 처리 완료' 가 없어 진행 표시는 그대로 두고, 가장 최근 회차에 승인한
    // 추가 질문이 있으면 그 수를 칩으로 보인다(18절).
    const last = index === PROCESS_COLUMNS.length - 1;
    const approved = last ? input.questions?.questions.length ?? 0 : 0;

    return {
      label,
      // 원래 화면처럼 '녹취 올림' 칸은 번호 없이, 나머지는 1 · 2 · 3 · 4.
      mark: done ? "✓" : index === 0 ? "↑" : String(index),
      dot: done ? DOT_DONE : current ? DOT_CURRENT : DOT_PENDING,
      done,
      current,
      pending: !done && !current,
      chip: current && latest ? latest.statusLabel : approved > 0 ? `질문 ${approved}개 승인` : "",
      // 녹취 올림 칸은 새로 올리기(사례만), 나머지는 가장 최근 회차의 단계 화면.
      href: latestIds
        ? index === 0
          ? screenHref("/UploadModal", { caseId: latestIds.caseId })
          : screenHref(STEP_PAGES[index], latestIds)
        : null,
    };
  });

  const next = latest ? continueLink(latest) : null;

  const intake = intakeValues(input);

  return {
    ...caseHeaderValues(input),
    basics,
    intake,
    unsaved: intake.unsaved,
    ...riskCardValues(input.signals),
    latestLabel: latest ? `${latest.numberLabel} · ${latest.statusLabel}` : info ? "회차 없음" : "",
    continueHref: next ? next.href : screenHref("/UploadModal", { caseId: input.caseId }),
    continueLabel: next ? next.label : "녹취 올려 시작하기",
    progress,
    formsChip: NOT_READY,
    formsHref: screenHref("/CaseForm", { caseId: input.caseId }),
    notReady: NOT_READY,
    // 녹음하기 창(components/RecordDialog.jsx)
  };
}

/** 세부 신호 행렬 칸 색: 4단계 이상 진하게, 1~3단계 옅게, 심각도 제안 없이 관련 신호만 있으면 테두리. */
const DOT_STRONG = { bg: "#7A776F", fg: "#FFFFFF", ring: "none" };
const DOT_LIGHT = { bg: "#EAE7DF", fg: "#2B2A26", ring: "none" };
const DOT_RING = { bg: "#FFFFFF", fg: "#7A776F", ring: "inset 0 0 0 1.5px #7A776F" };
const DOT_NONE = { bg: "transparent", fg: "#9C978C", ring: "none" };

/**
 * 탭 2 · 상담 이력.
 *  - 회차 카드 '신호' · 회차별 세부 신호 행렬(2026-10-28): 사례 단위 signal-history API(#99, useSignalHistory).
 *    카드는 'AI 신호 · 신체 · 정서'(관련 신호가 있는 유형) 옆에 상담원 판단이 있으면 '판단 상' 을 따로 붙인다(섞이지 않게,
 *    민규 님 리뷰). 행렬(2026-10-30, 디자인 그대로)은 줄 = 세부 신호 × 열 = 회차, 칸 = 근거 발화 수(1번 · 2번 이상),
 *    근거가 모두 화자 미확인이면 '보류'(signal-history subtypes). 10/28 에는 세부 유형이 고정 목록이 아니라고 보고 네 유형 ×
 *    AI 심각도로 채웠는데(민규 님 합의 ①), 2차 모델 세부 유형은 고정 14종이고 목록 밖 이름은 코드가 버린다(second_stage_llm).
 *    디자인 설명의 '채택 신호' 는 서버에 채택 기록이 없어 '관련 신호' 로 쓰고 'AI 제안' 칩을 붙인다. AI 심각도는 유형별 위험도 화면.
 *  - 누적 요약(2026-10-28): 승인 완료한 최근 회차들의 상담 요약 4칸(상담원 확정 문장, useApprovedSummaries)을 회차마다 한 상자로.
 *    AI 가 새로 만든 요약이 아니라 칩 · 안내에 '승인된 회차 요약 모음 · AI 생성 아님' 이라고 밝힌다(민규 님 합의).
 *  - 주제 비중 · 덜 다룬 부분(2026-10-29): 회차 분석의 대화 주제(topic_tags → signal-history topics)를 더한 비율(AI 제안).
 * 회차 카드는 최근 3회차(recent)를 보이고, '전 회차 보기' 창(all)에는 불러온 회차를 모두 보인다.
 * 창이 열렸는지는 화면이 들고 있다가 historyOpen · setHistoryOpen 으로 넘긴다.
 */
export function caseHistoryValues(
  input: CaseScreenInput & {
    historyOpen?: boolean;
    setHistoryOpen?: (open: boolean) => void;
    history?: SignalHistoryState;
    approved?: ApprovedSummariesState;
  },
) {
  const { detail, history } = input;
  const historyBySession = new Map((history?.sessions ?? []).map((row) => [row.session_id, row]));
  const sigOf = (sessionId: string) => {
    const row = historyBySession.get(sessionId);
    if (!row) return `신호 ${NOT_PROVIDED}`;
    const pending = pendingLabel(row);
    if (pending) return `AI 신호 · ${pending}`;
    const labels = detectedTypeLabels(row);
    // 관련 신호가 없을 때 detected 가 모두 null 이면 '없음' 으로 단정하지 않는다(민규 #104 리뷰).
    let ai = "AI 신호 · 검출 여부 미확인";
    if (labels.length > 0) ai = `AI 신호 · ${labels.join(" · ")}`;
    else if (signalsClearlyAbsent(row)) ai = "AI 관련 신호 없음";
    const top = counselorTop(row);
    return top ? `${ai} / 판단 ${RISK_LEVEL_LABELS[top]}` : ai;
  };
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
    sig: sigOf(row.id),
    href: screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.id }),
  }));

  // 세부 신호 행렬: 열은 회차(오래된 회차부터, 신호 이력을 받았으면 그 회차 전부), 줄은 네 학대 유형.
  const historyRows = history?.loaded ? history.sessions : [];
  const cols =
    historyRows.length > 0
      ? historyRows.map((row) => ({
          label: `${row.session_number}회`,
          href: screenHref("/SessionDetail", { caseId: input.caseId, sessionId: row.session_id }),
        }))
      : [...detail.sessions].reverse().map((row) => ({
          label: `${row.sessionNumber}회`,
          href: screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.id }),
        }));
  // 세부 신호 행렬(10/30, 디자인 그대로): 줄 = 세부 신호(2차 모델 고정 14종 중 나온 것, 유형 순서 → 처음 나온 순서),
  // 칸 = 그 회차 근거 발화 수(1번 · 2번 이상), 근거가 모두 화자 미확인이면 '보류'(?). signal-history subtypes.
  const rowKeys: { type: (typeof TREND_TYPES)[number]; subtype: string }[] = [];
  for (const type of TREND_TYPES) {
    for (const row of historyRows) {
      for (const item of row.subtypes ?? []) {
        if (item.abuse_type === type && !rowKeys.some((key) => key.type === type && key.subtype === item.subtype)) {
          rowKeys.push({ type, subtype: item.subtype });
        }
      }
    }
  }
  const mrows = rowKeys.map((key) => ({
    type: TYPE_SHORT[key.type],
    name: key.subtype,
    cells: historyRows.map((row) => {
      const item = (row.subtypes ?? []).find((s) => s.abuse_type === key.type && s.subtype === key.subtype);
      const at = `${row.session_number}회차 · ${key.subtype}`;
      if (!item) return { v: "", tip: `${at} · ${row.subtypes ? "없음" : pendingLabel(row) || "분석 전"}`, ...DOT_NONE };
      if (item.pending) return { v: "?", tip: `${at} · 보류(화자 확인 중) · 근거 ${item.count}번`, ...DOT_RING };
      return { v: String(item.count), tip: `${at} · 근거 ${item.count}번`, ...(item.count >= 2 ? DOT_STRONG : DOT_LIGHT) };
    }),
  }));
  let signalNote = "";
  if (history?.error) signalNote = history.error;
  else if (history && !history.loaded) signalNote = history.loading ? "회차별 신호를 불러오는 중…" : "";
  else if (historyRows.length > 0 && !historyRows.some((row) => Array.isArray(row.subtypes))) {
    signalNote = "AI 분석이 끝난 회차가 없습니다.";
  } else if (historyRows.length > 0 && mrows.length === 0) {
    signalNote = "분석한 회차에 근거 발화가 있는 세부 신호가 없습니다.";
  }

  let sessionsNote = "";
  if (detail.caseInfo && sessions.length === 0) sessionsNote = "회차가 없습니다. 녹취를 올리면 회차가 생깁니다.";
  else if (detail.sessionTotal !== null && detail.sessionTotal > sessions.length) {
    sessionsNote = `최근 ${sessions.length}회차만 보입니다(전체 ${detail.sessionTotal}회차).`;
  }

  // 누적 요약: 승인 회차마다 한 상자. 요약 4칸을 위험요인 → 강점과 자원 → 조사 후 변화 → 원하는 변화 순서로 보고,
  // 채워진 첫 칸이 제목 · 둘째 칸이 아래 줄이다. 4칸이 다 비었을 때만 '비어 있습니다'(민규 #104 R3).
  const clip = (text: string, max: number) => (text.length > max ? `${text.slice(0, max)}…` : text);
  const approved = input.approved;
  const SUMMARY_ORDER = [
    ["safety_risks", "위험요인"],
    ["strengths_resources", "강점과 자원"],
    ["safety_changes", "조사 후 변화"],
    ["desired_changes", "원하는 변화"],
  ] as const;
  const periods = (approved?.items ?? []).map((item) => {
    const a = item.assessment;
    const filled = SUMMARY_ORDER.map(([key, label]) => ({ label, text: a?.[key]?.text?.trim() ?? "" })).filter(
      (field) => field.text,
    );
    const date = item.consultedAt ? ` · ${toDateOnly(item.consultedAt)}` : "";
    const line = (field: { label: string; text: string } | undefined) =>
      field ? `${field.label} · ${clip(field.text, 80)}` : "";

    return {
      range: `${item.sessionNumber}회차${date}`,
      title: item.failed ? "요약을 불러오지 못했습니다" : filled.length > 0 ? line(filled[0]) : "요약 4칸이 비어 있습니다",
      note: item.failed ? "" : line(filled[1]),
    };
  });
  let overviewNote = "";
  if (approved?.error) overviewNote = approved.error;
  else if (approved?.loading) overviewNote = "승인된 회차 요약을 불러오는 중…";
  else if (periods.length === 0 && history?.loaded) overviewNote = "승인한 회차가 아직 없습니다.";
  else if (approved?.truncated) overviewNote = `승인한 최근 ${MAX_APPROVED}회차만 모았습니다.`;

  // 주제 비중 · 덜 다룬 부분(2026-10-29): 회차마다 AI 가 고정 주제로 나눈 아동 발화 수를 더한다(signalHistoryRows.topicShares).
  const historySessions = history?.loaded ? history.sessions : [];
  const shares = topicShares(historySessions);
  const taggedCount = taggedSessions(historySessions).length;
  const topics = shares.map((share) => ({ label: share.topic, width: `${share.pct}%`, pct: `${share.pct}%` }));
  const insights: { title: string; text: string; src: string }[] = [];
  if (shares.length >= 2) {
    const least = shares[shares.length - 1];
    const first = firstMentions(historySessions).get(least.topic);
    const at = first ? [`${first.sessionNumber}회차`, formatClock(first.startMs)].filter(Boolean).join(" ") : "";
    // 앞에 주제 분류가 없는 분석 회차가 있으면 '첫 언급' 이라 단정하지 않는다(민규 #122 리뷰).
    const src = !at ? "" : first?.certain ? `${at} 첫 언급` : `주제 분류가 있는 회차 중 ${at} 처음`;
    insights.push({ title: "덜 다룬 부분", text: least.topic, src });
  }
  const skippedCount = untaggedAnalyzed(historySessions).length;
  const skippedNote = skippedCount > 0 ? ` · 분석했지만 주제 분류가 없는 ${skippedCount}회차는 뺐습니다` : "";
  let topicNote = "";
  if (history && !history.loaded) topicNote = history.loading ? "주제를 불러오는 중…" : "";
  else if (taggedCount === 0) {
    topicNote =
      skippedCount > 0
        ? "AI 주제 분류가 있는 회차가 없습니다(이 기능 전 분석이거나 분류 실패). 'AI 결과 검수 필요' 회차는 다시 분석하면 생깁니다."
        : "AI 분석이 끝난 회차가 없습니다.";
  } else if (shares.length === 0) topicNote = `AI 제안 · ${taggedCount}회차에서 주제로 나눈 아동 발화가 없습니다${skippedNote}.`;
  else {
    const total = shares.reduce((sum, share) => sum + share.count, 0);
    topicNote = `AI 제안 · 주제 분류가 있는 ${taggedCount}회차의 아동 발화 ${total}개 기준${skippedNote}`;
  }

  return {
    ...caseHeaderValues(input),
    overviewChip: "승인된 회차 요약 모음 · AI 생성 아님",
    overviewSrc: "근거 · 승인된 회차의 상담 요약",
    overviewNote,
    periods,
    topics,
    topicNote,
    insights,
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
    mrows,
    /** 행렬 열 수에 맞춘 격자(디자인은 8회차 고정). */
    mxCols: `150px repeat(${Math.max(cols.length, 1)}, minmax(44px, 1fr))`,
    signalNote,
  };
}
