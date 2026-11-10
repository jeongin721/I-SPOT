// 상담사 앱(폰) · 메모 저장(현장에서 바로 적어 두기).
//
// 메모를 둘 서버 자리가 아직 없어 **이 폰에만** 계정별로 저장한다(localStorage 'ispot-app-memo:<계정 ID>').
// 다른 기기 · 웹에서는 보이지 않는다. 로그아웃해도 지우지 않는다(지우면 적어 둔 것을 잃는다 — 녹음 대기열과 같은 판단).
// 서버에 메모 자리가 생기면 이 파일만 API 로 바꾸면 된다.

export interface AppMemo {
  id: string;
  caseId: string | null;
  /** 적을 때의 아이 이름(목록 표시용). */
  childLabel: string;
  text: string;
  createdAt: number;
  updatedAt: number;
}

const keyOf = (userId: string) => `ispot-app-memo:${userId}`;

export function readMemos(userId: string): AppMemo[] {
  try {
    const rows = JSON.parse(localStorage.getItem(keyOf(userId)) || "[]");

    return Array.isArray(rows) ? (rows as AppMemo[]).sort((a, b) => b.createdAt - a.createdAt) : [];
  } catch {
    return [];
  }
}

/** 저장하지 못하면(저장 공간 · 사생활 보호 창) false. */
export function writeMemos(userId: string, rows: AppMemo[]): boolean {
  try {
    localStorage.setItem(keyOf(userId), JSON.stringify(rows));
    return true;
  } catch {
    return false;
  }
}
