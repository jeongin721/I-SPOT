// 사례의 아이 앱(콩콩) 연결 · 받은 내용(API_CONTRACT 23절). 아이 답변을 보려고 30초마다 조용히 다시 받는다.

import { useCallback, useEffect, useState } from "react";

import { childApp as childAppApi } from "../api/endpoints";
import type { ChildAppCase, ChildAppInvite } from "../api/types";
import { errorMessage, useRemote } from "./useRemote";

const REFRESH_MS = 30_000;
/** 확인 처리 뒤 위쪽 긴급 배너를 바로 다시 받게 알린다. */
export const CHILD_ALERT_TEXT = {
  ALERT: "아이가 급하다고 알렸어요.",
  RED_ANSWER: "아이 답변에 바로 확인할 내용이 있어요.",
  CONTACT_REQUEST: "아이가 연락을 요청했어요.",
  TEXT_ANSWER: "아이가 글을 남겼어요.",
  NEEDS_CHECK: "아이 앱에서 확인이 필요한 알림이 왔어요.",
} as const;

export const CHILD_ALERTS_CHANGED = "ispot:child-alerts-changed";

export function useCaseChildApp(caseId: string | null, enabled: boolean) {
  const remote = useRemote<ChildAppCase>(
    enabled ? caseId : null,
    (key) => childAppApi.get(key),
    "아이 앱 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );
  const { refresh } = remote;
  const [invite, setInvite] = useState<ChildAppInvite | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setInvite(null);
    setActionError(null);
  }, [caseId]);

  useEffect(() => {
    if (!enabled || !caseId) return undefined;

    const timer = window.setInterval(refresh, REFRESH_MS);

    return () => window.clearInterval(timer);
  }, [enabled, caseId, refresh]);

  const run = useCallback(
    async (work: () => Promise<void>, fallback: string): Promise<boolean> => {
      setBusy(true);
      setActionError(null);

      try {
        await work();
        refresh();

        return true;
      } catch (caught) {
        setActionError(errorMessage(caught, fallback));

        return false;
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const createInvite = useCallback(
    () =>
      run(async () => {
        if (caseId) setInvite(await childAppApi.invite(caseId));
      }, "연결 코드를 만들지 못했습니다."),
    [caseId, run],
  );

  const sendQuestions = useCallback(
    (questionIds: string[]) =>
      run(async () => {
        if (caseId) await childAppApi.sendQuestions(caseId, questionIds);
      }, "질문을 보내지 못했습니다."),
    [caseId, run],
  );

  const acknowledge = useCallback(
    (alertId: string) =>
      run(async () => {
        if (!caseId) return;
        await childAppApi.acknowledgeAlert(caseId, alertId);
        window.dispatchEvent(new Event(CHILD_ALERTS_CHANGED));
      }, "확인 처리를 하지 못했습니다."),
    [caseId, run],
  );

  return { ...remote, invite, busy, actionError, createInvite, sendQuestions, acknowledge };
}
