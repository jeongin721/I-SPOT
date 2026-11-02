// 상담 기록 문서 회차 훅(GET /sessions/{id}/source-document, POST …/followups, API_CONTRACT 21절, 2026-11-02).
//
// 3단계(상담일지 작성)는 note_draft 를 상담 일지 초안으로, 4단계(다음 상담 준비)는 followup_draft 를 확인 사항 · 추가 질문
// 초안으로 쓴다. 4단계 초안은 3단계에 저장한 칸으로 만든다(draftFollowups — 동기, 1~2분). 문서 회차가 아니면 부르지 않는다.

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { sourceDocuments } from "../api/endpoints";
import type { SourceDocument } from "../api/types";
import { errorMessage, useRemote } from "./useRemote";

export interface SourceDocumentState {
  document: SourceDocument | null;
  loading: boolean;
  error: string | null;
  /** 4단계 초안을 만드는 중. */
  drafting: boolean;
  draftError: string | null;
  draftFollowups: () => Promise<boolean>;
}

export function useSourceDocument(sessionId: string | null | undefined, { enabled = true }: { enabled?: boolean } = {}): SourceDocumentState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<SourceDocument>(key, sourceDocuments.get, "올린 상담 기록 문서를 불러오지 못했습니다.");
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setDraftError(null);
    inFlight.current = false;
    setDrafting(false);
  }

  const draftFollowups = useCallback(async () => {
    const ticket = remote.capture();
    if (!ticket || inFlight.current) return false;
    inFlight.current = true;
    setDrafting(true);
    setDraftError(null);
    try {
      return remote.setData(ticket, await sourceDocuments.draftFollowups(ticket.key));
    } catch (caught) {
      if (remote.isCurrent(ticket) && !(caught instanceof ApiError && caught.isUnauthorized)) {
        setDraftError(errorMessage(caught, "다음 상담 준비 초안을 만들지 못했습니다. 잠시 후 다시 시도해 주세요."));
      }
      return false;
    } finally {
      if (remote.sameGeneration(ticket)) {
        inFlight.current = false;
        setDrafting(false);
      }
    }
  }, [remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration]);

  return {
    document: remote.data,
    loading: remote.loading,
    error: remote.error,
    drafting,
    draftError,
    draftFollowups,
  };
}
