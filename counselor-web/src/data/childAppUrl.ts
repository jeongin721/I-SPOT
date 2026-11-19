// 아이 앱(콩콩) 주소(2026-11-19). 배포가 아이 앱을 상담사 화면과 다른 주소(deploy/web-deploy.sh KID_SITE)로 낸다.
//  - 빌드 때 VITE_CHILD_APP_URL 을 넣으면 그 주소(배포 스크립트가 https://<KID_SITE>/ 로 넣는다).
//  - 없으면 지금 주소가 sslip.io · nip.io 면 배포 기본값과 같은 kong.<주소>, 아니면 같은 주소의 /child-app/(개발 · 예전 배포).

export function childAppUrl(): string {
  const fromEnv = (import.meta.env.VITE_CHILD_APP_URL as string | undefined)?.trim();
  if (fromEnv) return fromEnv.endsWith("/") ? fromEnv : `${fromEnv}/`;
  const { protocol, hostname, origin } = window.location;
  if (/\.(sslip|nip)\.io$/.test(hostname) && !hostname.startsWith("kong.")) return `${protocol}//kong.${hostname}/`;
  return `${origin}/child-app/`;
}

/** QR 에 넣는 주소. 연결 코드를 붙이면 아이 앱이 코드 칸을 채우고 주소창에서 지운다. */
export function childAppLinkUrl(code: string | null | undefined): string {
  const base = childAppUrl();
  return code ? `${base}?code=${encodeURIComponent(code)}` : base;
}

/** 화면에 적는 주소(https:// 와 끝 / 를 뺀 짧은 꼴). */
export function childAppUrlLabel(): string {
  return childAppUrl().replace(/^https?:\/\//, "").replace(/\/$/, "");
}
