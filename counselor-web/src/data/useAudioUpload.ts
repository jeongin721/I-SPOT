// 녹음 업로드 → 원문 변환(STT) 훅. 업로드 창이 쓴다.
//
//   (새 회차면) POST /cases/{id}/sessions → POST /sessions/{id}/audio → POST /sessions/{id}/transcript(202)
//   → GET /sessions/{id}/transcript 를 POLL_INTERVAL_MS 마다 조회해 변환이 끝날 때까지 기다린다.
//
// 화면은 start() 에 사례 · 회차 · 파일을 넘기고 phase 를 보고 그린다. 실패하면 retry() 가 실패한 단계부터 다시 한다.
//  - 새 회차를 만든 뒤 업로드 · 변환이 실패하고 다시 시도하면 **이미 만든 회차를 다시 쓴다**
//    (예전 화면은 새 회차를 또 만들어 빈 회차가 쌓였다). 회차 만들기 응답을 놓쳤으면(연결 끊김 · 5xx) 다시 시도할 때
//    그사이 생긴 빈 회차(CREATED)를 먼저 찾아 쓴다.
//  - 진행률(%)은 Backend 가 주지 않는다. 단계(phase)로 보여 준다.
//  - 화면을 닫아도 서버의 변환은 계속된다. 결과는 회차 상세 · 처리 대기 업무에서 이어서 본다.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, getToken } from "../api/client";
import { cases, sessions, transcript } from "../api/endpoints";
import type { SessionCreateRequest, SessionStatus } from "../api/types";
import { checkAudioFile } from "./audioFile";
import { notifySessionChanged } from "./sessionEvents";
import { parseBackendTime } from "./time";
import { POLL_INTERVAL_MS, errorMessage } from "./useRemote";

/**
 * idle            시작 전
 * creatingSession 새 회차를 만드는 중
 * uploading       음성을 올리는 중
 * requestingStt   원문 변환을 요청하는 중
 * transcribing    서버가 원문으로 바꾸는 중(되풀이 조회)
 * done            끝(원문 검수 차례. requestStt=false 면 업로드까지만 하고 끝)
 * failed          실패. failedStep 에서 멈췄다
 */
export type UploadPhase = "idle" | "creatingSession" | "uploading" | "requestingStt" | "transcribing" | "done" | "failed";

/** 실패한 단계. retry() 가 여기서부터 다시 한다. */
export type UploadFailedStep = "file" | "createSession" | "upload" | "requestStt" | "transcribing";

export const UPLOAD_PHASE_LABELS: Record<UploadPhase, string> = {
  idle: "대기",
  creatingSession: "회차 만드는 중",
  uploading: "음성 올리는 중",
  requestingStt: "원문 변환 요청 중",
  transcribing: "원문으로 바꾸는 중",
  done: "완료",
  failed: "실패",
};

export interface UploadRequest {
  caseId: string;
  /** 이미 있는 회차에 올릴 때. 없으면 newSession 으로 새 회차를 만든다. */
  sessionId?: string | null;
  /** 새 회차 정보(제목 · 상담 일시(UTC ISO) · 장소 · 메모). 모두 빼도 된다. */
  newSession?: SessionCreateRequest;
  file: File;
  /** 음성 길이(밀리초). readAudioDuration 으로 잴 수 있다. WAV 는 서버가 잰다. */
  durationMs?: number;
  /** false 면 업로드까지만 한다. 기본 true. */
  requestStt?: boolean;
}

export interface AudioUploadState {
  phase: UploadPhase;
  phaseLabel: string;
  /** 작업 대상 회차. 새 회차면 만든 뒤 채워진다. 끝난 뒤 검수 화면으로 보낼 때 쓴다. */
  sessionId: string | null;
  /** 마지막으로 확인한 회차 상태. */
  sessionStatus: SessionStatus | null;
  error: string | null;
  failedStep: UploadFailedStep | null;
  /** 진행 중이면 true(단추를 끄는 데 쓴다). */
  busy: boolean;
  /** 시작한다. 이미 진행 중이면 아무것도 하지 않고 false(먼저 reset 한다). */
  start: (request: UploadRequest) => Promise<boolean>;
  /** 실패한 단계부터 다시 한다. 파일 검사에서 실패했으면 다시 할 것이 없어 false. */
  retry: () => Promise<boolean>;
  /** 처음 상태로. 기다리던 조회도 멈춘다(서버 변환은 계속된다). */
  reset: () => void;
}

/** 변환 결과 조회가 연달아 이만큼 실패하면 멈추고 알린다(잠깐 끊긴 연결로 바로 실패하지 않게). */
const MAX_POLL_FAILURES = 3;

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/** 응답을 놓친 회차 만들기 요청이 서버에서 만든 회차를 가늠하는 여유(서버 · 브라우저 시계 차이 포함). */
const CREATE_LOOKBACK_MS = 5 * 60 * 1000;

/**
 * since 무렵 이후에 생긴, 음성이 없는(CREATED) 회차 중 가장 최근 것. 없으면 null.
 * 응답을 놓친 회차 만들기를 다시 시도할 때 빈 회차를 또 만들지 않으려고 쓴다.
 */
async function findCreatedSession(caseId: string, since: number): Promise<string | null> {
  const page = await cases.listSessions(caseId, { page: 1, page_size: 100 });
  const recent = page.items
    .filter((row) => row.status === "CREATED")
    .filter((row) => (parseBackendTime(row.created_at)?.getTime() ?? 0) >= since - CREATE_LOOKBACK_MS)
    .sort((a, b) => b.session_number - a.session_number);

  return recent.length > 0 ? recent[0].id : null;
}

export function useAudioUpload(): AudioUploadState {
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failedStep, setFailedStep] = useState<UploadFailedStep | null>(null);

  // 지금 진행 중인 실행의 번호. reset · 화면 닫기 · 새 시작으로 바뀌면 앞 실행은 조용히 멈춘다.
  const runId = useRef(0);
  const request = useRef<UploadRequest | null>(null);
  // 이 창에서 만든 회차(사례별). 실패 뒤 다시 시도할 때 또 만들지 않는다.
  const created = useRef<{ caseId: string; sessionId: string } | null>(null);
  // 회차 만들기 요청이 서버에 닿았는지 모르게 실패했다(연결 끊김 · 5xx). 다시 시도할 때 그사이 생긴 빈 회차를 먼저 찾는다.
  const uncertain = useRef<{ caseId: string; since: number } | null>(null);
  const failedAt = useRef<UploadFailedStep | null>(null);
  // 실행 중인가. 실행 중에는 start · retry 를 받지 않는다.
  const running = useRef(false);

  useEffect(
    () => () => {
      runId.current += 1;
    },
    [],
  );

  const run = useCallback(async (input: UploadRequest, from: UploadFailedStep, token: string | null): Promise<boolean> => {
    const id = ++runId.current;
    // 시작할 때의 로그인이 그대로인가도 본다. 다른 탭에서 다시 로그인하면(토큰이 바뀜) 화면은 그대로라 runId 가 오르지 않는다.
    // 그때 앞 로그인으로 시작한 실행이 다음 단계(업로드 · 변환 요청 · 조회)를 새 로그인 토큰으로 보내지 않게 멈춘다.
    const alive = () => id === runId.current && getToken() === token;
    // 같은 화면의 회차 상세 · 사례 상세 훅이 새 상태를 받아 가게 알린다.
    const changed = (target: string) => notifySessionChanged({ sessionId: target, caseId: input.caseId });
    const steps: UploadFailedStep[] = ["file", "createSession", "upload", "requestStt", "transcribing"];
    const startAt = steps.indexOf(from);
    let step: UploadFailedStep = from;

    const fail = (at: UploadFailedStep, message: string) => {
      if (!alive()) return false;

      failedAt.current = at;
      setFailedStep(at);
      setError(message);
      setPhase("failed");

      return false;
    };

    setError(null);
    setFailedStep(null);
    failedAt.current = null;

    try {
      if (startAt <= 0) {
        step = "file";
        const problem = checkAudioFile(input.file);

        if (problem) return fail("file", problem);
      }

      // 회차 정하기: 넘겨받은 회차 → 이 창에서 앞서 만든 회차(같은 사례) → 새로 만들기.
      let target = input.sessionId ?? null;

      if (!target && created.current?.caseId === input.caseId) target = created.current.sessionId;

      if (!target && uncertain.current?.caseId === input.caseId) {
        step = "createSession";
        setPhase("creatingSession");

        const found = await findCreatedSession(input.caseId, uncertain.current.since);

        if (!alive()) return false;

        uncertain.current = null;

        if (found) {
          created.current = { caseId: input.caseId, sessionId: found };
          target = found;
        }
      }

      if (!target) {
        step = "createSession";
        setPhase("creatingSession");

        const since = Date.now();
        let session;

        try {
          session = await cases.createSession(input.caseId, input.newSession ?? {});
        } catch (caught) {
          // 응답을 못 받았으면(연결 끊김 · 5xx) 서버에는 회차가 생겼을 수 있다.
          if (caught instanceof ApiError && (caught.status === 0 || caught.status >= 500)) {
            uncertain.current = { caseId: input.caseId, since };
          }
          throw caught;
        }

        if (!alive()) return false;

        created.current = { caseId: input.caseId, sessionId: session.id };
        target = session.id;
        setSessionStatus(session.status);
        changed(target);
      }

      setSessionId(target);

      if (startAt <= 2) {
        step = "upload";
        setPhase("uploading");

        const uploaded = await sessions.uploadAudio(target, input.file, input.durationMs);

        if (!alive()) return false;

        setSessionStatus(uploaded.session_status);
        changed(target);
      }

      if (input.requestStt === false) {
        created.current = null;
        setPhase("done");

        return true;
      }

      if (startAt <= 3) {
        step = "requestStt";
        setPhase("requestingStt");

        const requested = await transcript.run(target);

        if (!alive()) return false;

        setSessionStatus(requested.session_status);
        changed(target);
      }

      step = "transcribing";
      setPhase("transcribing");

      let failures = 0;

      for (;;) {
        await wait(POLL_INTERVAL_MS);

        if (!alive()) return false;

        try {
          const envelope = await transcript.get(target);

          if (!alive()) return false;

          failures = 0;
          setSessionStatus(envelope.session_status);

          if (envelope.session_status === "STT_PROCESSING") continue;

          changed(target);

          if (envelope.session_status === "STT_FAILED") {
            // 변환 실패는 같은 회차에 다시 요청하면 된다(재시도 = requestStt 부터).
            return fail("requestStt", envelope.error?.message ?? "원문 변환에 실패했습니다. 다시 시도해 주세요.");
          }

          // STT_REVIEW_REQUIRED(검수 차례). 그사이 다른 창에서 검수를 마쳤으면 그 뒤 상태일 수도 있다.
          created.current = null;
          setPhase("done");

          return true;
        } catch (caught) {
          if (!alive()) return false;
          // 로그인이 끝났으면(401) 기다려도 소용없다.
          if (caught instanceof ApiError && caught.isUnauthorized) throw caught;

          failures += 1;

          if (failures >= MAX_POLL_FAILURES) throw caught;
        }
      }
    } catch (caught) {
      return fail(step, errorMessage(caught, "처리하지 못했습니다. 잠시 후 다시 시도해 주세요."));
    }
  }, []);

  /**
   * 진행 중인 실행이 없을 때만 시작한다. 같은 순간 start 를 두 번 불러도(두 번 누름) 회차가 두 개 생기지 않게.
   * phase 는 그린 뒤에야 바뀌므로 ref 로 막는다.
   */
  const launch = useCallback(
    (input: UploadRequest, from: UploadFailedStep) => {
      if (running.current) return Promise.resolve(false);

      running.current = true;

      const token = getToken();
      // run 은 첫 await 전까지 바로 돌아 runId 를 올린다. 그 번호의 실행이 끝날 때만 풀어 준다
      // (reset 뒤 새로 시작한 실행의 잠금을 앞 실행이 풀지 않게).
      const finished = run(input, from, token);
      const id = runId.current;

      return finished
        .then((ok) => {
          // 다른 탭에서 다시 로그인해 멈춘 실행이면 진행 표시를 거두고 처음부터 다시 올리게 한다. 다시 시도는 막는다
          // (앞 로그인으로 고른 회차 · 요청을 새 로그인으로 보내게 되므로).
          if (!ok && runId.current === id && getToken() !== token) {
            request.current = null;
            created.current = null;
            uncertain.current = null;
            failedAt.current = "file";
            setFailedStep("file");
            setError("로그인이 바뀌어 올리기를 멈췄습니다. 다시 올려 주세요.");
            setPhase("failed");
          }

          return ok;
        })
        .finally(() => {
          if (runId.current === id) running.current = false;
        });
    },
    [run],
  );

  const start = useCallback(
    (input: UploadRequest) => {
      if (running.current) return Promise.resolve(false);

      // 다른 사례로 새로 시작하면 앞 사례에서 만든 회차는 잊는다(같은 사례면 retry 처럼 다시 쓴다).
      if (created.current && created.current.caseId !== input.caseId) created.current = null;
      if (uncertain.current && uncertain.current.caseId !== input.caseId) uncertain.current = null;

      request.current = input;
      setSessionId(input.sessionId ?? null);
      setSessionStatus(null);

      return launch(input, "file");
    },
    [launch],
  );

  const retry = useCallback(() => {
    const input = request.current;
    const from = failedAt.current;

    if (!input || !from || from === "file") return Promise.resolve(false);

    return launch(input, from);
  }, [launch]);

  const reset = useCallback(() => {
    // 기다리던 실행은 다음 확인 때 조용히 멈춘다. 그 실행이 이미 보낸 요청(회차 만들기 · 업로드)은 서버에서 끝까지 간다.
    runId.current += 1;
    running.current = false;
    request.current = null;
    created.current = null;
    uncertain.current = null;
    failedAt.current = null;
    setPhase("idle");
    setSessionId(null);
    setSessionStatus(null);
    setError(null);
    setFailedStep(null);
  }, []);

  const busy = phase !== "idle" && phase !== "done" && phase !== "failed";

  return {
    phase,
    phaseLabel: UPLOAD_PHASE_LABELS[phase],
    sessionId,
    sessionStatus,
    error,
    failedStep,
    busy,
    start,
    retry,
    reset,
  };
}
