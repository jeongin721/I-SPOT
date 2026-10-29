// 승인한 추가 질문 훅(GET · PUT /sessions/{id}/followup-questions, API_CONTRACT 18절).
//
// 상담사가 승인 · 고친 · 직접 쓴 질문 목록을 불러오고 통째로 저장한다. AI 초안은 분석 결과(followup_questions)에 따로 있고
// 여기에는 승인한 것만 있다.
//  - 저장은 목록 전체를 바꾼다. 서버 목록을 한 번이라도 받기 전에는 저장하지 않는다(모르는 질문을 지우지 않게).
//  - 원문 확정 뒤(STT_CONFIRMED · AI_REVIEW_REQUIRED · AI_FAILED · APPROVED)에만 저장된다. 그 밖에는 409 문구를 보여 준다.
//  - 저장해도 회차 상태는 바뀌지 않는다.

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { followupQuestions as questionsApi } from "../api/endpoints";
import type { FollowupQuestion, FollowupQuestionInput, FollowupQuestionList } from "../api/types";
import { errorMessage, useRemote } from "./useRemote";

/** Backend 제한(API_CONTRACT 18절). */
export const FOLLOWUP_QUESTIONS_MAX = 20;
export const FOLLOWUP_QUESTION_TEXT_MAX = 300;

export interface FollowupQuestionsOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface FollowupQuestionsState {
  /** 승인한 질문(보낸 순서). 받기 전이면 []. */
  questions: FollowupQuestion[];
  /** 서버 목록을 한 번이라도 받았는가. 화면은 이 값이 true 이고 loadError 가 없을 때만 저장 단추를 켠다. */
  loaded: boolean;
  submitting: boolean;
  loading: boolean;
  /** 저장 실패 또는 조회 실패 문구. */
  error: string | null;
  loadError: string | null;
  /** 목록 전체를 저장한다. 성공하면 true. */
  save: (questions: FollowupQuestionInput[]) => Promise<boolean>;
  reload: () => void;
}

/** 저장 전에 걸러 낼 문제가 있으면 그 문장, 없으면 null. 서버가 최종으로 거절한다(422). */
export function checkFollowupQuestions(questions: FollowupQuestionInput[]): string | null {
  if (questions.length > FOLLOWUP_QUESTIONS_MAX) return `추가 질문은 ${FOLLOWUP_QUESTIONS_MAX}개까지 승인할 수 있습니다.`;

  for (const question of questions) {
    const text = question.text.trim();

    if (!text) return "질문 문장이 비어 있습니다.";
    // 서버(파이썬 len)처럼 코드 포인트로 센다.
    if (Array.from(text).length > FOLLOWUP_QUESTION_TEXT_MAX) {
      return `질문 문장은 ${FOLLOWUP_QUESTION_TEXT_MAX}자까지 쓸 수 있습니다.`;
    }
  }

  return null;
}

export function useFollowupQuestions(
  sessionId: string | null | undefined,
  { enabled = true }: FollowupQuestionsOptions = {},
): FollowupQuestionsState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<FollowupQuestionList>(
    key,
    questionsApi.get,
    "추가 질문을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
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
    async (questions: FollowupQuestionInput[]): Promise<boolean> => {
      const ticket = remote.capture();

      if (!ticket || ticket.key !== key || inFlight.current) return false;

      const problem = checkFollowupQuestions(questions);

      if (problem) {
        setActionError(problem);
        return false;
      }

      inFlight.current = true;
      setSubmitting(true);
      setActionError(null);

      try {
        const result = await questionsApi.save(
          ticket.key,
          questions.map((question) => ({ ...question, text: question.text.trim() })),
        );

        return remote.setData(ticket, result);
      } catch (caught) {
        if (!remote.isCurrent(ticket)) return false;

        if (!(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, "추가 질문을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."));
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
    questions: remote.data?.questions ?? [],
    loaded: remote.data !== null,
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    loadError: remote.error,
    save,
    reload: remote.reload,
  };
}
