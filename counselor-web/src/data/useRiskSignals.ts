// 위험 신호 훅(유형별 위험도 · 추가 확인 화면). AI 결과의 위험 배열(useSessionAnalysis 가 내보낸 riskUtterances · abuseSignals)에
// 원문(GET /sessions/{id}/transcript)의 발화를 붙여 근거 위치(몇 분 · 누구)를 만든다(README "지켜야 할 원칙" 3).
//
//  - 원문은 근거 번호가 하나라도 있을 때만 부른다 — 위험 발화, 보호요인 · 확인 메모의 segment_ids(없으면 보일 근거가 없다).
//  - 원문을 못 받았으면(evidenceLoading · evidenceError) 근거는 번호만 남는다 — '없음' 이 아니라 '모름' 이다.
//  - 채택 · 보류 · 제외 기록은 서버에 없다(팀 결정 전). 읽기 전용이다.

import { useCallback, useMemo } from "react";

import { transcript as transcriptApi } from "../api/endpoints";
import type { TranscriptEnvelope } from "../api/types";
import { locateEvidence, positionLabel, toSignalCards, toTypeSignals } from "./riskRows";
import type { SignalCard, SignalEvidence, TypeSignal } from "./riskRows";
import { useRemote } from "./useRemote";
import type { AnalysisView } from "./useSessionAnalysis";

export interface RiskSignalsOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
  /**
   * 분석 결과 밖에 근거 번호가 있어 원문이 필요한가(추가 질문 초안 · 승인 목록 — 승인은 분석 없이도 된다). 기본 false.
   * true 면 분석이 끝나지 않았어도 원문을 받는다.
   */
  needEvidence?: boolean;
}

/** segment_ids 를 원문에서 찾은 결과. */
export interface LocatedEvidence {
  evidence: SignalEvidence[];
  /** "01:36 아동 · 02:10 상담원". 원문이 없으면 "발화 seg_002". 번호가 없으면 "". */
  label: string;
}

export interface RiskSignalsState {
  /** 위험 관련 발화 카드. 분석 결과가 없으면 빈 배열. */
  cards: SignalCard[];
  /** 학대 유형별 줄(네 유형 고정 순서). 분석 결과가 없으면 빈 배열. */
  types: TypeSignal[];
  /** 보호요인 · 확인 메모 같은 다른 항목의 segment_ids 를 원문에서 찾는다. */
  locate: (ids: unknown) => LocatedEvidence;
  /** 근거 위치를 찾을 원문을 받는 중인가. */
  evidenceLoading: boolean;
  /** 원문을 못 받았으면 그 문구. 이때 카드의 근거는 번호만 있다. */
  evidenceError: string | null;
  reload: () => void;
}

function hasIds(items: { segment_ids?: unknown }[]): boolean {
  return items.some(
    (item) => Array.isArray(item?.segment_ids) && item.segment_ids.some((id) => typeof id === "string" && id !== ""),
  );
}

export function useRiskSignals(
  sessionId: string | null | undefined,
  analysis: AnalysisView | null,
  { enabled = true, needEvidence = false }: RiskSignalsOptions = {},
): RiskSignalsState {
  // 끝난 분석(COMPLETED)만 값으로 본다. 처리 중 · 실패한 분석 행도 AnalysisView 로 오지만(위험 배열은 빈 배열)
  // 그걸로 유형 줄을 만들면 네 유형이 모두 '응답에 없음' 이 된다(Codex R3).
  const completed = analysis !== null && analysis.status === "COMPLETED";
  const utterances = completed ? analysis.riskUtterances : [];
  const signals = completed ? analysis.abuseSignals : [];
  const needSource =
    (completed && (utterances.length > 0 || hasIds(analysis.protectiveFactors) || hasIds(analysis.followupCheckPoints))) ||
    needEvidence;
  const key = enabled && sessionId && needSource ? sessionId : null;
  const source = useRemote<TranscriptEnvelope>(key, transcriptApi.get, "근거 발화를 불러오지 못했습니다.");
  const segments = key ? (source.data?.transcript?.segments ?? null) : null;

  const cards = useMemo(() => toSignalCards(utterances, segments), [utterances, segments]);
  const types = useMemo(() => (completed ? toTypeSignals(signals, utterances) : []), [completed, signals, utterances]);
  const locate = useCallback(
    (ids: unknown): LocatedEvidence => {
      const evidence = locateEvidence(ids, segments);

      return { evidence, label: positionLabel(evidence) };
    },
    [segments],
  );

  return {
    cards,
    types,
    locate,
    evidenceLoading: key !== null && source.loading,
    evidenceError: key !== null ? source.error : null,
    reload: source.reload,
  };
}
