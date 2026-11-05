// 기관 서식 작성 기록 훅(GET · POST · PATCH /cases/{id}/forms, API_CONTRACT 22절, 2026-11-02).
//
// 사례 하나의 서식 기록(서식 종류마다 차수 여러 개)을 불러오고, 서식 하나를 임시 저장 · 확정한다.
//  - 서식은 사례 단위다. 종류마다 임시 저장(DRAFT) 차수는 하나뿐이고, 확정(APPROVED)한 차수는 고칠 수 없다.
//  - 임시 저장: 임시 저장 차수가 있으면 그 차수를 고치고(PATCH), 없으면 다음 차수를 만든다(POST).
//  - 확정: 먼저 임시 저장한 뒤 그 차수를 확정한다. 확정을 푸는 API 는 없다 — 다시 쓰면 다음 차수가 된다.
//  - 칸 값은 상담사가 고른 · 쓴 것만 보낸다. AI 가 칸을 채우지 않는다. 합계는 서버 totals · 화면 계산.
//  - 서버 목록을 받기 전에는 저장하지 않는다(임시 저장 차수가 있는지 몰라 차수를 하나 더 열지 않게).
//  - 저장 직전에 서버 최신 기록을 다시 보고, 다른 창에서 바뀌었으면 저장하지 않는다(오래된 창이 최신 값을 덮어 확정하지 않게).

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { caseForms as formsApi } from "../api/endpoints";
import type { CaseForm, CaseFormType } from "../api/types";
import { errorMessage, useRemote } from "./useRemote";

export interface CaseFormsOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export type SaveResult = "saved" | "conflict" | "failed";

export interface CaseFormsState {
  /** 서식 기록 전부(종류 → 차수가 큰 것부터). 받기 전이면 []. */
  items: CaseForm[];
  loaded: boolean;
  loading: boolean;
  submitting: boolean;
  /** 저장 · 확정 실패 문구가 먼저, 없으면 조회 실패 문구. */
  error: string | null;
  loadError: string | null;
  /**
   * 임시 저장(confirm=false) 또는 임시 저장 뒤 확정(confirm=true). "saved" 성공, "conflict" 다른 창이 먼저 바꿈(409 — 최신 기록을
   * 다시 받는다), "failed" 그 밖 실패 · 보내지 않음.
   */
  save: (formType: CaseFormType, values: object, confirm: boolean) => Promise<SaveResult>;
  reload: () => void;
}

/** 그 종류의 차수들(차수가 큰 것부터). */
export function formRounds(items: CaseForm[], formType: CaseFormType): CaseForm[] {
  return items.filter((item) => item.form_type === formType).sort((a, b) => b.round - a.round);
}

/** 화면이 열어 보일 차수: 임시 저장 차수, 없으면 가장 최근 확정 차수, 없으면 null. */
export function currentForm(items: CaseForm[], formType: CaseFormType): CaseForm | null {
  const rounds = formRounds(items, formType);
  return rounds.find((item) => item.status === "DRAFT") ?? rounds[0] ?? null;
}

/** 가장 최근 확정 차수(없으면 null). */
export function lastConfirmed(items: CaseForm[], formType: CaseFormType, before?: number): CaseForm | null {
  return (
    formRounds(items, formType).find(
      (item) => item.status === "APPROVED" && (before === undefined || item.round < before),
    ) ?? null
  );
}

function merge(items: CaseForm[], row: CaseForm): CaseForm[] {
  return [row, ...items.filter((item) => item.id !== row.id)];
}

export function useCaseForms(
  caseId: string | null | undefined,
  { enabled = true }: CaseFormsOptions = {},
): CaseFormsState {
  const key = enabled && caseId ? caseId : null;
  const remote = useRemote<{ items: CaseForm[] }>(
    key,
    formsApi.list,
    "서식 작성 기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );
  const [submitting, setSubmitting] = useState(false);
  // 같은 순간의 두 번째 누름을 막는다(임시 저장 차수가 둘 생기려다 409 가 나지 않게).
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  // 대상(사례)이 바뀌면 앞 사례의 오류 · 보내는 중 표시를 지운다.
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setSubmitting(false);
  }

  const save = useCallback(
    async (formType: CaseFormType, values: object, confirm: boolean): Promise<SaveResult> => {
      const ticket = remote.capture();

      if (!ticket || ticket.key !== key || inFlight.current || remote.data === null) return "failed";

      inFlight.current = true;
      setSubmitting(true);
      setActionError(null);

      try {
        // 다른 창에서 이 서식을 먼저 저장 · 확정했으면 덮어쓰지 않는다(Codex #140 H2 · H3) — 이 창이 본 임시 저장 차수의 판(version)을
        // 보내고, 서버가 그 판일 때만 바꾼다(아니면 409 STALE_VERSION · ALREADY_APPROVED → 아래에서 최신 기록을 다시 받는다).
        // 본 임시 저장 차수가 없으면 새 차수를 만든다(다른 창이 먼저 만들었으면 409 DUPLICATE_RESOURCE).
        const draft = formRounds(remote.data.items, formType).find((item) => item.status === "DRAFT");
        let row = draft
          ? await formsApi.update(ticket.key, draft.id, values, draft.version)
          : await formsApi.create(ticket.key, formType, values);

        if (!remote.isCurrent(ticket)) return "failed";
        remote.setData(ticket, (current) => ({ items: merge(current?.items ?? [], row) }));

        if (confirm) {
          row = await formsApi.confirm(ticket.key, row.id, row.version);
          if (!remote.isCurrent(ticket)) return "failed";
          remote.setData(ticket, (current) => ({ items: merge(current?.items ?? [], row) }));
        }

        return "saved";
      } catch (caught) {
        if (!remote.isCurrent(ticket)) return "failed";

        // 409(다른 창이 먼저 저장 · 확정 · 만듦)는 "conflict" 로 돌려주고 화면이 고친 칸을 버린 뒤 안내한다. 아래에서 최신 기록을 다시 받는다.
        const conflict = caught instanceof ApiError && caught.status === 409;
        if (!conflict && !(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, "서식을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }

        // 다른 창에서 먼저 저장 · 확정했을 수 있다. 최신 기록을 다시 받는다.
        remote.refresh();

        return conflict ? "conflict" : "failed";
      } finally {
        if (remote.sameGeneration(ticket)) {
          inFlight.current = false;
          setSubmitting(false);
        }
      }
    },
    [key, remote.data, remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.refresh],
  );

  return {
    items: remote.data?.items ?? [],
    loaded: remote.data !== null,
    loading: remote.loading,
    submitting,
    error: actionError ?? remote.error,
    loadError: remote.error,
    save,
    reload: remote.reload,
  };
}
