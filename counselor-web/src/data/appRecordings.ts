// 상담사 앱(폰) 녹음 보관함 · 올리기 대기열(앱 · 녹음 / 앱 · 업로드 화면, 2026-11-10 디자인).
//
// 폰에서 녹음한 파일을 이 브라우저의 IndexedDB 에 먼저 저장한 뒤 서버로 올린다. 올리는 길은 웹 녹취 올리기 창과 같다:
//   (새 회차면) POST /cases/{id}/sessions → POST /sessions/{id}/audio → POST /sessions/{id}/transcript(원문 변환 요청)
// 그래서 웹에서 같은 사례 · 회차를 열면 그 녹음이 그대로 있고, 변환이 끝나면 '원문 검수(1단계)' 부터 이어서 한다.
//
//  - 녹음은 1초마다 조각(chunk)으로 저장한다. 앱이 꺼지거나 화면이 닫혀도 녹음된 데까지는 남고, 다음에 열면
//    업로드 목록에 '실패' 로 올라와 다시 올릴 수 있다(recoverDrafts).
//  - 올리기가 실패하면(연결 끊김 등) 그 단계를 기억한다. 연결이 돌아오면(online 이벤트) · 앱을 다시 열면 실패한 단계부터
//    자동으로 다시 올린다. 새 회차를 이미 만들었으면 다시 만들지 않는다(빈 회차가 쌓이지 않게, useAudioUpload 와 같은 규칙).
//  - 대기열은 로그인한 계정별로 나눈다(userId). 같은 폰에서 다른 계정으로 로그인하면 앞 계정의 녹음은 보이지도 올라가지도 않는다.
//  - 다 올린 녹음은 파일 본문(blob)을 지우고 목록 줄만 남긴다(폰 저장 공간). 7일 지난 완료 줄은 지운다.

import { ApiError, getToken } from "../api/client";
import { cases, sessions, transcript } from "../api/endpoints";
import type { ConsultationType } from "../api/types";
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
  consultationType: ConsultationType;
  /** 녹음 시작 시각(UTC ISO). 새 회차의 상담 일시로 쓴다. */
  consultedAt: string;
  fileName: string;
  mime: string;
  size: number;
  durationMs: number;
  /** 파일 본문. 다 올리면 지운다. */
  blob: Blob | null;
  status: RecordingStatus;
  /** 다음에 할(또는 실패한) 단계. */
  step: RecordingStep;
  error: string | null;
  /** 회차 만들기 응답을 놓쳤을 때(연결 끊김 · 5xx) 그 시각. 다시 할 때 그사이 생긴 빈 회차를 먼저 찾는다. */
  createUncertainSince: number | null;
  /** 연결 끊김 · 서버 오류(5xx)로 실패했는가. 그런 줄만 자동으로 다시 올린다(형식 오류 등은 눌러야 다시 올린다). 옛 줄은 키가 없다. */
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
  consultationType: ConsultationType;
  consultedAt: string;
  mime: string;
  ext: string;
  durationMs: number;
  /** 마지막으로 조각을 저장한 시각. 오래되었으면(녹음기가 멈춤) 되살린다. */
  heartbeat: number;
}

const DB_NAME = "ispot-counselor-app";
const DB_VERSION = 1;
const ITEMS = "recordings";
const DRAFTS = "drafts";
const CHUNKS = "chunks";
const DONE_KEEP_MS = 7 * 24 * 60 * 60 * 1000;
/** 이보다 오래 조각이 안 들어온 녹음은 끊긴 것으로 본다. */
const DRAFT_STALE_MS = 15_000;
const CREATE_LOOKBACK_MS = 60_000;

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve, reject) => {
    let request: IDBOpenDBRequest;

    try {
      request = indexedDB.open(DB_NAME, DB_VERSION);
    } catch (caught) {
      reject(caught);
      return;
    }

    request.onupgradeneeded = () => {
      const db = request.result;

      if (!db.objectStoreNames.contains(ITEMS)) db.createObjectStore(ITEMS, { keyPath: "id" });
      if (!db.objectStoreNames.contains(DRAFTS)) db.createObjectStore(DRAFTS, { keyPath: "id" });
      if (!db.objectStoreNames.contains(CHUNKS)) db.createObjectStore(CHUNKS, { keyPath: ["draftId", "seq"] });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
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
        const request = work(t);

        if (request) request.onsuccess = () => (result = request.result);
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
// 목록
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

/** 목록에서 지운다(파일 본문도). 올리는 중이면 지우지 않는다. */
export async function removeRecording(id: string): Promise<void> {
  if (activeId === id) return;

  await tx([ITEMS], "readwrite", (t) => t.objectStore(ITEMS).delete(id));
  changed();
}

// ---------------------------------------------------------------------------
// 녹음 중 조각 저장 · 끊긴 녹음 되살리기
// ---------------------------------------------------------------------------

export async function startDraft(draft: RecordingDraft): Promise<void> {
  await tx([DRAFTS], "readwrite", (t) => t.objectStore(DRAFTS).put(draft));
}

export async function saveChunk(draftId: string, seq: number, blob: Blob, durationMs: number): Promise<void> {
  await tx([DRAFTS, CHUNKS], "readwrite", (t) => {
    t.objectStore(CHUNKS).put({ draftId, seq, blob });
    const drafts = t.objectStore(DRAFTS);
    const read = drafts.get(draftId);

    read.onsuccess = () => {
      if (read.result) drafts.put({ ...read.result, durationMs, heartbeat: Date.now() });
    };
  });
}

async function draftChunks(draftId: string): Promise<Blob[]> {
  const range = IDBKeyRange.bound([draftId, 0], [draftId, Number.MAX_SAFE_INTEGER]);
  const rows = ((await tx<{ seq: number; blob: Blob }[]>([CHUNKS], "readonly", (t) => t.objectStore(CHUNKS).getAll(range))) ??
    []) as { seq: number; blob: Blob }[];

  return rows.sort((a, b) => a.seq - b.seq).map((row) => row.blob);
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

/** 녹음을 마쳤다. 조각을 하나의 파일로 묶어 대기열에 넣고 바로 올리기 시작한다. */
export async function finishDraft(draft: RecordingDraft, fileName: string, durationMs: number): Promise<string> {
  const chunks = await draftChunks(draft.id);
  const blob = new Blob(chunks, { type: draft.mime });
  const now = Date.now();

  await putItem({
    id: draft.id,
    userId: draft.userId,
    caseId: draft.caseId,
    childLabel: draft.childLabel,
    sessionId: draft.sessionId,
    sessionNumber: draft.sessionNumber,
    consultationType: draft.consultationType,
    consultedAt: draft.consultedAt,
    fileName,
    mime: draft.mime,
    size: blob.size,
    durationMs,
    blob,
    status: "wait",
    step: draft.sessionId ? "upload" : "createSession",
    error: null,
    createUncertainSince: null,
    createdAt: now,
    updatedAt: now,
  });
  await dropDraft(draft.id);
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

  await putItem({
    id,
    userId: input.userId,
    caseId: input.caseId,
    childLabel: input.childLabel,
    sessionId: null,
    sessionNumber: null,
    consultationType: "REGULAR",
    consultedAt: new Date(input.file.lastModified || now).toISOString(),
    fileName: input.file.name,
    mime: input.file.type || "application/octet-stream",
    size: input.file.size,
    durationMs: input.durationMs ?? 0,
    blob: input.file,
    status: "wait",
    step: "createSession",
    error: null,
    createUncertainSince: null,
    createdAt: now,
    updatedAt: now,
  });
  void processQueue();

  return id;
}

/**
 * 끊긴 녹음(앱이 꺼짐 · 화면이 닫힘)을 대기열의 '실패' 줄로 되살린다. 녹음된 데까지 올릴 수 있다.
 * activeDraftId 는 지금 이 화면에서 녹음 중인 것(건너뛴다).
 */
export async function recoverDrafts(userId: string, activeDraftId: string | null, kindLabel: (type: ConsultationType) => string): Promise<void> {
  const drafts = ((await tx<RecordingDraft[]>([DRAFTS], "readonly", (t) => t.objectStore(DRAFTS).getAll())) ?? []) as RecordingDraft[];

  for (const draft of drafts) {
    if (draft.userId !== userId || draft.id === activeDraftId) continue;
    if (Date.now() - draft.heartbeat < DRAFT_STALE_MS) continue;

    const chunks = await draftChunks(draft.id);

    if (chunks.length === 0) {
      await dropDraft(draft.id);
      continue;
    }

    const blob = new Blob(chunks, { type: draft.mime });
    const now = Date.now();

    await putItem({
      id: draft.id,
      userId: draft.userId,
      caseId: draft.caseId,
      childLabel: draft.childLabel,
      sessionId: draft.sessionId,
      sessionNumber: draft.sessionNumber,
      consultationType: draft.consultationType,
      consultedAt: draft.consultedAt,
      fileName: fileNameFor(draft, kindLabel(draft.consultationType)),
      mime: draft.mime,
      size: blob.size,
      durationMs: draft.durationMs,
      blob,
      status: "fail",
      step: draft.sessionId ? "upload" : "createSession",
      error: "녹음이 중간에 끊겼어요. 녹음된 데까지 저장해 두었어요.",
      autoRetry: false,
      createUncertainSince: null,
      createdAt: now,
      updatedAt: now,
    });
    await dropDraft(draft.id);
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

/** 이 단계에서 실패한 이유를 사람 말로. */
function failText(caught: unknown): string {
  if (caught instanceof ApiError) {
    if (caught.status === 0) return "네트워크 연결이 끊겨 올리지 못했어요";
    if (caught.isUnauthorized) return "로그인이 끝났어요. 다시 로그인한 뒤 다시 올려 주세요";

    return caught.message;
  }

  return "올리지 못했어요. 잠시 후 다시 올려 주세요";
}

async function findCreatedSession(caseId: string, since: number): Promise<{ id: string; number: number } | null> {
  const page = await cases.listSessions(caseId, { page: 1, page_size: 100 });
  const recent = page.items
    .filter((row) => row.status === "CREATED")
    .filter((row) => (parseBackendTime(row.created_at)?.getTime() ?? 0) >= since - CREATE_LOOKBACK_MS)
    .sort((a, b) => b.session_number - a.session_number);

  return recent.length > 0 ? { id: recent[0].id, number: recent[0].session_number } : null;
}

async function uploadOne(id: string, kindTitle: (type: ConsultationType) => string): Promise<void> {
  let item = await getItem(id);

  if (!item || !item.blob || item.status === "done") return;

  const token = getToken();

  if (!token) {
    await patchItem(id, { status: "fail", error: "로그인이 끝났어요. 다시 로그인한 뒤 다시 올려 주세요" });
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
          const session = await cases.createSession(item.caseId, {
            title: `${kindTitle(item.consultationType)} 녹음`,
            consulted_at: item.consultedAt,
            consultation_type: item.consultationType,
          });

          sessionId = session.id;
          sessionNumber = session.session_number;
        } catch (caught) {
          if (caught instanceof ApiError && (caught.status === 0 || caught.status >= 500)) {
            await patchItem(id, { createUncertainSince: since });
          }
          throw caught;
        }
      }

      const fileName = item.fileName.replace("_새회차_", `_${sessionNumber}회차_`);

      item = (await patchItem(id, { sessionId, sessionNumber, fileName, step: "upload", createUncertainSince: null })) ?? item;
    }

    if (item.step === "upload" && item.sessionId) {
      const file = new File([item.blob as Blob], item.fileName, { type: item.mime });

      await sessions.uploadAudio(item.sessionId, file, item.durationMs > 0 ? Math.round(item.durationMs) : undefined);
      item = (await patchItem(id, { step: "requestStt" })) ?? item;
    }

    if (item.step === "requestStt" && item.sessionId) {
      await transcript.run(item.sessionId);
    }

    await patchItem(id, { status: "done", error: null, blob: null });
  } catch (caught) {
    const transient = caught instanceof ApiError ? caught.status === 0 || caught.status >= 500 : true;

    await patchItem(id, { status: "fail", error: failText(caught), autoRetry: transient });
  } finally {
    activeId = null;
  }
}

let kindTitleFn: (type: ConsultationType) => string = (type) => type;

export function setKindTitle(fn: (type: ConsultationType) => string): void {
  kindTitleFn = fn;
}

/**
 * 기다리는 줄(wait · 앱이 꺼져 멈춘 run)을 차례로 올린다. includeFailed 면 연결 끊김 · 서버 오류로 실패한 줄도 다시 올린다
 * (연결이 돌아왔을 때 · 앱을 열 때 · 앱을 켜 둔 동안 1분마다).
 * 이미 돌고 있으면 끝난 뒤 한 번 더 돈다.
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
  {
    do {
      again = false;
      const items = await listRecordings(userId);

      // 오래된 완료 줄 정리.
      for (const item of items) {
        if (item.status === "done" && Date.now() - item.updatedAt > DONE_KEEP_MS) {
          await tx([ITEMS], "readwrite", (t) => t.objectStore(ITEMS).delete(item.id));
        }
      }

      const todo = items
        .filter((item) => item.blob && (item.status === "wait" || item.status === "run" || (includeFailed && item.status === "fail" && item.autoRetry === true)))
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
}

/** 한 줄만 다시 올린다(다시 올리기 단추). */
export async function retryRecording(id: string): Promise<void> {
  await patchItem(id, { status: "wait", error: null });
  await processQueue();
}

export function isUploading(id: string): boolean {
  return activeId === id;
}

if (typeof window !== "undefined") {
  window.addEventListener("online", () => void processQueue(true));
}
