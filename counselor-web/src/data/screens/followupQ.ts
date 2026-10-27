// 4 · 추가 확인 · 질문(FollowupQ) 화면 값. 10/27 디자인(counselor-design/screens/FollowupQ.dc.html)의 칸에 서버 값을 넣는다.
//
// 디자인 칸 → 서버 값:
//  - 다음 상담 전 확인할 사항: AI 분석 결과의 선택 필드 followup_check_points(AI 확인 메모)를 읽기 전용으로 보인다
//    (10/26 까지는 유형별 위험도 화면에 있던 카드). 질문 은행의 질문이 아니고 아이에게 할 질문으로 보이지 않는다
//    ('AI 확인 메모 · 질문 아님' 으로만 보이면 원칙 7 과 어긋나지 않는다는 2026-10-26 결정).
//    근거 · 위치는 segment_ids 를 원문에서 찾아 '몇 분 · 누구' 로 보이고 누르면 STT 검수의 그 발화로 간다.
//    서버가 segment_ids 를 비워 보내면(2026-10-27 #84 이전에 저장된 결과) '근거 위치 없음' 이다.
//  - 브리핑에 넣기 체크 · 수정 · 확인 사항 직접 추가: 저장할 API 가 없어 보이지 않고 준비 중이라고만 쓴다(가짜 저장 없음).
//  - 추가 질문(다음 상담에서 직접 · 아이 앱으로 먼저): 질문 은행 · 아이 앱 발송이 서버에 없어 준비 중이다(예시 질문을 보이지 않는다).
//  - 아래 'n회차 처리 완료 · 브리핑 보기': 회차 상태에 '질문 처리 완료' 가 없고 상담 전 브리핑은 아직 예시 화면이라
//    회차 상세로 가는 단추로 둔다.

import type { FollowupCheckPoint } from "../../api/types";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { NOT_READY } from "./common";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";
import { segmentHref } from "./sttReview";

export interface FollowupScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
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

    items.push({
      key: `f${index}`,
      text,
      why: located.label || "근거 위치 없음",
      href: first ? segmentHref(ids, first) : null,
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
    questionNote: `추가 질문(다음 상담에서 직접 · 아이 앱으로 먼저)은 ${NOT_READY}입니다(질문 은행 · 아이 앱 발송이 서버에 없음).`,
    error: analysis.error,
    signalError: completed ? signals.evidenceError : null,
    backHref: screenHref("/NoteWrite", ids),
    doneHref: screenHref("/SessionDetail", ids),
    doneLabel: sessionLabel ? `${sessionLabel} 보기 →` : "회차 보기 →",
  };
}
