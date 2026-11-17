// 상담사 계정 관리(AdminAccounts) 값. 디자인 counselor-design/screens/AdminAccounts.dc.html.
//
// 서버 연결: useAdminAccounts(GET /auth/users + 계정별 담당 사례 수, 계정 만들기 = POST /auth/users → 임시 비밀번호 발급).
//  - 만들기 칸은 앱 그대로 이메일(로그인 ID) · 이름 · 역할이다. 디자인의 '기관 ID' 는 서버에 없다(로그인 ID 는 이메일 — 팀 질문 D4).
//  - 만든 뒤 임시 비밀번호를 한 번만 보인다(디자인은 보이지 않지만 서버는 응답 한 번에만 준다). 첫 로그인 때 새 비밀번호로 바꾸게 된다.
//    디자인 문구의 'OTP 등록' 은 OTP 가 없어(D1) 뺐다.
//  - 목록은 디자인대로 이름(→ 상담사 상세) · 상태 필터 · 검색. 검색은 이미 받은 목록 안에서 이름 · 이메일로 거른다(서버 검색 없음).
//    디자인의 '기관 ID' 열은 이메일, '접속 IP' 열은 10/6 결정(계정 목록에 IP 열을 두지 않음)대로 뺐고, 앱에 있던 역할 열을 둔다.
//  - 비밀번호 초기화 · 잠금 해제 · 휴면 해제 · 비활성화 · 강제 로그아웃은 상담사 상세(AdminStaffDetail)에서 한다(디자인의 '상세').
//  - 가입 신청(로그인 화면 회원가입, useSignupRequests): 디자인에 없는 칸이라 계정 목록과 같은 표 모양으로 대기 신청이 있을 때만 보인다.
//    역할을 골라 승인하면 신청 때 비밀번호 그대로 계정이 생긴다. 거절은 신청자에게 알리지 않는다.

import type { UserRole } from "../../api/types";
import { toDateOnly, toDateTime } from "../time";
import type { AdminAccountsState } from "../useAdminAccounts";
import type { SignupRequestsState } from "../useSignupRequests";
import type { AuthSession } from "../useAuthSession";
import {
  accountChips,
  initialOf,
  issuedPasswordValues,
  segButton,
  staffDetailHref,
  tablePhase,
  type IssuedPassword,
} from "./admin";

export type AccountFilter = "all" | "on" | "off";

export interface AdminAccountsUiState {
  /** '+ 계정 생성' 으로 펼친 만들기 칸. */
  showForm: boolean;
  form: { email: string; name: string; role: UserRole };
  filter: AccountFilter;
  /** 목록 검색어와 그것을 입력한 관리자. 다른 관리자로 바뀌면 비운 것으로 본다. */
  search: { text: string; forAdmin: string };
  /** 방금 받은 임시 비밀번호. '닫기' 를 누르면 null. */
  issued: IssuedPassword | null;
  /** 마지막 요청이 성공했다는 안내. */
  done: { text: string; forAdmin: string } | null;
  copied: boolean;
  /** 가입 신청마다 고른 역할(기본 상담원). */
  signupRoles: Record<string, UserRole>;
}

export const INITIAL_ACCOUNTS_UI: AdminAccountsUiState = {
  showForm: false,
  form: { email: "", name: "", role: "COUNSELOR" },
  filter: "all",
  search: { text: "", forAdmin: "" },
  issued: null,
  done: null,
  copied: false,
  signupRoles: {},
};

type Change = { target: { value: string } };

export function adminAccountsValues(input: {
  session: AuthSession;
  accounts: AdminAccountsState;
  signups: SignupRequestsState;
  state: AdminAccountsUiState;
  setState: (
    patch: Partial<AdminAccountsUiState> | ((current: AdminAccountsUiState) => Partial<AdminAccountsUiState>),
  ) => void;
}) {
  const { session, accounts, signups, state, setState } = input;
  const adminId = session.me?.id ?? "";
  const busy = accounts.submitting;
  const search = state.search.forAdmin === adminId ? state.search.text : "";
  const query = search.trim().toLowerCase();

  // ---------------- 목록 ----------------
  const onCount = accounts.rows.filter((row) => row.active).length;
  const filters = [
    segButton("all", `전체 ${accounts.rows.length}`, state.filter === "all", () => setState({ filter: "all" })),
    segButton("on", `활성 ${onCount}`, state.filter === "on", () => setState({ filter: "on" })),
    segButton("off", `비활성 ${accounts.rows.length - onCount}`, state.filter === "off", () =>
      setState({ filter: "off" }),
    ),
  ];
  const shown = accounts.rows.filter((row) => {
    if (state.filter === "on" && !row.active) return false;
    if (state.filter === "off" && row.active) return false;

    return !query || row.name.toLowerCase().includes(query) || row.email.toLowerCase().includes(query);
  });
  const rows = shown.map((row) => ({
    key: row.id,
    href: staffDetailHref(row.id),
    ini: initialOf(row.name),
    name: row.name,
    self: row.isSelf ? "(나)" : "",
    email: row.email,
    role: row.roleLabel,
    cases: row.caseCountLabel,
    last: row.lastLoginAt,
    chips: accountChips(row),
    lockedUntil: row.lockedUntil ? `${row.lockedUntil}에 풀림` : "",
    // 비활성 계정은 흐리게(+ 칩 글자 '비활성').
    op: row.active ? 1 : 0.6,
  }));
  // 계정이 하나도 없으면 '계정이 없습니다', 거른 결과만 없으면 '조건에 맞는 계정이 없습니다'.
  const phase = tablePhase(accounts.loading, accounts.rows.length === 0 ? accounts.error : null, rows.length);

  // ---------------- 만들기 ----------------
  const form = state.form;
  const field = (key: "email" | "name") => ({
    value: form[key],
    onChange: (e: Change) => setState((current) => ({ form: { ...current.form, [key]: e.target.value } })),
  });
  const create = async (e: { preventDefault: () => void }) => {
    e.preventDefault();
    setState({ done: null });

    const created = await accounts.create({ email: form.email, name: form.name, role: form.role });

    if (!created) return;

    setState({ form: INITIAL_ACCOUNTS_UI.form, showForm: false });

    if (created.temporaryPassword) {
      setState({
        issued: {
          ...created.temporaryPassword,
          forAdmin: adminId,
          userId: created.account.id,
          name: created.account.name,
          email: created.account.email,
          reason: "새 계정",
        },
        copied: false,
        done: { text: `${created.account.name} 계정을 만들었습니다.`, forAdmin: adminId },
      });
    }
  };

  // ---------------- 가입 신청 ----------------
  const roleOf = (id: string): UserRole => state.signupRoles[id] ?? "COUNSELOR";
  const signupRows = signups.items.map((item) => {
    const role = roleOf(item.id);
    const rowBusy = signups.busyId === item.id;

    return {
      key: item.id,
      name: item.name,
      email: item.email,
      requestedAt: toDateTime(item.created_at),
      expiresAt: item.expires_at ? `${toDateOnly(item.expires_at)}까지` : "",
      role: {
        value: role,
        onChange: (e: Change) =>
          setState((current) => ({ signupRoles: { ...current.signupRoles, [item.id]: e.target.value as UserRole } })),
      },
      busy: signups.busyId !== null,
      approveLabel: rowBusy ? "처리 중…" : "승인",
      approve: async () => {
        setState({ done: null });
        const approved = await signups.approve(item.id, role);
        // 실패해도 다시 받는다. 다른 관리자가 먼저 승인했으면 계정이 생겼다.
        accounts.reload();
        if (!approved) return;
        setState({
          done: {
            text: `${item.name} 님 가입을 승인했습니다(${role === "ADMIN" ? "관리자" : "상담원"}). 신청 때 정한 비밀번호로 로그인합니다.`,
            forAdmin: adminId,
          },
        });
      },
      reject: async () => {
        if (!window.confirm(`${item.name} 님의 가입 신청을 거절할까요? 신청자에게 따로 알리지 않습니다.`)) return;
        setState({ done: null });
        const rejected = await signups.reject(item.id);
        accounts.reload();
        if (!rejected) return;
        setState({ done: { text: `${item.name} 님 가입 신청을 거절했습니다.`, forAdmin: adminId } });
      },
    };
  });

  return {
    signupShown: signups.total > 0 || signups.error !== null || signups.actionError !== null,
    signupTitle: `가입 신청 ${signups.total}건`,
    signupRows,
    signupMore:
      signups.total > signupRows.length ? `오래된 신청 ${signupRows.length}건만 보입니다. 처리하면 다음 신청이 보입니다.` : "",
    signupError: signups.actionError ?? (signups.items.length === 0 ? signups.error : null),
    signupRetry: signups.reload,
    formOpen: state.showForm,
    formBtnLabel: state.showForm ? "닫기" : "+ 계정 생성",
    formBtnCls: state.showForm ? "btn btn-s" : "btn btn-p",
    toggleForm: () => setState({ showForm: !state.showForm }),
    email: field("email"),
    name: field("name"),
    role: {
      value: form.role,
      onChange: (e: Change) => setState((current) => ({ form: { ...current.form, role: e.target.value as UserRole } })),
    },
    busy,
    createLabel: busy && accounts.busyId === null ? "만드는 중…" : "계정 생성",
    create,
    issued: issuedPasswordValues(state.issued, adminId, state.copied, setState),
    done: state.done && state.done.forAdmin === adminId ? state.done.text : "",
    // 목록을 못 받은 오류는 표 안에 보이므로, 표 밖에는 요청(만들기) 오류만 보인다.
    actionError: phase === "error" ? null : accounts.error,
    caseCountError: accounts.caseCountError,
    search: {
      value: search,
      onChange: (e: Change) => setState({ search: { text: e.target.value, forAdmin: adminId } }),
    },
    filters,
    rows,
    phase,
    emptyText: accounts.rows.length === 0 ? "계정이 없습니다." : "조건에 맞는 계정이 없습니다.",
    errorText: accounts.error,
    retry: accounts.reload,
  };
}
