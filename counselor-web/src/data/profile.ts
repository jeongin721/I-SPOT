// 내 정보(GET /auth/me 의 User) → 설정 화면의 계정 칸.
//
// 설정 화면은 useAuthSession().me 를 이 함수로 바꿔 그리고, 비밀번호 변경은 usePasswordChange 를 그대로 쓴다
// (현재 비밀번호를 넣고 바꾸는 방식. 성공하면 서버가 토큰을 모두 끊어 다시 로그인하게 된다).
// /auth/me 는 useAuthSession 이 이미 부르므로 여기서 다시 부르지 않는다.
//
// Backend 에 없는 값은 NOT_PROVIDED 로 둔다(팀 결정 — 일정 · 인증 · 알림):
//  - 기관 이름, 알림 설정
//  - 마지막 비밀번호 변경일: DB 에는 있지만(users.password_changed_at) 응답(UserResponse)에 없다. 내보내려면 계약 변경이다
//  - 이름 · 이메일 바꾸기(본인이 바꾸는 API 가 없다. 이름은 관리자만 바꾼다)
//  - '재설정 링크 30분' 메일 발송(기존 결정은 이메일 임시 코드 3분이고 아직 구현 전)

import type { User, UserRole } from "../api/types";
import { NOT_PROVIDED } from "./caseRows";
import { toDateOnly, toDateTime } from "./time";

export const ROLE_LABELS: Record<UserRole, string> = {
  COUNSELOR: "상담원",
  ADMIN: "관리자",
};

export interface ProfileView {
  name: string;
  email: string;
  role: UserRole;
  roleLabel: string;
  /** 계정을 만든 날짜. */
  joinedDate: string;
  /** 최근 로그인 일시. 로그인할 때 바뀌므로 보통 지금 로그인한 시각이다('지난 접속' 이 아니다). 없으면 NOT_PROVIDED. */
  lastLoginAt: string;
  /** 임시 비밀번호라 바꿔야 하는가. */
  mustChangePassword: boolean;
  /** Backend 에 없는 값. 팀 결정 전까지 항상 NOT_PROVIDED. */
  organization: string;
  /** Backend 에 없는 값. 팀 결정 전까지 항상 NOT_PROVIDED. */
  passwordChangedAt: string;
}

export function toProfileView(user: User): ProfileView {
  return {
    name: user.name,
    email: user.email,
    role: user.role,
    roleLabel: ROLE_LABELS[user.role] ?? user.role,
    joinedDate: toDateOnly(user.created_at),
    lastLoginAt: toDateTime(user.last_login_at) || NOT_PROVIDED,
    mustChangePassword: user.must_change_password ?? false,
    organization: NOT_PROVIDED,
    passwordChangedAt: NOT_PROVIDED,
  };
}
