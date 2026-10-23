// 위험 신호 검토 화면 훅. AI 결과의 위험 배열(useSessionAnalysis 가 내보낸 riskUtterances · abuseSignals)에
// 원문(GET /sessions/{id}/transcript)의 발화를 붙여 근거 위치(몇 분 · 누구)를 만든다(README "지켜야 할 원칙" 3).
//
//  - 원문은 위험 발화가 하나라도 있을 때만 부른다(없으면 보일 근거가 없다).
//  - 원문을 못 받았으면(evidenceLoading · evidenceError) 카드의 근거는 번호만 남는다 — '없음' 이 아니라 '모름' 이다.
//  - 채택 · 보류 · 제외 기록은 서버에 없다(팀 결정 전). 읽기 전용이다.

import { useMemo } from "react";

import { transcript as transcriptApi } from "../api/endpoints";
import type { TranscriptEnvelope } from "../api/types";
import { toSignalCards, toTypeSignals } from "./riskRows";
import type { SignalCard, TypeSignal } from "./riskRows";
import { useRemote } from "./useRemote";
import type { AnalysisView } from "./useSessionAnalysis";

export interface RiskSignalsOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface RiskSignalsState {
  /** 위험 관련 발화 카드. 분석 결과가 없으면 빈 배열. */
  cards: SignalCard[];
  /** 학대 유형별 줄(네 유형 고정 순서). 분석 결과가 없으면 빈 배열. */
  types: TypeSignal[];
  /** 근거 위치를 찾을 원문을 받는 중인가. */
  evidenceLoading: boolean;
  /** 원문을 못 받았으면 그 문구. 이때 카드의 근거는 번호만 있다. */
  evidenceError: string | null;
  reload: () => void;
}

export function useRiskSignals(
  sessionId: string | null | undefined,
  analysis: AnalysisView | null,
  { enabled = true }: RiskSignalsOptions = {},
): RiskSignalsState {
  const utterances = analysis?.riskUtterances ?? [];
  const signals = analysis?.abuseSignals ?? [];
  const key = enabled && sessionId && utterances.length > 0 ? sessionId : null;
  const source = useRemote<TranscriptEnvelope>(key, transcriptApi.get, "근거 발화를 불러오지 못했습니다.");
  const segments = key ? (source.data?.transcript?.segments ?? null) : null;

  const cards = useMemo(() => toSignalCards(utterances, segments), [utterances, segments]);
  const types = useMemo(() => (analysis ? toTypeSignals(signals, utterances) : []), [analysis, signals, utterances]);

  return {
    cards,
    types,
    evidenceLoading: key !== null && source.loading,
    evidenceError: key !== null ? source.error : null,
    reload: source.reload,
  };
}
