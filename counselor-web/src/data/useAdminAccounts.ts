// 상담사 계정 관리 훅(관리자 전용). ispotvscode/src/admin/AdminApp.tsx 의 AccountsView · AccountDialogs 에서 옮겨 왔다.
//
//  - 목록: GET /auth/users(관리자 포함 전체) + 담당 사례 수(GET /cases 전체 페이지를 받아 셈. 실패해도 목록은 보인다)
//  - 등록: 아무도 모르는 임의 비밀번호로 POST /auth/users → 곧바로 POST …/password-reset 으로 임시 비밀번호 발급
//    (POST /auth/users 는 보낸 비밀번호를 그대로 쓰고 첫 로그인 때 변경을 강제하지 않아서다. initialPassword.ts)
//  - 수정(이름 · 역할 · 활성/비활성): PATCH /auth/users/{id}. 역할 · 활성을 바꾸면 그 계정 토큰이 모두 끊긴다
//  - 비밀번호 초기화 · 휴면 해제: 임시 비밀번호를 돌려준다. 이 훅은 들고 있지 않는다(화면이 한 번 보여 주고 버린다)
//  - 잠금 해제 · 강제 로그아웃(그 계정의 토큰을 모두 끊는다)
//
// 자기 계정에는 비활성화 · 역할 변경 · 강제 로그아웃 · 비밀번호 초기화 · 휴면 해제를 하지 않는다(바로 자기 로그인이
// 끊긴다). 줄마다 can 으로 알려 주고, 화면이 단추를 빠뜨려도 훅이 막는다. 마지막 관리자를 내리는 것은 서버가 409 로 막는다.
//
// 요청은 한 번에 하나다(같은 순간 두 번 눌러도 두 번째는 null). 요청이 끝나면 목록을 다시 받고, 같은 탭의
// 다른 관리자 훅(대시보드 · 접속 기록)에도 알린다(adminEvents).
//
// 요청을 여러 번 보내는 일(등록 = 만들기 → 초기화, WEAK_PASSWORD 다시 보내기, 사례 수의 다음 쪽)은 다음 요청을
// 보내기 직전마다 로그인이 그대로인지(토큰이 같은지 · 화면에 붙어 있는지) 본다. 그사이 로그아웃하거나 다른 계정으로
// 바뀌었으면 멈춘다 — 바뀐 계정의 토큰으로 앞 사람의 작업을 이어 보내지 않게.

import { useCallback, useMemo, useRef, useState } from "react";

import { ApiError, getToken } from "../api/client";
import { auth, cases } from "../api/endpoints";
import type { Case, User, UserRole, UserUpdateRequest } from "../api/types";
import { adminKey, type AdminAccess, type AdminHookOptions } from "./adminAccess";
import { notifyAccountsChanged } from "./adminEvents";
import {
  countCasesByCounselor,
  toAccountRow,
  toTemporaryPasswordView,
  type AccountAbilities,
  type AccountRow,
  type TemporaryPasswordView,
} from "./adminRows";
import { generateInitialPassword } from "./initialPassword";
import { errorMessage, useRemote } from "./useRemote";

/** Backend 제한(UserCreateRequest · UserUpdateRequest). */
export const ACCOUNT_NAME_MAX = 100;

/** 임의 비밀번호에 이메일 아이디 · 이름 조각이 우연히 들어가 WEAK_PASSWORD 가 나면 새로 만들어 다시 보내는 횟수. */
const CREATE_ATTEMPTS = 3;

const CASE_PAGE_SIZE = 100;

/** 요청을 보내기 직전에 로그인이 그대로인지 볼 때 던진다. 받은 쪽은 조용히 그만둔다. */
class SessionChangedError extends Error {
  constructor() {
    super("로그인이 바뀌어 요청을 멈췄습니다.");
    this.name = "SessionChangedError";
  }
}

async function loadAllCases(): Promise<Case[]> {
  const all: Case[] = [];
  // 첫 쪽을 보낼 때의 로그인. 다음 쪽을 보내기 전에 바뀌었으면 멈춘다(결과는 useRemote 가 어차피 버린다).
  const token = getToken();

  for (let page = 1; ; page += 1) {
    if (page > 1 && getToken() !== token) throw new SessionChangedError();

    const result = await cases.list({ page, page_size: CASE_PAGE_SIZE });

    all.push(...result.items);

    if (page >= result.meta.total_pages || result.items.length === 0) return all;
  }
}

const loadCaseCounts = () => loadAllCases().then(countCasesByCounselor);

export interface CreateAccountInput {
  /** 로그인 ID. */
  email: string;
  name: string;
  /** 빼면 상담원. */
  role?: UserRole;
}

export interface CreatedAccount {
  account: AccountRow;
  /** 임시 비밀번호 발급까지 성공했으면 그 값. 발급만 실패했으면 null — 계정은 만들어졌다(error 에 안내). */
  temporaryPassword: TemporaryPasswordView | null;
}

export interface AccountUpdateInput {
  name?: string;
  role?: UserRole;
  active?: boolean;
}

export interface AdminAccountsState {
  rows: AccountRow[];
  loading: boolean;
  /** 목록을 못 받았거나 마지막 요청이 실패한 이유. */
  error: string | null;
  /** 담당 사례 수를 세지 못한 이유(목록은 그대로 보이고 사례 수 칸만 NOT_PROVIDED). */
  caseCountError: string | null;
  /** 요청 중인가(등록 포함). */
  submitting: boolean;
  /** 요청 중인 계정 ID. 등록 중이거나 요청이 없으면 null. */
  busyId: string | null;
  /** 성공하면 만든 계정과 임시 비밀번호, 실패하면 null. */
  create: (input: CreateAccountInput) => Promise<CreatedAccount | null>;
  /** 바꿀 칸만 넘긴다. 성공하면 바뀐 줄, 실패하면 null. */
  update: (userId: string, input: AccountUpdateInput) => Promise<AccountRow | null>;
  setActive: (userId: string, active: boolean) => Promise<AccountRow | null>;
  /** 성공하면 true. */
  unlock: (userId: string) => Promise<boolean>;
  /** 그 계정의 모든 기기 로그인을 끊는다. 비밀번호는 그대로다. 성공하면 true. */
  logoutAll: (userId: string) => Promise<boolean>;
  /** 성공하면 임시 비밀번호(한 번만 온다), 실패하면 null. */
  resetPassword: (userId: string) => Promise<TemporaryPasswordView | null>;
  /** 휴면을 풀고 임시 비밀번호를 새로 발급한다. */
  reactivate: (userId: string) => Promise<TemporaryPasswordView | null>;
  reload: () => void;
}

/** 자기 계정 · 상태 때문에 할 수 없는 요청이면 그 이유. */
const BLOCKED_REASONS: Record<keyof AccountAbilities, string> = {
  activate: "이미 활성 상태인 계정입니다.",
  deactivate: "자기 계정이거나 이미 비활성 상태인 계정입니다.",
  unlock: "잠긴 계정이 아닙니다.",
  reactivate: "휴면 계정이 아니거나 자기 계정입니다.",
  logoutAll: "자기 계정은 강제 로그아웃할 수 없습니다. 로그아웃을 눌러 주세요.",
  resetPassword: "자기 비밀번호는 설정의 비밀번호 변경에서 바꿔 주세요.",
  changeRole: "자기 역할은 바꿀 수 없습니다.",
};

export function checkCreateInput(input: CreateAccountInput): string | null {
  const email = input.email.trim();
  const name = input.name.trim();

  if (!email || !name) return "이메일과 이름을 입력해 주세요.";
  // 형식은 서버(EmailStr)가 최종으로 본다. 여기서는 흔한 실수만 거른다.
  if (!/^[^\s@]+@[^\s@]+$/.test(email)) return "이메일 형식을 확인해 주세요.";
  if (name.length > ACCOUNT_NAME_MAX) return `이름은 ${ACCOUNT_NAME_MAX}자까지 쓸 수 있습니다.`;

  return null;
}

export function useAdminAccounts(access: AdminAccess, { enabled = true }: AdminHookOptions = {}): AdminAccountsState {
  const key = adminKey(access, enabled, "accounts");
  const users = useRemote<User[]>(key, auth.listUsers, "계정 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.", () => false);
  const counts = useRemote<Map<string, number>>(
    adminKey(access, enabled, "accounts:caseCounts"),
    loadCaseCounts,
    "담당 사례 수를 세지 못했습니다.",
    () => false,
  );
  // 진행 중인 요청과 그 요청을 보낸 계정 key. 다른 관리자로 바뀌면 앞 사람의 요청은 새 사람의 진행 상태 ·
  // 두 번 누름 막기에 끼어들지 않는다. state 는 같은 순간의 두 번째 누름을 막지 못해 ref 로도 든다.
  const [busy, setBusy] = useState<{ id: number; key: string; userId: string | null } | null>(null);
  const inFlight = useRef<{ id: number; key: string } | null>(null);
  const lastRequestId = useRef(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState(key);

  if (errorKey !== key) {
    setErrorKey(key);
    setActionError(null);
  }

  const meId = access.me?.id ?? null;

  const rows = useMemo(
    () => (users.data ?? []).map((user) => toAccountRow(user, meId, counts.data)),
    [users.data, meId, counts.data],
  );

  // 요청을 보낼 때의 줄. 목록을 다시 받기 전에 다른 탭에서 바뀌었을 수 있어 서버가 최종으로 막는다.
  const rowsRef = useRef(rows);
  rowsRef.current = rows;

  /**
   * 요청 하나를 보낸다. 한 번에 하나만. 성공하면 목록을 다시 받고 다른 관리자 훅에 알린다.
   * 요청한 뒤 로그아웃하거나 다른 계정으로 바뀌었으면 결과를 돌려주지 않는다(null) — 임시 비밀번호를 다른 사람에게 보이지 않게.
   */
  const perform = useCallback(
    async <T>(
      userId: string | null,
      send: (stillSame: () => void) => Promise<T>,
      fallback: string,
      onFailure?: (caught: unknown) => T | null,
    ): Promise<T | null> => {
      if (!key || inFlight.current?.key === key) return null;

      const forKey = key;
      const token = getToken();
      const id = ++lastRequestId.current;
      // 보낸 계정 그대로 화면에 붙어 있고 토큰도 같은가. key 에 관리자 ID 가 들어 있어 세대(useRemote 의 표)는 보지 않는다 —
      // 같은 관리자 · 같은 토큰으로 보기만 바꿨다 돌아왔으면(key 가 null 을 거침) 결과(임시 비밀번호)를 그대로 돌려준다.
      const same = () => users.capture()?.key === forKey && getToken() === token;
      // 다음 요청을 보내기 직전에 부른다. 바뀌었으면 멈춘다.
      const stillSame = () => {
        if (!same()) throw new SessionChangedError();
      };

      inFlight.current = { id, key: forKey };
      setBusy({ id, key: forKey, userId });
      setActionError(null);

      try {
        const result = await send(stillSame);

        notifyAccountsChanged();

        if (!same()) return null;

        users.refresh();
        counts.refresh();

        return result;
      } catch (caught) {
        // 로그인이 바뀌어 중간에 멈췄다. 앞 요청(예: 계정 만들기)은 이미 처리됐을 수 있어 다른 관리자 훅에 알린다.
        // 결과 · 오류는 바뀐 로그인에 보이지 않는다.
        if (caught instanceof SessionChangedError) notifyAccountsChanged();

        if (!same()) return null;

        if (!(caught instanceof ApiError && caught.isUnauthorized)) setActionError(errorMessage(caught, fallback));

        // 다른 창에서 먼저 바뀌었을 수 있다(409 등). 최신 목록을 다시 받는다.
        users.refresh();

        return onFailure ? onFailure(caught) : null;
      } finally {
        if (inFlight.current?.id === id) inFlight.current = null;
        setBusy((current) => (current?.id === id ? null : current));
      }
    },
    [key, users.capture, users.refresh, counts.refresh],
  );

  /** 그 줄에서 할 수 있는 요청인지 본다. 안 되면 이유를 error 에 두고 false. */
  const allowed = useCallback((userId: string, ability: keyof AccountAbilities): boolean => {
    const row = rowsRef.current.find((item) => item.id === userId);

    if (!row) {
      setActionError("계정을 찾지 못했습니다. 목록을 다시 불러와 주세요.");
      return false;
    }

    if (!row.can[ability]) {
      setActionError(BLOCKED_REASONS[ability]);
      return false;
    }

    return true;
  }, []);

  const create = useCallback(
    async (input: CreateAccountInput): Promise<CreatedAccount | null> => {
      const problem = checkCreateInput(input);

      if (problem) {
        setActionError(problem);
        return null;
      }

      const payload = { email: input.email.trim(), name: input.name.trim(), role: input.role ?? "COUNSELOR" };
      let created: User | null = null;

      return perform<CreatedAccount>(
        null,
        async (stillSame) => {
          for (let attempt = 1; !created; attempt += 1) {
            if (attempt > 1) stillSame();

            try {
              created = await auth.createUser({ ...payload, password: generateInitialPassword() });
            } catch (caught) {
              // 임의 비밀번호에 이메일 아이디 · 이름 조각이 우연히 들어가면 WEAK_PASSWORD 다. 새로 만들어 다시 보낸다.
              if (caught instanceof ApiError && caught.code === "WEAK_PASSWORD" && attempt < CREATE_ATTEMPTS) continue;
              throw caught;
            }
          }

          const account = toAccountRow(created, meId, null);

          stillSame();

          const temporary = await auth.resetPassword(created.id);

          return { account, temporaryPassword: toTemporaryPasswordView(temporary) };
        },
        "계정을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.",
        // 계정은 만들었는데 임시 비밀번호 발급만 실패했다. 계정은 돌려주고, 목록에서 초기화를 누르라고 안내한다.
        (): CreatedAccount | null => {
          if (!created) return null;

          // 계정은 만들어졌다. 같은 탭의 대시보드 · 접속 기록도 다시 부르게 알린다.
          notifyAccountsChanged();
          counts.refresh();
          setActionError(`${created.name} 계정은 만들었지만 임시 비밀번호를 발급하지 못했습니다. 목록에서 이름을 눌러 상담사 상세의 '비밀번호 초기화'를 눌러 주세요.`);

          return { account: toAccountRow(created, meId, null), temporaryPassword: null };
        },
      );
    },
    [perform, meId, counts.refresh],
  );

  const update = useCallback(
    async (userId: string, input: AccountUpdateInput): Promise<AccountRow | null> => {
      const payload: UserUpdateRequest = {};

      if (input.name !== undefined) {
        const name = input.name.trim();

        if (!name) {
          setActionError("이름을 입력해 주세요.");
          return null;
        }

        if (name.length > ACCOUNT_NAME_MAX) {
          setActionError(`이름은 ${ACCOUNT_NAME_MAX}자까지 쓸 수 있습니다.`);
          return null;
        }

        payload.name = name;
      }

      if (input.role !== undefined) {
        if (!allowed(userId, "changeRole")) return null;
        payload.role = input.role;
      }

      if (input.active !== undefined) {
        if (!allowed(userId, input.active ? "activate" : "deactivate")) return null;
        payload.is_active = input.active;
      }

      if (Object.keys(payload).length === 0) {
        setActionError("바꿀 내용이 없습니다.");
        return null;
      }

      const user = await perform(
        userId,
        () => auth.updateUser(userId, payload),
        "계정을 바꾸지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );

      return user ? toAccountRow(user, meId, counts.data) : null;
    },
    [perform, allowed, meId, counts.data],
  );

  const setActive = useCallback((userId: string, active: boolean) => update(userId, { active }), [update]);

  const unlock = useCallback(
    async (userId: string) => {
      if (!allowed(userId, "unlock")) return false;

      const done = await perform(
        userId,
        () => auth.unlockUser(userId).then(() => true),
        "잠금을 해제하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );

      return done === true;
    },
    [perform, allowed],
  );

  const logoutAll = useCallback(
    async (userId: string) => {
      if (!allowed(userId, "logoutAll")) return false;

      const done = await perform(
        userId,
        () => auth.logoutAll(userId).then(() => true),
        "로그인을 끊지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );

      return done === true;
    },
    [perform, allowed],
  );

  const resetPassword = useCallback(
    async (userId: string) => {
      if (!allowed(userId, "resetPassword")) return null;

      return perform(
        userId,
        () => auth.resetPassword(userId).then(toTemporaryPasswordView),
        "비밀번호를 초기화하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    },
    [perform, allowed],
  );

  const reactivate = useCallback(
    async (userId: string) => {
      if (!allowed(userId, "reactivate")) return null;

      return perform(
        userId,
        () => auth.reactivateUser(userId).then(toTemporaryPasswordView),
        "휴면을 해제하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    },
    [perform, allowed],
  );

  const reload = useCallback(() => {
    users.reload();
    counts.reload();
  }, [users.reload, counts.reload]);

  return {
    rows,
    loading: users.loading,
    error: actionError ?? users.error,
    caseCountError: counts.error,
    submitting: busy?.key === key,
    busyId: busy?.key === key ? busy.userId : null,
    create,
    update,
    setActive,
    unlock,
    logoutAll,
    resetPassword,
    reactivate,
    reload,
  };
}
