// 회차 처리 화면(STT 검수 · 유형별 위험도 · 요약 · 일지 작성 · 추가 확인 · 질문) 공통 머리: 위치 표시 · 제목 · 단계 표시.

import { processNav } from "./flow";
import { type SessionScreenInput, sessionHeaderValues } from "./sessionDetail";

/** here: 지금 화면의 단계 칸(0 STT 검수 · 1 유형별 위험도 · 2 요약 · 일지 작성 · 3 추가 확인 · 질문). */
export function processHeaderValues(input: SessionScreenInput, here: number) {
  const header = sessionHeaderValues(input);
  const sv = input.detail.session;

  return {
    ...header,
    title: sv ? `${sv.numberLabel} 처리 · ${header.alias}` : "",
    steps: processNav(sv?.step ?? null, here, header.ids),
  };
}
