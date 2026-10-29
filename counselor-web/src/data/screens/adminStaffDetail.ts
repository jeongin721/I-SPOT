// 상담사 상세(AdminStaffDetail) 값. 디자인 counselor-design/screens/AdminStaffDetail.dc.html.
//
// 주소: #/AdminStaffDetail?user=<계정 ID>. 디자인은 고른 계정을 브라우저 저장소(ispot-staff)로 넘기고 없으면 예시 계정을
// 보이지만, 앱은 주소 쿼리로 받고 계정 목록(GET /auth/users — 한 계정만 받는 API 는 없다)에서 찾는다. 없으면 안내만 보인다.
//
// 서버 값: 이름 · 이메일 · 역할 · 상태(활성 · 잠금 · 휴면 · 임시 비밀번호) · 담당 사례 수(종결 포함) · 계정 생성일 · 최근 로그인.
// 할 수 있는 일(앱의 계정 관리 기능을 이 화면에 모았다. 자기 계정은 훅이 막는다):
//  - 비활성화 · 다시 활성화(디자인의 머리 단추). 비활성화는 한 번 더 묻는다.
//  - 비밀번호 초기화(디자인의 '재설정 링크 보내기' 자리). 서버는 링크 · 메일이 아니라 임시 비밀번호를 한 번 준다 — 한 번 더 묻고,
//    받은 임시 비밀번호는 이 화면 상태에만 한 번 보인다.
//  - 잠금 해제 · 휴면 해제(임시 비밀번호 새로 발급, 한 번 더 물음) · 강제 로그아웃(한 번 더 물음).
// 서버에 없어 '—' · 준비 중: 비밀번호 마지막 변경일(응답에 없음), 소속 기관(모델 없음), 접속 IP(감사 로그를 계정으로 거르는 훅이 없음),
// 알림 설정(저장소 없음). OTP 줄은 OTP 가 없어(D1) 두지 않는다.

import type { AccountRow, TemporaryPasswordView } from "../adminRows";
import type { AdminAccountsState } from "../useAdminAccounts";
import type { AuthSession } from "../useAuthSession";
import { NOT_PROVIDED } from "../caseRows";
import { NOT_READY, notice, screenNotice } from "./common";
import { ADMIN_PAGES, accountChips, initialOf, issuedPasswordValues, type IssuedPassword } from "./admin";

/** 한 번 더 묻는 요청. 임시 비밀번호가 새로 나오거나 그 계정의 로그인이 끊기는 것들이다. */
export type AccountAsk = "resetPassword" | "reactivate" | "deactivate" | "logoutAll";

export interface StaffDetailUiState {
  ask: { userId: string; kind: AccountAsk; forAdmin: string } | null;
  /** 방금 받은 임시 비밀번호. '닫기' 를 누르면 null. */
  issued: IssuedPassword | null;
  /** 마지막 요청이 성공했다는 안내. */
  done: { text: string; forAdmin: string } | null;
  copied: boolean;
}

export const INITIAL_STAFF_DETAIL_UI: StaffDetailUiState = { ask: null, issued: null, done: null, copied: false };

const ASK_TEXT: Record<AccountAsk, { label: string; question: (name: string) => string }> = {
  resetPassword: {
    label: "비밀번호 초기화",
    question: (name) => `${name} 계정의 비밀번호를 초기화할까요? 임시 비밀번호가 새로 나오고 그 계정의 로그인은 모두 끊깁니다.`,
  },
  reactivate: {
    label: "휴면 해제",
    question: (name) => `${name} 계정의 휴면을 풀까요? 임시 비밀번호가 새로 나옵니다.`,
  },
  deactivate: {
    label: "계정 비활성화",
    question: (name) => `${name} 계정을 비활성화할까요? 그 계정의 로그인이 모두 끊기고 다시 활성화하기 전에는 로그인할 수 없습니다.`,
  },
  logoutAll: {
    label: "강제 로그아웃",
    question: (name) => `${name} 계정의 모든 기기 로그인을 끊을까요? 비밀번호는 그대로입니다.`,
  },
};

type Action = { key: string; label: string; onClick: () => void };

export function adminStaffDetailValues(input: {
  session: AuthSession;
  /** 주소의 user 쿼리. 없으면 null. */
  staffId: string | null;
  accounts: AdminAccountsState;
  state: StaffDetailUiState;
  setState: (patch: Partial<StaffDetailUiState>) => void;
}) {
  const { session, staffId, accounts, state, setState } = input;
  const adminId = session.me?.id ?? "";
  const row = staffId ? (accounts.rows.find((item) => item.id === staffId) ?? null) : null;
  const backToList = { href: ADMIN_PAGES.accounts, hrefLabel: "계정 목록으로" };

  // ---------------- 안내(대상 없음 · 불러오는 중 · 오류 · 못 찾음) ----------------
  const missing = !staffId ? notice("상담사를 고르지 않았습니다. 계정 목록에서 이름을 눌러 주세요.", backToList) : null;
  const pageNotice =
    screenNotice({
      session,
      missing,
      loading: accounts.loading && !row,
      error: !row && accounts.rows.length === 0 ? accounts.error : null,
      retry: accounts.reload,
    }) ??
    (row ? null : notice("계정을 찾지 못했습니다. 지워졌거나 주소가 맞지 않습니다.", backToList));

  // ---------------- 요청 ----------------
  const busy = accounts.submitting;
  const issue = (source: TemporaryPasswordView | null, target: AccountRow, reason: string) => {
    const issued = issuedOf(source, target, reason, adminId);
    if (issued) setState({ issued, copied: false });
  };
  const finish = (text: string) => setState({ ask: null, done: { text, forAdmin: adminId } });

  const run = async (target: AccountRow, kind: AccountAsk | "unlock" | "activate") => {
    setState({ done: null });

    if (kind === "resetPassword") {
      const result = await accounts.resetPassword(target.id);
      if (result) {
        issue(result, target, "비밀번호 초기화");
        finish(`${target.name} 계정의 비밀번호를 초기화했습니다.`);
      }
    } else if (kind === "reactivate") {
      const result = await accounts.reactivate(target.id);
      if (result) {
        issue(result, target, "휴면 해제");
        finish(`${target.name} 계정의 휴면을 풀었습니다.`);
      }
    } else if (kind === "deactivate") {
      if (await accounts.setActive(target.id, false)) finish(`${target.name} 계정을 비활성화했습니다. 로그인할 수 없습니다.`);
    } else if (kind === "logoutAll") {
      if (await accounts.logoutAll(target.id)) finish(`${target.name} 계정의 로그인을 모두 끊었습니다.`);
    } else if (kind === "unlock") {
      if (await accounts.unlock(target.id)) finish(`${target.name} 계정의 잠금을 풀었습니다.`);
    } else if (await accounts.setActive(target.id, true)) {
      finish(`${target.name} 계정을 다시 활성화했습니다.`);
    }
  };

  const asking =
    row && state.ask && state.ask.forAdmin === adminId && state.ask.userId === row.id ? state.ask.kind : null;
  const ask = (kind: AccountAsk) => () => {
    if (row) setState({ ask: { userId: row.id, kind, forAdmin: adminId }, done: null });
  };

  // 머리 단추: 비활성화(한 번 더 물음) · 다시 활성화 · 자기 계정은 '본인 계정'(누를 수 없음).
  const toggle = !row
    ? null
    : row.isSelf
      ? { label: "본인 계정", onClick: () => undefined, disabled: true }
      : row.can.deactivate
        ? { label: "계정 비활성화", onClick: ask("deactivate"), disabled: busy }
        : row.can.activate
          ? { label: "계정 다시 활성화", onClick: () => void run(row, "activate"), disabled: busy }
          : null;

  const stateActions: Action[] = row
    ? [
        row.can.unlock ? { key: "unlock", label: "잠금 해제", onClick: () => void run(row, "unlock") } : null,
        row.can.reactivate ? { key: "reactivate", label: "휴면 해제", onClick: ask("reactivate") } : null,
        row.can.logoutAll ? { key: "logoutAll", label: "강제 로그아웃", onClick: ask("logoutAll") } : null,
      ].filter((action): action is Action => action !== null)
    : [];

  const mustChange = row ? row.tags.some((tag) => tag.label === "임시 비밀번호") : false;

  return {
    notice: pageNotice,
    found: Boolean(row),
    listHref: ADMIN_PAGES.accounts,
    securityHref: ADMIN_PAGES.security,
    notReady: NOT_READY,
    name: row ? row.name : "",
    ini: row ? initialOf(row.name) : "",
    self: row && row.isSelf ? "(나)" : "",
    chips: row ? accountChips(row) : [],
    lockedUntil: row && row.lockedUntil ? `${row.lockedUntil}에 풀림` : "",
    sub: row ? `${row.email} · 담당 사례 ${row.caseCountLabel}(종결 포함)` : "",
    toggle,
    email: row ? row.email : "",
    role: row ? row.roleLabel : "",
    pwText: mustChange ? "임시 비밀번호 사용 중 · 첫 로그인 때 새 비밀번호로 바꿈" : `마지막 변경 ${NOT_PROVIDED}`,
    reset: row && row.can.resetPassword ? { label: "비밀번호 초기화", onClick: ask("resetPassword") } : null,
    resetNote: row && row.isSelf ? "자기 비밀번호는 설정의 비밀번호 변경에서 바꿉니다." : "",
    org: NOT_PROVIDED,
    stateActions,
    stateNote: row && stateActions.length === 0 ? (row.isSelf ? "자기 계정" : "할 수 있는 요청이 없습니다.") : "",
    created: row ? row.createdAt || NOT_PROVIDED : "",
    last: row ? row.lastLoginAt : "",
    ip: NOT_PROVIDED,
    busy,
    busyText: busy ? "처리 중…" : "",
    asking: asking
      ? {
          text: ASK_TEXT[asking].question(row ? row.name : ""),
          label: ASK_TEXT[asking].label,
          confirm: () => {
            if (row) void run(row, asking);
          },
          cancel: () => setState({ ask: null }),
        }
      : null,
    // 주소만 바꿔 다른 계정을 보면(같은 화면) 앞 계정의 임시 비밀번호는 보이지 않는다.
    issued: issuedPasswordValues(
      row && state.issued?.userId === row.id ? state.issued : null,
      adminId,
      state.copied,
      setState,
    ),
    done: state.done && state.done.forAdmin === adminId ? state.done.text : "",
    error: row ? accounts.error : null,
    caseCountError: accounts.caseCountError,
  };
}

/** 임시 비밀번호 응답 → 이 화면 상태에 한 번 둘 값. */
function issuedOf(
  source: TemporaryPasswordView | null,
  target: AccountRow,
  reason: string,
  adminId: string,
): IssuedPassword | null {
  if (!source) return null;

  return { ...source, forAdmin: adminId, userId: target.id, name: target.name, email: target.email, reason };
}
