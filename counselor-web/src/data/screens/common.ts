// 여러 화면이 함께 쓰는 값: 사이드바 내 정보 · 로그아웃, 로그인 화면으로 보낼지, 화면 위 안내 줄, 회차 상태 칩.
//
// src/data/screens/ 의 함수는 훅 결과를 받아 화면의 예시 데이터를 대신할 값(문자열 · 목록 · 링크 · 이벤트 함수)을 만든다.
// 화면 파일(.jsx)은 훅을 부르고 결과를 useDC(Logic, …) 로 넘긴 뒤 renderVals() 에서 이 함수를 부르기만 한다.
// 피그마 화면으로 바꿀 때는 JSX 만 바꾸고 이 함수들은 그대로 쓴다(배치가 달라 필요한 값이 다르면 여기에 더한다).

import type { AuthSession } from "../useAuthSession";
import type { SessionTone } from "../sessionRows";

/** 사이드바 아래 내 정보와 로그아웃. 로그아웃 링크는 /Login 으로 옮기기 전에 이 함수로 로그아웃한다. */
export function sidebarValues(session: AuthSession): { meName: string; meInitial: string; logout: () => void } {
  const me = session.me;

  return {
    meName: me ? `${me.name} ${me.role === "ADMIN" ? "관리자" : "상담원"}` : "",
    meInitial: me && me.name ? Array.from(me.name)[0] : "",
    logout: () => session.logout(),
  };
}

/** 로그인하지 않았거나 임시 비밀번호 상태라 로그인 화면(비밀번호 변경 단계)으로 보내야 하는가. */
export function needsLogin(session: AuthSession): boolean {
  return session.status === "signedOut" || session.status === "mustChangePassword";
}

/** 로그인이 확인된 뒤에만 서버를 부르도록 훅에 넘기는 값. */
export function signedIn(session: AuthSession): boolean {
  return session.status === "signedIn";
}

/**
 * 화면 위에 한 줄로 보여 줄 안내(불러오는 중 · 오류 · 대상이 없음). 없으면 null.
 * alert 면 오류다(role="alert"). retry 가 있으면 '다시 시도' 단추, href 가 있으면 링크를 함께 보인다.
 */
export interface ScreenNotice {
  text: string;
  alert: boolean;
  retry: (() => void) | null;
  href: string | null;
  hrefLabel: string;
}

export function notice(text: string, extra: Partial<Omit<ScreenNotice, "text">> = {}): ScreenNotice {
  return { text, alert: false, retry: null, href: null, hrefLabel: "", ...extra };
}

/**
 * 로그인 확인 → 대상 ID → 불러오기 순으로 안내를 고른다. 모두 괜찮으면 null.
 * missing 은 주소에 필요한 ID 가 없을 때 보여 줄 안내다.
 */
export function screenNotice(input: {
  session: AuthSession;
  missing?: ScreenNotice | null;
  loading?: boolean;
  error?: string | null;
  retry?: () => void;
}): ScreenNotice | null {
  const { session } = input;

  if (session.status === "checking") return notice("로그인 상태를 확인하는 중…");
  if (session.status === "error") {
    return notice(session.error ?? "로그인 상태를 확인하지 못했습니다.", { alert: true, retry: session.recheck });
  }
  if (input.missing) return input.missing;
  if (input.error) return notice(input.error, { alert: true, retry: input.retry ?? null });
  if (input.loading) return notice("불러오는 중…");

  return null;
}

/** 회차 상태 칩의 class. 색만으로 상태를 나타내지 않도록 칩 글자는 항상 상태 이름(statusLabel)이다. */
export const TONE_CHIP: Record<SessionTone, string> = {
  progress: "chip c-sky",
  action: "chip c-check",
  failed: "chip c-urgent",
  done: "chip c-ok",
};

/** 서버에 아직 없는 기능 · 값의 자리 표시. */
export const NOT_READY = "준비 중";
