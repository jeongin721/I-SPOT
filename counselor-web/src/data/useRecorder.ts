// 폰 마이크 녹음기(앱 · 녹음 화면). 마이크 소리를 직접 받아 MP3 로 바꾸며 1초 남짓마다 조각을 IndexedDB 에 저장한다(appRecordings).
//
//  idle → (start) rec ⇄ paused → (stop) done → (save) 대기열 · (reset) idle
//
// 왜 MediaRecorder 를 쓰지 않나(11/11 실제 아이폰): 잠금 · 전화로 오디오가 '중단' 되면 같은 MediaRecorder 를 다시 켜도 소리가 들어오지
// 않았다('계속' 뒤 부분이 파일에 없음). 새 MediaRecorder 로 이어 붙이면 m4a · webm 파일이 깨진다. 한 상담은 한 회차 · 한 파일이어야
// 해서, 앱이 직접 소리(PCM)를 받아 MP3 로 바꾼다. MP3 는 프레임을 이어 붙여도 깨지지 않으므로, 끊긴 뒤 '계속' 을 누르면 오디오 ·
// 마이크를 새로 켜서 같은 인코더 · 같은 파일에 이어 붙인다.
//
//  - 형식: MP3 16kHz 모노 32kbps(말소리 · 원문 변환용, 1시간 ≈ 14MB). 인코더는 lamejs(public/app/lame.min.js, LGPL-3.0 — 녹음할 때만
//    따로 불러 쓴다. 사용자가 깔 것은 없다). 서버는 .mp3 를 받는다.
//  - 녹음 시간은 화면 시계가 아니라 실제로 받은 소리 길이(인코딩한 표본 수)다. 화면이 꺼진 시간이 더해지지 않는다.
//  - 끊김: 마이크 트랙 ended · 오디오 'interrupted' · 화면이 돌아왔는데 소리가 2.5초 넘게 안 왔음 · 녹음 중 소리가 3초 넘게 안 옴
//    → 오디오를 닫고 '일시정지'. '계속' 을 누르면(사용자 손길이 있어야 아이폰이 오디오를 켜 준다) 새로 켜서 이어 간다.
//    '계속' 뒤에도 소리가 안 오면 3초 안에 다시 일시정지하고 알린다(녹음이 안 되는데 '녹음 중' 으로 보이지 않게).
//  - 화면이 잠긴 '동안' 은 녹음되지 않는다(웹 앱 한계 — 브라우저가 페이지를 멈춘다). 그 사이는 비고, '계속' 으로 이어진다.
//  - 녹음하는 동안 화면이 꺼지지 않게 한다(Wake Lock). 이 녹음의 잠금(Web Locks)을 잡고 5초마다 살아 있음을 표시한다(민규 #168).
//  - 녹음기는 앱 전체에 하나다(이 모듈). 녹음 중에 다른 탭(앱 화면)에 다녀와도 녹음은 계속된다.
//  - 앱이 꺼지거나 탭을 닫으면 녹음은 멈춘다. 그때까지의 조각은 남아 다음에 열 때 업로드 목록에 되살아난다(recoverDrafts).

import { useSyncExternalStore } from "react";

import { DbBlockedError, RECORDING_LOCK_PREFIX, discardDraft, saveChunk, startDraft, touchDraft, type RecordingDraft } from "./appRecordings";

export type RecorderPhase = "idle" | "rec" | "paused" | "done";

/** 녹음 비트레이트(bps). MP3 16kHz 모노. */
export const AUDIO_BPS = 32_000;
const SAMPLE_RATE = 16_000;
const MP3_KBPS = AUDIO_BPS / 1000;
/** 인코더에 한 번에 넣는 표본 수. */
const FRAME = 1152;
/** 이만큼(바이트) 모이면 조각으로 저장한다(32kbps ≈ 1초). */
const CHUNK_BYTES = 4096;
const MIME = "audio/mpeg";
const EXT = ".mp3";

export type DraftInfo = Omit<RecordingDraft, "id" | "mime" | "ext" | "durationMs" | "heartbeat">;

export interface RecorderSnapshot {
  phase: RecorderPhase;
  /** 녹음 시간(밀리초) — 실제로 받은 소리 길이. */
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

const PAUSED_TEXT =
  "마이크가 끊겨(화면 잠금 · 전화 · 다른 앱) 일시정지했어요. '계속' 을 누르면 같은 녹음에 이어서 녹음해요. 끊긴 동안은 녹음되지 않았어요.";
const NO_SOUND_TEXT = "마이크 소리가 들어오지 않아 일시정지했어요. 통화가 끝났는지 확인하고 '계속' 을 다시 눌러 주세요.";
const MIC_TEXT = "마이크를 다시 켜지 못했어요. 통화가 끝났는지 확인하고 '계속' 을 다시 눌러 주세요.";
const MUTED_TEXT = "마이크가 잠시 끊겼어요(전화 등). 그동안은 소리가 녹음되지 않아요.";
const STORAGE_TEXT = "폰 저장 공간이 부족해 녹음을 저장하지 못하고 있어요. 녹음을 멈추고 공간을 확보해 주세요.";

// ---------------------------------------------------------------------------
// MP3 인코더(lamejs) — 녹음할 때 한 번 불러 온다.
// ---------------------------------------------------------------------------

interface Mp3Encoder {
  encodeBuffer(samples: Int16Array): Int8Array;
  flush(): Int8Array;
}

type LameGlobal = { Mp3Encoder: new (channels: number, rate: number, kbps: number) => Mp3Encoder };

let lameLoading: Promise<LameGlobal> | null = null;

function loadLame(): Promise<LameGlobal> {
  const ready = (window as unknown as { lamejs?: LameGlobal }).lamejs;

  if (ready) return Promise.resolve(ready);
  if (lameLoading) return lameLoading;

  lameLoading = new Promise<LameGlobal>((resolve, reject) => {
    const script = document.createElement("script");

    script.src = "app/lame.min.js";
    script.async = true;
    script.onload = () => {
      const lame = (window as unknown as { lamejs?: LameGlobal }).lamejs;

      if (lame) resolve(lame);
      else reject(new Error("lamejs"));
    };
    script.onerror = () => reject(new Error("lamejs"));
    document.head.appendChild(script);
  });
  lameLoading.catch(() => {
    lameLoading = null;
  });

  return lameLoading;
}

/** 녹음 화면을 열 때 미리 불러 둔다(녹음 시작을 누른 순간 기다리지 않게). */
export function preloadRecorder(): void {
  void loadLame().catch(() => {});
}

// ---------------------------------------------------------------------------
// 오디오 길(마이크 → 표본 받기). 끊기면 통째로 닫고, '계속' 에서 새로 만든다.
// ---------------------------------------------------------------------------

const WORKLET = `
class IspotPcm extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(2048); this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      for (let i = 0; i < ch.length; i++) {
        this.buf[this.n++] = ch[i];
        if (this.n === this.buf.length) { this.port.postMessage(this.buf.slice(0)); this.n = 0; }
      }
    }
    return true;
  }
}
registerProcessor('ispot-pcm', IspotPcm);
`;

interface Chain {
  ctx: AudioContext;
  mic: MediaStream;
  nodes: AudioNode[];
}

let chain: Chain | null = null;
let encoder: Mp3Encoder | null = null;
/** 다시 표본 뽑기(장치 표본율 → 16kHz): 다음 표본의 위치(이번 묶음 기준, 음수면 앞 묶음 끝)와 앞 묶음 마지막 값. */
let rsPos = 0;
let rsPrev = 0;
/** 인코더에 아직 안 넣은 16kHz 표본. */
let pcm = new Int16Array(FRAME * 4);
let pcmLen = 0;
/** 인코딩한 16kHz 표본 수 — 녹음 길이. */
let encoded = 0;
/** 저장 안 한 MP3 바이트. */
let outParts: Uint8Array[] = [];
let outBytes = 0;
/** 마지막으로 소리(표본)를 받은 실제 시각. */
let lastSoundWall = 0;
let lastShown = 0;
let seq = 0;
let saving: Promise<void> = Promise.resolve();
let draftId: string | null = null;
let watchdog: number | null = null;
let wakeLock: { release: () => Promise<void> } | null = null;
let heartbeat: number | null = null;
let releaseRecLock: (() => void) | null = null;
let busy = false;

const durMs = () => Math.round(((encoded + pcmLen) * 1000) / SAMPLE_RATE);
/** 마이크 트랙이 살아 있는가. 끊긴 트랙도 브라우저에 따라 '소리 없음' 표본은 계속 보내므로 표본이 온다고 마이크가 산 것은 아니다. */
const micAlive = () => !!chain && chain.mic.getAudioTracks().some((track) => track.readyState === "live");
const live = () => snapshot.phase === "rec" || snapshot.phase === "paused";

function newContext(): AudioContext {
  const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

  if (!Ctx) throw new Error("no AudioContext");

  return new Ctx();
}

async function openMic(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true, channelCount: 1 },
  });
}

function pushMp3(bytes: Int8Array) {
  if (bytes.length === 0) return;
  outParts.push(new Uint8Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)));
  outBytes += bytes.length;
}

/** 모인 MP3 바이트를 조각 하나로 저장한다. */
function flushChunk() {
  if (!draftId || outBytes === 0) return;

  const id = draftId;
  const index = seq++;
  const blob = new Blob(outParts as BlobPart[], { type: MIME });
  const duration = Math.round((encoded * 1000) / SAMPLE_RATE);

  outParts = [];
  outBytes = 0;
  saving = saving.then(() => saveChunk(id, index, blob, duration)).catch(() => set({ error: STORAGE_TEXT }));
}

/** 장치 표본을 16kHz 로 바꿔 인코더에 넣는다. */
function onSamples(input: Float32Array, rate: number) {
  // 마이크가 끊겼으면 '소리 없음' 표본이 와도 세지 않는다(녹음 길이에 끊긴 시간이 들어가지 않게).
  if (snapshot.phase !== "rec" || !encoder || input.length === 0 || !micAlive()) return;

  const step = rate / SAMPLE_RATE;
  let pos = rsPos;

  while (pos < input.length - 1) {
    const i = Math.floor(pos);
    const frac = pos - i;
    const a = i < 0 ? rsPrev : input[i];
    const b = input[i + 1];
    const v = a + (b - a) * frac;

    if (pcmLen === pcm.length) {
      const grown = new Int16Array(pcm.length * 2);

      grown.set(pcm);
      pcm = grown;
    }
    pcm[pcmLen++] = Math.max(-32768, Math.min(32767, Math.round(v * 32767)));
    pos += step;
  }
  rsPos = pos - input.length;
  rsPrev = input[input.length - 1];
  lastSoundWall = Date.now();

  let used = 0;

  while (pcmLen - used >= FRAME) {
    pushMp3(encoder.encodeBuffer(pcm.subarray(used, used + FRAME)));
    used += FRAME;
    encoded += FRAME;
  }
  if (used > 0) {
    pcm.copyWithin(0, used, pcmLen);
    pcmLen -= used;
  }
  if (outBytes >= CHUNK_BYTES) flushChunk();

  const now = Date.now();

  if (now - lastShown > 250) {
    lastShown = now;
    set({ elapsedMs: durMs() });
  }
}

/** 오디오 길을 만든다. ctx 는 단추를 누른 순간 만든 것(아이폰은 사용자 손길 안에서 만든 오디오만 켜 준다). */
async function buildChain(ctx: AudioContext): Promise<void> {
  if (ctx.state !== "running") await ctx.resume().catch(() => {});

  const mic = await openMic();
  const src = ctx.createMediaStreamSource(mic);
  const nodes: AudioNode[] = [src];
  const rate = ctx.sampleRate;
  let sink: AudioNode;

  if (ctx.audioWorklet && typeof AudioWorkletNode !== "undefined") {
    const url = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));

    try {
      await ctx.audioWorklet.addModule(url);
    } finally {
      URL.revokeObjectURL(url);
    }
    const node = new AudioWorkletNode(ctx, "ispot-pcm", { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1 });

    node.port.onmessage = (event: MessageEvent<Float32Array>) => {
      if (chain?.ctx === ctx) onSamples(event.data, rate);
    };
    sink = node;
  } else {
    const node = ctx.createScriptProcessor(4096, 1, 1);

    node.onaudioprocess = (event) => {
      if (chain?.ctx === ctx) onSamples(new Float32Array(event.inputBuffer.getChannelData(0)), rate);
    };
    sink = node;
  }
  src.connect(sink);
  // 오디오 길이 돌아가게 소리 없는 출구에 잇는다(스피커로 나가지 않음).
  const mute = ctx.createGain();

  mute.gain.value = 0;
  sink.connect(mute);
  mute.connect(ctx.destination);
  nodes.push(sink, mute);

  ctx.onstatechange = () => {
    if (chain?.ctx === ctx && ctx.state !== "running" && snapshot.phase === "rec") void lost(PAUSED_TEXT);
  };
  mic.getAudioTracks().forEach((track) => {
    track.addEventListener("ended", () => {
      if (chain?.mic === mic) void lost(PAUSED_TEXT);
    });
    track.addEventListener("mute", () => {
      if (chain?.mic === mic && snapshot.phase === "rec") set({ error: MUTED_TEXT });
    });
    track.addEventListener("unmute", () => {
      if (snapshot.error === MUTED_TEXT) set({ error: null });
    });
  });

  rsPos = 0;
  rsPrev = 0;
  chain = { ctx, mic, nodes };
}

/** 오디오 길을 닫는다(마이크 끄기 · 오디오 닫기). 인코더 · 아직 안 넣은 표본은 그대로 두어 이어 붙인다. */
function closeChain() {
  const old = chain;

  chain = null;
  if (!old) return;
  old.nodes.forEach((node) => {
    try {
      node.disconnect();
    } catch {
      // 이미 떨어짐
    }
  });
  old.mic.getTracks().forEach((track) => track.stop());
  old.ctx.onstatechange = null;
  old.ctx.close().catch(() => {});
}

function holdRecLock(id: string) {
  const locks = (navigator as Navigator & { locks?: LockManager }).locks;

  if (!locks) return;

  locks.request(RECORDING_LOCK_PREFIX + id, () => new Promise<void>((resolve) => (releaseRecLock = resolve))).catch(() => {});
}

function dropRecLock() {
  releaseRecLock?.();
  releaseRecLock = null;
}

function beat(on: boolean) {
  if (heartbeat !== null) window.clearInterval(heartbeat);
  heartbeat = on
    ? window.setInterval(() => {
        if (draftId) void touchDraft(draftId, durMs()).catch(() => {});
      }, 5000)
    : null;
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

/** 녹음 중 소리가 3초 넘게 안 오면(보이는 화면에서) 일시정지 — 녹음이 안 되는데 '녹음 중' 으로 보이지 않게. */
function watch(on: boolean) {
  if (watchdog !== null) window.clearInterval(watchdog);
  watchdog = on
    ? window.setInterval(() => {
        if (snapshot.phase !== "rec" || document.visibilityState !== "visible") return;
        if (Date.now() - lastSoundWall > 3000 || !micAlive()) void lost(NO_SOUND_TEXT);
      }, 1000)
    : null;
}

/** 끊겼다(잠금 · 전화 · 다른 앱 · 소리 안 옴). 오디오를 닫고 일시정지. 지금까지 받은 것은 저장해 둔다. */
async function lost(reason: string): Promise<void> {
  if (snapshot.phase !== "rec") return;

  closeChain();
  watch(false);
  flushChunk();
  set({ phase: "paused", elapsedMs: durMs(), error: reason });
}

if (typeof document !== "undefined") {
  // 화면이 돌아왔는데 그동안 소리가 안 왔으면(아이폰이 페이지를 멈춤) 바로 일시정지. 왔으면(안드로이드 등) 그대로 이어 간다.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible" || snapshot.phase !== "rec") return;

    if (!chain || !micAlive() || Date.now() - lastSoundWall > 2500) {
      void lost(PAUSED_TEXT);
      return;
    }
    wakeLock = null;
    void lockScreen();
  });
}

export async function startRecording(info: DraftInfo): Promise<boolean> {
  if (snapshot.phase !== "idle" || busy) return false;

  busy = true;
  set({ error: null });

  // 단추를 누른 그 순간 오디오를 만든다(아이폰).
  let ctx: AudioContext;

  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("no getUserMedia");
    ctx = newContext();
  } catch {
    busy = false;
    set({ error: "이 브라우저에서는 녹음할 수 없어요. 휴대폰의 Chrome 이나 Safari 로 열어 주세요." });
    return false;
  }

  try {
    const lame = await loadLame();

    encoder = new lame.Mp3Encoder(1, SAMPLE_RATE, MP3_KBPS);
  } catch {
    ctx.close().catch(() => {});
    busy = false;
    set({ error: "녹음 도구를 불러오지 못했어요. 연결을 확인하고 다시 눌러 주세요." });
    return false;
  }

  const id = `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const draft: RecordingDraft = { ...info, id, mime: MIME, ext: EXT, durationMs: 0, heartbeat: Date.now() };

  try {
    await startDraft(draft);
  } catch (caught) {
    ctx.close().catch(() => {});
    encoder = null;
    busy = false;
    set({
      error:
        caught instanceof DbBlockedError ? caught.message : "폰에 녹음을 저장할 수 없어요. 사생활 보호(시크릿) 창이면 일반 창으로 열어 주세요.",
    });
    return false;
  }

  draftId = id;
  seq = 0;
  saving = Promise.resolve();
  encoded = 0;
  pcmLen = 0;
  outParts = [];
  outBytes = 0;
  lastSoundWall = Date.now();
  set({ phase: "rec", elapsedMs: 0, draft });

  try {
    await buildChain(ctx);
  } catch (caught) {
    closeChain();
    ctx.close().catch(() => {});
    void discardDraft(id);
    draftId = null;
    encoder = null;
    busy = false;
    const name = caught instanceof DOMException ? caught.name : "";

    set({
      phase: "idle",
      draft: null,
      error:
        name === "NotAllowedError"
          ? "마이크 사용을 허용해 주세요. 브라우저 주소창의 사이트 설정에서 마이크를 허용할 수 있어요."
          : "마이크를 켜지 못했어요. 다른 앱이 마이크를 쓰고 있는지 확인해 주세요.",
    });
    return false;
  }

  lastSoundWall = Date.now();
  watch(true);
  void lockScreen();
  holdRecLock(id);
  beat(true);
  busy = false;

  return true;
}

/** 사용자 일시정지. 오디오를 닫는다(아이폰에서 '계속' 이 늘 같은 길로 새로 켜게). */
export function pauseRecording(): void {
  if (snapshot.phase !== "rec" || busy) return;

  closeChain();
  watch(false);
  flushChunk();
  set({ phase: "paused", elapsedMs: durMs() });
}

/** '계속'. 오디오 · 마이크를 새로 켜서 같은 인코더 · 같은 파일에 이어 붙인다. */
export async function resumeRecording(): Promise<void> {
  if (snapshot.phase !== "paused" || busy || !encoder) return;

  busy = true;

  let ctx: AudioContext;

  try {
    ctx = newContext();
  } catch {
    busy = false;
    set({ error: MIC_TEXT });
    return;
  }

  set({ phase: "rec", error: null });
  lastSoundWall = Date.now();

  try {
    await buildChain(ctx);
  } catch {
    closeChain();
    ctx.close().catch(() => {});
    busy = false;
    set({ phase: "paused", elapsedMs: durMs(), error: MIC_TEXT });
    return;
  }

  lastSoundWall = Date.now();
  watch(true);
  wakeLock = null;
  void lockScreen();
  busy = false;
}

export async function stopRecording(): Promise<void> {
  if (!live() || busy) return;

  busy = true;
  closeChain();
  watch(false);

  // 남은 표본을 넣고 인코더를 비운다.
  if (encoder) {
    if (pcmLen > 0) {
      pushMp3(encoder.encodeBuffer(pcm.subarray(0, pcmLen)));
      encoded += pcmLen;
      pcmLen = 0;
    }
    pushMp3(encoder.flush());
  }
  flushChunk();
  await saving;
  unlockScreen();
  beat(false);
  encoder = null;
  busy = false;

  const durationMs = durMs();
  const keep = snapshot.error === STORAGE_TEXT ? snapshot.error : null;

  set({ phase: "done", elapsedMs: durationMs, draft: snapshot.draft ? { ...snapshot.draft, durationMs } : null, error: keep });
}

/** 저장한 뒤 처음으로(조각은 대기열로 옮겨졌다). */
export function clearRecording(): void {
  dropRecLock();
  beat(false);
  draftId = null;
  encoded = 0;
  pcmLen = 0;
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
