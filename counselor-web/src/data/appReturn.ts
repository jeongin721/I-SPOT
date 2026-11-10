// 상담사 앱(폰) 화면에서 로그인 화면으로 보냈을 때, 로그인한 뒤 그 앱 화면으로 돌아오게 하는 표시.
// 로그인 화면은 웹과 같이 쓴다. 이 표시가 없으면 로그인 화면은 원래대로 웹 홈(/Main)으로 간다.

const KEY = "ispot-app-return";
const ALLOWED = new Set(["/AppHome", "/AppCases", "/AppBrief", "/AppRecord", "/AppUpload", "/AppSchedule", "/AppMemo", "/AppSettings"]);

export function rememberAppReturn(path: string): void {
  try {
    if (ALLOWED.has(path)) sessionStorage.setItem(KEY, path);
  } catch {
    // 저장이 막힌 브라우저면 로그인 뒤 웹 홈으로 간다.
  }
}

/** 남겨 둔 앱 화면 주소를 꺼내고 지운다. 없으면 null. */
export function takeAppReturn(): string | null {
  try {
    const path = sessionStorage.getItem(KEY);

    sessionStorage.removeItem(KEY);

    return path && ALLOWED.has(path) ? path : null;
  } catch {
    return null;
  }
}
