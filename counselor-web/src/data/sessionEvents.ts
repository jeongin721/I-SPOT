// 회차가 바뀌었다는 알림. 한 화면이 훅 여러 개(회차 상세 · 원문 검수 · AI 분석 · 요약 · 사례 상세)를 함께 쓸 때
// 한 훅에서 보낸 요청(업로드 · 원문 확정 · 분석 요청 · 승인 등)으로 회차 상태가 바뀌면, 같은 회차를 보는 다른 훅이
// 옛 상태로 단추를 막고 있지 않게 조용히 다시 조회하게 한다.
//
// 요청을 보낸 훅이 notifySessionChanged 를 부르고, useRemote 가 받아서 맞는 대상이면 refresh 한다.
// 같은 탭 안에서만 알린다(다른 탭은 각자 되풀이 조회 · 새로고침으로 맞춘다).

export const SESSION_CHANGED_EVENT = "ispot:session-changed";

export interface SessionChange {
  sessionId: string;
  /** 알면 넣는다. 사례 상세가 자기 사례의 회차인지 알아보는 데 쓴다. */
  caseId?: string | null;
}

export function notifySessionChanged(change: SessionChange): void {
  window.dispatchEvent(new CustomEvent<SessionChange>(SESSION_CHANGED_EVENT, { detail: change }));
}

/** 알림을 받는다. 그만 받을 때 부를 함수를 돌려준다. */
export function onSessionChanged(listener: (change: SessionChange) => void): () => void {
  const handler = (event: Event) => listener((event as CustomEvent<SessionChange>).detail);

  window.addEventListener(SESSION_CHANGED_EVENT, handler);

  return () => window.removeEventListener(SESSION_CHANGED_EVENT, handler);
}
