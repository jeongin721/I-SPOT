// 2 · 위험 신호 검토(SignalReview) 화면 값. AI 분석 요청 · 진행 · 실패 · 결과 안내는 useSessionAnalysis 로,
// 위험 신호 카드(유형 · 세부 유형 · 근거 발화 · 근거 직접성 · 이유)와 유형별 줄은 useRiskSignals(riskRows) 로 만든다.
//
//  - 카드는 AI 결과 risk_utterances(PROPOSAL_risk_fields.md §7-0) 그대로이고 읽기 전용이다. 서버가 근거 없는 항목은 이미 뺐다.
//  - 채택 · 보류 · 제외 기록은 서버에 없다(specs 대응표 '팀 결정 — AI 신호 · 검수'). 단추를 보이지 않고 준비 중으로 둔다.
//  - AI 결과는 판정이 아니라 참고정보다("관련 신호" · "추가 확인 필요", 05_RULES §1). 요약은 다음 단계에서 상담사가 고치고 승인한다.

import { NOT_PROVIDED } from "../caseRows";
import type { SignalCard, TypeSignal } from "../riskRows";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { NOT_READY } from "./common";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";

export interface SignalScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
}

/** 카드 하나를 화면 칸에 맞춘 값. */
export interface SignalCardValues {
  key: string;
  type: string;
  title: string;
  st: string;
  stCls: string;
  quote: string;
  at: string;
  why: string;
  check: string;
  evidence: SignalCard["evidence"];
}

export function signalCardValues(card: SignalCard, evidenceLoading: boolean): SignalCardValues {
  let at = card.positionLabel;

  if (!at) at = "근거 발화 번호 없음";
  else if (evidenceLoading && !card.evidence.some((item) => item.found)) at = `원문 받는 중 · ${at}`;

  return {
    key: card.key,
    type: card.typeLabel,
    title: card.subtype || "세부 유형 없음",
    st: `근거 직접성 ${card.strengthLabel}`,
    stCls: "chip c-check",
    quote: card.quote || "(발화 문장 없음)",
    at,
    why: card.reason || "AI 가 이유를 남기지 않았습니다.",
    check: card.verified ? "원문 대조 확인됨 · 상담사 확인 필요" : "원문 대조 안 됨 · 추가 확인 필요",
    evidence: card.evidence,
  };
}

/** 유형별 줄 하나. */
export interface TypeRowValues {
  key: string;
  label: string;
  state: TypeSignal["state"];
  text: string;
  countLabel: string;
}

export function typeRowValues(row: TypeSignal): TypeRowValues {
  const text = row.state === "filtered" && row.filteredReason ? `${row.stateLabel}(${row.filteredReason})` : row.stateLabel;

  return {
    key: row.abuseType || row.typeLabel,
    label: row.typeLabel,
    state: row.state,
    text,
    countLabel: row.count > 0 ? `근거 발화 ${row.count}건` : "",
  };
}

export function signalReviewValues(input: SignalScreenInput) {
  const { analysis, signals, go } = input;
  const header = processHeaderValues(input, 1);
  const ids = header.ids;
  const status = analysis.sessionStatus;
  const view = analysis.analysis;
  const sttHref = screenHref("/SttReview", ids);
  const noteHref = screenHref("/NoteWrite", ids);

  // AI 분석 카드: 지금 상태에 맞는 문구와 할 일.
  let aiChip = "";
  let aiText = "";
  let aiActionLabel = "";
  let aiAction: (() => void) | null = null;

  if (status === null) {
    aiText = "";
  } else if (status === "AI_PROCESSING") {
    aiChip = "AI 분석 중";
    aiText = "AI 가 원문을 분석하는 중입니다. 끝나면 이 화면이 저절로 바뀝니다.";
  } else if (status === "AI_FAILED") {
    aiChip = "AI 분석 실패";
    aiText = analysis.sessionError ?? "AI 분석에 실패했습니다.";
    aiActionLabel = "다시 분석";
  } else if (status === "STT_CONFIRMED") {
    aiChip = "분석 대기";
    aiText = "원문을 확정했습니다. AI 분석을 요청해 주세요.";
    aiActionLabel = "AI 분석 요청";
  } else if (status === "AI_REVIEW_REQUIRED" || status === "APPROVED") {
    aiChip = view ? view.statusLabel : "AI 분석 완료";
    aiText = view?.completedAt ? `분석 완료 · ${view.completedAt}` : "분석이 끝났습니다.";
  } else {
    aiChip = "원문 확정 전";
    aiText = "STT 검수에서 원문을 확정하면 AI 분석을 요청할 수 있습니다.";
    aiActionLabel = "STT 검수로";
    aiAction = () => go(sttHref);
  }

  if (aiActionLabel && !aiAction) {
    aiAction = analysis.canRequest && !analysis.submitting ? () => void analysis.run() : null;
  }

  const analyzed = status === "AI_REVIEW_REQUIRED" || status === "APPROVED";
  const completed = analyzed && view !== null && view.status === "COMPLETED";
  const sigs = completed ? signals.cards.map((card) => signalCardValues(card, signals.evidenceLoading)) : [];
  const typeRows = completed ? signals.types.map(typeRowValues) : [];

  // 신호 안내: 결과가 없으면 왜 없는지, 있으면 몇 건이고 무엇이 준비 중인지.
  let signalNote: string;

  if (!completed) {
    signalNote = "AI 분석이 끝나면 AI 가 찾은 위험 관련 발화가 여기에 보입니다. 판정이 아니라 참고정보입니다.";
  } else if (sigs.length === 0) {
    signalNote =
      "AI 가 근거 발화가 있는 위험 관련 발화를 찾지 못했습니다. 근거 발화가 없는 신호는 서버가 제외합니다(위 AI 안내 참고).";
  } else {
    signalNote = `AI 가 찾은 위험 관련 발화 ${sigs.length}건입니다. 판정이 아니라 참고정보이며, 상담사가 원문을 확인하고 판단합니다.`;
  }

  return {
    ...header,
    aiChip,
    aiText,
    aiActionLabel: analysis.submitting ? "요청 중…" : aiActionLabel,
    aiAction,
    aiWarnings: view?.warnings ?? [],
    error: analysis.error,
    sigs,
    typeRows,
    signalNote,
    /** 원문을 못 받아 근거 위치를 못 찾았을 때의 문구. 카드는 번호만 보인다. */
    signalError: completed ? signals.evidenceError : null,
    reviewReady: false,
    reviewNote: `채택 · 보류 · 제외 기록은 ${NOT_READY}입니다(팀 결정 뒤).`,
    nA: NOT_PROVIDED,
    nH: NOT_PROVIDED,
    nD: NOT_PROVIDED,
    sttHref,
    riskHref: screenHref("/RiskProfile", ids),
    nextHref: noteHref,
    nextLabel: "요약 · 일지 작성 →",
    canNext: analyzed,
  };
}
