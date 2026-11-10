// 상담사 앱(폰) 연결 없이 열기 — 서비스워커(2026-11-10).
//
// 앱 화면에서 등록한다(src/data/useAppInstall.ts). 하는 일은 '화면 파일을 폰에 저장해 두었다가 연결이 없을 때 내주기' 뿐이다.
//  - 화면 첫 문서(/, /index.html, /app/): 늘 서버에서 먼저 받는다(새로 배포한 화면이 바로 보이게). 받으면 저장해 두고,
//    연결이 없을 때만 저장한 것을 내준다. 새 문서를 받으면 그 문서가 쓰지 않는 옛 화면 파일(assets)은 지운다.
//  - 화면 파일(/assets/* — 빌드마다 이름이 바뀌므로 내용이 안 바뀜) · 앱 아이콘(/app/*): 저장한 것이 있으면 그것, 없으면 받아서 저장.
//  - 글꼴(Google Fonts): 저장한 것을 먼저, 뒤에서 새로 받아 둔다.
//  - API(/api/*) · 아동 앱(/child-app/*) · 그 밖의 요청은 손대지 않는다(상담 자료는 폰에 저장하지 않는다 — 녹음 대기열은 앱이 따로 둔다).

const SHELL = "ispot-app-shell-v1";
// 저장한 것을 꺼낼 때 Vary 는 보지 않는다(서버가 Vary: Origin 을 붙이면 같은 파일인데 못 찾는다).
const FONTS = "ispot-app-fonts-v1";

const isDoc = (url) => url.origin === self.location.origin && (url.pathname === "/" || url.pathname === "/index.html");
const isAppPage = (url) => url.origin === self.location.origin && (url.pathname === "/app/" || url.pathname === "/app/index.html");
const isAsset = (url) => url.origin === self.location.origin && (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/app/"));
const isFont = (url) => url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com";

/** 문서가 쓰는 화면 파일 주소들. */
function assetsIn(html) {
  const found = new Set();
  const re = /(?:\.\/|\/)?(assets\/[^"'\s>]+)/g;
  let m;

  while ((m = re.exec(html))) found.add(new URL("/" + m[1], self.location.origin).href);

  return [...found];
}

/** 새 문서를 저장하고, 그 문서의 화면 파일을 미리 받고, 쓰지 않는 옛 파일을 지운다. */
async function storeDoc(response) {
  const cache = await caches.open(SHELL);
  const html = await response.clone().text();
  const wanted = assetsIn(html);

  await cache.put(new URL("/", self.location.origin).href, response.clone());
  await Promise.all(
    wanted.map(async (href) => {
      if (await cache.match(href, { ignoreVary: true })) return;
      try {
        const res = await fetch(href);
        if (res.ok) await cache.put(href, res);
      } catch {
        // 다음에 다시
      }
    }),
  );
  for (const req of await cache.keys()) {
    const url = new URL(req.url);
    if (url.pathname.startsWith("/assets/") && !wanted.includes(req.url)) await cache.delete(req);
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      try {
        const res = await fetch("/", { cache: "no-cache" });
        if (res.ok) await storeDoc(res);
        const cache = await caches.open(SHELL);
        await cache.addAll(["/app/", "/app/manifest.webmanifest", "/app/icon-192.png", "/app/icon-512.png", "/app/apple-touch-icon.png"]);
      } catch {
        // 연결이 없으면 다음 방문 때 채운다
      }
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) if (key !== SHELL && key !== FONTS) await caches.delete(key);
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;

  if (req.method !== "GET") return;

  const url = new URL(req.url);

  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/child-app/")) return;

  if (isDoc(url)) {
    event.respondWith(
      (async () => {
        try {
          const res = await fetch(req, { cache: "no-cache" });
          if (res.ok) event.waitUntil(storeDoc(res.clone()));
          return res;
        } catch {
          const cached = await caches.match(new URL("/", self.location.origin).href, { ignoreVary: true });
          return cached || Response.error();
        }
      })(),
    );
    return;
  }

  if (isAppPage(url)) {
    event.respondWith(
      (async () => {
        try {
          const res = await fetch(req, { cache: "no-cache" });
          if (res.ok) {
            const cache = await caches.open(SHELL);
            event.waitUntil(cache.put("/app/", res.clone()));
          }
          return res;
        } catch {
          return (await caches.match("/app/", { ignoreVary: true })) || Response.error();
        }
      })(),
    );
    return;
  }

  if (isAsset(url)) {
    event.respondWith(
      (async () => {
        const cached = await caches.match(req, { ignoreVary: true });
        if (cached) return cached;
        const res = await fetch(req);
        if (res.ok) {
          const cache = await caches.open(SHELL);
          event.waitUntil(cache.put(req, res.clone()));
        }
        return res;
      })(),
    );
    return;
  }

  if (isFont(url)) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(FONTS);
        const cached = await cache.match(req, { ignoreVary: true });
        const fresh = fetch(req)
          .then((res) => {
            if (res.ok || res.type === "opaque") cache.put(req, res.clone());
            return res;
          })
          .catch(() => null);
        if (cached) {
          event.waitUntil(fresh);
          return cached;
        }
        return (await fresh) || Response.error();
      })(),
    );
  }
});
