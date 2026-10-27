// 회차 상태 → 다음에 갈 화면. 사례 상세의 '이어서 하기' · 회차 상세의 단계 카드가 쓴다.
//
// 화면의 회차 처리 단계(녹취 올림 → STT 검수 → 유형별 위험도 → 요약 · 일지 작성 → 추가 확인 · 질문, 10/27 디자인)와
// Backend 상태(sessionRows 의 SessionStep)를 맞춘다.
//  - AI 분석은 STT 검수의 '유형별 위험도 →' 가 원문 확정과 함께 요청하고, 진행 · 실패 · 다시 요청은 '유형별 위험도' 화면에서 본다.
//  - 요약 검수 · 승인은 '요약 · 일지 작성' 화면에서 한다.
//  - '추가 확인 · 질문' 은 Backend 에 없다(회차 상태에 '질문 처리 완료' 단계가 없다). 늘 준비 중이다.

import type { SessionRow, SessionStep } from "../sessionRows";
import { type ScreenIds, screenHref } from "./links";

/** 화면의 회차 처리 단계. index 는 사례 상세 '현재 진행 상황' 의 칸 순서다. */
export const PROCESS_COLUMNS = ["녹취 올림", "STT 검수", "유형별 위험도", "요약 · 일지 작성", "추가 확인 · 질문"] as const;

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
  analysis: "유형별 위험도 · AI 분석",
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

/**
 * 회차 처리 단계 카드 · 탭 4개(STT 검수 · 유형별 위험도 · 요약 · 일지 작성 · 추가 확인 · 질문)에서 회차가 있는 칸.
 * 승인 완료면 -1(앞 세 칸을 모두 지났다). '추가 확인 · 질문' 칸에 오는 상태는 없다.
 */
export const CARD_OF: Record<SessionStep, number> = {
  upload: 0,
  stt: 0,
  sttReview: 0,
  analysis: 1,
  summaryReview: 2,
  done: -1,
};

const PROCESS_SCREENS = [
  { page: "/SttReview", label: "STT 검수" },
  { page: "/SignalReview", label: "유형별 위험도" },
  { page: "/NoteWrite", label: "요약 · 일지 작성" },
  { page: "/FollowupQ", label: "추가 확인 · 질문" },
] as const;

/**
 * 회차 처리 화면 위의 단계 표시(.steps). here 는 지금 화면의 칸(0~3).
 * 지금 화면은 'on', 회차가 이미 지난 칸은 'done'(✓). 링크는 같은 사례 · 회차 주소다.
 */
export function processNav(step: SessionStep | null, here: number, ids: Partial<ScreenIds>) {
  const at = step === null ? 0 : CARD_OF[step];
  const lastDone = at === -1 ? 2 : at - 1;

  return PROCESS_SCREENS.map((screen, index) => {
    const on = index === here;
    const done = step !== null && index <= lastDone;

    return {
      href: screenHref(screen.page, ids),
      label: screen.label,
      cls: on ? "stp on" : done ? "stp done" : "stp",
      mark: done && !on ? "✓" : String(index + 1),
      weight: on ? "700" : "500",
      current: on ? "step" : undefined,
    };
  });
}
