// 2 · 위험 신호 검토(SignalReview) 화면 값. AI 분석 요청 · 진행 · 실패 · 결과 안내는 useSessionAnalysis 로 한다.
//
// 위험 신호 카드(신체 · 정서 · 방임 세부 신호, 근거 발화, 채택 · 보류 · 제외)는 준비 중이다.
// 서버(AI)가 아직 위험 신호 목록을 주지 않고(mock · pipeline · langgraph 모두 빈 배열), 항목 구조와 채택 · 보류 · 제외 기록이
// 팀 결정 전이다(specs 대응표 '팀 결정 — AI 신호 · 검수'). 화면에는 AI 분석 상태와 AI 가 남긴 안내만 보인다.
// AI 결과는 판정이 아니라 참고정보다. 요약은 다음 단계(요약 · 일지 작성)에서 상담사가 고치고 승인한다.

import { NOT_PROVIDED } from "../caseRows";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { NOT_READY } from "./common";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";

export interface SignalScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
}

export function signalReviewValues(input: SignalScreenInput) {
  const { analysis, go } = input;
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

  return {
    ...header,
    aiChip,
    aiText,
    aiActionLabel: analysis.submitting ? "요청 중…" : aiActionLabel,
    aiAction,
    aiWarnings: view?.warnings ?? [],
    error: analysis.error,
    sigs: [] as Record<string, unknown>[],
    signalNote: `위험 신호 검토는 ${NOT_READY}입니다. 서버(AI)가 아직 위험 신호 목록을 주지 않습니다.`,
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
