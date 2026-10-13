// 계정이 바뀌었다는 알림. 관리자 화면이 훅 여러 개(대시보드 · 계정 관리 · 접속 기록)를 함께 쓸 때
// 계정 관리 훅의 요청(등록 · 활성/비활성 · 잠금 해제 등)으로 숫자 · 기록이 바뀌면 다른 훅이 조용히 다시 조회하게 한다.
// sessionEvents 와 같은 방식이다. 같은 탭 안에서만 알린다.

export const ACCOUNTS_CHANGED_EVENT = "ispot:accounts-changed";

export function notifyAccountsChanged(): void {
  window.dispatchEvent(new Event(ACCOUNTS_CHANGED_EVENT));
}

/** 알림을 받는다. 그만 받을 때 부를 함수를 돌려준다. */
export function onAccountsChanged(listener: () => void): () => void {
  window.addEventListener(ACCOUNTS_CHANGED_EVENT, listener);

  return () => window.removeEventListener(ACCOUNTS_CHANGED_EVENT, listener);
}
