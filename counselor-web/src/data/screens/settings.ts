// 설정(Settings) 화면 값. 계정 칸은 로그인한 내 정보(useAuthSession().me → profile.toProfileView), 비밀번호는 usePasswordChange.
//
//  - 이름 · 이메일을 본인이 바꾸는 API 는 Backend 에 없어 '수정' · '변경' 단추는 준비 중으로 막는다(이름은 관리자가 바꾼다).
//  - 비밀번호는 디자인의 '재설정 링크 메일' 대신 현재 비밀번호를 넣고 바꾼다(기존 결정은 이메일 임시 코드이고 아직 구현 전).
//    바꾸면 서버가 이 계정의 로그인을 모두 끊고, 화면은 로그인 화면으로 간다("새 비밀번호로 다시 로그인").
//  - 소속 기관 · 마지막 비밀번호 변경일 · 알림 설정은 Backend 에 없어 '—' · 준비 중으로 둔다(profile.ts 머리말).
//  - 비밀번호 입력 칸은 그 칸을 연 계정 것만 보인다(다른 탭에서 다른 계정으로 바뀌면 비운 것으로 본다).
//  - 10/21 디자인의 '계정' 진입 전 비밀번호 확인 창은 만들지 않는다. 비밀번호만 확인하는 API 가 서버에 없고(로그인 API 를 쓰면
//    로그인 기록 · 실패 횟수에 남는다), 디자인 창은 아무 비밀번호나 통과시켜 확인이 되지 않는다(재인증 여부는 팀 결정).
//  - 10/21 디자인의 leaveReset(왼쪽 메뉴를 누르면 설정 첫 화면으로): 다른 화면으로 가면 이 화면이 내려가 저절로 처음으로 돌아가고,
//    같은 주소(메뉴의 '설정')를 다시 누르면 화면 이동 표시(navKey = 라우터 location.key)가 바뀌어 첫 화면을 보인다.

import { NOT_PROVIDED } from "../caseRows";
import { toProfileView } from "../profile";
import type { AuthSession } from "../useAuthSession";
import { PASSWORD_RULE_TEXT, type PasswordChangeState } from "../usePasswordChange";
import { NOT_READY, screenNotice, sidebarValues } from "./common";

export type SettingsView = "home" | "account" | "notify";

export interface SettingsUiState {
  view: SettingsView;
  /** view 를 연 화면 이동(navKey). 지금 navKey 와 다르면(메뉴의 '설정' 을 다시 누름) 첫 화면으로 본다. */
  viewKey: string | null;
  /** 비밀번호 바꾸기 칸을 연 계정. null 이면 닫혀 있다. */
  pwFor: string | null;
  current: string;
  next: string;
  confirm: string;
}

export const INITIAL_SETTINGS_STATE: SettingsUiState = {
  view: "home",
  viewKey: null,
  pwFor: null,
  current: "",
  next: "",
  confirm: "",
};

export interface SettingsScreenInput {
  session: AuthSession;
  pwChange: PasswordChangeState;
  /** 라우터의 location.key. 같은 주소로 다시 와도 바뀐다. */
  navKey: string;
  state: SettingsUiState;
  setState: (patch: Partial<SettingsUiState> | ((current: SettingsUiState) => Partial<SettingsUiState>)) => void;
}

const CLOSED: Partial<SettingsUiState> = { pwFor: null, current: "", next: "", confirm: "" };

/** 알림 설정 줄(디자인). 서버에 없어 모두 꺼진 채로 막는다. */
const NOTIFY_LABELS = ["긴급 응답 즉시 알림", "상담 30분 전 브리핑 알림", "STT 분석 완료 알림"];

export function settingsValues(input: SettingsScreenInput) {
  const { session, pwChange, navKey, state, setState } = input;
  const me = session.me;
  const profile = me ? toProfileView(me) : null;
  const view: SettingsView = state.viewKey === navKey ? state.view : "home";
  const pwOpen = view === "account" && Boolean(me) && state.pwFor === me?.id;
  const titles: Record<SettingsView, string> = { home: "설정", account: "계정", notify: "알림 설정" };
  const field = (key: "current" | "next" | "confirm") => ({
    value: pwOpen ? state[key] : "",
    onChange: (e: { target: { value: string } }) => setState({ [key]: e.target.value }),
  });

  return {
    ...sidebarValues(session),
    notice: screenNotice({ session }),
    title: titles[view],
    subTitle: titles[view],
    atHome: view === "home",
    inSub: view !== "home",
    isAccount: view === "account",
    isNotify: view === "notify",
    goHome: () => setState({ view: "home", viewKey: null, ...CLOSED }),
    goAccount: () => setState({ view: "account", viewKey: navKey, ...CLOSED }),
    goNotify: () => setState({ view: "notify", viewKey: navKey, ...CLOSED }),
    notReady: NOT_READY,

    // ---------------- 계정 ----------------
    name: profile ? profile.name : NOT_PROVIDED,
    mail: profile ? profile.email : NOT_PROVIDED,
    role: profile ? profile.roleLabel : NOT_PROVIDED,
    joined: profile?.joinedDate || NOT_PROVIDED,
    organization: profile ? profile.organization : NOT_PROVIDED,
    pwText: `마지막 변경 ${profile ? profile.passwordChangedAt : NOT_PROVIDED}`,
    pwOpen,
    pwLabel: pwOpen ? "닫기" : "비밀번호 바꾸기",
    pwCls: pwOpen ? "btn-s" : "btn-p",
    togglePw: () => {
      pwChange.clearErrors();
      setState(pwOpen || !me ? CLOSED : { ...CLOSED, pwFor: me.id });
    },
    current: field("current"),
    next: field("next"),
    confirm: field("confirm"),
    ruleText: PASSWORD_RULE_TEXT,
    pwErrors: pwOpen ? pwChange.errors : [],
    pwBusy: pwChange.submitting,
    pwSubmitLabel: pwChange.submitting ? "바꾸는 중…" : "새 비밀번호로 바꾸기",
    submitPw: async (e: { preventDefault: () => void }) => {
      e.preventDefault();
      if (!pwOpen) return;

      // 성공하면 로그아웃되어 로그인 화면으로 간다(Settings.jsx 의 needsLogin).
      // 응답을 기다리는 사이 다른 탭에서 다른 계정으로 바뀌어 그 계정이 칸을 새로 열었으면 그 칸은 건드리지 않는다.
      const forUser = state.pwFor;
      const ok = await pwChange.change({
        currentPassword: state.current,
        newPassword: state.next,
        confirmPassword: state.confirm,
      });

      if (ok) setState((current) => (current.pwFor === forUser ? CLOSED : {}));
    },

    // ---------------- 알림 설정 ----------------
    toggles: NOTIFY_LABELS.map((label) => ({ label, bg: "#DAD5C9", x: "3px", on: "false" })),
  };
}
