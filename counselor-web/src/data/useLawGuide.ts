// 법령 · 매뉴얼 AI 질문 훅(POST /law-guide/questions, API_CONTRACT 17절, #109).
//
// 질문 하나에 답 하나(대화 맥락 없음 — 서버 모듈이 이전 대화를 받지 않는다). 화면의 말풍선 목록은 여기서만 들고 있고
// 서버는 질문 · 답변을 저장하지 않는다. '새 대화' 는 목록만 비운다.
//  - 동기 응답이라 기다리는 동안 pending(화면은 '찾는 중' 점 세 개)이고, 한 번에 하나만 보낸다.
//  - 오류는 서버의 고정 문구(LAW_QA_DISABLED · RATE_LIMITED · AI_TIMEOUT · AI_FAILED · LAW_SOURCE_UNAVAILABLE 등)를
//    그대로 말풍선으로 보인다(문구에 질문 원문 · 내부 값이 없다).
//  - 새 대화를 누르거나 화면을 떠난 뒤 온 응답은 버린다(세대 번호).

import { useCallback, useEffect, useRef, useState } from "react";

import { lawGuide as lawGuideApi } from "../api/endpoints";
import type { LawSource, ManualSource } from "../api/types";
import { errorMessage } from "./useRemote";

/** 서버와 같은 질문 길이 상한(앞뒤 공백 뺀 뒤). */
export const QUESTION_MAX = 500;

export interface LawGuideMessage {
  id: number;
  role: "user" | "bot";
  text: string;
  laws: LawSource[];
  manual: ManualSource[];
  /** 오류 말풍선인가. */
  error: boolean;
}

export interface LawGuideState {
  messages: LawGuideMessage[];
  pending: boolean;
  /** 보낼 수 있으면 true(질문을 받으면 보낸다). */
  ask: (question: string) => Promise<boolean>;
  reset: () => void;
}

export function useLawGuide(): LawGuideState {
  const [messages, setMessages] = useState<LawGuideMessage[]>([]);
  const [pending, setPending] = useState(false);
  const generation = useRef(0);
  const nextId = useRef(1);
  const inFlight = useRef(false);

  useEffect(
    () => () => {
      // 화면을 떠나면 늦게 온 응답을 버린다.
      generation.current += 1;
    },
    [],
  );

  const push = useCallback((message: Omit<LawGuideMessage, "id">) => {
    const id = nextId.current;
    nextId.current += 1;
    setMessages((current) => [...current, { ...message, id }]);
  }, []);

  const ask = useCallback(
    async (raw: string) => {
      const question = raw.trim().slice(0, QUESTION_MAX);
      if (!question || inFlight.current) return false;

      const ticket = generation.current;
      inFlight.current = true;
      setPending(true);
      push({ role: "user", text: question, laws: [], manual: [], error: false });

      try {
        const answer = await lawGuideApi.ask(question);
        if (ticket !== generation.current) return true;
        push({
          role: "bot",
          text: answer.answer,
          laws: answer.sources?.laws ?? [],
          manual: answer.sources?.manual ?? [],
          error: false,
        });
      } catch (caught) {
        if (ticket !== generation.current) return true;
        push({
          role: "bot",
          text: errorMessage(caught, "답변을 받지 못했습니다. 잠시 후 다시 시도해 주세요."),
          laws: [],
          manual: [],
          error: true,
        });
      } finally {
        if (ticket === generation.current) {
          inFlight.current = false;
          setPending(false);
        }
      }

      return true;
    },
    [push],
  );

  const reset = useCallback(() => {
    generation.current += 1;
    inFlight.current = false;
    setPending(false);
    setMessages([]);
  }, []);

  return { messages, pending, ask, reset };
}
