// 사례의 아이 앱(콩콩) 연결 · 받은 내용(API_CONTRACT 24절). 아이 답변을 보려고 30초마다 조용히 다시 받는다.

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { childApp as childAppApi } from "../api/endpoints";
import type { ChildAppCase, ChildAppInvite, ChildQuestionDeliver, ChildSilentDays } from "../api/types";
import { errorMessage, useRemote } from "./useRemote";

const REFRESH_MS = 30_000;
/** 확인 처리 뒤 위쪽 긴급 배너를 바로 다시 받게 알린다. */
export const CHILD_ALERT_TEXT = {
  ALERT: "아이가 급하다고 알렸어요.",
  RED_ANSWER: "아이 답변에 바로 확인할 내용이 있어요.",
  CONTACT_REQUEST: "아이가 연락을 요청했어요.",
  TEXT_ANSWER: "아이가 글을 남겼어요.",
  FOLLOWUP_ANSWER: "아이가 추가 질문에 답했어요.",
  FOLLOWUP_SKIPPED: "아이가 추가 질문에 답하기 어렵다고 했어요.",
  NOTE: "아이가 메시지를 보냈어요.",
  SCHEDULE_REQUEST: "아이가 다음 상담에 가기 어렵다고 알렸어요.",
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

  /** deliver "EVENING" 은 발송 예약(그날 저녁 시각부터 아이 앱에 보인다, 지났으면 바로 — API_CONTRACT 24절). */
  const sendQuestions = useCallback(
    (questionIds: string[], deliver?: ChildQuestionDeliver) =>
      run(async () => {
        if (caseId) await childAppApi.sendQuestions(caseId, questionIds, deliver);
      }, deliver === "EVENING" ? "발송 예약을 하지 못했습니다." : "질문을 보내지 못했습니다."),
    [caseId, run],
  );

  /** 응답 상태 '기준' 일수 바꾸기(5 · 7 · 10일). */
  const setSilentDays = useCallback(
    (days: ChildSilentDays) =>
      run(async () => {
        if (caseId) await childAppApi.setSilentDays(caseId, days);
      }, "기준을 바꾸지 못했습니다."),
    [caseId, run],
  );

  /** 발송 예약 취소. 예약 시각이 지나 이미 아이에게 보였으면 서버가 409 로 거절한다. */
  const cancelScheduled = useCallback(
    (questionSetId: string) =>
      run(async () => {
        if (caseId) await childAppApi.cancelScheduledQuestions(caseId, questionSetId);
      }, "발송 예약을 취소하지 못했습니다."),
    [caseId, run],
  );

  const [aiCreating, setAiCreating] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  useEffect(() => {
    setAiError(null);
  }, [caseId]);

  const createAiDraft = useCallback(async () => {
    if (!caseId) return;
    setAiCreating(true);
    setAiError(null);
    try {
      await childAppApi.createAiDraft(caseId);
      refresh();
    } catch (caught) {
      setAiError(errorMessage(caught, "AI 초안을 만들지 못했습니다."));
    } finally {
      setAiCreating(false);
    }
  }, [caseId, refresh]);

  const saveAiNote = useCallback(
    (draftId: string, questionId: string, text: string) =>
      run(async () => {
        if (caseId) await childAppApi.updateAiNote(caseId, draftId, questionId, text);
      }, "확인해 볼 점을 저장하지 못했습니다."),
    [caseId, run],
  );

  const saveAiQuestion = useCallback(
    (draftId: string, id: string, text: string, options: string[]) =>
      run(async () => {
        if (caseId) await childAppApi.updateAiQuestion(caseId, draftId, id, text, options);
      }, "추가 질문을 저장하지 못했습니다."),
    [caseId, run],
  );

  const setAiApproval = useCallback(
    (draftId: string, id: string, approved: boolean) =>
      run(async () => {
        if (caseId) await childAppApi.setAiApproval(caseId, draftId, id, approved);
      }, "승인을 바꾸지 못했습니다."),
    [caseId, run],
  );

  /** 아이 앱 연결 해지(담당 상담사). 그 기기는 바로 끊기고 답하지 않은 질문은 거둔다. 받은 답 · 알림은 남는다. */
  const unlink = useCallback(
    () =>
      run(async () => {
        if (caseId) await childAppApi.unlink(caseId);
      }, "앱 연동을 해지하지 못했습니다."),
    [caseId, run],
  );

  /** 코드 재발급(11/19 팀 요청): 연결된 사례면 지금 기기를 끊고 새 연결 코드를 만든다(서버는 연결된 사례에 코드를 주지 않는다 — 409). */
  const reissueInvite = useCallback(
    (linked: boolean) =>
      run(async () => {
        if (!caseId) return;
        if (linked) await childAppApi.unlink(caseId);
        try {
          setInvite(await childAppApi.invite(caseId));
        } catch (caught) {
          if (!linked) throw caught;
          // 해지는 됐는데 코드 만들기만 실패했다 — 아이 기기는 이미 끊겼으니 지금 상태를 알리고 화면을 '미연결' 로 맞춘다(민규 #187).
          refresh();
          throw new ApiError(
            "CHILD_APP_REISSUE_PARTIAL",
            "연결이 끊겼습니다. 새 코드를 만들지 못했으니 '연결 코드 만들기'로 코드를 다시 만들어 주세요.",
            caught instanceof ApiError ? caught.status : 0,
          );
        }
      }, "연결 코드를 다시 만들지 못했습니다."),
    [caseId, refresh, run],
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

  return { ...remote, invite, busy, actionError, aiCreating, aiError, createAiDraft, saveAiNote, saveAiQuestion, setAiApproval, createInvite, reissueInvite, sendQuestions, cancelScheduled, setSilentDays, acknowledge, unlink };
}
