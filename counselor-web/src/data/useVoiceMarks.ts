// 구간별 음성 참고 표시 훅(GET /sessions/{id}/voice-marks, API_CONTRACT 16절).
//
// STT 가 끝난 뒤 Backend 가 같은 백그라운드 작업에서 계산해 저장하므로 원문이 생긴 직후에는 아직 없을 수 있다(data null).
// 그때는 잠시 되풀이 조회한다(최대 MAX_POLLS 회). 원문을 확정하면 아동 구간이 바뀌었을 때 Backend 가 다시 계산해
// 새 판(transcript_version)이 생기므로, 받은 결과의 판이 지금 원문 판보다 낮은 동안에도 잠시 되풀이 조회한다.
// 회차 변경 알림(확정 · 다시 변환)이 오면 조용히 다시 부른다(useRemote 기본).
//
// 이 표시는 상담사가 다시 들어 볼 구간을 알려 주는 참고 정보이며 학대 · 위험을 판정하지 않는다.

import { useEffect, useRef } from "react";

import { voiceMarks as voiceMarksApi } from "../api/endpoints";
import type { VoiceMarks } from "../api/types";
import { usePolling, useRemote } from "./useRemote";

/** 분석을 기다리며 되풀이 조회하는 최대 횟수(2.5초 간격 → 약 5분. 30분 녹음도 보통 그 안에 끝난다). */
export const MAX_POLLS = 120;

export interface VoiceMarksOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
  /** 원문이 있어 결과를 기다릴 만한가(변환 중 · 원문 없음이면 false). 기본 false. */
  waiting?: boolean;
  /** 지금 보는 원문 판. 결과의 판이 이보다 낮으면 새 판을 잠시 기다린다. 모르면 null. */
  transcriptVersion?: number | null;
}

export interface VoiceMarksState {
  /** 가장 최근 결과. 아직 계산 전이면 null. */
  marks: VoiceMarks | null;
  loading: boolean;
  error: string | null;
  /** 기다리는 중인가(분석 전이거나 새 판을 기다리며 되풀이 조회 중). */
  waiting: boolean;
  reload: () => void;
  refresh: () => void;
}

export function useVoiceMarks(
  sessionId: string | null | undefined,
  { enabled = true, waiting = false, transcriptVersion = null }: VoiceMarksOptions = {},
): VoiceMarksState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<VoiceMarks | null>(
    key,
    voiceMarksApi.get,
    "음성 참고 표시를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  );
  const marks = remote.data;
  const stale =
    marks !== null &&
    transcriptVersion !== null &&
    marks.transcript_version !== null &&
    marks.transcript_version < transcriptVersion;
  const needs = waiting && remote.error === null && (marks === null || stale);

  // 되풀이 조회 횟수. 회차가 바뀌거나 기다릴 원문 판이 바뀌면 다시 센다.
  const polls = useRef(0);
  const target = `${key ?? ""}#${transcriptVersion ?? ""}`;
  const targetRef = useRef(target);

  useEffect(() => {
    if (targetRef.current !== target) {
      targetRef.current = target;
      polls.current = 0;
    }
  }, [target]);

  const active = needs && polls.current < MAX_POLLS;
  const { refresh } = remote;

  usePolling(
    active,
    () => {
      polls.current += 1;
      refresh();
    },
    remote.settled,
  );

  return {
    marks,
    loading: remote.loading,
    error: remote.error,
    waiting: active,
    reload: remote.reload,
    refresh: remote.refresh,
  };
}
