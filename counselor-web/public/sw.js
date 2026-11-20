// 상담사 앱(폰) 연결 없이 열기 — 서비스워커(2026-11-10).
//
// 앱 화면에서 등록한다(src/data/useAppInstall.ts). 하는 일은 '화면 파일을 폰에 저장해 두었다가 연결이 없을 때 내주기' 뿐이다.
//  - 화면 첫 문서(/, /index.html, /app/): 늘 서버에서 먼저 받는다(새로 배포한 화면이 바로 보이게). 받으면 저장해 두고,
//    연결이 없을 때만 저장한 것을 내준다. 새 문서를 받으면 그 문서가 쓰지 않는 옛 화면 파일(assets)은 지운다.
//  - 화면 파일(/assets/* — 빌드마다 이름이 바뀌므로 내용이 안 바뀜) · 앱 아이콘(/app/*): 저장한 것이 있으면 그것, 없으면 받아서 저장.
//  - 글꼴(Google Fonts): 저장한 것을 먼저, 뒤에서 새로 받아 둔다.
//  - 폰 알림(2026-11-19, API_CONTRACT 27절): 서버가 보낸 푸시(상담 30분 전 · 아이 긴급 알림 · 시험)를 띄우고, 누르면 앱의 그 화면을 연다.
//    문구는 서버가 정한다(아이 이름 · 사례 내용 없음). 내용을 못 읽으면 일반 문구로 띄운다(iPhone 은 푸시마다 알림을 꼭 띄워야 한다).
//  - API(/api/*) · 아동 앱(/child-app/*) · 그 밖의 요청은 손대지 않는다(상담 자료는 폰에 저장하지 않는다 — 녹음 대기열은 앱이 따로 둔다).

const SHELL = "ispot-app-shell-v2";
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
        await cache.addAll(["/app/", "/app/manifest.webmanifest", "/app/icon-192.png", "/app/icon-512.png", "/app/apple-touch-icon.png", "/app/lame.min.js"]);
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

self.addEventListener("push", (event) => {
  let msg = {};

  try {
    msg = event.data ? event.data.json() : {};
  } catch {
    msg = {};
  }

  // 같은 사이트 안의 경로만 받는다. "//host" · "/\\host" 는 다른 사이트로 가므로 막는다(민규 #186).
  const url = typeof msg.url === "string" && msg.url.startsWith("/") && !/^\/[\/\\]/.test(msg.url) ? msg.url : "/#/AppHome";

  event.waitUntil(
    self.registration.showNotification(msg.title || "I-SPOT", {
      body: msg.body || "새 알림이 있어요.",
      tag: msg.tag || undefined,
      icon: "/app/icon-192.png",
      badge: "/app/icon-192.png",
      data: { url },
    }),
  );
});

// 브라우저가 구독을 바꾸거나 없앴으면 같은 서버 키로 다시 구독해 둔다(11/20 점검).
// 서비스워커에는 로그인 토큰이 없어 서버에 바로 알리지 못한다 — 앱을 열 때 syncPush 가 새 구독을 서버에 저장하고,
// 옛 구독은 서버가 다음에 보낼 때 404 · 410 을 받고 지운다.
self.addEventListener("pushsubscriptionchange", (event) => {
  const key = event.oldSubscription && event.oldSubscription.options && event.oldSubscription.options.applicationServerKey;
  if (!key || event.newSubscription) return;
  event.waitUntil(
    self.registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }).catch(() => undefined),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const asked = new URL((event.notification.data && event.notification.data.url) || "/#/AppHome", self.location.origin);
  // 알림을 누르면 이 사이트 안에서만 연다(민규 #186).
  const url = asked.origin === self.location.origin ? asked.href : new URL("/#/AppHome", self.location.origin).href;

  event.waitUntil(
    (async () => {
      const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });

      for (const win of wins) {
        if (new URL(win.url).origin === self.location.origin && "focus" in win) {
          await win.focus();
          if ("navigate" in win) await win.navigate(url).catch(() => undefined);
          return;
        }
      }

      await self.clients.openWindow(url);
    })(),
  );
});
