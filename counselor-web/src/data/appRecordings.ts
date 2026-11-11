// 상담사 앱(폰) 녹음 보관함 · 올리기 대기열(앱 · 녹음 / 앱 · 업로드 화면, 2026-11-10 디자인).
//
// 폰에서 녹음한 파일을 이 브라우저의 IndexedDB 에 먼저 저장한 뒤 서버로 올린다. 올리는 길은 웹 녹취 올리기 창과 같다:
//   (새 회차면) POST /cases/{id}/sessions → POST /sessions/{id}/audio → POST /sessions/{id}/transcript(원문 변환 요청)
// 그래서 웹에서 같은 사례 · 회차를 열면 그 녹음이 그대로 있고, 변환이 끝나면 '원문 검수(1단계)' 부터 이어서 한다.
//
//  - 녹음은 1초마다 조각(chunk)으로 저장한다. 앱이 꺼지거나 화면이 닫혀도 녹음된 데까지는 남고, 다음에 열면
//    업로드 목록에 '실패' 로 올라와 다시 올릴 수 있다(recoverDrafts).
//  - 조각은 Blob 이 아니라 바이트(ArrayBuffer)로 저장한다. iPhone Safari 는 IndexedDB 에서 꺼낸 Blob 을 합친 뒤
//    원래 조각을 지우면 합친 Blob 을 읽지 못해 올리기가 멈출 수 있어서다(11/10 실제 폰에서 45초 녹음이 끝없이 '올리는 중').
//  - 녹음을 마쳐도 조각을 하나로 합쳐 다시 저장하지 않는다. 조각은 그대로 두고(chunked) 올릴 때만 몇 MB 씩 이어 붙인 Blob 을 만든다
//    (민규 #169 — 조각 전부 + 합친 Blob + 본문이 한꺼번에 메모리에 올라가 1시간 녹음이면 탭이 죽을 수 있었다). 끊긴 녹음 되살리기도
//    조각을 읽지 않고 줄만 만든다. 폰의 음성 파일도 1MB 씩 잘라 조각으로 넣는다. 옛 줄(blob · bodies)도 읽는다.
//  - 단계마다 시간 제한을 둔다(연결이 걸려 응답이 오지 않으면 '실패' 로 두고 자동으로 다시 올린다). 전에는 제한이 없어
//    요청 하나가 멈추면 그 줄이 계속 '올리는 중' 이고 대기열 전체가 멈췄다.
//  - 올리기가 실패하면(연결 끊김 등) 그 단계를 기억한다. 연결이 돌아오면(online 이벤트) · 앱을 다시 열면 · 1분마다 실패한 단계부터
//    자동으로 다시 올린다. 새 회차를 이미 만들었으면 다시 만들지 않는다(빈 회차가 쌓이지 않게, useAudioUpload 와 같은 규칙).
//  - 고른 회차는 올리기 직전에 상태를 다시 본다(민규 #168). 그사이 웹에서 그 회차에 녹음을 올렸거나 검수 · 확정이 됐으면
//    올리지 않고 '새 회차로 올리기' 를 고르게 한다(덮어쓰기 · 409 로 녹음을 잃는 것을 막는다).
//  - 원문 변환 요청이 409 면 회차 상태를 읽어 이미 변환 중 · 그 뒤면 완료로 둔다(응답을 놓친 뒤 다시 요청한 경우, 민규 #168).
//  - 대기열은 로그인한 계정별로 나눈다(userId). 같은 폰에서 다른 계정으로 로그인하면 앞 계정의 녹음은 보이지도 올라가지도 않는다.
//  - 다 올린 녹음은 본문을 지우고 목록 줄만 남긴다(폰 저장 공간). 7일 지난 완료 줄은 지운다.

import { ApiError, getToken, request } from "../api/client";
import type { AudioFile, ConsultationType, Session, SessionDetail, SessionStatus } from "../api/types";
import { parseBackendTime } from "./time";

export type RecordingStatus = "wait" | "run" | "fail" | "done";
export type RecordingStep = "createSession" | "upload" | "requestStt";

export interface RecordingItem {
  id: string;
  userId: string;
  caseId: string;
  /** 목록에 보일 아이 이름(올릴 때의 이름). */
  childLabel: string;
  /** 고른 회차. null 이면 새 회차(만든 뒤 채워진다). */
  sessionId: string | null;
  /** 목록에 보일 회차 번호. 새 회차면 만든 뒤 채워진다. */
  sessionNumber: number | null;
  /** 회차를 고를(만들) 때의 상태. 올리기 직전 상태가 이것과 맞지 않으면 올리지 않는다. 옛 줄은 키가 없다. */
  expectStatus?: SessionStatus;
  consultationType: ConsultationType;
  /** 녹음 시작 시각(UTC ISO). 새 회차의 상담 일시로 쓴다. */
  consultedAt: string;
  fileName: string;
  mime: string;
  size: number;
  durationMs: number;
  /** 본문이 조각(chunks, 녹음 ID 로 묶임)으로 있는가. 다 올리면 지운다. */
  chunked?: boolean;
  /** (11/10 판) 본문이 bodies 저장소에 한 덩이로 있는가. */
  hasBody?: boolean;
  /** (옛 줄) 본문 Blob. 새 줄은 bodies 에 둔다. */
  blob?: Blob | null;
  status: RecordingStatus;
  /** 다음에 할(또는 실패한) 단계. */
  step: RecordingStep;
  error: string | null;
  /** 회차 만들기 응답을 놓쳤을 때(연결 끊김 · 5xx) 그 시각. 다시 할 때 그사이 생긴 빈 회차를 먼저 찾는다. */
  createUncertainSince: number | null;
  /** 음성 올리기를 한 번이라도 보냈는가. 응답을 놓쳤을 때 서버의 최신 음성이 이 녹음인지 크기로 확인한다. */
  uploadSent?: boolean;
  /** 고른 회차가 그사이 바뀌어 올릴 수 없다. '새 회차로 올리기' 를 보인다. */
  needNewSession?: boolean;
  /** 연결 끊김 · 서버 오류(5xx) · 시간 초과로 실패했는가. 그런 줄만 자동으로 다시 올린다. 옛 줄은 키가 없다. */
  autoRetry?: boolean;
  createdAt: number;
  updatedAt: number;
}

/** 녹음 중인 조각 묶음의 머리 정보. 녹음이 끝나면 지운다. 남아 있으면 녹음이 중간에 끊긴 것이다. */
export interface RecordingDraft {
  id: string;
  userId: string;
  caseId: string;
  childLabel: string;
  sessionId: string | null;
  sessionNumber: number | null;
  expectStatus?: SessionStatus;
  consultationType: ConsultationType;
  consultedAt: string;
  mime: string;
  ext: string;
  durationMs: number;
  /** 지금까지 저장한 조각 크기 합(바이트). 옛 판은 키가 없다. */
  bytes?: number;
  /** 마지막으로 조각을 저장(또는 일시정지 중 살아 있음을 표시)한 시각. 오래되었으면(녹음기가 멈춤) 되살린다. */
  heartbeat: number;
}

const DB_NAME = "ispot-counselor-app";
const DB_VERSION = 2;
const ITEMS = "recordings";
const BODIES = "bodies";
const DRAFTS = "drafts";
const CHUNKS = "chunks";
const DONE_KEEP_MS = 7 * 24 * 60 * 60 * 1000;
/** 이보다 오래 조각 · 살아 있음 표시가 안 들어온 녹음은 끊긴 것으로 본다. */
const DRAFT_STALE_MS = 15_000;
const CREATE_LOOKBACK_MS = 60_000;
/** 녹음 중인 탭이 잡는 잠금 이름 앞부분. 다른 탭의 되살리기가 이 잠금이 잡힌 녹음은 건너뛴다. */
export const RECORDING_LOCK_PREFIX = "ispot-app-rec-";

/** 올릴 수 있는 회차 상태. */
const UPLOADABLE: SessionStatus[] = ["CREATED", "AUDIO_UPLOADED", "STT_FAILED"];

let dbPromise: Promise<IDBDatabase> | null = null;

/** 다른 탭이 옛 판 저장소를 열고 있어 열 수 없다. */
export class DbBlockedError extends Error {
  constructor() {
    super("앱이 다른 탭에도 열려 있어요. 다른 탭을 모두 닫고 다시 해 주세요.");
  }
}

function openDb(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve, reject) => {
    let open: IDBOpenDBRequest;

    try {
      open = indexedDB.open(DB_NAME, DB_VERSION);
    } catch (caught) {
      reject(caught);
      return;
    }

    open.onupgradeneeded = () => {
      const db = open.result;

      if (!db.objectStoreNames.contains(ITEMS)) db.createObjectStore(ITEMS, { keyPath: "id" });
      if (!db.objectStoreNames.contains(BODIES)) db.createObjectStore(BODIES);
      if (!db.objectStoreNames.contains(DRAFTS)) db.createObjectStore(DRAFTS, { keyPath: "id" });
      if (!db.objectStoreNames.contains(CHUNKS)) db.createObjectStore(CHUNKS, { keyPath: ["draftId", "seq"] });
    };
    // 옛 판을 연 탭이 남아 있으면 판 올리기가 멈춘다(민규 #169). 기다리지 않고 알려 그 탭을 닫게 한다.
    open.onblocked = () => reject(new DbBlockedError());
    open.onsuccess = () => {
      const db = open.result;

      // 다음 판이 열리려 하면 이 연결을 닫아 막지 않는다.
      db.onversionchange = () => {
        db.close();
        dbPromise = null;
      };
      resolve(db);
    };
    open.onerror = () => reject(open.error);
  });
  dbPromise.catch(() => {
    dbPromise = null;
  });

  return dbPromise;
}

function tx<T>(stores: string[], mode: IDBTransactionMode, work: (t: IDBTransaction) => IDBRequest<T> | void): Promise<T | undefined> {
  return openDb().then(
    (db) =>
      new Promise<T | undefined>((resolve, reject) => {
        const t = db.transaction(stores, mode);
        let result: T | undefined;
        const req = work(t);

        if (req) req.onsuccess = () => (result = req.result);
        t.oncomplete = () => resolve(result);
        t.onerror = () => reject(t.error);
        t.onabort = () => reject(t.error ?? new Error("저장하지 못했어요"));
      }),
  );
}

// ---------------------------------------------------------------------------
// 바뀜 알림(같은 탭 화면 + 다른 탭)
// ---------------------------------------------------------------------------

const listeners = new Set<() => void>();
const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("ispot-app-recordings") : null;

channel?.addEventListener("message", () => listeners.forEach((fn) => fn()));

function changed() {
  listeners.forEach((fn) => fn());
  channel?.postMessage("changed");
}

export function subscribeRecordings(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// ---------------------------------------------------------------------------
// 목록 · 본문
// ---------------------------------------------------------------------------

export async function listRecordings(userId: string): Promise<RecordingItem[]> {
  const all = ((await tx<RecordingItem[]>([ITEMS], "readonly", (t) => t.objectStore(ITEMS).getAll())) ?? []) as RecordingItem[];

  return all.filter((item) => item.userId === userId).sort((a, b) => b.createdAt - a.createdAt);
}

async function getItem(id: string): Promise<RecordingItem | undefined> {
  return tx<RecordingItem>([ITEMS], "readonly", (t) => t.objectStore(ITEMS).get(id));
}

async function putItem(item: RecordingItem): Promise<void> {
  await tx([ITEMS], "readwrite", (t) => t.objectStore(ITEMS).put(item));
  changed();
}

async function patchItem(id: string, patch: Partial<RecordingItem>): Promise<RecordingItem | null> {
  const item = await getItem(id);

  if (!item) return null;

  const next = { ...item, ...patch, updatedAt: Date.now() };

  await putItem(next);

  return next;
}

/** 본문이 남아 있는가(조각 · 옛 판 blob · bodies). */
function hasPayload(item: RecordingItem): boolean {
  return !!item.chunked || !!item.hasBody || !!item.blob;
}

const chunkRange = (id: string) => IDBKeyRange.bound([id, 0], [id, Number.MAX_SAFE_INTEGER]);

/** 이어 붙일 때 한 번에 모으는 크기. 모은 만큼 Blob 으로 합치고 바이트는 놓는다(메모리는 대략 파일 크기 + 이만큼). */
const ASSEMBLE_BATCH = 4 * 1024 * 1024;

/** 조각을 차례로 읽어 하나의 Blob 으로 잇는다. 조각을 한꺼번에 들지 않는다. */
function assembleChunks(id: string, mime: string): Promise<Blob | null> {
  return openDb().then(
    (db) =>
      new Promise<Blob | null>((resolve, reject) => {
        const t = db.transaction([CHUNKS], "readonly");
        const cursorReq = t.objectStore(CHUNKS).openCursor(chunkRange(id));
        let blob: Blob | null = null;
        let parts: BlobPart[] = [];
        let pending = 0;
        let count = 0;
        const flush = () => {
          if (parts.length === 0) return;
          blob = new Blob(blob ? [blob, ...parts] : parts, { type: mime });
          parts = [];
          pending = 0;
        };

        cursorReq.onsuccess = () => {
          const cursor = cursorReq.result;

          if (!cursor) return;

          const row = cursor.value as { buf?: ArrayBuffer; blob?: Blob };
          const part = (row.buf ?? row.blob) as BlobPart;

          parts.push(part);
          pending += row.buf ? row.buf.byteLength : row.blob?.size ?? 0;
          count += 1;
          if (pending >= ASSEMBLE_BATCH) flush();
          cursor.continue();
        };
        t.oncomplete = () => {
          flush();
          resolve(count > 0 ? blob : null);
        };
        t.onerror = () => reject(t.error);
      }),
  );
}

/** 조각 크기 합(줄을 만들 때 크기를 모르면). 조각을 하나씩만 읽는다. */
function chunkBytes(id: string): Promise<number> {
  return openDb().then(
    (db) =>
      new Promise<number>((resolve, reject) => {
        const t = db.transaction([CHUNKS], "readonly");
        const cursorReq = t.objectStore(CHUNKS).openCursor(chunkRange(id));
        let total = 0;

        cursorReq.onsuccess = () => {
          const cursor = cursorReq.result;

          if (!cursor) return;

          const row = cursor.value as { buf?: ArrayBuffer; blob?: Blob };

          total += row.buf ? row.buf.byteLength : row.blob?.size ?? 0;
          cursor.continue();
        };
        t.oncomplete = () => resolve(total);
        t.onerror = () => reject(t.error);
      }),
  );
}

async function readBody(item: RecordingItem): Promise<Blob | null> {
  if (item.blob) return item.blob;
  if (item.chunked) return assembleChunks(item.id, item.mime);
  if (!item.hasBody) return null;

  const body = await tx<ArrayBuffer>([BODIES], "readonly", (t) => t.objectStore(BODIES).get(item.id));

  return body ? new Blob([body], { type: item.mime }) : null;
}

/** 줄의 본문(조각 · bodies)을 지운다. 줄은 patch 를 넣어 남기거나(keep) 함께 지운다. */
async function dropPayload(id: string, keep: Partial<RecordingItem> | null): Promise<void> {
  const item = await getItem(id);

  await tx([ITEMS, BODIES, CHUNKS], "readwrite", (t) => {
    t.objectStore(BODIES).delete(id);
    t.objectStore(CHUNKS).delete(chunkRange(id));
    if (keep && item) t.objectStore(ITEMS).put({ ...item, ...keep, chunked: false, hasBody: false, blob: null, updatedAt: Date.now() });
    else t.objectStore(ITEMS).delete(id);
  });
  changed();
}

const dropBody = (id: string, patch: Partial<RecordingItem>) => dropPayload(id, patch);

/** 목록에서 지운다(파일 본문도). 올리는 중이면 지우지 않는다. */
export async function removeRecording(id: string): Promise<void> {
  if (activeId === id) return;

  await dropPayload(id, null);
}

/**
 * 다 올린 줄을 서버와 맞춘다(업로드 목록을 열 때). 웹에서 그 회차를 지웠거나(404) 담당이 바뀌어 볼 수 없게 됐으면(403)
 * 폰 목록에서 뺀다 — 전에는 폰에 남은 기록만 보여 지운 회차가 '완료' 로 남았다(11/11 시연 준비 요청 4번).
 * 연결이 없거나 서버가 답하지 않으면 그대로 둔다. 회차 한 건씩 짧게 묻는다(완료 줄은 7일만 남으므로 많지 않다).
 */
export async function syncDoneWithServer(userId: string): Promise<number> {
  const done = (await listRecordings(userId)).filter((item) => item.status === "done" && item.sessionId);
  let removed = 0;

  for (const item of done) {
    try {
      await getSession(item.sessionId as string);
    } catch (caught) {
      if (caught instanceof ApiError && (caught.status === 404 || caught.status === 403)) {
        await dropPayload(item.id, null);
        removed += 1;
      } else if (caught instanceof ApiError && caught.isUnauthorized) {
        break;
      }
      // 연결 끊김 · 시간 초과 · 5xx: 이번에는 그대로 둔다.
    }
  }

  return removed;
}

// ---------------------------------------------------------------------------
// 녹음 중 조각 저장 · 끊긴 녹음 되살리기
// ---------------------------------------------------------------------------

export async function startDraft(draft: RecordingDraft): Promise<void> {
  await tx([DRAFTS], "readwrite", (t) => t.objectStore(DRAFTS).put(draft));
}

export async function saveChunk(draftId: string, seq: number, blob: Blob, durationMs: number): Promise<void> {
  // 거래 안에서는 기다릴 수 없어서 바이트로 먼저 바꾼다.
  const buf = await blob.arrayBuffer();

  await tx([DRAFTS, CHUNKS], "readwrite", (t) => {
    t.objectStore(CHUNKS).put({ draftId, seq, buf });
    const drafts = t.objectStore(DRAFTS);
    const read = drafts.get(draftId);

    read.onsuccess = () => {
      if (read.result) drafts.put({ ...read.result, durationMs, bytes: (read.result.bytes ?? 0) + buf.byteLength, heartbeat: Date.now() });
    };
  });
}

/** 일시정지 중에도 녹음이 살아 있음을 표시한다(다른 탭이 끊긴 녹음으로 가져가지 않게, 민규 #168). */
export async function touchDraft(draftId: string, durationMs: number): Promise<void> {
  await tx([DRAFTS], "readwrite", (t) => {
    const drafts = t.objectStore(DRAFTS);
    const read = drafts.get(draftId);

    read.onsuccess = () => {
      if (read.result) drafts.put({ ...read.result, durationMs, heartbeat: Date.now() });
    };
  });
}

/**
 * 녹음 머리 줄을 지우고 같은 거래에서 대기열 줄을 넣는다. 조각은 그대로 둔다(그 녹음 ID 로 묶여 대기열 줄의 본문이 된다).
 * 한 거래라 앱이 그 사이에 꺼져도 머리 줄만 남거나 둘 다 남지 않는다.
 */
async function promoteDraft(draftId: string, item: RecordingItem): Promise<void> {
  await tx([DRAFTS, ITEMS], "readwrite", (t) => {
    t.objectStore(DRAFTS).delete(draftId);
    t.objectStore(ITEMS).put({ ...item, chunked: true });
  });
  changed();
}

async function dropDraft(draftId: string): Promise<void> {
  const range = IDBKeyRange.bound([draftId, 0], [draftId, Number.MAX_SAFE_INTEGER]);

  await tx([DRAFTS, CHUNKS], "readwrite", (t) => {
    t.objectStore(DRAFTS).delete(draftId);
    t.objectStore(CHUNKS).delete(range);
  });
}

/** 녹음을 그만두고(다시 녹음) 조각을 버린다. */
export function discardDraft(draftId: string): Promise<void> {
  return dropDraft(draftId);
}

export function fileNameFor(draft: Pick<RecordingDraft, "childLabel" | "sessionNumber" | "consultationType" | "ext">, kindLabel: string): string {
  const session = draft.sessionNumber ? `${draft.sessionNumber}회차` : "새회차";
  const safe = (text: string) => text.replace(/[\\/:*?"<>|\s]+/g, "");

  return `${safe(draft.childLabel)}_${session}_${safe(kindLabel)}${draft.ext}`;
}

function itemFromDraft(draft: RecordingDraft, fileName: string, size: number, durationMs: number): RecordingItem {
  const now = Date.now();

  return {
    id: draft.id,
    userId: draft.userId,
    caseId: draft.caseId,
    childLabel: draft.childLabel,
    sessionId: draft.sessionId,
    sessionNumber: draft.sessionNumber,
    expectStatus: draft.sessionId ? draft.expectStatus : "CREATED",
    consultationType: draft.consultationType,
    consultedAt: draft.consultedAt,
    fileName,
    mime: draft.mime,
    size,
    durationMs,
    status: "wait",
    step: draft.sessionId ? "upload" : "createSession",
    error: null,
    createUncertainSince: null,
    createdAt: now,
    updatedAt: now,
  };
}

/** 녹음을 마쳤다. 조각을 하나의 파일로 묶어 대기열에 넣고 바로 올리기 시작한다. */
export async function finishDraft(draft: RecordingDraft, fileName: string, durationMs: number): Promise<string> {
  const size = await chunkBytes(draft.id);

  await promoteDraft(draft.id, itemFromDraft(draft, fileName, size, durationMs));
  void processQueue();

  return draft.id;
}

/**
 * 폰에 있던 음성 파일(다른 녹음 앱으로 녹음한 것)을 대기열에 넣는다(앱 · 업로드의 '파일'). 늘 새 회차로 올린다.
 * 상담 일시는 파일의 수정 시각(대개 녹음을 마친 때)이다.
 */
export async function enqueueAudioFile(input: { userId: string; caseId: string; childLabel: string; file: File; durationMs?: number }): Promise<string> {
  const now = Date.now();
  const id = `f${now.toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  // 파일을 1MB 씩 잘라 조각으로 넣는다(한꺼번에 메모리에 올리지 않게).
  const PIECE = 1024 * 1024;

  for (let seq = 0, at = 0; at < input.file.size; seq += 1, at += PIECE) {
    const buf = await input.file.slice(at, at + PIECE).arrayBuffer();

    await tx([CHUNKS], "readwrite", (t) => {
      t.objectStore(CHUNKS).put({ draftId: id, seq, buf });
    });
  }

  await putItem(
    {
      id,
      userId: input.userId,
      caseId: input.caseId,
      childLabel: input.childLabel,
      sessionId: null,
      sessionNumber: null,
      expectStatus: "CREATED",
      consultationType: "REGULAR",
      consultedAt: new Date(input.file.lastModified || now).toISOString(),
      fileName: input.file.name,
      mime: input.file.type || "application/octet-stream",
      size: input.file.size,
      durationMs: input.durationMs ?? 0,
      chunked: true,
      status: "wait",
      step: "createSession",
      error: null,
      createUncertainSince: null,
      createdAt: now,
      updatedAt: now,
    },
  );
  void processQueue();

  return id;
}

async function heldRecordingLocks(): Promise<Set<string>> {
  try {
    const locks = (navigator as Navigator & { locks?: LockManager }).locks;

    if (!locks) return new Set();

    const state = await locks.query();

    return new Set((state.held ?? []).map((lock) => lock.name ?? "").filter((name) => name.startsWith(RECORDING_LOCK_PREFIX)));
  } catch {
    return new Set();
  }
}

/**
 * 끊긴 녹음(앱이 꺼짐 · 화면이 닫힘)을 대기열의 '실패' 줄로 되살린다. 녹음된 데까지 올릴 수 있다.
 * activeDraftId 는 지금 이 화면에서 녹음 중인 것(건너뛴다). 다른 탭이 녹음 중(잠금을 잡고 있음)인 것도 건너뛴다.
 */
export async function recoverDrafts(userId: string, activeDraftId: string | null, kindLabel: (type: ConsultationType) => string): Promise<void> {
  const drafts = ((await tx<RecordingDraft[]>([DRAFTS], "readonly", (t) => t.objectStore(DRAFTS).getAll())) ?? []) as RecordingDraft[];
  const held = await heldRecordingLocks();

  for (const draft of drafts) {
    if (draft.userId !== userId || draft.id === activeDraftId) continue;
    if (held.has(RECORDING_LOCK_PREFIX + draft.id)) continue;
    if (Date.now() - draft.heartbeat < DRAFT_STALE_MS) continue;

    // 조각을 읽지 않고 크기만 센다(되살릴 때 녹음 전체를 메모리에 올리지 않게).
    const size = draft.bytes ?? (await chunkBytes(draft.id));

    if (size === 0) {
      await dropDraft(draft.id);
      continue;
    }

    const item = itemFromDraft(draft, fileNameFor(draft, kindLabel(draft.consultationType)), size, draft.durationMs);

    await promoteDraft(draft.id, { ...item, status: "fail", error: "녹음이 중간에 끊겼어요. 녹음된 데까지 저장해 두었어요.", autoRetry: false });
  }
}

// ---------------------------------------------------------------------------
// 올리기
// ---------------------------------------------------------------------------

/** 지금 올리는 줄. 한 번에 하나씩 올린다. */
let activeId: string | null = null;
let running = false;
let again = false;
/** 대기열을 돌릴 계정. 화면이 로그인을 확인한 뒤 정한다. */
let queueUser: string | null = null;

export function setQueueUser(userId: string | null): void {
  queueUser = userId;
}

/** 시간 초과(응답이 오지 않음). 연결 끊김처럼 자동으로 다시 올린다. */
class UploadTimeout extends Error {}

/** 이 단계에서 실패한 이유를 사람 말로. */
function failText(caught: unknown): string {
  if (caught instanceof UploadTimeout) return "연결이 느려 응답을 받지 못했어요. 자동으로 다시 올려요";
  if (caught instanceof ApiError) {
    if (caught.status === 0) return "네트워크 연결이 끊겨 올리지 못했어요";
    if (caught.isUnauthorized) return "로그인이 끝났어요. 다시 로그인한 뒤 다시 올려 주세요";

    return caught.message;
  }

  return "올리지 못했어요. 잠시 후 다시 올려 주세요";
}

function isTransient(caught: unknown): boolean {
  if (caught instanceof UploadTimeout) return true;
  if (caught instanceof ApiError) return caught.status === 0 || caught.status >= 500;

  return true;
}

/** 시간 제한을 둔 요청. 시간이 지나면 요청을 끊고 UploadTimeout 을 던진다. */
async function call<T>(ms: number, run: (signal: AbortSignal) => Promise<T>): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), ms);

  try {
    return await run(controller.signal);
  } catch (caught) {
    if (controller.signal.aborted) throw new UploadTimeout();
    throw caught;
  } finally {
    window.clearTimeout(timer);
  }
}

const SHORT_MS = 30_000;
/** 음성 올리기: 기본 90초 + 초당 20KB 로 잡은 시간(느린 모바일 연결 기준). */
const uploadMs = (bytes: number) => 90_000 + Math.ceil(bytes / 20);

const getSession = (id: string) => call(SHORT_MS, (signal) => request<SessionDetail>(`/sessions/${id}`, { signal }));

async function findCreatedSession(caseId: string, since: number): Promise<{ id: string; number: number } | null> {
  const page = await call(SHORT_MS, (signal) =>
    request<{ items: Session[] }>(`/cases/${caseId}/sessions`, { query: { page: 1, page_size: 100 }, signal }),
  );
  const recent = page.items
    .filter((row) => row.status === "CREATED")
    .filter((row) => (parseBackendTime(row.created_at)?.getTime() ?? 0) >= since - CREATE_LOOKBACK_MS)
    .sort((a, b) => b.session_number - a.session_number);

  return recent.length > 0 ? { id: recent[0].id, number: recent[0].session_number } : null;
}

/** 변환을 요청한 뒤(또는 이미 변환 중 · 그 뒤) 상태인가. */
function pastUpload(status: SessionStatus): boolean {
  return !UPLOADABLE.includes(status);
}

/**
 * 올리기 직전 회차 확인. 'ok' 면 올린다, 'ours' 면 앞서 보낸 이 녹음이 이미 올라가 있다(변환 요청부터),
 * 'changed' 면 그사이 다른 곳에서 바뀌어 올리지 않는다.
 */
async function checkTarget(item: RecordingItem): Promise<"ok" | "ours" | "changed"> {
  let session: SessionDetail;

  try {
    session = await getSession(item.sessionId as string);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) return "changed";
    throw caught;
  }

  if (session.source === "DOCUMENT") return "changed";

  // 앞서 보낸 음성의 응답을 놓쳤으면 서버의 최신 음성이 이 녹음인지 크기 · 이름으로 본다.
  if (item.uploadSent && session.has_audio) {
    try {
      const audio = await call(SHORT_MS, (signal) => request<AudioFile>(`/sessions/${item.sessionId}/audio`, { signal }));

      if (audio.size_bytes === item.size) return "ours";
    } catch (caught) {
      if (!(caught instanceof ApiError && caught.status === 404)) throw caught;
    }
  }

  const expect = item.expectStatus ?? "CREATED";

  if (expect === "CREATED") return session.status === "CREATED" ? "ok" : "changed";

  // 녹음이 있는 회차를 바꾸기로 골랐다: 그때처럼 아직 변환 전(녹음만 있음 · 변환 실패)일 때만.
  return session.status === "AUDIO_UPLOADED" || session.status === "STT_FAILED" ? "ok" : "changed";
}

async function uploadOne(id: string, kindTitle: (type: ConsultationType) => string): Promise<void> {
  let item = await getItem(id);

  if (!item || !hasPayload(item) || item.status === "done") return;

  if (!getToken()) {
    await patchItem(id, { status: "fail", error: "로그인이 끝났어요. 다시 로그인한 뒤 다시 올려 주세요", autoRetry: false });
    return;
  }

  activeId = id;
  item = (await patchItem(id, { status: "run", error: null })) ?? item;

  try {
    if (item.step === "createSession") {
      let sessionId: string | null = null;
      let sessionNumber: number | null = null;

      if (item.createUncertainSince) {
        const found = await findCreatedSession(item.caseId, item.createUncertainSince);

        if (found) {
          sessionId = found.id;
          sessionNumber = found.number;
        }
      }

      if (!sessionId) {
        const since = Date.now();

        try {
          const session = await call(SHORT_MS, (signal) =>
            request<Session>(`/cases/${item!.caseId}/sessions`, {
              method: "POST",
              json: { title: `${kindTitle(item!.consultationType)} 녹음`, consulted_at: item!.consultedAt, consultation_type: item!.consultationType },
              signal,
            }),
          );

          sessionId = session.id;
          sessionNumber = session.session_number;
        } catch (caught) {
          if (isTransient(caught)) await patchItem(id, { createUncertainSince: since });
          throw caught;
        }
      }

      const fileName = item.fileName.replace("_새회차_", `_${sessionNumber}회차_`);

      item =
        (await patchItem(id, { sessionId, sessionNumber, fileName, expectStatus: "CREATED", step: "upload", createUncertainSince: null, uploadSent: false })) ??
        item;
    }

    if (item.step === "upload" && item.sessionId) {
      const target = await checkTarget(item);

      if (target === "changed") {
        await patchItem(id, {
          status: "fail",
          needNewSession: true,
          autoRetry: false,
          error: "그사이 이 회차에 다른 녹음이 올라갔거나 검수가 시작됐어요. 새 회차로 올려 주세요.",
        });
        return;
      }

      if (target === "ok") {
        const body = await readBody(item);

        if (!body) throw new Error("본문 없음");

        const form = new FormData();

        form.append("file", new File([body], item.fileName, { type: item.mime }));
        // 본문 Blob 은 조각을 이은 것이라 여기서 바이트를 새로 복사하지 않는다.
        if (item.durationMs > 0) form.append("duration_ms", String(Math.round(item.durationMs)));

        item = (await patchItem(id, { uploadSent: true })) ?? item;
        await call(uploadMs(item.size), (signal) => request(`/sessions/${item!.sessionId}/audio`, { method: "POST", body: form, signal }));
      }

      item = (await patchItem(id, { step: "requestStt" })) ?? item;
    }

    if (item.step === "requestStt" && item.sessionId) {
      // 다시 할 때: 이미 변환 중 · 그 뒤면 다시 요청하지 않는다(변환이 두 번 돌지 않게).
      const before = await getSession(item.sessionId);

      if (!pastUpload(before.status)) {
        try {
          await call(SHORT_MS, (signal) => request(`/sessions/${item!.sessionId}/transcript`, { method: "POST", signal }));
        } catch (caught) {
          // 앞선 요청이 이미 닿았으면 409 다. 상태를 다시 보고 변환 중 · 그 뒤면 끝난 것으로 둔다.
          if (!(caught instanceof ApiError && caught.status === 409)) throw caught;

          const after = await getSession(item.sessionId);

          if (!pastUpload(after.status)) throw caught;
        }
      }
    }

    await dropBody(id, { status: "done", error: null, needNewSession: false });
  } catch (caught) {
    await patchItem(id, { status: "fail", error: failText(caught), autoRetry: isTransient(caught) });
  } finally {
    activeId = null;
  }
}

let kindTitleFn: (type: ConsultationType) => string = (type) => type;

export function setKindTitle(fn: (type: ConsultationType) => string): void {
  kindTitleFn = fn;
}

/**
 * 기다리는 줄(wait · 앱이 꺼져 멈춘 run)을 차례로 올린다. includeFailed 면 연결 끊김 · 서버 오류 · 시간 초과로 실패한 줄도
 * 다시 올린다(연결이 돌아왔을 때 · 앱을 열 때 · 앱을 켜 둔 동안 1분마다). 이미 돌고 있으면 끝난 뒤 한 번 더 돈다.
 */
export async function processQueue(includeFailed = false): Promise<void> {
  if (running) {
    again = true;
    return;
  }

  const userId = queueUser;

  if (!userId) return;

  running = true;

  // 같은 폰의 다른 탭과 동시에 올리지 않게 잠근다(Web Locks, 되는 브라우저만).
  const locks = typeof navigator !== "undefined" ? (navigator as Navigator & { locks?: LockManager }).locks : undefined;

  try {
    if (locks) await locks.request("ispot-app-upload", () => drain(userId, includeFailed));
    else await drain(userId, includeFailed);
  } finally {
    running = false;
  }
}

async function drain(userId: string, includeFailed: boolean): Promise<void> {
  do {
    again = false;
    const items = await listRecordings(userId);

    // 오래된 완료 줄 정리.
    for (const item of items) {
      if (item.status === "done" && Date.now() - item.updatedAt > DONE_KEEP_MS) {
        await dropPayload(item.id, null);
      }
    }

    const todo = items
      .filter(
        (item) =>
          hasPayload(item) &&
          (item.status === "wait" || item.status === "run" || (includeFailed && item.status === "fail" && item.autoRetry === true)),
      )
      .sort((a, b) => a.createdAt - b.createdAt);

    for (const item of todo) {
      if (queueUser !== userId) break;
      // 연결이 없으면 실패로 표시만 하고 기다린다(online 이벤트에서 다시 돈다).
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        await patchItem(item.id, { status: "fail", error: "네트워크 연결이 끊겨 올리지 못했어요", autoRetry: true });
        continue;
      }

      await uploadOne(item.id, kindTitleFn);
    }
    includeFailed = false;
  } while (again);
}

/** 한 줄만 다시 올린다(다시 올리기 단추). */
export async function retryRecording(id: string): Promise<void> {
  await patchItem(id, { status: "wait", error: null });
  await processQueue();
}

/** 고른 회차가 바뀌어 못 올린 줄을 새 회차로 올린다('새 회차로 올리기' 단추). */
export async function uploadAsNewSession(id: string): Promise<void> {
  const item = await getItem(id);

  if (!item) return;

  await patchItem(id, {
    sessionId: null,
    sessionNumber: null,
    expectStatus: "CREATED",
    fileName: item.fileName.replace(/_\d+회차_/, "_새회차_"),
    step: "createSession",
    createUncertainSince: null,
    uploadSent: false,
    needNewSession: false,
    status: "wait",
    error: null,
  });
  await processQueue();
}

export function isUploading(id: string): boolean {
  return activeId === id;
}

if (typeof window !== "undefined") {
  window.addEventListener("online", () => void processQueue(true));
}
