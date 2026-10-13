// 회차 상태 → 다음에 갈 화면. 사례 상세의 '이어서 하기' · 회차 상세의 단계 카드가 쓴다.
//
// 화면의 회차 처리 단계(녹취 올림 → STT 검수 → 위험 신호 검토 → 요약 · 일지 작성 → 추가 확인 · 질문)와
// Backend 상태(sessionRows 의 SessionStep)를 맞춘다.
//  - AI 분석 요청 · 진행은 '위험 신호 검토' 화면에서 한다(위험 신호 자체는 서버가 아직 빈 목록이라 준비 중).
//  - 요약 검수 · 승인은 '요약 · 일지 작성' 화면에서 한다.
//  - '추가 확인 · 질문' 은 Backend 에 없다(회차 상태에 '질문 처리 완료' 단계가 없다). 늘 준비 중이다.

import type { SessionRow, SessionStep } from "../sessionRows";
import { screenHref } from "./links";

/** 화면의 회차 처리 단계. index 는 사례 상세 '현재 진행 상황' 의 칸 순서다. */
export const PROCESS_COLUMNS = ["녹취 올림", "STT 검수", "위험 신호 검토", "요약 · 일지 작성", "추가 확인 · 질문"] as const;

/** 회차 단계가 화면의 몇 번째 칸인가. 승인 완료(done)는 앞 네 칸을 모두 지난 것으로 본다. */
export const COLUMN_OF: Record<SessionStep, number> = {
  upload: 0,
  stt: 0,
  sttReview: 1,
  analysis: 2,
  summaryReview: 3,
  done: 4,
};

/** 회차 단계에서 할 일이 있는 화면. */
export const STEP_SCREEN: Record<SessionStep, string> = {
  upload: "/UploadModal",
  stt: "/SttReview",
  sttReview: "/SttReview",
  analysis: "/SignalReview",
  summaryReview: "/NoteWrite",
  done: "/SessionDetail",
};

const CONTINUE_LABEL: Record<SessionStep, string> = {
  upload: "녹취 올리기",
  stt: "STT 검수",
  sttReview: "STT 검수",
  analysis: "위험 신호 검토 · AI 분석",
  summaryReview: "요약 · 일지 작성",
  done: "회차 보기",
};

/** 그 회차를 이어서 할 화면 링크. */
export function continueLink(row: Pick<SessionRow, "id" | "caseId" | "step">): { href: string; label: string } {
  return {
    href: screenHref(STEP_SCREEN[row.step], { caseId: row.caseId, sessionId: row.id }),
    label: `이어서 하기 · ${CONTINUE_LABEL[row.step]}`,
  };
}
