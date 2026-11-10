// 다음 상담 체크리스트 훅(GET · POST /sessions/{id}/followup-checklist, API_CONTRACT 19절).
//
// rag 로 만든 '다음 상담 전 확인할 사항' 과 추가 질문 AI 초안에 붙인 공식 근거(검토 통과분만)를 받는다.
//  - 서버가 꺼져 있으면(enabled=false) 아무것도 보이지 않는다(화면은 AI 확인 메모만).
//  - 응답은 늘 { enabled, checklist } 객체라 '받았는데 체크리스트 없음(null)' 과 '아직 못 받음' 이 섞이지 않는다
//    (닫힌 #117 교차검증 R2 — data:null 을 영구 로딩으로 보아 첫 만들기 단추가 막혔다).
//  - 만드는 중(PROCESSING)이거나 분석이 처리 중(watch)이면 되풀이 조회한다. 분석이 끝나면 서버가 같은 작업 안에서 바로
//    만들기를 시작하므로, watch 가 꺼진 직후 잠깐(GRACE_POLLS 번) 더 조회해 '아직 없음' 으로 멈추지 않게 한다.
//  - run() 은 만들기 · 다시 만들기(POST). 이미 만드는 중이면 서버가 그 행을 그대로 돌려준다.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { followupChecklist as checklistApi } from "../api/endpoints";
import type { FollowupChecklist, FollowupChecklistEnvelope } from "../api/types";
import { errorMessage, usePolling, useRemote } from "./useRemote";

/** 분석이 끝난 뒤 체크리스트 행이 생길 때까지 더 조회하는 횟수(POLL_INTERVAL_MS 간격). */
export const GRACE_POLLS = 4;

export interface FollowupChecklistOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
  /** 분석이 처리 중인가. 그동안 되풀이 조회하고, 끝나면 잠깐 더 조회한다. */
  watch?: boolean;
}

export interface FollowupChecklistState {
  /** 서버 응답을 한 번이라도 받았는가. */
  loaded: boolean;
  /** 서버에서 켜져 있는가. 받기 전이면 false. */
  enabled: boolean;
  /** 만든 적이 없으면 null. */
  checklist: FollowupChecklist | null;
  /** 분석이 끝난 직후 행이 생기기를 기다리는 중인가(이때는 '아직 없음' 대신 '기다리는 중'). */
  waiting: boolean;
  submitting: boolean;
  /** 만들기 실패 또는 조회 실패 문구. */
  error: string | null;
  run: () => Promise<boolean>;
  reload: () => void;
}

export function useFollowupChecklist(
  sessionId: string | null | undefined,
  { enabled = true, watch = false }: FollowupChecklistOptions = {},
): FollowupChecklistState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<FollowupChecklistEnvelope>(
    key,
    checklistApi.get,
    "다음 상담 체크리스트를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  );
  const [submitting, setSubmitting] = useState(false);
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);
  const [grace, setGrace] = useState(0);
  const previousWatch = useRef(watch);

  // 대상이 바뀌면 앞 대상의 오류 · 보내는 중 표시를 지운다(useFollowupQuestions 와 같다).
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setSubmitting(false);
    setGrace(0);
  }

  const checklist = remote.data?.checklist ?? null;
  const hasRow = checklist !== null;
  const { refresh, settled } = remote;

  // 분석이 막 끝났다: 서버가 같은 작업 안에서 만들기를 시작하므로 행이 생길 때까지 잠깐 더 조회한다.
  useEffect(() => {
    if (previousWatch.current && !watch) {
      setGrace(GRACE_POLLS);
      refresh();
    }
    previousWatch.current = watch;
  }, [watch, refresh]);

  // 조회가 끝날 때마다 남은 횟수를 줄인다. 행이 생겼으면 그만 기다린다.
  useEffect(() => {
    setGrace((left) => (left > 0 ? (hasRow ? 0 : left - 1) : left));
  }, [settled, hasRow]);

  const processing = checklist?.status === "PROCESSING";
  const waiting = grace > 0 && checklist === null && Boolean(remote.data?.enabled);

  usePolling(key !== null && (processing || watch || waiting), remote.refresh, remote.settled);

  const run = useCallback(async (): Promise<boolean> => {
    const ticket = remote.capture();

    if (!ticket || ticket.key !== key || inFlight.current) return false;

    inFlight.current = true;
    setSubmitting(true);
    setActionError(null);

    try {
      const row = await checklistApi.create(ticket.key);

      return remote.setData(ticket, (current) => ({ enabled: current?.enabled ?? true, checklist: row }));
    } catch (caught) {
      if (!remote.isCurrent(ticket)) return false;

      if (!(caught instanceof ApiError && caught.isUnauthorized)) {
        setActionError(errorMessage(caught, "다음 상담 체크리스트를 만들지 못했습니다. 잠시 후 다시 시도해 주세요."));
      }

      remote.refresh();

      return false;
    } finally {
      if (remote.sameGeneration(ticket)) {
        inFlight.current = false;
        setSubmitting(false);
      }
    }
  }, [key, remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.refresh]);

  return {
    loaded: remote.data !== null,
    enabled: remote.data?.enabled ?? false,
    checklist,
    waiting,
    submitting,
    error: actionError ?? remote.error,
    run,
    reload: remote.reload,
  };
}
