// 2 · 유형별 위험도(RiskProfile) 화면 값.
//
//  - AI 심각도 1~5: AI 분석 결과의 선택 필드 severity_ratings(API_CONTRACT 8절 "선택 필드"). major_type 은 한글 이름으로
//    오므로 여기서 영문 유형으로 맞춘다. 판정이 아니라 'AI 제안' 이고, 화면에서 고칠 수 없다(고친 단계를 저장할 API 가 없음).
//  - 상담원 판단 상 · 중 · 하: useRiskAssessments(API_CONTRACT 11절). 유형마다 따로 저장하고, 저장할 때 서버가
//    그때의 AI 제안(ai_level)을 함께 기록한다. 원문 확정 뒤(STT_CONFIRMED · AI_REVIEW_REQUIRED · AI_FAILED · APPROVED)에만 된다.
//  - 유형별 관련 신호 · 근거 발화는 위험 신호 검토와 같은 useRiskSignals(riskRows) 값이다.
//  - 서버에 없는 것(회차 전체 AI 위험도 · AI 단계와 상 · 중 · 하 대응 규칙 · 안전 플래그 · 재학대 요인 · 회차별 추이 ·
//    다음 상담에서 확인할 것)은 팀 결정 전이라 '준비 중' 으로 두고 예시 값을 보이지 않는다.

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

export interface RiskProfileInput extends SessionScreenInput {
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

/** 유형별 관련 신호 상태 → 칩 문구. */
export const SIGNAL_STATE_CHIPS: Record<TypeSignal["state"], string> = {
  signal: "관련 신호",
  filtered: "부정 응답으로 뺌",
  none: "관련 신호 없음",
  unknown: "검출 여부 미확인",
  missing: "근거 없어 제외",
};

/** 참고 기준(디자인 초안의 단계 설명). 팀이 확정한 기준이 아니라 '참고' 로만 보인다. */
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

/** 근거 발화 한 줄 문구("01:36 아동 "…""). 3건까지. */
export function evidenceLines(cards: SignalCard[]): { lines: string[]; more: number } {
  const lines = cards.slice(0, 3).map((card) => `${card.positionLabel || "발화 번호 없음"} "${card.quote || "(발화 문장 없음)"}"`);

  return { lines, more: Math.max(0, cards.length - 3) };
}

export interface RiskTypeValues {
  key: AbuseType;
  label: string;
  /** 관련 신호 칩 문구. 분석 전이면 "분석 전". */
  ev: string;
  /** AI 심각도. 없으면 "–". */
  sevText: string;
  sevSuffix: string;
  boxes: { n: number; aria: string; on: boolean }[];
  /** AI 가 그 단계로 본 이유(또는 발췌). */
  matched: string;
  refs: string[];
  moreRefs: string;
  /** 상담원 판단 상 · 중 · 하 단추. */
  levels: { key: RiskLevel; label: string; on: boolean; disabled: boolean; pick: () => void }[];
  assessNote: string;
  rubric: { n: number; text: string; on: boolean }[];
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

export function riskProfileValues(input: RiskProfileInput, openRubric: Partial<Record<AbuseType, boolean>> = {}) {
  const { analysis, signals, assessments } = input;
  const header = processHeaderValues(input, 1);
  const ids = header.ids;
  const status = analysis.sessionStatus;
  const view = analysis.analysis;
  const analyzed = status === "AI_REVIEW_REQUIRED" || status === "APPROVED";
  const completed = analyzed && view !== null && view.status === "COMPLETED";
  const canAssess = canAssessNow(status, assessments);
  const assessLoadFailed = assessments.loadError !== null;
  const severity = severityByType(view?.severityRatings ?? []);
  const signalByType = new Map(signals.types.map((row) => [row.abuseType, row]));
  const cardsByType = new Map<string, SignalCard[]>();

  for (const card of signals.cards) {
    const list = cardsByType.get(card.abuseType) ?? [];
    list.push(card);
    cardsByType.set(card.abuseType, list);
  }

  const types: RiskTypeValues[] = ABUSE_TYPES.map((type) => {
    const label = ABUSE_TYPE_LABELS[type];
    const signal = signalByType.get(type);
    const suggestion = severity.get(type);
    const level = suggestion?.level ?? null;
    const { lines, more } = evidenceLines(completed ? (cardsByType.get(type) ?? []) : []);
    const row = assessments.rows.find((candidate) => candidate.abuseType === type);

    let matched: string;

    if (!completed) matched = "AI 분석이 끝나면 보입니다.";
    else if (!suggestion) matched = "AI 심각도 제안이 없습니다.";
    else if (level === null) matched = suggestion.reason || "근거가 약해 AI 가 단계를 매기지 않았습니다(정보 부족).";
    else matched = suggestion.reason || suggestion.matchedEvidence || "AI 가 이유를 남기지 않았습니다.";

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
      ev: completed ? SIGNAL_STATE_CHIPS[signal?.state ?? "none"] : "분석 전",
      sevText: level !== null ? String(level) : "–",
      sevSuffix: level !== null ? "/ 5" : suggestion ? "정보 부족" : completed ? "제안 없음" : "",
      boxes: [1, 2, 3, 4, 5].map((n) => ({ n, aria: `${label} AI 심각도 ${n}`, on: level !== null && n <= level })),
      matched,
      refs: lines,
      moreRefs: more > 0 ? `근거 발화 ${more}건 더 있음 · 위험 신호 보기에서 확인` : "",
      levels: RISK_LEVELS.map((candidate) => ({
        key: candidate,
        label: RISK_LEVEL_LABELS[candidate],
        on: row?.level === candidate,
        disabled: !canAssess,
        pick: () => void assessments.save(type, { level: candidate, reason: row?.reason || undefined }),
      })),
      assessNote,
      rubric: SEVERITY_RUBRIC[type].map((text, index) => ({ n: index + 1, text, on: level === index + 1 })),
    };
  });

  const assessedCount = assessments.rows.filter((row) => row.assessed).length;

  return {
    ...header,
    types,
    openRubric,
    /** 회차 전체 AI 위험도(상 · 중 · 하)는 AI 단계와 대응시키는 규칙이 팀 결정 전이라 없다. */
    aiOverallNote: `회차 전체 AI 위험도는 ${NOT_READY}입니다(AI 단계 1~5 와 상 · 중 · 하를 대응시키는 규칙은 팀 결정 전).`,
    assessSummary: assessments.loading
      ? "불러오는 중…"
      : assessLoadFailed
        ? "판단 목록을 불러오지 못했습니다"
        : `유형별 상담원 판단 ${assessedCount}/4 저장됨`,
    assessHint: "판단은 유형마다 따로 저장되고, 저장할 때의 AI 제안이 함께 기록됩니다. 회차 전체 위험도는 팀 결정 전입니다.",
    /** 판단 목록 조회 실패 문구. 있으면 '다시 불러오기' 단추를 보인다. */
    assessLoadError: assessments.loadError,
    reloadAssess: assessments.reload,
    rubricNote: "참고 기준은 디자인 초안의 단계 설명이며 팀이 확정한 기준이 아닙니다.",
    notReady: [
      `안전 플래그 · 재학대 요인 · 보호 요인 표시는 ${NOT_READY}입니다(서버에 안전 플래그 값이 없고 보호 요인은 표시 방식 결정 전).`,
      `회차별 추이는 ${NOT_READY}입니다(서버에 회차 간 비교 값이 없음).`,
      `다음 상담에서 확인할 것은 ${NOT_READY}입니다(AI 확인 메모를 아이에게 할 질문으로 보일지 팀 결정 전).`,
    ],
    error: assessments.error ?? analysis.error,
    signalError: completed ? signals.evidenceError : null,
    signalHref: screenHref("/SignalReview", ids),
    nextHref: screenHref("/NoteWrite", ids),
    nextLabel: "요약 · 일지 작성 →",
    canNext: analyzed,
  };
}
