// 관리자 훅(useAdmin* · useAuditLogs)의 공통 입구.
//
// 관리자 API(/auth/users · /auth/audit-logs)는 상담사가 부르면 403 이다. 화면이 { enabled } 를 빠뜨려도 상담사 계정으로
// 서버를 부르지 않도록, 관리자 훅은 useAuthSession() 의 결과를 첫 인자로 받아 isAdmin 이 아니면 부르지 않는다.
//
//   const session = useAuthSession();
//   const dashboard = useAdminDashboard(session);
//
// 불러온 값은 관리자 계정마다 따로다(key 에 계정 ID). 로그아웃하거나 다른 계정으로 바뀌면 앞 값을 바로 비우고,
// 늦게 온 앞 계정의 응답은 버린다(useRemote).

import type { User } from "../api/types";

/** useAuthSession() 의 결과를 그대로 넘긴다. */
export interface AdminAccess {
  isAdmin: boolean;
  me: User | null;
}

export interface AdminHookOptions {
  /** false 면 부르지 않는다(관리자라도 그 칸을 아직 그리지 않을 때). 기본 true. */
  enabled?: boolean;
}

/** 관리자이고 enabled 면 useRemote 에 넘길 key, 아니면 null(부르지 않음). */
export function adminKey(access: AdminAccess, enabled: boolean, name: string): string | null {
  return access.isAdmin && enabled && access.me ? `${access.me.id}:${name}` : null;
}
