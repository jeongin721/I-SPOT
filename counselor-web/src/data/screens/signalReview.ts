// 2 · 유형별 위험도(SignalReview) 화면 값. 10/27 디자인(counselor-design/screens/SignalReview.dc.html)의 칸에 서버 값을 넣는다.
// 예전 '위험 신호 검토' 와 '유형별 위험도'(RiskProfile) 두 화면이 디자인에서 이 화면 하나가 됐다.
//
// 디자인 칸 → 서버 값:
//  - 위쪽 카드 'AI 초안': 분석이 끝났으면 유형별 심각도 중 가장 높은 단계를 상 · 중 · 하로 크게 보인다(2026-11-05 경진님 결정 —
//    4~5 상 · 3 중 · 1~2 하, aiLevelFromSeverity). 옆에는 그 단계 · 유형, 지난 회차 AI 초안과 비교(↑ 증가 · → 같음 · ↓ 감소,
//    사례 단위 signal-history)를 둔다. 디자인의 '안전 플래그 n개' 는 서버에 없어 보이지 않는다. 아래에 AI 분석 상태
//    (분석 중 · 실패 · 요청 대기 · 완료)를 보인다 — 디자인에는 분석 요청 단계가 없고, STT 검수의 '유형별 위험도 →' 가
//    원문 확정과 분석 요청을 같이 한다(sttReview.ts). 여기서는 실패 · 대기일 때 다시 요청할 수 있게만 둔다.
//  - 위쪽 카드 '상담원 판단': 디자인대로 회차 전체 상 · 중 · 하 **하나**(2026-10-29, 서버 API_CONTRACT 11.1절 회차 전체 판단 —
//    useOverallRiskAssessment). 유형 줄마다 있던 상담원 판단 단추는 뺐다(유형별 판단 창구는 서버에 남아 있지만 화면은 쓰지 않는다).
//    저장 뒤에는 '저장 · 시각 · 그때 AI 최고 심각도 n/5' 를 보인다. 디자인의 'AI 제안과 같음/다름' 은 AI 단계 ↔ 상 · 중 · 하
//    대응 규칙이 팀 결정 전이라 쓰지 않는다.
//  - 판단 없이는 다음으로 못 간다(2026-10-29 사용자 결정): 분석이 끝나 검수 중인데 판단이 없으면(needsJudgment) 아래
//    '요약 · 일지 작성 →' 와 단계 표시 3단계는 옮기지 않고 팝업 "위험도를 선택해주세요." 를 띄운다(nextBlocked). 요약 · 일지 작성에
//    바로 들어온 경우(이어서 하기 · 주소 입력)는 그 화면이 이리로 돌려보내며 ?ask=1 을 붙여 같은 팝업을 연다(askLevelHref).
//  - 유형 줄: 관련 신호 칩(abuse_signals + risk_utterances, riskRows) · 심각도 1~5(severity_ratings, AI 제안이라 고칠 수
//    없다 — 디자인의 '눌러서 상담사 수정' 은 저장할 API 가 없어 하지 않음) · 해당 기준(단계 설명) · AI 이유 · 근거 발화
//    (누르면 STT 검수의 그 발화로) · 기준 보기(단계 설명 전체 + 근거 발화 전체와 세부 유형 · 근거 직접성).
//    안전 플래그 칩은 서버에 값이 없어 보이지 않는다.
//  - 회차별 추이(2026-10-28, 사례 단위 signal-history API #99): 이 회차까지 최근 3회차 × 유형(신체 · 정서 · 방임 · 성).
//    칸은 AI 심각도 숫자 · '확인 필요'(관련 신호만) · '–' · '분석 전'(signalHistoryRows), 맨 아래 '위험도 (상담원)' 줄은
//    회차마다 상담원 판단 중 가장 높은 것. 이 회차 열은 굵게(디자인).
//  - 안전 플래그 · 재학대 요인(2026-11-05, 분석 결과 safety_flags · reabuse_factors — 팀 확인 기준안 S1~S10 · R1~R10):
//    AI 확인 후보다. 안전 플래그는 certainty CLEAR 면 빨간 칩 'S2', CHECK 면 회색 칩 'S7 확인 후보'(디자인 'S6 확인 후보')에
//    문장 · 근거 위치. 재학대 요인은 아래 줄 칩(디자인 'R1 중복 유형')이고 문장 · 근거는 칩의 title. R1(중복학대)은 AI 가 아니라
//    이 화면이 관련 신호가 잡힌 유형 수(2 이상)로 센다. null(만들지 못함 · 이 기능 전 분석)은 '없음' 과 다르게 안내한다 —
//    언급 없음 ≠ 안전함. 플래그가 있고 사례 출생연도로 5세 이하면 '더 취약함' 을 함께 적는다(기준안 — 출생연도뿐이라 1세 미만은
//    가리지 못한다). 사례관리 중 재신고 표시는 아직 없다.
//  - 보호요인: protective_factors 를 읽기 전용으로 보인다(근거 위치는 원문에서).
//  - 다음 상담에서 확인할 것(followup_check_points)은 4 · 추가 확인 · 질문 화면으로 옮겼다(followupQ.ts).
//  - 아래 '확정 · 요약 · 일지 작성 →' 의 '확정' 은 서버에 위험 신호 확정 기록이 없어 빼고 '요약 · 일지 작성 →' 으로만 간다.
// 모두 AI 제안이고 판정이 아니다(05_RULES §1). 채택 · 보류 · 제외 기록은 서버에 없다(팀 결정 전).

import type { AbuseType, RiskLevel, SeverityRating, SignalHistorySession } from "../../api/types";
import { ABUSE_TYPES, ABUSE_TYPE_LABELS, RISK_LEVELS, RISK_LEVEL_LABELS } from "../../api/types";
import { abuseTypeLabel, type SignalCard, type TypeSignal } from "../riskRows";
import {
  ASSESSABLE_STATUSES,
  canAssessNow,
  needsJudgment,
  type OverallRiskAssessmentState,
} from "../useOverallRiskAssessment";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import type { SignalHistoryState } from "../useSignalHistory";
import { DASH, TREND_TYPES, TYPE_SHORT, counselorTopLabel, historyCell } from "../signalHistoryRows";
import { type ScreenIds, screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";
import { segmentHref } from "./sttReview";

export interface SignalScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
  /** 회차 전체 상담원 판단(상 · 중 · 하 하나). */
  overall: OverallRiskAssessmentState;
  /** 사례 단위 신호 이력(회차별 추이). 없으면 추이 칸은 안내만. */
  history?: SignalHistoryState;
}

/** 회차별 추이에 보이는 회차 수(디자인: 이 회차까지 3회차). */
const TREND_SESSIONS = 3;

/** 회차별 추이 표 값. 이 회차(sessionId)까지 최근 TREND_SESSIONS 회차. */
export function trendValues(history: SignalHistoryState | undefined, sessionId: string | null | undefined) {
  if (!history) return { trend: null, trendNote: "" };
  if (history.error) return { trend: null, trendNote: history.error };
  if (!history.loaded) return { trend: null, trendNote: history.loading ? "회차별 추이를 불러오는 중…" : "" };

  const index = history.sessions.findIndex((row) => row.session_id === sessionId);
  const upto = index >= 0 ? history.sessions.slice(0, index + 1) : history.sessions;
  const shown = upto.slice(-TREND_SESSIONS);

  if (shown.length === 0) return { trend: null, trendNote: "회차가 없습니다." };

  const current = (row: SignalHistorySession) => row.session_id === sessionId;

  return {
    trend: {
      cols: shown.map((row) => ({ key: row.session_id, label: `${row.session_number}회차`, current: current(row) })),
      rows: [
        ...TREND_TYPES.map((type) => ({
          key: type,
          label: TYPE_SHORT[type],
          cells: shown.map((row) => ({ key: row.session_id, ...historyCell(row, type), bold: current(row) })),
        })),
        {
          key: "counselor",
          label: "위험도 (상담원)",
          cells: shown.map((row) => {
            const text = counselorTopLabel(row);
            return { key: row.session_id, text, muted: text === DASH, level: null, detected: false, bold: current(row) };
          }),
        },
      ],
    },
    trendNote: "숫자는 AI 심각도 제안(1~5), '확인 필요' 는 관련 신호만 있고 심각도 제안이 없는 유형입니다. 위험도는 상담원 판단입니다.",
  };
}

/** 팝업 문구(2026-10-29 사용자 요청 그대로). */
export const ASK_LEVEL_TEXT = "위험도를 선택해주세요.";

/** 유형별 위험도 주소에 붙여 판단 팝업을 연 채 열게 하는 쿼리. 요약 · 일지 작성이 판단 없는 회차를 돌려보낼 때 붙인다. */
export const ASK_PARAM = "ask";

/** 주소에 ?ask=1 이 있는가(판단 팝업을 연 채 시작). */
export function readAskLevel(search: URLSearchParams | string): boolean {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;

  return params.get(ASK_PARAM) === "1";
}

/** 그 회차 유형별 위험도를 판단 팝업을 연 채 여는 주소. 회차 ID 가 없으면 팝업 쿼리를 붙이지 않는다. */
export function askLevelHref(ids: Partial<ScreenIds>): string {
  const href = screenHref("/SignalReview", ids);

  if (!ids.sessionId) return href;

  return `${href}&${ASK_PARAM}=1`;
}

const LABEL_TO_ABUSE_TYPE: Record<string, AbuseType> = {
  신체학대: "PHYSICAL",
  정서학대: "EMOTIONAL",
  성학대: "SEXUAL",
  방임: "NEGLECT",
};

/** severity_ratings[].major_type(한글 이름 · 띄어쓰기 · 영문 값)을 유형으로. 모르면 null(서버 enums.abuse_type_from_label 과 같은 규칙). */
export function abuseTypeFromLabel(value: unknown): AbuseType | null {
  if (typeof value !== "string") return null;

  const key = value.replace(/\s+/g, "");
  const upper = key.toUpperCase();

  if ((ABUSE_TYPES as readonly string[]).includes(upper)) return upper as AbuseType;

  // 표에 선언한 이름만 읽는다("__proto__" 같은 Object 상속 속성 이름이 와도 null, Codex #80 R1 과 같은 방어).
  return Object.prototype.hasOwnProperty.call(LABEL_TO_ABUSE_TYPE, key) ? LABEL_TO_ABUSE_TYPE[key] : null;
}

/** AI 심각도 제안 한 유형. */
export interface SeveritySuggestion {
  /** 1~5. 정보 부족이면 null. */
  level: number | null;
  reason: string;
  matchedEvidence: string;
  segmentIds: string[];
}

function readText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** 유형별 첫 항목만 쓴다(서버가 ai_level 을 읽는 규칙과 같다). level 은 1~5 정수일 때만. */
export function severityByType(ratings: SeverityRating[]): Map<AbuseType, SeveritySuggestion> {
  const map = new Map<AbuseType, SeveritySuggestion>();

  for (const rating of ratings) {
    const type = abuseTypeFromLabel(rating.major_type);

    if (!type || map.has(type)) continue;

    const level = rating.level;

    map.set(type, {
      level: typeof level === "number" && Number.isInteger(level) && level >= 1 && level <= 5 ? level : null,
      reason: readText(rating.reason),
      matchedEvidence: readText(rating.matched_evidence),
      segmentIds: Array.isArray(rating.segment_ids) ? rating.segment_ids.filter((id) => typeof id === "string") : [],
    });
  }

  return map;
}

/** 유형 줄 관련 신호 칩 문구. */
export const SIGNAL_STATE_CHIPS: Record<TypeSignal["state"], string> = {
  signal: "관련 신호",
  filtered: "부정 응답으로 뺌",
  none: "관련 신호 없음",
  unknown: "검출 여부 미확인",
  missing: "근거 없어 제외",
};

/** 칩 색(디자인 evTone: 직접 근거 · 확인 필요 · 언급 없음 세 가지). [배경, 글자]. */
const CHIP_TONES: Record<"strong" | "check" | "none", [string, string]> = {
  strong: ["#2B2A26", "#FFFFFF"],
  check: ["#F2EFE8", "#66625A"],
  none: ["#FFFFFF", "#98948B"],
};

const STATE_TONE: Record<TypeSignal["state"], keyof typeof CHIP_TONES> = {
  signal: "strong",
  unknown: "check",
  filtered: "check",
  none: "none",
  missing: "none",
};

/** 참고 기준(디자인의 단계 설명). 팀이 확정한 기준이 아니라 '참고' 로만 보인다. */
export const SEVERITY_RUBRIC: Record<AbuseType, string[]> = {
  PHYSICAL: [
    "흔적 없는 가벼운 체벌, 단발",
    "경미한 흔적, 반복 체벌",
    "멍 · 통증이 남음, 도구 사용, 몸통 · 팔다리 상해",
    "머리 · 얼굴 · 목 상해, 반복적 도구 폭행, 병원 치료 필요",
    "골절 · 화상 · 목 조름 등 생명 위험",
  ],
  EMOTIONAL: [
    "단발성 고성 · 꾸중, 반응 거의 없음",
    "반복적 고성 · 비하, 또는 함구 요구 1회",
    "위협 · 유기 위협 반복, 또는 두려움 · 위축 진술",
    "지속적 위협 · 고립, 가정폭력 반복 노출, 일상 기능 손상",
    "생명 위협, 극단적 공포, 자해 · 자살 언급",
  ],
  SEXUAL: [
    "성적 수치심을 주는 언행, 단발",
    "반복적 성적 언행, 음란물 노출",
    "비접촉 성적 행위 요구 · 노출 · 촬영",
    "접촉을 동반한 성적 행위",
    "반복 · 지속적 접촉, 위협 · 강압 동반",
  ],
  NEGLECT: [
    "일시적 · 가벼운 돌봄 소홀",
    "식사 · 위생 소홀 반복, 건강 영향 없음",
    "지속적 방치, 결석 방치, 학령기 아동 장시간 방치",
    "건강 영향, 치료 방치, 영유아 방치",
    "유기, 생명 위협 수준의 방치",
  ],
};

/** 접혀 있을 때 보이는 근거 발화 수(디자인은 유형마다 1~2줄). */
const REFS_SHOWN = 2;

/** 근거 발화 한 줄. 누르면 STT 검수의 그 발화로 간다(근거 번호가 있을 때). */
export interface RefLine {
  key: string;
  text: string;
  /** 펼쳤을 때만 보이는 세부(세부 유형 · 근거 직접성 · 원문 대조 · AI 이유). */
  detail: string;
  href: string | null;
}

export function refLine(card: SignalCard, sessionLabel: string, ids: { caseId?: string | null; sessionId?: string | null }): RefLine {
  const where = card.positionLabel || "발화 번호 없음";
  const first = card.evidence[0]?.segmentId ?? null;
  const parts = [
    card.subtype || "세부 유형 없음",
    `근거 직접성 ${card.strengthLabel}`,
    card.verified ? "원문 대조 확인됨" : "원문 대조 안 됨 · 추가 확인 필요",
  ];

  if (card.reason) parts.push(card.reason);

  return {
    key: card.key,
    text: `${sessionLabel ? `${sessionLabel} ` : ""}${where} "${card.quote || "(발화 문장 없음)"}"`,
    detail: parts.join(" · "),
    href: first ? segmentHref(ids, first) : null,
  };
}

export interface RiskTypeValues {
  key: AbuseType;
  label: string;
  ev: string;
  evBg: string;
  evFg: string;
  sevText: string;
  sevSuffix: string;
  boxes: { n: number; aria: string; bg: string; fg: string; bd: string }[];
  /** 해당 기준(디자인): "3단계 · 단계 설명". */
  matched: string;
  /** AI 가 그 단계로 본 이유. 없으면 "". */
  why: string;
  refs: RefLine[];
  /** 접혀 있을 때 더 있는 근거 발화 수 문구. */
  moreRefs: string;
  /** 근거 발화가 없을 때 문구(언급 없음 ≠ 학대 없음). */
  noRef: string;
  anchors: { n: number; text: string; bg: string; fg: string; fw: number }[];
}

/** 상담원 판단 상 · 중 · 하 단추 하나(위 카드, 회차 전체). */
export interface LevelButton {
  key: RiskLevel;
  label: string;
  on: boolean;
  disabled: boolean;
  bg: string;
  bd: string;
  fg: string;
  pick: () => void;
}

/**
 * AI 심각도(1~5)를 위쪽 카드 'AI 초안' 상 · 중 · 하로(2026-11-05 경진님 결정): 4~5 상 · 3 중 · 1~2 하. 없으면 null.
 * AI 제안을 읽기 쉽게 바꾼 것일 뿐 판정이 아니다 — 회차 위험도는 옆의 상담원 판단이 정한다.
 */
export function aiLevelFromSeverity(severity: number | null | undefined): RiskLevel | null {
  if (typeof severity !== "number" || severity < 1) return null;
  if (severity >= 4) return "HIGH";
  if (severity === 3) return "MEDIUM";
  return "LOW";
}

const LEVEL_RANK: Record<RiskLevel, number> = { LOW: 1, MEDIUM: 2, HIGH: 3 };

/**
 * 지난 회차와 비교(디자인 '· 7회차 중 → ↑ 증가'). 사례 신호 이력에서 이 회차 바로 앞 회차의 AI 최고 심각도를 같은 규칙으로 바꿔 견준다.
 * 앞 회차가 없거나 · 분석 전이거나 · 심각도 제안이 없으면 ''.
 */
export function aiTrendText(
  history: SignalHistoryState | undefined,
  sessionId: string | null | undefined,
  current: RiskLevel | null,
): string {
  if (!history?.loaded || !sessionId || current === null) return "";

  const index = history.sessions.findIndex((row) => row.session_id === sessionId);
  if (index <= 0) return "";

  const previous = history.sessions[index - 1];
  const levels = previous.types.map((row) => (typeof row.ai_level === "number" ? row.ai_level : 0));
  const before = aiLevelFromSeverity(levels.length > 0 ? Math.max(...levels) : null);
  if (before === null) return "";

  const diff = LEVEL_RANK[current] - LEVEL_RANK[before];
  const change = diff > 0 ? "↑ 증가" : diff < 0 ? "↓ 감소" : "같음";

  return `· ${previous.session_number}회차 ${RISK_LEVEL_LABELS[before]} → ${change}`;
}

/** 재학대 요인 칩 이름(팀 확인 기준안 2026-11-05, ai/modeling/abuse/safety_flag_llm.REABUSE_FACTOR_DEFINITIONS 를 줄인 것). */
const REABUSE_LABELS: Record<string, string> = {
  R1: "중복 유형",
  R2: "알코올 남용",
  R3: "부부 폭력",
  R4: "친부모가 행위자",
  R5: "경제적 어려움",
  R6: "양육 기술 부족",
  R7: "행위자 정신건강",
  R8: "아동에게 책임 전가",
  R9: "개입 거부",
  R10: "새 동거인 · 여러 행위자",
};

/** 상 · 중 · 하 단추 색(디자인). */
const LEVEL_TONES: Record<RiskLevel, { tone: string; bg: string }> = {
  HIGH: { tone: "#A33B2E", bg: "#F7E4DF" },
  MEDIUM: { tone: "#7A5F28", bg: "#F3EAD3" },
  LOW: { tone: "#66625A", bg: "#F2EFE8" },
};

export function signalReviewValues(input: SignalScreenInput, open: Partial<Record<AbuseType, boolean>> = {}) {
  const { analysis, signals, overall, go } = input;
  const header = processHeaderValues(input, 1);
  const ids = header.ids;
  const status = analysis.sessionStatus;
  const view = analysis.analysis;
  const sttHref = screenHref("/SttReview", ids);
  const analyzed = status === "AI_REVIEW_REQUIRED" || status === "APPROVED";
  const completed = analyzed && view !== null && view.status === "COMPLETED";
  const canAssess = canAssessNow(status, overall);
  const assessLoadFailed = overall.loadError !== null;
  const judged = overall.assessment;
  const severity = severityByType(view?.severityRatings ?? []);
  const signalByType = new Map(signals.types.map((row) => [row.abuseType, row]));
  const cardsByType = new Map<string, SignalCard[]>();
  const sessionLabel = input.detail.session?.numberLabel ?? "";

  for (const card of completed ? signals.cards : []) {
    const list = cardsByType.get(card.abuseType) ?? [];
    list.push(card);
    cardsByType.set(card.abuseType, list);
  }

  // 위쪽 카드 'AI 초안' 자리: AI 분석 상태와 할 일.
  let aiText: string;
  let aiActionLabel = "";
  let aiAction: (() => void) | null = null;
  let top = 0;
  const topTypes: string[] = [];

  if (status === null) {
    aiText = "";
  } else if (status === "AI_PROCESSING") {
    aiText = "AI 가 원문을 분석하는 중입니다. 끝나면 이 화면이 저절로 바뀝니다.";
  } else if (status === "AI_FAILED") {
    aiText = analysis.sessionError ?? "AI 분석에 실패했습니다.";
    aiActionLabel = "다시 분석";
  } else if (status === "STT_CONFIRMED") {
    aiText = "원문을 확정했습니다. AI 분석을 요청해 주세요.";
    aiActionLabel = "AI 분석 요청";
  } else if (analyzed) {
    aiText = view?.completedAt ? `AI 분석 완료 · ${view.completedAt}` : "AI 분석이 끝났습니다.";

    // 유형별 심각도(AI 제안) 중 가장 높은 단계. 같은 단계면 유형 순서(신체 · 정서 · 성 · 방임)대로 함께 적는다.
    for (const type of ABUSE_TYPES) {
      const level = completed ? severity.get(type)?.level ?? null : null;
      if (level === null || level < top) continue;
      if (level > top) topTypes.length = 0;
      top = level;
      topTypes.push(ABUSE_TYPE_LABELS[type]);
    }
  } else {
    aiText = "기록 확인에서 원문을 확정하면 AI 분석이 시작됩니다.";
    aiActionLabel = "기록 확인으로";
    aiAction = () => go(sttHref);
  }

  if (aiActionLabel && !aiAction) {
    aiAction = analysis.canRequest && !analysis.submitting ? () => void analysis.run() : null;
  }

  const types: RiskTypeValues[] = ABUSE_TYPES.map((type) => {
    const label = ABUSE_TYPE_LABELS[type];
    const signal = signalByType.get(type);
    const state = signal?.state ?? "none";
    const suggestion = severity.get(type);
    const level = suggestion?.level ?? null;
    const isOpen = !!open[type];
    const cards = cardsByType.get(type) ?? [];
    const lines = cards.map((card) => refLine(card, sessionLabel, ids));
    const shown = isOpen ? lines : lines.slice(0, REFS_SHOWN);
    const [evBg, evFg] = CHIP_TONES[completed ? STATE_TONE[state] : "none"];

    let matched: string;

    if (!completed) matched = "AI 분석이 끝나면 보입니다.";
    else if (level !== null) matched = `${level}단계 · ${SEVERITY_RUBRIC[type][level - 1]}`;
    else if (suggestion) matched = "근거가 약해 단계를 매기지 않았어요(정보 부족).";
    else matched = state === "signal" || state === "unknown" ? "AI 심각도 제안이 없습니다." : "해당 내용 없음";

    return {
      key: type,
      label,
      ev: completed ? SIGNAL_STATE_CHIPS[state] : "분석 전",
      evBg,
      evFg,
      sevText: level !== null ? String(level) : "–",
      sevSuffix: level !== null ? "/ 5" : suggestion ? "정보 부족" : completed ? "제안 없음" : "",
      boxes: [1, 2, 3, 4, 5].map((n) => {
        const on = level !== null && n <= level;

        return {
          n,
          aria: `${label} AI 심각도 ${n}`,
          bg: on ? (level !== null && level >= 4 ? "#A33B2E" : "#C2A36B") : "#FFFFFF",
          fg: on ? "#FFFFFF" : "#98948B",
          bd: on ? "transparent" : "#DAD5C9",
        };
      }),
      matched,
      why: completed && suggestion ? suggestion.reason || suggestion.matchedEvidence : "",
      refs: shown,
      moreRefs: !isOpen && lines.length > REFS_SHOWN ? `근거 발화 ${lines.length - REFS_SHOWN}건 더 · 기준 보기에서 모두` : "",
      noRef: completed && lines.length === 0 ? "근거 발화 없음 · 언급 없음 ≠ 학대 없음(질문하지 않았을 수 있음)" : "",
      anchors: SEVERITY_RUBRIC[type].map((text, index) => {
        const on = level === index + 1;

        return { n: index + 1, text, bg: on ? "#F1EADA" : "transparent", fg: on ? "#2B2A26" : "#7A776F", fw: on ? 700 : 400 };
      }),
    };
  });

  // 위쪽 카드 '상담원 판단': 회차 전체 상 · 중 · 하 하나. 이미 고른 단추를 다시 눌러도 보내지 않는다(지우는 API 가 없다).
  const levels: LevelButton[] = RISK_LEVELS.map((candidate) => {
    const on = judged?.level === candidate;
    const tone = LEVEL_TONES[candidate];

    return {
      key: candidate,
      label: RISK_LEVEL_LABELS[candidate],
      on,
      disabled: !canAssess,
      bg: on ? tone.bg : "#FFFFFF",
      bd: on ? tone.tone : "#DAD5C9",
      fg: on ? tone.tone : "#66625A",
      pick: () => {
        if (!on) void overall.save({ level: candidate, reason: judged?.reason || undefined });
      },
    };
  });

  let assessNote: string;

  if (assessLoadFailed) {
    assessNote = "판단을 불러오지 못해 저장할 수 없습니다. 다시 불러온 뒤 판단해 주세요.";
  } else if (overall.loading) {
    assessNote = "불러오는 중…";
  } else if (judged) {
    // 고른 단계 이름을 글로도 적는다(색만으로 나타내지 않는다 — 05_RULES).
    assessNote = `저장 · ${judged.levelLabel} · ${judged.assessedAt}${judged.aiLevel !== null ? ` · 그때 AI 최고 심각도 ${judged.aiLevel}/5` : ""}`;
  } else if (status !== null && ASSESSABLE_STATUSES.includes(status)) {
    assessNote = "아직 판단하지 않았습니다.";
  } else if (status === "AI_PROCESSING") {
    assessNote = "AI 분석이 끝난 뒤 판단을 저장할 수 있습니다.";
  } else {
    assessNote = "원문을 확정하면 판단을 저장할 수 있습니다.";
  }

  const aiLevel = aiLevelFromSeverity(top);

  const protective = completed
    ? (view?.protectiveFactors ?? [])
        .map((factor, index) => {
          const text = readText(factor?.text);
          const category = readText(factor?.category);
          const where = signals.locate(factor?.segment_ids).label;

          return { key: `p${index}`, code: `P${index + 1}`, category, text, where: where || "근거 위치 없음" };
        })
        .filter((factor) => factor.text !== "")
    : [];

  const flagsRaw = completed ? (view?.safetyFlags ?? null) : null;
  const safetyFlags = (flagsRaw ?? [])
    .map((flag, index) => {
      const code = readText(flag?.code);
      const clear = flag?.certainty === "CLEAR";
      const where = signals.locate(flag?.segment_ids).label;

      return {
        key: `s${index}`,
        chip: clear ? code : `${code} 확인 후보`,
        tone: clear ? "c-hi" : "c-normal",
        text: readText(flag?.text),
        where: where || "근거 위치 없음",
      };
    })
    .filter((flag) => flag.text !== "");

  let flagEmpty = "";
  if (!completed) flagEmpty = "AI 분석이 끝나면 안전 플래그 후보가 보입니다.";
  else if (flagsRaw === null) flagEmpty = "안전 플래그 · 재학대 요인을 만들지 못했습니다. 다시 분석하면 만들어집니다.";
  else if (safetyFlags.length === 0) flagEmpty = "AI 가 찾은 안전 플래그 후보가 없습니다. 언급 없음 ≠ 안전함(묻지 않았을 수 있음).";

  // 더 취약함(기준안): 플래그가 있고 출생연도로 5세 이하. 상담일 연도가 없으면 올해로 센다.
  const birthYear = input.caseDetail.caseInfo?.childBirthYear ?? null;
  const consultedYear = Number((input.detail.session?.consultedAt ?? "").slice(0, 4)) || new Date().getFullYear();
  const youngChild = birthYear !== null && consultedYear - birthYear <= 5;
  const vulnerableNote =
    safetyFlags.length > 0 && youngChild ? "더 취약함 · 출생연도로 5세 이하(어린 아동은 같은 위협에도 더 위험합니다)" : "";

  // 재학대 요인: R1 은 관련 신호가 잡힌 유형이 둘 이상일 때 화면이 센다. 나머지는 AI 후보.
  const signalTypes = completed ? signals.types.filter((row) => row.state === "signal").map((row) => abuseTypeLabel(row.abuseType)) : [];
  const reabuseRaw = completed ? (view?.reabuseFactors ?? null) : null;
  const reabuse = [
    ...(signalTypes.length >= 2
      ? [{ key: "r1", chip: `R1 ${REABUSE_LABELS.R1}`, title: `관련 신호가 잡힌 유형: ${signalTypes.join(" · ")}` }]
      : []),
    ...(reabuseRaw ?? [])
      .map((factor, index) => {
        const code = readText(factor?.code);
        const where = signals.locate(factor?.segment_ids).label;

        return {
          key: `r${index + 2}`,
          chip: REABUSE_LABELS[code] ? `${code} ${REABUSE_LABELS[code]}` : code,
          title: `${readText(factor?.text)}${where ? ` · ${where}` : ""}`,
        };
      })
      .filter((factor) => factor.chip !== ""),
  ];

  return {
    ...header,
    aiText,
    aiActionLabel: analysis.submitting ? "요청 중…" : aiActionLabel,
    aiAction,
    aiWarnings: completed ? (view?.warnings ?? []) : [],
    /** 위 카드 'AI 초안' 큰 글자(상 · 중 · 하) · 색 · 옆 설명 · 지난 회차 비교. 심각도 제안이 없으면 aiLevel 이 ''. */
    aiLevel: aiLevel ? RISK_LEVEL_LABELS[aiLevel] : "",
    aiLevelColor: aiLevel ? LEVEL_TONES[aiLevel].tone : "",
    aiLevelText: aiLevel ? `최고 심각도 ${top}/5 · ${topTypes.join(" · ")}` : "",
    aiTrend: aiTrendText(input.history, ids.sessionId, aiLevel),
    aiOverallNote: "AI 초안은 아래 유형별 심각도 중 가장 높은 값입니다(4~5 상 · 3 중 · 1~2 하). 위험도는 상담원 판단으로 정합니다.",
    /** 위 카드 상담원 판단: 상 · 중 · 하 단추(회차 전체 하나), 상태 안내, 저장 중 표시. */
    levels,
    assessNote,
    assessHint: "유형별 심각도(AI 제안)를 보고 이 회차 전체를 상 · 중 · 하 하나로 판단합니다. 저장할 때의 AI 최고 심각도가 함께 기록됩니다.",
    assessSaving: overall.submitting,
    assessLoadError: overall.loadError,
    reloadAssess: overall.reload,
    types,
    rubricNote: "단계 설명은 디자인 초안의 참고 기준이며 팀이 확정한 기준이 아닙니다.",
    ...trendValues(input.history, ids.sessionId),
    /** 안전 플래그 후보 줄(칩 · 문장 · 근거 위치), 비었을 때 안내, 더 취약함 안내. */
    safetyFlags,
    flagEmpty,
    vulnerableNote,
    /** 재학대 요인 칩(R1 은 화면 계산). 문장 · 근거는 title. */
    reabuse,
    reabuseNote: completed && reabuse.length > 0 ? "R1~R6 은 통계 연구, R7~R10 은 사례 연구(14건) 근거입니다. 칩을 가리키면 근거가 보입니다." : "",
    factorTitle: completed
      ? // AI 후보를 만들지 못했으면(null) 개수를 세지 않는다 — R1 하나만 보고 '위험요인 1' 이라 하면 '하나뿐' 으로 읽힌다.
        `위험요인 ${reabuseRaw === null ? "확인 못 함" : reabuse.length} · 보호요인 ${protective.length}`
      : "위험요인 · 보호요인",
    protective,
    protectiveEmpty: !completed ? "AI 분석이 끝나면 보호요인이 보입니다." : protective.length === 0 ? "AI 가 찾은 보호요인이 없습니다." : "",
    error: overall.error ?? analysis.error,
    signalError: completed ? signals.evidenceError : null,
    sttHref,
    nextHref: screenHref("/NoteWrite", ids),
    // '확정' 은 디자인 문구(2026-11-05). 따로 저장하는 것은 없고, 상담원 판단이 있어야 넘어간다(nextBlocked).
    nextLabel: "확정 · 상담일지 작성 →",
    canNext: analyzed,
    /** 분석은 끝났는데 판단이 없어 다음 단추 · 단계 표시 3단계를 팝업으로 막는가. */
    nextBlocked: needsJudgment(status, overall),
    askText: ASK_LEVEL_TEXT,
    askHint: "상담원 판단(상 · 중 · 하)을 고르면 상담일지 작성으로 넘어갈 수 있습니다.",
  };
}
