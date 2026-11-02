// 가입 신청 목록 훅(관리자 전용, API_CONTRACT 3절 '회원가입'). 상담사 계정 관리 화면이 대기(PENDING) 신청을 보이고
// 역할을 골라 승인하거나 거절한다. 승인하면 신청 때 비밀번호 그대로 계정이 생긴다.
//
// - 오래된 신청부터 한 쪽(100건)만 받는다. 대기 신청은 14일 뒤 서버가 지운다.
// - 요청은 한 번에 하나다. 끝나면 목록을 다시 받고 다른 관리자 훅(대시보드 · 접속 기록)에 알린다(adminEvents).
// - 두 관리자가 같은 신청을 동시에 누르면 하나만 된다(409 SIGNUP_ALREADY_DECIDED). 그때도 목록을 다시 받는다.

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { signup } from "../api/endpoints";
import type { Paged, SignupRequestItem, UserRole } from "../api/types";
import { adminKey, type AdminAccess, type AdminHookOptions } from "./adminAccess";
import { notifyAccountsChanged } from "./adminEvents";
import { errorMessage, useRemote } from "./useRemote";

const PAGE_SIZE = 100;

const EMPTY: Paged<SignupRequestItem> = { items: [], meta: { page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 0 } };

// 회원가입 창구가 없는 Backend(404)면 빈 목록으로 본다 — 칸을 숨기고 오류도 띄우지 않는다.
const loadPending = () =>
  signup.list({ status: "PENDING", page: 1, page_size: PAGE_SIZE }).catch((caught) => {
    if (caught instanceof ApiError && caught.status === 404) return EMPTY;
    throw caught;
  });

export interface SignupRequestsState {
  items: SignupRequestItem[];
  /** 대기 신청 전체 수(한 쪽보다 많을 수 있다). */
  total: number;
  loading: boolean;
  error: string | null;
  /** 요청 중인 신청 ID. */
  busyId: string | null;
  actionError: string | null;
  /** 성공하면 true. */
  approve: (requestId: string, role: UserRole) => Promise<boolean>;
  reject: (requestId: string) => Promise<boolean>;
  reload: () => void;
}

export function useSignupRequests(access: AdminAccess, { enabled = true }: AdminHookOptions = {}): SignupRequestsState {
  const key = adminKey(access, enabled, "signupRequests");
  const list = useRemote<Paged<SignupRequestItem>>(
    key,
    loadPending,
    "가입 신청 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );
  const [busy, setBusy] = useState<{ key: string; id: string } | null>(null);
  const inFlight = useRef<string | null>(null);
  const [actionError, setActionError] = useState<{ key: string | null; message: string } | null>(null);

  const perform = useCallback(
    async (requestId: string, send: () => Promise<unknown>, fallback: string) => {
      const ticket = list.capture();

      if (!key || !ticket || inFlight.current === key) return false;

      inFlight.current = key;
      setBusy({ key, id: requestId });
      setActionError(null);

      try {
        await send();
        if (list.isCurrent(ticket)) notifyAccountsChanged();

        return list.isCurrent(ticket);
      } catch (caught) {
        if (list.isCurrent(ticket)) setActionError({ key, message: errorMessage(caught, fallback) });

        return false;
      } finally {
        inFlight.current = null;
        setBusy(null);
        // 성공 · 실패 모두 다시 받는다(다른 관리자가 먼저 처리했거나 보관 기한으로 지워졌을 수 있다).
        list.resync(ticket);
      }
    },
    [key, list],
  );

  const approve = useCallback(
    (requestId: string, role: UserRole) =>
      perform(requestId, () => signup.approve(requestId, role), "승인하지 못했습니다. 잠시 후 다시 시도해 주세요."),
    [perform],
  );

  const reject = useCallback(
    (requestId: string) =>
      perform(requestId, () => signup.reject(requestId), "거절하지 못했습니다. 잠시 후 다시 시도해 주세요."),
    [perform],
  );

  return {
    items: list.data?.items ?? [],
    total: list.data?.meta.total ?? 0,
    loading: list.loading,
    error: list.error,
    busyId: busy && busy.key === key ? busy.id : null,
    actionError: actionError && actionError.key === key ? actionError.message : null,
    approve,
    reject,
    reload: list.reload,
  };
}
