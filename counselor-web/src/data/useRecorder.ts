// 폰 마이크 녹음기(앱 · 녹음 화면). MediaRecorder 로 녹음하고 1초마다 조각을 IndexedDB 에 저장한다(appRecordings).
//
//  idle → (start) rec ⇄ paused → (stop) done → (save) 대기열 · (reset) idle
//  - 녹음기는 앱 전체에 하나다(이 모듈). 녹음 중에 아래 탭으로 업로드 목록 등에 다녀와도 녹음은 계속되고,
//    녹음 화면으로 돌아오면 그대로 이어서 보인다.
//  - 형식은 브라우저가 되는 것 중 서버가 받는 것: iPhone(Safari)은 audio/mp4(.m4a), 안드로이드 · PC Chrome 은 audio/webm(.webm).
//  - 녹음하는 동안 화면이 꺼지지 않게 한다(Wake Lock, 되는 브라우저만). 화면이 꺼지면 폰이 녹음을 멈출 수 있어서다.
//  - 녹음 시간은 일시정지를 뺀 시간이다. 올릴 때 duration_ms 로 함께 보낸다.
//  - 녹음하는 동안 이 녹음의 잠금(Web Locks)을 잡고, 일시정지 중에도 5초마다 살아 있음을 표시한다. 다른 탭에서 앱을 열어도
//    이 녹음을 '끊긴 녹음' 으로 가져가지 않는다(민규 #168).
//
// 끊겼다가 이어서 녹음하기(11/11 경진님 — 전화 · 화면 꺼짐 뒤에도 같은 녹음을 이어서):
//  - 녹음기는 마이크를 바로 녹음하지 않고, 오디오 믹서(WebAudio MediaStreamDestination)를 녹음한다. 마이크는 그 믹서에 꽂는다.
//    전화 · 화면 꺼짐으로 폰이 마이크를 끊어도 녹음기는 살아 있으므로 '일시정지' 로 두고, '계속' 을 누르면 마이크를 다시 켜 믹서에
//    꽂고 같은 녹음기를 이어 간다 — 파일 하나 · 회차 하나다(파일 두 개를 이어 붙이면 m4a · webm 이 깨진다).
//  - 끊긴 동안의 소리는 녹음되지 않는다. 시간은 마지막 조각을 받은 때까지로 되돌린다(실제 녹음된 길이).
//  - 폰이 녹음기까지 끝내 버렸으면(오래 꺼져 있음 등) 이어 갈 수 없어 녹음된 데까지 '녹음 완료' 로 정리하고 알린다.
//  - 믹서를 못 쓰는 브라우저는 마이크를 바로 녹음한다(그때는 끊기면 '녹음 완료' 로 정리 — 11/11 오전 방식).
//  - 웹 앱은 화면이 꺼진 동안 녹음을 이어 갈 수 없다(브라우저가 마이크를 끊는다). 그동안은 비고, 돌아와 '계속' 을 누르면 이어진다.
//  - 앱이 꺼지거나 탭을 닫으면 녹음은 멈춘다. 그때까지의 조각은 남아 다음에 열 때 업로드 목록에 되살아난다(recoverDrafts).

import { useSyncExternalStore } from "react";

import { DbBlockedError, RECORDING_LOCK_PREFIX, discardDraft, saveChunk, startDraft, touchDraft, type RecordingDraft } from "./appRecordings";

export type RecorderPhase = "idle" | "rec" | "paused" | "done";

/** 녹음 비트레이트(말소리 · 원문 변환용). */
export const AUDIO_BPS = 32_000;

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

const MUTED_TEXT = "마이크가 잠시 끊겼어요(전화 등). 그동안은 소리가 녹음되지 않아요.";
const PAUSED_TEXT =
  "마이크가 끊겨(전화 · 화면 꺼짐 · 다른 앱) 일시정지했어요. '계속' 을 누르면 같은 녹음에 이어서 녹음해요. 끊긴 동안은 녹음되지 않았어요.";
const INTERRUPTED_TEXT = "마이크가 끊겨 녹음을 멈췄어요(전화 등). 녹음된 데까지 저장하고 올릴 수 있어요.";
const ENDED_TEXT =
  "화면이 오래 꺼져 있었거나 폰이 녹음을 끝내서 이어서 녹음할 수 없어요. 녹음된 데까지 저장하고 올릴 수 있어요. 녹음하는 동안에는 화면을 켜 두세요.";
const MIC_TEXT = "마이크를 다시 켜지 못했어요. 통화가 끝났는지 확인하고 다시 '계속' 을 눌러 주세요.";

let recorder: MediaRecorder | null = null;
/** 지금 꽂혀 있는 마이크. 끊기면 null 이 되고 '계속' 에서 다시 연다. */
let mic: MediaStream | null = null;
/** 믹서(녹음기가 녹음하는 곳). 못 쓰는 브라우저면 null — 그때는 마이크를 바로 녹음한다. */
let audioCtx: AudioContext | null = null;
let mixer: MediaStreamAudioDestinationNode | null = null;
let micNode: MediaStreamAudioSourceNode | null = null;
let seq = 0;
let saving: Promise<void> = Promise.resolve();
let banked = 0;
let segmentStart: number | null = null;
let timer: number | null = null;
let wakeLock: { release: () => Promise<void> } | null = null;
let heartbeat: number | null = null;
let releaseRecLock: (() => void) | null = null;
/** 우리가 정지를 부른 중인가. 아니면 녹음기가 스스로 멈춘 것이다. */
let stopping = false;
/** 마지막 조각을 받았을 때의 녹음 시간. 끊겼을 때 실제 녹음된 길이는 여기까지다. */
let lastDataElapsed = 0;
/**
 * 녹음 중 화면이 가려진 때의 녹음 시간. 가려진 동안 · 돌아온 직후 밀려 들어오는 조각은 이 시간 + 1초를 넘겨 세지 않는다
 * (꺼져 있던 시간이 녹음 길이에 더해지지 않게, 민규 #169 5). 돌아와서 마이크가 살아 있으면(그동안도 녹음됨) 풀고, 죽어 있으면
 * 일시정지로 두며 길이는 여기까지다.
 */
let hiddenAt: number | null = null;
/** 마지막 조각을 받은 실제 시각(Date.now). 화면이 다시 켜졌을 때 그동안 녹음이 이어졌는지 보는 데 쓴다. */
let lastChunkWall = 0;
/** 화면이 다시 켜졌을 때, 마지막 조각이 이보다 오래전이면 그동안 녹음이 멈춘 것으로 본다(조각은 1초마다 온다). */
const STALL_MS = 2500;

const now = () => banked + (segmentStart !== null ? Date.now() - segmentStart : 0);
const live = () => snapshot.phase === "rec" || snapshot.phase === "paused";
const micLive = () => !!mic && mic.getAudioTracks().some((t) => t.readyState === "live");

function holdRecLock(draftId: string) {
  const locks = (navigator as Navigator & { locks?: LockManager }).locks;

  if (!locks) return;

  locks
    .request(RECORDING_LOCK_PREFIX + draftId, () => new Promise<void>((resolve) => (releaseRecLock = resolve)))
    .catch(() => {});
}

function dropRecLock() {
  releaseRecLock?.();
  releaseRecLock = null;
}

function beat(on: boolean, draftId?: string) {
  if (heartbeat !== null) window.clearInterval(heartbeat);
  heartbeat = on && draftId ? window.setInterval(() => void touchDraft(draftId, now()).catch(() => {}), 5000) : null;
}

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

function tick(on: boolean) {
  if (timer !== null) window.clearInterval(timer);
  timer = on ? window.setInterval(() => set({ elapsedMs: now() }), 250) : null;
}

/** 마이크를 뺀다(믹서에서 떼고 끈다). 녹음기는 그대로다. */
function unplugMic() {
  try {
    micNode?.disconnect();
  } catch {
    // 이미 떨어짐
  }
  micNode = null;
  mic?.getTracks().forEach((track) => track.stop());
  mic = null;
}

function closeMixer() {
  unplugMic();
  audioCtx?.close().catch(() => {});
  audioCtx = null;
  mixer = null;
}

async function openMic(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true },
  });
}

/** 마이크를 믹서에 꽂고 끊김을 지켜본다. */
function plugMic(stream: MediaStream) {
  mic = stream;
  if (audioCtx && mixer) {
    micNode = audioCtx.createMediaStreamSource(stream);
    micNode.connect(mixer);
  }
  stream.getAudioTracks().forEach((track) => {
    track.addEventListener("ended", () => {
      if (mic === stream) void micLost();
    });
    track.addEventListener("mute", () => {
      if (mic === stream && snapshot.phase === "rec") set({ error: MUTED_TEXT });
    });
    track.addEventListener("unmute", () => {
      if (snapshot.error === MUTED_TEXT) set({ error: null });
    });
  });
}

/** 녹음기가 멈출 때까지(마지막 조각까지) 기다린다. 이미 멈췄거나 3초 안에 답이 없으면 그냥 넘어간다. */
function waitStop(media: MediaRecorder): Promise<void> {
  if (media.state === "inactive") return Promise.resolve();

  return new Promise<void>((resolve) => {
    const timeout = window.setTimeout(resolve, 3000);

    media.addEventListener(
      "stop",
      () => {
        window.clearTimeout(timeout);
        resolve();
      },
      { once: true },
    );
    try {
      media.stop();
    } catch {
      window.clearTimeout(timeout);
      resolve();
    }
  });
}

/** 녹음을 '녹음 완료' 로 정리한다. 녹음기 상태와 상관없이 늘 끝까지 한다. error 는 보일 안내(null 이면 지운다). */
async function finalize(durationMs: number, error: string | null): Promise<void> {
  segmentStart = null;
  banked = durationMs;
  tick(false);
  beat(false);
  await saving;
  closeMixer();
  unlockScreen();
  recorder = null;
  stopping = false;
  set({ phase: "done", elapsedMs: durationMs, draft: snapshot.draft ? { ...snapshot.draft, durationMs } : null, error });
}

/** 녹음기가 스스로 끝났다(이어 갈 수 없음). 녹음된 데까지로 정리하고 알린다. */
async function recorderEnded(reason: string): Promise<void> {
  if (!live() || stopping) return;

  stopping = true;
  if (recorder) await waitStop(recorder);
  await finalize(lastDataElapsed, reason);
}

/** 마이크가 끊겼다(전화 · 화면 꺼짐 · 다른 앱). 믹서가 있으면 일시정지로 두고 '계속' 을 기다린다. 없으면 녹음 완료로 정리. */
async function micLost(): Promise<void> {
  if (!live() || stopping) return;

  if (!mixer || !recorder || recorder.state === "inactive") {
    await recorderEnded(mixer ? ENDED_TEXT : INTERRUPTED_TEXT);
    return;
  }

  unplugMic();
  try {
    if (recorder.state === "recording") recorder.pause();
  } catch {
    // 이미 멈춤
  }
  // 녹음 중에 끊겼으면 그 사이 흐른 시간은 녹음되지 않았다 — 마지막 조각까지로 되돌린다. 이미 일시정지였으면 그대로.
  if (snapshot.phase === "rec") banked = lastDataElapsed;
  segmentStart = null;
  tick(false);
  set({ phase: "paused", elapsedMs: banked, error: PAUSED_TEXT });
}

if (typeof document !== "undefined") {
  // 화면이 다시 보이면: 녹음기가 끝났으면 정리, 마이크만 끊겼으면 일시정지(이어서 할 수 있게). 살아 있으면 화면 꺼짐 막기를 다시 건다.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      if (snapshot.phase === "rec") {
        hiddenAt = now();
        // 화면 시계는 멈춘다 — 꺼진 동안 녹음이 됐는지는 돌아와서 안다(11/11 실제 폰: 돌아오면 1분대로 튀었다가 몇 초 뒤 일시정지).
        tick(false);
      }
      return;
    }
    if (!live()) {
      hiddenAt = null;
      return;
    }

    if (!recorder || recorder.state === "inactive") {
      void recorderEnded(ENDED_TEXT).finally(() => (hiddenAt = null));
      return;
    }
    // 마이크가 죽었거나, 꺼진 동안 조각이 오지 않았으면(아이폰은 돌아온 순간엔 마이크가 살아 있다고 하고 몇 초 뒤에야 끊김을
    // 알린다) 바로 일시정지 — 시간은 실제 녹음된 데까지.
    if (snapshot.phase === "rec" && (!micLive() || Date.now() - lastChunkWall > STALL_MS)) {
      void micLost().finally(() => (hiddenAt = null));
      return;
    }
    // 꺼진 동안도 조각이 왔다 — 그동안도 녹음됐다(안드로이드 등). 길이를 다시 그대로 세고 시계를 다시 돌린다.
    hiddenAt = null;
    if (snapshot.phase === "rec") tick(true);
    wakeLock = null;
    void lockScreen();
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

  let stream: MediaStream;

  try {
    stream = await openMic();
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
  } catch (caught) {
    stream.getTracks().forEach((track) => track.stop());
    set({
      error:
        caught instanceof DbBlockedError
          ? caught.message
          : "폰에 녹음을 저장할 수 없어요. 사생활 보호(시크릿) 창이면 일반 창으로 열어 주세요.",
    });
    return false;
  }

  // 믹서를 만든다(녹음 시작 단추를 누른 때라 오디오를 켤 수 있다). 못 만들면 마이크를 바로 녹음한다.
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

    if (Ctx) {
      audioCtx = new Ctx();
      mixer = audioCtx.createMediaStreamDestination();
      if (audioCtx.state === "suspended") await audioCtx.resume();
      // 전화 등으로 오디오가 막히면(iOS 'interrupted') 마이크가 끊긴 것과 같이 본다.
      audioCtx.onstatechange = () => {
        if (audioCtx && audioCtx.state !== "running" && snapshot.phase === "rec") void micLost();
      };
    }
  } catch {
    audioCtx = null;
    mixer = null;
  }

  plugMic(stream);

  let media: MediaRecorder;
  const source = mixer ? mixer.stream : stream;

  // 말소리라 낮게 잡는다(1시간 ≈ 14MB). 지정이 없으면 브라우저마다 128kbps 안팎이라 1시간이면 50MB 를 넘는다(민규 #169).
  try {
    media = new MediaRecorder(source, { mimeType: format.mime, audioBitsPerSecond: AUDIO_BPS });
  } catch {
    try {
      media = new MediaRecorder(source, { audioBitsPerSecond: AUDIO_BPS });
    } catch {
      // 믹서 녹음을 못 하는 브라우저: 마이크를 바로 녹음한다.
      if (mixer) {
        try {
          micNode?.disconnect();
        } catch {
          // 무시
        }
        audioCtx?.close().catch(() => {});
        audioCtx = null;
        mixer = null;
        micNode = null;
      }
      media = new MediaRecorder(stream, { mimeType: format.mime, audioBitsPerSecond: AUDIO_BPS });
    }
  }

  seq = 0;
  saving = Promise.resolve();
  media.ondataavailable = (event) => {
    if (!event.data || event.data.size === 0) return;

    const index = seq++;
    const duration = hiddenAt !== null ? Math.min(now(), hiddenAt + 1000) : now();

    lastDataElapsed = duration;
    lastChunkWall = Date.now();
    saving = saving
      .then(() => saveChunk(id, index, event.data, duration))
      .catch(() => {
        set({ error: "폰 저장 공간이 부족해 녹음을 저장하지 못하고 있어요. 녹음을 멈추고 공간을 확보해 주세요." });
      });
  };
  media.onerror = () => void recorderEnded(INTERRUPTED_TEXT);
  // 우리가 부르지 않았는데 녹음기가 끝났으면(폰이 끝냄) 이어 갈 수 없다 — 녹음된 데까지 정리한다.
  media.onstop = () => {
    if (!stopping) void recorderEnded(mixer ? ENDED_TEXT : INTERRUPTED_TEXT);
  };

  recorder = media;
  stopping = false;
  lastDataElapsed = 0;
  hiddenAt = null;
  lastChunkWall = Date.now();
  banked = 0;
  segmentStart = Date.now();
  media.start(1000);
  tick(true);
  void lockScreen();
  holdRecLock(id);
  beat(true, id);
  set({ phase: "rec", elapsedMs: 0, draft });

  return true;
}

export function pauseRecording(): void {
  if (snapshot.phase !== "rec" || recorder?.state !== "recording") return;

  recorder.pause();
  banked = now();
  segmentStart = null;
  tick(false);
  set({ phase: "paused", elapsedMs: banked });
}

/** '계속'. 마이크가 끊겨 있으면 다시 켜서 믹서에 꽂고 같은 녹음기를 이어 간다. */
export async function resumeRecording(): Promise<void> {
  if (snapshot.phase !== "paused" || stopping) return;

  if (!recorder || recorder.state === "inactive") {
    await recorderEnded(ENDED_TEXT);
    return;
  }

  if (!micLive()) {
    if (!mixer) {
      await recorderEnded(INTERRUPTED_TEXT);
      return;
    }
    try {
      if (audioCtx && audioCtx.state !== "running") await audioCtx.resume();
      plugMic(await openMic());
    } catch {
      set({ error: MIC_TEXT });
      return;
    }
  }

  try {
    recorder.resume();
  } catch {
    await recorderEnded(ENDED_TEXT);
    return;
  }
  segmentStart = Date.now();
  lastChunkWall = Date.now();
  tick(true);
  wakeLock = null;
  void lockScreen();
  set({ phase: "rec", error: snapshot.error === PAUSED_TEXT || snapshot.error === MIC_TEXT ? null : snapshot.error });
}

export async function stopRecording(): Promise<void> {
  if (!live() || stopping) return;

  const media = recorder;
  const alive = !!media && media.state !== "inactive";
  // 녹음 중이면 지금까지, 일시정지면 쌓아 둔 시간, 녹음기가 이미 끝났으면 마지막 조각까지가 녹음된 길이다.
  const elapsed = !alive ? lastDataElapsed : snapshot.phase === "rec" ? now() : banked;

  stopping = true;
  if (media) await waitStop(media);
  // 보통 정지면 일시정지 안내 등은 지운다. 녹음기가 이미 끝나 있었으면 그 사실을 알린다.
  await finalize(elapsed, alive ? null : mixer ? ENDED_TEXT : INTERRUPTED_TEXT);
}

/** 저장한 뒤 처음으로(조각은 대기열로 옮겨졌다). */
export function clearRecording(): void {
  dropRecLock();
  beat(false);
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
