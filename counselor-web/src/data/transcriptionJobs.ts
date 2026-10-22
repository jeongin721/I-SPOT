// 녹취 올리기 · 녹음 저장 뒤 원문 변환을 화면과 상관없이 끝까지 따라가는 공용 저장소.
// 10/22 디자인의 '분석 중입니다... → 분석 완료 [검수]' 알림(components/JobToast.jsx)이 읽는다.
//
// useAudioUpload 는 원문 변환을 요청하면 trackTranscription 으로 그 회차를 여기에 맡긴다. 업로드 창 · 녹음하기 창을 닫거나 다른
// 화면으로 가도 이 저장소가 GET /sessions/{id}/transcript 를 되풀이 조회해 끝을 안다(디자인은 8초 가짜 타이머 · 브라우저 저장소).
//  - 맡길 때의 로그인 토큰을 같이 둔다. 토큰이 바뀌면(로그아웃 · 다른 계정 · 다시 로그인) 그 일은 버린다 — 앞 계정의 회차를
//    새 계정 화면에 알리거나 새 토큰으로 조회하지 않게.
//  - 끝나면(검수 차례) '완료', 변환에 실패하면 '실패' 로 바꾼다. 끝난 알림은 화면이 실제로 보인 때(markTranscriptionShown)부터
//    DONE_MS · FAILED_MS 뒤 사라진다 — 다른 회차가 '분석 중' 으로 앞에 보이는 동안 앞 회차의 끝 알림이 보이지 않고 사라지지 않게.
//  - 조회가 연달아 실패하면 조용히 그만둔다(화면의 회차 상태는 회차 상세 · STT 검수에서 다시 본다).
// 화면 상태일 뿐 서버에 저장하지 않고, 새로고침하면 사라진다.

import { ApiError, getToken } from "../api/client";
import { transcript } from "../api/endpoints";
import { POLL_INTERVAL_MS } from "./useRemote";

export type TranscriptionJobPhase = "run" | "done" | "failed";

export interface TranscriptionJob {
  sessionId: string;
  caseId: string;
  /** 올린 파일 이름(알림에 흐리게 보인다). */
  name: string;
  phase: TranscriptionJobPhase;
  /** 맡긴 순서. 알림은 가장 최근 것 하나만 보인다. */
  seq: number;
}

/** 완료 · 실패 알림을 보이는 시간. 디자인은 완료 3초. */
const DONE_MS = 3000;
const FAILED_MS = 6000;
/** 조회가 연달아 이만큼 실패하면 그만둔다. */
const MAX_FAILURES = 5;

interface Entry extends TranscriptionJob {
  token: string;
  failures: number;
  /** 끝난 알림을 화면에 보이기 시작했는가(그때부터 사라질 시간을 센다). */
  shown: boolean;
}

let entries: Entry[] = [];
let snapshot: TranscriptionJob[] = [];
let seq = 0;
let timer: number | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  snapshot = entries.map(({ sessionId, caseId, name, phase, seq: order }) => ({ sessionId, caseId, name, phase, seq: order }));
  listeners.forEach((listener) => listener());
}

function remove(sessionId: string, order?: number): void {
  const before = entries.length;

  entries = entries.filter((entry) => !(entry.sessionId === sessionId && (order === undefined || entry.seq === order)));
  if (entries.length !== before) emit();
}

/** 토큰이 바뀐 일은 버린다. */
function dropStale(): void {
  const token = getToken();
  const before = entries.length;

  entries = entries.filter((entry) => entry.token === token);
  if (entries.length !== before) emit();
}

function finish(entry: Entry, phase: "done" | "failed"): void {
  entry.phase = phase;
  emit();
}

async function poll(): Promise<void> {
  timer = null;
  dropStale();

  const running = entries.filter((entry) => entry.phase === "run");

  await Promise.all(
    running.map(async (entry) => {
      try {
        const envelope = await transcript.get(entry.sessionId);

        // 기다리는 사이 토큰이 바뀌었거나 이미 빠진 일이면 버린다.
        if (!entries.includes(entry) || entry.token !== getToken()) return;

        entry.failures = 0;

        if (envelope.session_status === "STT_PROCESSING") return;

        finish(entry, envelope.session_status === "STT_FAILED" ? "failed" : "done");
      } catch (caught) {
        if (!entries.includes(entry)) return;

        entry.failures += 1;

        // 로그인이 끝났거나(401) 계속 실패하면 그만둔다.
        if ((caught instanceof ApiError && caught.isUnauthorized) || entry.failures >= MAX_FAILURES) {
          remove(entry.sessionId, entry.seq);
        }
      }
    }),
  );

  schedule();
}

function schedule(): void {
  if (timer !== null || !entries.some((entry) => entry.phase === "run")) return;

  timer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
}

/** 원문 변환을 요청한 회차를 맡긴다. 같은 회차를 다시 맡기면 새로 시작한다. 로그인하지 않았으면 맡지 않는다. */
export function trackTranscription(job: { sessionId: string; caseId: string; name: string }): void {
  const token = getToken();

  if (!token) return;

  entries = entries.filter((entry) => entry.sessionId !== job.sessionId);
  seq += 1;
  entries.push({ ...job, phase: "run", seq, token, failures: 0, shown: false });
  emit();
  schedule();
}

/**
 * 화면이 끝난 알림(완료 · 실패)을 보이기 시작할 때 부른다. 그때부터 DONE_MS · FAILED_MS 뒤 사라진다. 한 번만 센다.
 * 화면은 끝난 알림을 맡긴 순서대로(앞 회차 먼저) 하나씩 보이고, 끝난 것이 없으면 가장 최근의 '분석 중' 을 보인다(JobToast).
 */
export function markTranscriptionShown(sessionId: string, order: number): void {
  const entry = entries.find((item) => item.sessionId === sessionId && item.seq === order);

  if (!entry || entry.phase === "run" || entry.shown) return;

  entry.shown = true;
  window.setTimeout(() => remove(sessionId, order), entry.phase === "done" ? DONE_MS : FAILED_MS);
}

/** 알림을 닫는다('검수' 를 눌렀을 때). */
export function dismissTranscription(sessionId: string): void {
  remove(sessionId);
}

export function subscribeTranscriptionJobs(listener: () => void): () => void {
  listeners.add(listener);

  return () => {
    listeners.delete(listener);
  };
}

/** 맡은 일 목록(useSyncExternalStore 용 — 바뀔 때만 새 배열). */
export function getTranscriptionJobs(): TranscriptionJob[] {
  return snapshot;
}

/** 다른 탭에서 토큰이 바뀌었을 때 화면이 부른다(storage 이벤트를 받는 useAuthSession 다음에). */
export function dropStaleTranscriptionJobs(): void {
  dropStale();
}
