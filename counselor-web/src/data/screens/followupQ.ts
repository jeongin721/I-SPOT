// 4 · 추가 확인 · 질문(FollowupQ) 화면 값. 10/27 디자인(counselor-design/screens/FollowupQ.dc.html)의 칸에 서버 값을 넣는다.
//
// 디자인 칸 → 서버 값:
//  - 다음 상담 전 확인할 사항: AI 분석 결과의 선택 필드 followup_check_points(AI 확인 메모)를 읽기 전용으로 보인다
//    (10/26 까지는 유형별 위험도 화면에 있던 카드). 질문 은행의 질문이 아니고 아이에게 할 질문으로 보이지 않는다
//    ('AI 확인 메모 · 질문 아님' 으로만 보이면 원칙 7 과 어긋나지 않는다는 2026-10-26 결정).
//    근거 · 위치는 segment_ids 를 원문에서 찾아 '몇 분 · 누구' 로 보이고 누르면 STT 검수의 그 발화로 간다.
//    서버가 segment_ids 를 비워 보내면(2026-10-27 #84 이전에 저장된 결과) '근거 위치 없음' 이고, 근거가 지난 회차 확정 요약뿐인
//    메모(previous_session_label, 2026-10-28)는 '근거 · 7회차 확정 요약' 이다.
//  - 브리핑에 넣기 체크 · 수정 · 확인 사항 직접 추가: 저장할 API 가 없어 보이지 않고 준비 중이라고만 쓴다(가짜 저장 없음).
//  - 추가 질문: AI 초안(분석 결과 followup_questions) · 승인 목록(GET/PUT …/followup-questions, 18절)을 디자인의 카드 ·
//    [승인] · [수정] · [+ 질문 직접 추가] 로 보인다(followupQuestions.ts). '아이 앱으로 먼저' 탭은 준비 중이다.
//  - 아래 'n회차 처리 완료 · 브리핑 보기': 회차 상태에 '질문 처리 완료' 가 없고 상담 전 브리핑은 아직 예시 화면이라
//    회차 상세로 가는 단추로 둔다.

import type { FollowupCheckPoint, SessionStatus } from "../../api/types";
import type { FollowupQuestionsState } from "../useFollowupQuestions";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { NOT_READY } from "./common";
import { questionValues, type QuestionUiState } from "./followupQuestions";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";
import { segmentHref } from "./sttReview";

export interface FollowupScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
  questions: FollowupQuestionsState;
  state: QuestionUiState;
  setState: (patch: Partial<QuestionUiState> | ((current: QuestionUiState) => Partial<QuestionUiState>)) => void;
}

/** 승인한 추가 질문을 저장할 수 있는 회차 상태(API_CONTRACT 18절). */
const QUESTION_EDITABLE: SessionStatus[] = ["STT_CONFIRMED", "AI_REVIEW_REQUIRED", "AI_FAILED", "APPROVED"];

/** 저장할 수 없는 상태면 그 이유. 상태를 아직 모르면 null(서버가 409 로 거른다). */
export function questionBlockedReason(status: SessionStatus | null | undefined): string | null {
  if (!status || QUESTION_EDITABLE.includes(status)) return null;
  if (status === "AI_PROCESSING") return "AI 분석 중에는 질문을 승인할 수 없습니다. 분석이 끝난 뒤 승인해 주세요.";
  return "원문(STT)을 확정한 뒤 질문을 승인할 수 있습니다.";
}

/** 카드 머리 칩. 질문이 아니라 메모임을 늘 밝힌다(원칙 7). */
export const FOLLOWUP_CHIP = "AI 확인 메모 · 질문 아님";

/** '다음 상담 전 확인할 사항' 한 항목. */
export interface FollowupItem {
  key: string;
  text: string;
  /** 근거 위치("01:08 아동"). 원문을 못 받았으면 "발화 seg_003", 번호가 없으면 "근거 위치 없음". */
  why: string;
  /** 근거 발화로 가는 STT 검수 주소. 번호가 없으면 null. */
  href: string | null;
  /** 근거가 지난 회차 확정 요약뿐인가(why 가 'N회차 확정 요약'). */
  fromPrevious: boolean;
}

/**
 * followup_check_points → 항목. text 가 빈 문자열이 아닌 항목만 쓰고 다른 키는 보지 않는다.
 * locate 는 useRiskSignals 의 원문 찾기다(segment_ids 를 '몇 분 · 누구' 로).
 */
export function toFollowupItems(
  points: FollowupCheckPoint[],
  locate: RiskSignalsState["locate"],
  ids: { caseId?: string | null; sessionId?: string | null },
): FollowupItem[] {
  const items: FollowupItem[] = [];

  points.forEach((point, index) => {
    if (!point || typeof point !== "object") return;

    const text = typeof point.text === "string" ? point.text.trim() : "";

    if (!text) return;

    const located = locate(point.segment_ids);
    const first = located.evidence[0]?.segmentId ?? null;
    // 근거가 지난 회차 확정 요약뿐인 메모(previous_session_label, #100 §7 답 3).
    const previous =
      !first && typeof point.previous_session_label === "string" && point.previous_session_label
        ? point.previous_session_label
        : "";

    items.push({
      key: `f${index}`,
      text,
      why: located.label || (previous ? `${previous} 확정 요약` : "근거 위치 없음"),
      href: first ? segmentHref(ids, first) : null,
      fromPrevious: Boolean(previous),
    });
  });

  return items;
}

export function followupQValues(input: FollowupScreenInput) {
  const { analysis, signals } = input;
  const header = processHeaderValues(input, 3);
  const ids = header.ids;
  const status = analysis.sessionStatus;
  const view = analysis.analysis;
  const analyzed = status === "AI_REVIEW_REQUIRED" || status === "APPROVED";
  const completed = analyzed && view !== null && view.status === "COMPLETED";
  const checks = completed ? toFollowupItems(view?.followupCheckPoints ?? [], signals.locate, ids) : [];

  let empty = "";

  if (status === "AI_PROCESSING") empty = "AI 분석 중입니다. 끝나면 확인 메모가 보입니다.";
  else if (!completed) empty = "AI 분석이 끝나면 확인 메모가 보입니다.";
  else if (checks.length === 0) empty = "AI 가 남긴 확인 메모가 없습니다.";

  const sessionLabel = input.detail.session?.numberLabel ?? "";

  return {
    ...header,
    chip: FOLLOWUP_CHIP,
    checkNote:
      "AI 가 다음 상담에서 확인해 두면 좋겠다고 남긴 메모입니다. 아이에게 할 질문이 아니고, 확인할지는 상담원이 정합니다.",
    checks,
    checksEmpty: empty,
    checkEditNote: `브리핑에 넣기 · 수정 · 확인 사항 직접 추가는 ${NOT_READY}입니다(저장할 서버 기능이 없음).`,
    ...questionValues({
      state: input.state,
      setState: input.setState,
      drafts: completed ? view?.followupQuestions ?? [] : [],
      saved: input.questions,
      locate: signals.locate,
      ids,
      sessionLabel,
      blockedReason: questionBlockedReason(status),
    }),
    error: analysis.error,
    signalError: completed ? signals.evidenceError : null,
    backHref: screenHref("/NoteWrite", ids),
    doneHref: screenHref("/SessionDetail", ids),
    doneLabel: sessionLabel ? `${sessionLabel} 보기 →` : "회차 보기 →",
  };
}
