// 관리자 · 사례 목록 훅(10/30 디자인 AdminCases). 관리자 전용 — 상담사 계정이면 서버를 부르지 않는다(adminKey).
//
//  - 사례: GET /cases 의 쪽을 모두 받는다(관리자는 기관 전체 사례가 온다. useAdminAccounts 의 loadAllCases).
//    검색 · 상담원 거르기는 받은 목록에서 화면이 한다(GET /cases 에 상담원 조건이 없다).
//  - 상담원: GET /auth/users. 상담원 필터(담당 사례가 없는 상담원도 보이게)와 '재배정 필요'(담당 상담원 비활성)에 쓴다.
//    계정 목록을 받지 못해도 사례 목록은 그대로 보인다(usersError 만 채움).

import { auth } from "../api/endpoints";
import type { Case, User } from "../api/types";
import { adminKey, type AdminAccess, type AdminHookOptions } from "./adminAccess";
import { loadAllCases } from "./useAdminAccounts";
import { useRemote } from "./useRemote";

export interface AdminCasesState {
  /** 기관 전체 사례(등록 최신순, 서버 순서 그대로). 아직 못 받았으면 null. */
  cases: Case[] | null;
  /** 계정 목록. 못 받았으면 null. */
  users: User[] | null;
  /** 사례 목록을 처음 받거나 다시 받는 중. */
  loading: boolean;
  /** 사례 목록을 받지 못한 이유. */
  error: string | null;
  /** 계정 목록을 받지 못한 이유(사례 목록은 그대로 보인다). */
  usersError: string | null;
  reload: () => void;
}

export function useAdminCases(access: AdminAccess, { enabled = true }: AdminHookOptions = {}): AdminCasesState {
  const cases = useRemote<Case[]>(
    adminKey(access, enabled, "cases:all"),
    loadAllCases,
    "사례 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );
  const users = useRemote<User[]>(
    adminKey(access, enabled, "cases:users"),
    auth.listUsers,
    "상담원 목록을 불러오지 못했습니다.",
    () => false,
  );

  return {
    cases: cases.data,
    users: users.data,
    loading: cases.loading,
    error: cases.error,
    usersError: users.error,
    reload: () => {
      cases.reload();
      users.reload();
    },
  };
}
