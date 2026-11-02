// 다음 상담 전 확인할 사항 훅(GET · PUT /sessions/{id}/followup-checks, API_CONTRACT 18.1절, 2026-10-30).
//
// 상담사가 고친 · 직접 쓴 · 브리핑에 넣기로 고른 확인 사항 목록을 불러오고 통째로 저장한다. AI 확인 메모 초안은 분석 결과
// (followup_check_points)에 따로 있고, 한 번 저장하면(saved) 이 목록이 그 회차의 확인 사항이다. 추가 질문 훅과 같은 꼴이다.
//  - 저장은 목록 전체를 바꾼다. 서버 목록을 한 번이라도 받기 전에는 저장하지 않는다(모르는 질문을 지우지 않게).
//  - 원문 확정 뒤(STT_CONFIRMED · AI_REVIEW_REQUIRED · AI_FAILED · APPROVED)에만 저장된다. 그 밖에는 409 문구를 보여 준다.
//  - 저장해도 회차 상태는 바뀌지 않는다.

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { followupChecks as checksApi } from "../api/endpoints";
import type { FollowupCheck, FollowupCheckList } from "../api/types";
import { errorMessage, useRemote } from "./useRemote";

/** Backend 제한(API_CONTRACT 18.1절). */
export const FOLLOWUP_CHECKS_MAX = 20;
export const FOLLOWUP_CHECK_TEXT_MAX = 300;

export interface FollowupChecksOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface FollowupChecksState {
  /** 저장한 확인 사항(보낸 순서). 받기 전 · 저장 전이면 []. */
  items: FollowupCheck[];
  /** 한 번이라도 저장했는가. */
  saved: boolean;
  /** 서버 목록을 받았는가. 화면은 이 값이 true 이고 loadError 가 없을 때만 저장한다. */
  loaded: boolean;
  submitting: boolean;
  loading: boolean;
  error: string | null;
  loadError: string | null;
  save: (items: FollowupCheck[]) => Promise<boolean>;
  reload: () => void;
}

/** 저장 전에 걸러 낼 문제가 있으면 그 문장, 없으면 null. 서버가 최종으로 거절한다(422). */
export function checkFollowupChecks(items: FollowupCheck[]): string | null {
  if (items.length > FOLLOWUP_CHECKS_MAX) return `확인 사항은 ${FOLLOWUP_CHECKS_MAX}개까지 둘 수 있습니다.`;

  for (const item of items) {
    const text = item.text.trim();
    if (!text) return "확인 사항 문장이 비어 있습니다.";
    if (Array.from(text).length > FOLLOWUP_CHECK_TEXT_MAX) return `확인 사항은 ${FOLLOWUP_CHECK_TEXT_MAX}자까지 쓸 수 있습니다.`;
  }

  return null;
}

export function useFollowupChecks(
  sessionId: string | null | undefined,
  { enabled = true }: FollowupChecksOptions = {},
): FollowupChecksState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<FollowupCheckList>(
    key,
    checksApi.get,
    "확인 사항을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  );
  const [submitting, setSubmitting] = useState(false);
  // 같은 순간의 두 번째 누름을 막는다.
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  // 대상이 바뀌면 앞 대상의 오류 · 보내는 중 표시를 지운다(useOverallRiskAssessment 와 같다).
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setSubmitting(false);
  }

  const save = useCallback(
    async (items: FollowupCheck[]): Promise<boolean> => {
      const ticket = remote.capture();

      if (!ticket || ticket.key !== key || inFlight.current) return false;

      const problem = checkFollowupChecks(items);

      if (problem) {
        setActionError(problem);
        return false;
      }

      inFlight.current = true;
      setSubmitting(true);
      setActionError(null);

      try {
        const result = await checksApi.save(
          ticket.key,
          items.map((item) => ({ ...item, text: item.text.trim() })),
        );

        return remote.setData(ticket, result);
      } catch (caught) {
        if (!remote.isCurrent(ticket)) return false;

        if (!(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, "확인 사항을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }

        // 다른 창에서 먼저 저장했을 수 있다. 최신 목록을 다시 받는다.
        remote.refresh();

        return false;
      } finally {
        if (remote.sameGeneration(ticket)) {
          inFlight.current = false;
          setSubmitting(false);
        }
      }
    },
    [key, remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.refresh],
  );

  return {
    items: remote.data?.items ?? [],
    saved: remote.data?.saved ?? false,
    loaded: remote.data !== null,
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    loadError: remote.error,
    save,
    reload: remote.reload,
  };
}
