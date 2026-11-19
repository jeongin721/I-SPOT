// 상담사 앱(폰) 알림 — 웹 푸시(API_CONTRACT 27절, 2026-11-19).
//
//  - 알림 받기: 폰 알림 허락 → 서비스워커(public/sw.js)로 푸시 구독 → 서버에 구독 · 이 폰의 설정을 저장(PUT /push/subscription)
//    → '알림이 켜졌어요' 시험 알림. 끄면 구독을 지우고 서버에서도 지운다.
//  - 상담 30분 전 알림: 서버가 보낸다(이 폰 설정 before_session).
//  - 업로드 실패 알림: 녹음은 폰에 있으므로 폰이 스스로 띄운다(notifyUploadFailed — 녹음 하나에 한 번). 서버에는 설정만 둔다.
//  - 설정은 폰마다 다르다. 이 폰에 기억하고(localStorage), 앱을 열 때 서버와 맞춘다(다른 계정으로 로그인했으면 그 계정으로 옮겨짐).
//  - iPhone 은 '홈 화면에 추가' 한 앱에서만 웹 푸시가 된다(iOS 16.4+). 브라우저 탭에서는 켤 수 없다고 알린다.
//  - 잠금 화면에 보이므로 알림 문구에 아이 이름 · 사례 내용을 넣지 않는다(서버도 같은 규칙).

import { push } from "../api/endpoints";
import type { PushPrefs } from "../api/types";

const PREFS_KEY = "ispot.app.push";

interface Stored extends PushPrefs {
  on: boolean;
}

const DEFAULT: Stored = { on: false, before_session: true, upload_failed: true };

export function readPushPrefs(): Stored {
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    return raw ? { ...DEFAULT, ...(JSON.parse(raw) as Partial<Stored>) } : DEFAULT;
  } catch {
    return DEFAULT;
  }
}

function writePushPrefs(next: Stored): void {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(next));
  } catch {
    // 저장이 막힌 브라우저면 이번만
  }
}

/** 이 폰(브라우저)이 웹 푸시를 지원하는가. iPhone Safari 탭은 false(홈 화면 앱에서만 true). */
export function pushSupported(): boolean {
  try {
    return window.isSecureContext && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  } catch {
    return false;
  }
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const pad = "=".repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob((base64url + pad).replace(/-/g, "+").replace(/_/g, "/"));
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));

  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);

  return bytes;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  // 앱 화면이 sw.js 를 등록한다(useAppInstall). 아직이면 여기서 등록한다.
  const existing = await navigator.serviceWorker.getRegistration("/");
  if (!existing) await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  return navigator.serviceWorker.ready;
}

async function save(sub: PushSubscription, prefs: PushPrefs): Promise<void> {
  const json = sub.toJSON();
  await push.subscribe({
    endpoint: sub.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
    before_session: prefs.before_session,
    upload_failed: prefs.upload_failed,
  });
}

export type EnableResult = "ok" | "denied" | "unsupported" | "disabled";

/** 알림 받기 켜기. 폰 알림 허락 창은 사용자가 스위치를 눌렀을 때만 띄운다(브라우저 규칙). */
export async function enablePush(): Promise<EnableResult> {
  if (!pushSupported()) return "unsupported";

  const config = await push.config();
  if (!config.enabled || !config.public_key) return "disabled";

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return "denied";

  const reg = await registration();
  let sub = await reg.pushManager.getSubscription();
  const key = keyBytes(config.public_key);

  // 서버 키가 바뀌었으면 옛 구독은 쓸 수 없다. 새로 만든다.
  if (sub && sub.options.applicationServerKey) {
    const old = new Uint8Array(sub.options.applicationServerKey);
    if (old.length !== key.length || old.some((b, i) => b !== key[i])) {
      await sub.unsubscribe().catch(() => false);
      sub = null;
    }
  }

  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });

  const prefs = { ...readPushPrefs(), on: true };
  await save(sub, prefs);
  writePushPrefs(prefs);
  push.test().catch(() => undefined);

  return "ok";
}

/** 알림 받기 끄기 · 로그아웃. 서버에서 지우지 못해도(연결 없음) 폰 구독은 지운다 — 서버는 다음 보내기 때 410 을 받고 지운다. */
export async function disablePush(): Promise<void> {
  const prefs = readPushPrefs();
  writePushPrefs({ ...prefs, on: false });

  if (!pushSupported()) return;

  const reg = await navigator.serviceWorker.getRegistration("/");
  const sub = await reg?.pushManager.getSubscription();
  if (!sub) return;

  await push.unsubscribe(sub.endpoint).catch(() => undefined);
  await sub.unsubscribe().catch(() => false);
}

/**
 * 로그인이 풀렸을 때(토큰 만료 · 웹 로그아웃 · 비밀번호 변경 · 다른 탭 로그아웃) 이 폰의 구독을 지운다.
 * 같은 폰을 다음에 쓰는 분께 앞 분의 알림이 가지 않게(민규 #186). 토큰이 이미 없어 서버에는 지우라고 못 하지만,
 * 폰 구독을 지우면 푸시 서비스가 404 · 410 을 주고 서버는 다음 보내기 때 그 구독을 지운다.
 */
export async function dropPushOnSignOut(): Promise<void> {
  const prefs = readPushPrefs();
  if (prefs.on) writePushPrefs({ ...prefs, on: false });

  if (!pushSupported()) return;

  const reg = await navigator.serviceWorker.getRegistration("/");
  const sub = await reg?.pushManager.getSubscription();
  await sub?.unsubscribe().catch(() => false);
}

/** 상담 30분 전 · 업로드 실패 하나를 켜고 끈다. */
export async function setPushPref(name: keyof PushPrefs, value: boolean): Promise<void> {
  const prefs = { ...readPushPrefs(), [name]: value };
  writePushPrefs(prefs);

  if (!prefs.on || !pushSupported()) return;

  const reg = await navigator.serviceWorker.getRegistration("/");
  const sub = await reg?.pushManager.getSubscription();
  if (sub) await save(sub, prefs);
}

/**
 * 앱을 열 때 이 폰의 상태를 서버와 맞춘다. 알림 허락을 거두었거나 구독이 사라졌으면 '꺼짐' 으로 둔다.
 * 돌려주는 값은 화면이 보일 '알림 받기' 상태.
 */
export async function syncPush(): Promise<boolean> {
  const prefs = readPushPrefs();
  if (!prefs.on) return false;

  if (!pushSupported() || Notification.permission !== "granted") {
    writePushPrefs({ ...prefs, on: false });
    return false;
  }

  const reg = await navigator.serviceWorker.getRegistration("/");
  const sub = await reg?.pushManager.getSubscription();

  if (!sub) {
    writePushPrefs({ ...prefs, on: false });
    return false;
  }

  await save(sub, prefs).catch(() => undefined);
  return true;
}

/** 녹음 올리기가 실패했을 때(녹음 하나에 한 번). 알림 받기 · 업로드 실패 알림이 켜져 있고 허락돼 있을 때만. */
export function notifyUploadFailed(): void {
  try {
    const prefs = readPushPrefs();
    if (!prefs.on || !prefs.upload_failed || !pushSupported() || Notification.permission !== "granted") return;

    navigator.serviceWorker.ready
      .then((reg) =>
        reg.showNotification("녹음 올리기 실패", {
          body: "올리지 못한 녹음이 있어요. 앱에서 확인해 주세요.",
          tag: "ispot-upload-failed",
          icon: "/app/icon-192.png",
          data: { url: "/#/AppUpload" },
        }),
      )
      .catch(() => undefined);
  } catch {
    // 알림을 못 띄워도 업로드 목록에는 '실패' 로 남는다
  }
}
