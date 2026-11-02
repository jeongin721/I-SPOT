// 상담 기록 문서 올리기 훅(녹취 · 자료 올리기 '문서 파일', API_CONTRACT 20절, 2026-11-02).
//
//   (새 회차면) POST /cases/{id}/sessions → POST /sessions/{id}/source-document(동기 — 서버가 글자를 뽑고 AI 가 3단계 칸을 채운다)
//
// 끝나면 그 회차는 1 · 2단계 없이 3단계(상담 요약 · 상담 일지 검수)다. 실패한 뒤 다시 시도하면 **이미 만든 회차를 다시 쓴다**
// (useAudioUpload 와 같다 — 빈 회차가 쌓이지 않게). 진행률은 없고 단계 이름으로 보인다.

import { useCallback, useRef, useState } from "react";

import { cases, sourceDocuments } from "../api/endpoints";
import { checkDocumentFile } from "./documentFile";
import { notifySessionChanged } from "./sessionEvents";
import { errorMessage } from "./useRemote";

export type DocumentUploadPhase = "idle" | "creatingSession" | "reading" | "done" | "failed";

export const DOCUMENT_PHASE_LABELS: Record<DocumentUploadPhase, string> = {
  idle: "대기",
  creatingSession: "회차 만드는 중",
  reading: "문서를 읽고 상담일지 칸을 채우는 중(1~2분)",
  done: "완료",
  failed: "실패",
};

export interface DocumentUploadRequest {
  caseId: string;
  /** 이미 있는 빈 회차(CREATED). 없으면 새 회차를 만든다. */
  sessionId?: string | null;
  file: File;
}

export interface DocumentUploadState {
  phase: DocumentUploadPhase;
  phaseLabel: string;
  sessionId: string | null;
  error: string | null;
  busy: boolean;
  /** 다시 시도할 수 있는가(파일 검사에서 실패했으면 다시 할 것이 없다). */
  canRetry: boolean;
  start: (request: DocumentUploadRequest) => Promise<boolean>;
  retry: () => Promise<boolean>;
}

export function useDocumentUpload(): DocumentUploadState {
  const [phase, setPhase] = useState<DocumentUploadPhase>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [canRetry, setCanRetry] = useState(false);
  const last = useRef<{ request: DocumentUploadRequest; sessionId: string | null } | null>(null);
  const running = useRef(false);

  const run = useCallback(async (request: DocumentUploadRequest, knownSession: string | null): Promise<boolean> => {
    if (running.current) return false;
    running.current = true;
    setError(null);
    setCanRetry(false);

    const invalid = checkDocumentFile(request.file);
    if (invalid) {
      setError(invalid);
      setPhase("failed");
      running.current = false;
      return false;
    }

    let target = knownSession ?? request.sessionId ?? null;
    try {
      if (!target) {
        setPhase("creatingSession");
        target = (await cases.createSession(request.caseId, {})).id;
        setSessionId(target);
        last.current = { request, sessionId: target };
        notifySessionChanged({ sessionId: target, caseId: request.caseId });
      }
      setSessionId(target);
      last.current = { request, sessionId: target };
      setPhase("reading");
      await sourceDocuments.upload(target, request.file);
      notifySessionChanged({ sessionId: target, caseId: request.caseId });
      setPhase("done");
      return true;
    } catch (caught) {
      setError(errorMessage(caught, "문서를 올리지 못했습니다. 잠시 후 다시 시도해 주세요."));
      setCanRetry(true);
      setPhase("failed");
      return false;
    } finally {
      running.current = false;
    }
  }, []);

  const start = useCallback(
    (request: DocumentUploadRequest) => {
      last.current = { request, sessionId: request.sessionId ?? null };
      setSessionId(request.sessionId ?? null);
      return run(request, request.sessionId ?? null);
    },
    [run],
  );

  const retry = useCallback(() => {
    if (!last.current) return Promise.resolve(false);
    return run(last.current.request, last.current.sessionId);
  }, [run]);

  return {
    phase,
    phaseLabel: DOCUMENT_PHASE_LABELS[phase],
    sessionId,
    error,
    busy: phase === "creatingSession" || phase === "reading",
    canRetry,
    start,
    retry,
  };
}
