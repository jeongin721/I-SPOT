// 상담사 앱(폰) · 업로드 › 자료 올리기 '문서'(2026-11-19, 경진 결정).
//
// 폰에서 올린 상담 기록 문서는 녹음처럼 웹의 분석 · 상담일지로 넘어간다 — 웹 '녹취 · 자료 올리기' 의 문서 파일과 같은 서버 창구
// (API_CONTRACT 21절): 새 회차 → POST /sessions/{id}/source-document(동기, 서버가 글자를 뽑고 AI 가 상담 요약 · 일지 칸을 채움 1~2분)
// → 웹에서 그 회차를 열어 검수 · 승인. 서버는 원본 파일을 저장하지 않는다(뽑은 글만).
//
//  - 폰에는 파일을 남기지 않는다(녹음 대기열과 달리 IndexedDB 에 넣지 않음). 이 화면에 있는 동안만 목록에 보이고,
//    올리는 중에 앱을 닫으면 서버가 이어서 처리할 수도, 아닐 수도 있다 — 화면에 '이 화면에서 기다려 주세요' 를 보인다.
//  - 한 번에 하나씩 차례로 올린다(서버가 회차마다 · 서버 전체에서 동시에 읽는 수를 제한한다).
//  - 실패하면 '다시 올리기' 는 이미 만든 회차를 다시 쓴다(빈 회차가 쌓이지 않게, useDocumentUpload 와 같음).
//    파일 문제(형식 · 크기 · 글자 없음 422)는 다시 올려도 같으므로 '지우기' 만 보인다.

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { cases, sourceDocuments } from "../api/endpoints";
import { checkDocumentFile } from "./documentFile";
import { notifySessionChanged } from "./sessionEvents";
import { errorMessage } from "./useRemote";

export type AppDocStatus = "wait" | "run" | "done" | "fail";

export interface AppDocItem {
  id: string;
  caseId: string;
  childLabel: string;
  fileName: string;
  size: number;
  status: AppDocStatus;
  error: string | null;
  /** 파일 탓이 아닌 실패(연결 · 서버 · 시간 초과)라 다시 올릴 수 있는가. */
  canRetry: boolean;
  sessionId: string | null;
  sessionNumber: number | null;
  createdAt: number;
  updatedAt: number;
}

export interface AppDocuments {
  items: AppDocItem[];
  add: (input: { caseId: string; childLabel: string; file: File }) => string | null;
  retry: (id: string) => void;
  remove: (id: string) => void;
}

let seq = 0;

export function useAppDocuments(): AppDocuments {
  const [items, setItems] = useState<AppDocItem[]>([]);
  const files = useRef(new Map<string, File>());
  const queue = useRef<string[]>([]);
  const running = useRef(false);
  const state = useRef<AppDocItem[]>([]);

  const patch = useCallback((id: string, next: Partial<AppDocItem>) => {
    state.current = state.current.map((item) => (item.id === id ? { ...item, ...next, updatedAt: Date.now() } : item));
    setItems(state.current);
  }, []);

  const pump = useCallback(async () => {
    if (running.current) return;
    running.current = true;

    try {
      while (queue.current.length > 0) {
        const id = queue.current.shift() as string;
        const item = state.current.find((x) => x.id === id);
        const file = files.current.get(id);

        if (!item || !file) continue;

        patch(id, { status: "run", error: null });
        let sessionId = item.sessionId;

        try {
          if (!sessionId) {
            const created = await cases.createSession(item.caseId, {});
            sessionId = created.id;
            patch(id, { sessionId, sessionNumber: created.session_number });
            notifySessionChanged({ sessionId, caseId: item.caseId });
          }

          await sourceDocuments.upload(sessionId, file);
          notifySessionChanged({ sessionId, caseId: item.caseId });
          files.current.delete(id);
          patch(id, { status: "done" });
        } catch (caught) {
          // 422 는 파일 문제 — 다시 올려도 같다.
          const fileProblem = caught instanceof ApiError && caught.status === 422;
          patch(id, {
            status: "fail",
            canRetry: !fileProblem,
            error: errorMessage(caught, "문서를 올리지 못했어요. 연결을 확인하고 다시 올려 주세요."),
          });
          if (fileProblem) files.current.delete(id);
        }
      }
    } finally {
      running.current = false;
    }
  }, [patch]);

  const add = useCallback(
    ({ caseId, childLabel, file }: { caseId: string; childLabel: string; file: File }): string | null => {
      const problem = checkDocumentFile(file);
      if (problem) return problem;

      seq += 1;
      const id = `doc-${Date.now()}-${seq}`;
      const now = Date.now();

      files.current.set(id, file);
      state.current = [
        { id, caseId, childLabel, fileName: file.name, size: file.size, status: "wait", error: null, canRetry: false, sessionId: null, sessionNumber: null, createdAt: now, updatedAt: now },
        ...state.current,
      ];
      setItems(state.current);
      queue.current.push(id);
      void pump();

      return null;
    },
    [pump],
  );

  const retry = useCallback(
    (id: string) => {
      if (!files.current.has(id)) return;
      patch(id, { status: "wait", error: null });
      queue.current.push(id);
      void pump();
    },
    [patch, pump],
  );

  const remove = useCallback((id: string) => {
    files.current.delete(id);
    queue.current = queue.current.filter((x) => x !== id);
    state.current = state.current.filter((x) => x.id !== id);
    setItems(state.current);
  }, []);

  return { items, add, retry, remove };
}
