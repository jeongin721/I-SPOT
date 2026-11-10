// 폰 마이크 녹음기(앱 · 녹음 화면). MediaRecorder 로 녹음하고 1초마다 조각을 IndexedDB 에 저장한다(appRecordings).
//
//  idle → (start) rec ⇄ paused → (stop) done → (save) 대기열 · (reset) idle
//  - 녹음기는 앱 전체에 하나다(이 모듈). 녹음 중에 아래 탭으로 업로드 목록 등에 다녀와도 녹음은 계속되고,
//    녹음 화면으로 돌아오면 그대로 이어서 보인다.
//  - 형식은 브라우저가 되는 것 중 서버가 받는 것: iPhone(Safari)은 audio/mp4(.m4a), 안드로이드 · PC Chrome 은 audio/webm(.webm).
//  - 녹음하는 동안 화면이 꺼지지 않게 한다(Wake Lock, 되는 브라우저만). 화면이 꺼지면 폰이 녹음을 멈출 수 있어서다.
//  - 녹음 시간은 일시정지를 뺀 시간이다. 올릴 때 duration_ms 로 함께 보낸다.
//  - 앱이 꺼지거나 탭을 닫으면 녹음은 멈춘다. 그때까지의 조각은 남아 다음에 열 때 업로드 목록에 되살아난다(recoverDrafts).

import { useSyncExternalStore } from "react";

import { discardDraft, saveChunk, startDraft, type RecordingDraft } from "./appRecordings";

export type RecorderPhase = "idle" | "rec" | "paused" | "done";

const CANDIDATES: { mime: string; ext: string }[] = [
  { mime: "audio/mp4", ext: ".m4a" },
  { mime: "audio/webm;codecs=opus", ext: ".webm" },
  { mime: "audio/webm", ext: ".webm" },
  { mime: "audio/ogg;codecs=opus", ext: ".ogg" },
];

function pickFormat(): { mime: string; ext: string } | null {
  if (typeof MediaRecorder === "undefined") return null;

  for (const candidate of CANDIDATES) {
    try {
      if (MediaRecorder.isTypeSupported(candidate.mime)) return candidate;
    } catch {
      // 오래된 브라우저
    }
  }

  return null;
}

export type DraftInfo = Omit<RecordingDraft, "id" | "mime" | "ext" | "durationMs" | "heartbeat">;

export interface RecorderSnapshot {
  phase: RecorderPhase;
  /** 녹음 시간(밀리초, 일시정지 뺌). */
  elapsedMs: number;
  error: string | null;
  /** 녹음 중인(마친) 조각 묶음. 저장할 때 쓴다. */
  draft: RecordingDraft | null;
}

let snapshot: RecorderSnapshot = { phase: "idle", elapsedMs: 0, error: null, draft: null };
const listeners = new Set<() => void>();

function set(patch: Partial<RecorderSnapshot>) {
  snapshot = { ...snapshot, ...patch };
  listeners.forEach((fn) => fn());
}

let recorder: MediaRecorder | null = null;
let stream: MediaStream | null = null;
let seq = 0;
let saving: Promise<void> = Promise.resolve();
let banked = 0;
let segmentStart: number | null = null;
let timer: number | null = null;
let wakeLock: { release: () => Promise<void> } | null = null;

const now = () => banked + (segmentStart !== null ? Date.now() - segmentStart : 0);

async function lockScreen() {
  try {
    const nav = navigator as Navigator & { wakeLock?: { request: (type: "screen") => Promise<{ release: () => Promise<void> }> } };

    if (nav.wakeLock && !wakeLock) wakeLock = await nav.wakeLock.request("screen");
  } catch {
    // 안 되는 브라우저 · 절전 모드
  }
}

function unlockScreen() {
  wakeLock?.release().catch(() => {});
  wakeLock = null;
}

function releaseMic() {
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
}

function tick(on: boolean) {
  if (timer !== null) window.clearInterval(timer);
  timer = on ? window.setInterval(() => set({ elapsedMs: now() }), 250) : null;
}

if (typeof document !== "undefined") {
  // 화면이 다시 보이면 화면 꺼짐 막기를 다시 건다(가려지면 브라우저가 풀어 버린다).
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && recorder?.state === "recording") {
      wakeLock = null;
      void lockScreen();
    }
  });
}

export async function startRecording(info: DraftInfo): Promise<boolean> {
  if (snapshot.phase !== "idle") return false;

  set({ error: null });
  const format = pickFormat();

  if (!format || !navigator.mediaDevices?.getUserMedia) {
    set({ error: "이 브라우저에서는 녹음할 수 없어요. 휴대폰의 Chrome 이나 Safari 로 열어 주세요." });
    return false;
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true },
    });
  } catch (caught) {
    const name = caught instanceof DOMException ? caught.name : "";

    set({
      error:
        name === "NotAllowedError"
          ? "마이크 사용을 허용해 주세요. 브라우저 주소창의 사이트 설정에서 마이크를 허용할 수 있어요."
          : "마이크를 켜지 못했어요. 다른 앱이 마이크를 쓰고 있는지 확인해 주세요.",
    });
    return false;
  }

  const id = `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const draft: RecordingDraft = { ...info, id, mime: format.mime.split(";")[0], ext: format.ext, durationMs: 0, heartbeat: Date.now() };

  try {
    await startDraft(draft);
  } catch {
    releaseMic();
    set({ error: "폰에 녹음을 저장할 수 없어요. 사생활 보호(시크릿) 창이면 일반 창으로 열어 주세요." });
    return false;
  }

  let media: MediaRecorder;

  try {
    media = new MediaRecorder(stream, { mimeType: format.mime });
  } catch {
    media = new MediaRecorder(stream);
  }

  seq = 0;
  saving = Promise.resolve();
  media.ondataavailable = (event) => {
    if (!event.data || event.data.size === 0) return;

    const index = seq++;
    const duration = now();

    saving = saving
      .then(() => saveChunk(id, index, event.data, duration))
      .catch(() => {
        set({ error: "폰 저장 공간이 부족해 녹음을 저장하지 못하고 있어요. 녹음을 멈추고 공간을 확보해 주세요." });
      });
  };

  recorder = media;
  banked = 0;
  segmentStart = Date.now();
  media.start(1000);
  tick(true);
  void lockScreen();
  set({ phase: "rec", elapsedMs: 0, draft });

  return true;
}

export function pauseRecording(): void {
  if (recorder?.state !== "recording") return;

  recorder.pause();
  banked = now();
  segmentStart = null;
  tick(false);
  set({ phase: "paused", elapsedMs: banked });
}

export function resumeRecording(): void {
  if (recorder?.state !== "paused") return;

  recorder.resume();
  segmentStart = Date.now();
  tick(true);
  set({ phase: "rec" });
}

export async function stopRecording(): Promise<void> {
  const media = recorder;

  if (!media || media.state === "inactive") return;

  banked = now();
  segmentStart = null;
  tick(false);

  // 마지막 조각(dataavailable)이 저장될 때까지 기다린다.
  await new Promise<void>((resolve) => {
    media.addEventListener("stop", () => resolve(), { once: true });
    media.stop();
  });
  await saving;
  releaseMic();
  unlockScreen();
  recorder = null;
  set({ phase: "done", elapsedMs: banked, draft: snapshot.draft ? { ...snapshot.draft, durationMs: banked } : null });
}

/** 저장한 뒤 처음으로(조각은 대기열로 옮겨졌다). */
export function clearRecording(): void {
  banked = 0;
  set({ phase: "idle", elapsedMs: 0, error: null, draft: null });
}

/** 마친 녹음을 버리고 처음으로(다시 녹음). */
export function resetRecording(): void {
  const old = snapshot.draft;

  if (old) void discardDraft(old.id);
  clearRecording();
}

export function setRecorderError(error: string | null): void {
  set({ error });
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useRecorder(): RecorderSnapshot {
  return useSyncExternalStore(subscribe, () => snapshot);
}

/** 지금 이 탭에서 녹음 중(또는 마치고 저장 전)인 조각 묶음. 끊긴 녹음 되살리기에서 건너뛴다. */
export function activeDraftId(): string | null {
  return snapshot.draft?.id ?? null;
}
