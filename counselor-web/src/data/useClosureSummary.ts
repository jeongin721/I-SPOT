// 종결 검토 요약 · 보고서 훅(GET · POST · PUT /cases/{id}/closure-summary, API_CONTRACT 4절, 2026-10-30).
//
// ① 핵심 요약(만들기 · 확인 체크 · 고친 문장)과 ② 종결보고서 칸(초기상황 · 종결상황 · 종합의견 · 날짜)이 같이 쓴다.
//  - 만들기는 동기 요청이다. AI 면 수십 초 걸릴 수 있어 generating 으로 단추를 멈춘다.
//  - 저장은 보낸 칸만 바뀐다. 서버 기록을 받기 전에는 저장하지 않는다.
// 추가 질문 · 확인 사항 훅(useFollowupChecks)과 같은 꼴이다(대상이 바뀌면 오류 · 보내는 중 표시를 지움).

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { cases } from "../api/endpoints";
import type { ClosureSummaryRecord, ClosureSummarySave } from "../api/types";
import { errorMessage, useRemote } from "./useRemote";

export interface ClosureSummaryState {
  record: ClosureSummaryRecord | null;
  loaded: boolean;
  loading: boolean;
  /** 만들기 · 저장 중. */
  busy: "generate" | "save" | null;
  error: string | null;
  loadError: string | null;
  generate: () => Promise<boolean>;
  save: (patch: ClosureSummarySave) => Promise<boolean>;
}

export function useClosureSummary(
  caseId: string | null | undefined,
  { enabled = true }: { enabled?: boolean } = {},
): ClosureSummaryState {
  const key = enabled && caseId ? caseId : null;
  const remote = useRemote<ClosureSummaryRecord>(
    key,
    cases.getClosureSummary,
    "종결 검토 기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  );
  const [busy, setBusy] = useState<ClosureSummaryState["busy"]>(null);
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setBusy(null);
  }

  const run = useCallback(
    async (kind: "generate" | "save", call: (caseKey: string) => Promise<ClosureSummaryRecord>, fallback: string) => {
      const ticket = remote.capture();

      if (!ticket || ticket.key !== key || inFlight.current) return false;

      inFlight.current = true;
      setBusy(kind);
      setActionError(null);

      try {
        return remote.setData(ticket, await call(ticket.key));
      } catch (caught) {
        if (!remote.isCurrent(ticket)) return false;
        if (!(caught instanceof ApiError && caught.isUnauthorized)) setActionError(errorMessage(caught, fallback));
        remote.refresh();
        return false;
      } finally {
        if (remote.sameGeneration(ticket)) {
          inFlight.current = false;
          setBusy(null);
        }
      }
    },
    [key, remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.refresh],
  );

  const generate = useCallback(
    () => run("generate", (caseKey) => cases.generateClosureSummary(caseKey), "종결 요약을 만들지 못했습니다. 잠시 후 다시 시도해 주세요."),
    [run],
  );
  const save = useCallback(
    (patch: ClosureSummarySave) =>
      run("save", (caseKey) => cases.saveClosureSummary(caseKey, patch), "저장하지 못했습니다. 잠시 후 다시 시도해 주세요."),
    [run],
  );

  return {
    record: remote.data,
    loaded: remote.data !== null,
    loading: remote.loading,
    busy,
    error: actionError ?? remote.error,
    loadError: remote.error,
    generate,
    save,
  };
}
