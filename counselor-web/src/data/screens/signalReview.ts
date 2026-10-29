// 2 · 유형별 위험도(SignalReview) 화면 값. 10/27 디자인(counselor-design/screens/SignalReview.dc.html)의 칸에 서버 값을 넣는다.
// 예전 '위험 신호 검토' 와 '유형별 위험도'(RiskProfile) 두 화면이 디자인에서 이 화면 하나가 됐다.
//
// 디자인 칸 → 서버 값:
//  - 위쪽 카드 'AI 초안': 분석이 끝났으면 유형별 심각도 중 가장 높은 단계와 그 유형을 보인다(2026-10-28, severity_ratings —
//    1~5 단계를 상 · 중 · 하로 바꾸는 규칙은 정하지 않아 단계 숫자 그대로). 안전 플래그 수 · 회차 비교는 서버에 없어
//    준비 중이다(회차 비교는 사례 단위 signal-history API 뒤에). 그 자리에 AI 분석 상태
//    (분석 중 · 실패 · 요청 대기 · 완료)를 보인다 — 디자인에는 분석 요청 단계가 없고, STT 검수의 '유형별 위험도 →' 가
//    원문 확정과 분석 요청을 같이 한다(sttReview.ts). 여기서는 실패 · 대기일 때 다시 요청할 수 있게만 둔다.
//  - 위쪽 카드 '상담원 판단': 디자인은 회차 전체 상 · 중 · 하 하나지만 서버(API_CONTRACT 11절)는 유형마다 저장한다.
//    그래서 상 · 중 · 하 단추는 유형 줄마다 두고, 위쪽에는 저장한 수와 안내만 둔다.
//  - 유형 줄: 관련 신호 칩(abuse_signals + risk_utterances, riskRows) · 심각도 1~5(severity_ratings, AI 제안이라 고칠 수
//    없다 — 디자인의 '눌러서 상담사 수정' 은 저장할 API 가 없어 하지 않음) · 해당 기준(단계 설명) · AI 이유 · 근거 발화
//    (누르면 STT 검수의 그 발화로) · 기준 보기(단계 설명 전체 + 근거 발화 전체와 세부 유형 · 근거 직접성).
//    안전 플래그 칩은 서버에 값이 없어 보이지 않는다.
//  - 회차별 추이 · 안전 플래그 · 재학대 요인 · 위험요인: 서버에 없어 준비 중(예시 값을 보이지 않는다).
//  - 보호요인: protective_factors 를 읽기 전용으로 보인다(근거 위치는 원문에서).
//  - 다음 상담에서 확인할 것(followup_check_points)은 4 · 추가 확인 · 질문 화면으로 옮겼다(followupQ.ts).
//  - 아래 '확정 · 요약 · 일지 작성 →' 의 '확정' 은 서버에 위험 신호 확정 기록이 없어 빼고 '요약 · 일지 작성 →' 으로만 간다.
// 모두 AI 제안이고 판정이 아니다(05_RULES §1). 채택 · 보류 · 제외 기록은 서버에 없다(팀 결정 전).

import type { AbuseType, RiskLevel, SessionStatus, SeverityRating } from "../../api/types";
import { ABUSE_TYPES, ABUSE_TYPE_LABELS, RISK_LEVELS, RISK_LEVEL_LABELS } from "../../api/types";
import type { SignalCard, TypeSignal } from "../riskRows";
import type { RiskAssessmentsState } from "../useRiskAssessments";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { NOT_READY } from "./common";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";
import { segmentHref } from "./sttReview";

export interface SignalScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
  assessments: RiskAssessmentsState;
}

/** 상담원 판단을 저장할 수 있는 회차 상태(API_CONTRACT 11절). */
export const ASSESSABLE_STATUSES: readonly SessionStatus[] = ["STT_CONFIRMED", "AI_REVIEW_REQUIRED", "AI_FAILED", "APPROVED"];

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
  /** 상담원 판단 상 · 중 · 하 단추(서버는 유형마다 저장). */
  levels: { key: RiskLevel; label: string; on: boolean; disabled: boolean; bg: string; bd: string; fg: string; pick: () => void }[];
  assessNote: string;
}

/**
 * 지금 판단 단추를 켤 수 있는가.
 * 회차 상태가 저장 가능하고, 요청 중이 아니고, **서버 목록을 받은 뒤(loaded · 조회 오류 없음)** 여야 한다.
 * 목록을 못 받은 채 저장하면 서버에 있던 판단 이유를 모른 채 PUT 으로 지운다(Codex #81 R1). 오류를 보이는 것만으로는
 * 부족해서 단추 자체를 끈다.
 */
export function canAssessNow(
  status: SessionStatus | null,
  assessments: Pick<RiskAssessmentsState, "loaded" | "loading" | "loadError" | "submitting">,
): boolean {
  return (
    status !== null &&
    ASSESSABLE_STATUSES.includes(status) &&
    assessments.loaded &&
    !assessments.loading &&
    assessments.loadError === null &&
    !assessments.submitting
  );
}

/** 상 · 중 · 하 단추 색(디자인). */
const LEVEL_TONES: Record<RiskLevel, { tone: string; bg: string }> = {
  HIGH: { tone: "#A33B2E", bg: "#F7E4DF" },
  MEDIUM: { tone: "#7A5F28", bg: "#F3EAD3" },
  LOW: { tone: "#66625A", bg: "#F2EFE8" },
};

export function signalReviewValues(input: SignalScreenInput, open: Partial<Record<AbuseType, boolean>> = {}) {
  const { analysis, signals, assessments, go } = input;
  const header = processHeaderValues(input, 1);
  const ids = header.ids;
  const status = analysis.sessionStatus;
  const view = analysis.analysis;
  const sttHref = screenHref("/SttReview", ids);
  const analyzed = status === "AI_REVIEW_REQUIRED" || status === "APPROVED";
  const completed = analyzed && view !== null && view.status === "COMPLETED";
  const canAssess = canAssessNow(status, assessments);
  const assessLoadFailed = assessments.loadError !== null;
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
    let top = 0;
    const topTypes: string[] = [];
    for (const type of ABUSE_TYPES) {
      const level = completed ? severity.get(type)?.level ?? null : null;
      if (level === null || level < top) continue;
      if (level > top) topTypes.length = 0;
      top = level;
      topTypes.push(ABUSE_TYPE_LABELS[type]);
    }
    if (top > 0) aiText = `회차 최고 심각도 ${top}단계 · ${topTypes.join(" · ")} — ${aiText}`;
  } else {
    aiText = "STT 검수에서 원문을 확정하면 AI 분석이 시작됩니다.";
    aiActionLabel = "STT 검수로";
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
    const row = assessments.rows.find((candidate) => candidate.abuseType === type);
    const [evBg, evFg] = CHIP_TONES[completed ? STATE_TONE[state] : "none"];

    let matched: string;

    if (!completed) matched = "AI 분석이 끝나면 보입니다.";
    else if (level !== null) matched = `${level}단계 · ${SEVERITY_RUBRIC[type][level - 1]}`;
    else if (suggestion) matched = "근거가 약해 단계를 매기지 않았어요(정보 부족).";
    else matched = state === "signal" || state === "unknown" ? "AI 심각도 제안이 없습니다." : "해당 내용 없음";

    let assessNote: string;

    if (assessLoadFailed) {
      assessNote = "판단 목록을 불러오지 못해 저장할 수 없습니다. 다시 불러온 뒤 판단해 주세요.";
    } else if (row?.assessed) {
      assessNote = `저장 · ${row.assessedAt}${row.aiLevel !== null ? ` · 그때 AI 제안 ${row.aiLevel}/5` : ""}`;
    } else if (status !== null && ASSESSABLE_STATUSES.includes(status)) {
      assessNote = "아직 판단하지 않았습니다.";
    } else if (status === "AI_PROCESSING") {
      assessNote = "AI 분석이 끝난 뒤 판단을 저장할 수 있습니다.";
    } else {
      assessNote = "원문을 확정하면 판단을 저장할 수 있습니다.";
    }

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
      levels: RISK_LEVELS.map((candidate) => {
        const on = row?.level === candidate;
        const tone = LEVEL_TONES[candidate];

        return {
          key: candidate,
          label: RISK_LEVEL_LABELS[candidate],
          on,
          disabled: !canAssess,
          bg: on ? tone.bg : "#FFFFFF",
          bd: on ? tone.tone : "#DAD5C9",
          fg: on ? tone.tone : "#66625A",
          pick: () => void assessments.save(type, { level: candidate, reason: row?.reason || undefined }),
        };
      }),
      assessNote,
    };
  });

  const assessedCount = assessments.rows.filter((row) => row.assessed).length;
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

  return {
    ...header,
    aiText,
    aiActionLabel: analysis.submitting ? "요청 중…" : aiActionLabel,
    aiAction,
    aiWarnings: completed ? (view?.warnings ?? []) : [],
    aiOverallNote: `심각도는 아래 유형별 AI 제안 중 가장 높은 값입니다. 안전 플래그 · 지난 회차와 비교는 ${NOT_READY}입니다.`,
    assessSummary: assessments.loading
      ? "불러오는 중…"
      : assessLoadFailed
        ? "판단 목록을 불러오지 못했습니다"
        : `유형별 상담원 판단 ${assessedCount}/4 저장됨`,
    assessHint: "판단은 아래 유형마다 저장되고, 저장할 때의 AI 제안이 함께 기록됩니다.",
    assessLoadError: assessments.loadError,
    reloadAssess: assessments.reload,
    types,
    rubricNote: "단계 설명은 디자인 초안의 참고 기준이며 팀이 확정한 기준이 아닙니다.",
    trendNote: `회차별 추이는 ${NOT_READY}입니다(서버에 회차 간 비교 값이 없음).`,
    flagNote: `안전 플래그 · 재학대 요인은 ${NOT_READY}입니다(서버에 값이 없음).`,
    factorTitle: completed ? `위험요인 ${NOT_READY} · 보호요인 ${protective.length}` : "위험요인 · 보호요인",
    protective,
    protectiveEmpty: !completed ? "AI 분석이 끝나면 보호요인이 보입니다." : protective.length === 0 ? "AI 가 찾은 보호요인이 없습니다." : "",
    error: assessments.error ?? analysis.error,
    signalError: completed ? signals.evidenceError : null,
    sttHref,
    nextHref: screenHref("/NoteWrite", ids),
    nextLabel: "요약 · 일지 작성 →",
    canNext: analyzed,
  };
}
