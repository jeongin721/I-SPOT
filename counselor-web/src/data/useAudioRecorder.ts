// 마이크 녹음 훅. 사례 상세의 '녹음하기' 창(10/21 디자인 CaseDetail.dc.html)이 쓴다.
//
// 브라우저 MediaRecorder 로 녹음해 파일(File)을 만든다. 서버에 올리는 것은 이 훅이 아니라 useAudioUpload 다
// (녹취 올리기 창과 같은 흐름: 회차 · 업로드 · 원문 변환).
//  - 마이크는 HTTPS 또는 이 컴퓨터 주소(localhost)에서만 열린다. 브라우저가 지원하지 않거나 허락하지 않으면 error 에 이유를
//    적고 녹음하지 않는다(디자인 미리보기처럼 녹음하는 척하지 않는다).
//  - 녹음은 올리기 전까지 이 브라우저 메모리에만 있다. reset 하거나 화면을 떠나면 마이크를 끄고 녹음을 버린다.
//  - 길이(seconds)는 녹음한 시간을 1초마다 센다. 브라우저가 만든 webm 은 길이 정보가 없을 때가 많아 올릴 때 이 값을 쓴다.

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * idle      시작 전(또는 다시 녹음)
 * starting  마이크 허락을 기다리는 중
 * recording 녹음 중
 * paused    일시정지
 * stopping  정지를 눌러 파일을 만드는 중
 * done      녹음 끝 · 파일 있음
 */
export type RecorderStatus = "idle" | "starting" | "recording" | "paused" | "stopping" | "done";

export interface AudioRecorderState {
  status: RecorderStatus;
  /** 녹음한 시간(초). */
  seconds: number;
  /** 들어 보기용 주소(done 일 때). */
  url: string | null;
  /** 올릴 파일(done 일 때). */
  file: File | null;
  error: string | null;
  start: () => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  /** 녹음을 버리고 처음으로. 마이크도 끈다. */
  reset: () => void;
}

/** 브라우저가 고른 형식 → 확장자(서버 허용 목록 audioFile.AUDIO_EXTENSIONS 안에서). */
const EXTENSIONS: Record<string, string> = {
  "audio/webm": ".webm",
  "audio/ogg": ".ogg",
  "audio/mp4": ".m4a",
  "audio/mpeg": ".mp3",
  "audio/wav": ".wav",
};

function fileName(type: string, now: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`;

  return `recording_${stamp}${EXTENSIONS[type.split(";")[0]] ?? ".webm"}`;
}

export function useAudioRecorder(): AudioRecorderState {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [seconds, setSeconds] = useState(0);
  const [url, setUrl] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 지금 녹음의 번호. reset · 화면 떠남으로 바뀌면 앞 녹음의 늦은 콜백(마이크 허락 · 파일 만들기)은 버린다.
  const runRef = useRef(0);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<number | null>(null);
  const urlRef = useRef<string | null>(null);

  const tick = useCallback((on: boolean) => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = on ? window.setInterval(() => setSeconds((value) => value + 1), 1000) : null;
  }, []);

  const releaseMedia = useCallback(() => {
    const recorder = recorderRef.current;

    recorderRef.current = null;
    try {
      if (recorder && recorder.state !== "inactive") recorder.stop();
    } catch {
      // 이미 멈췄다.
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const dropUrl = useCallback(() => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  }, []);

  const reset = useCallback(() => {
    runRef.current += 1;
    tick(false);
    releaseMedia();
    dropUrl();
    setStatus("idle");
    setSeconds(0);
    setUrl(null);
    setFile(null);
    setError(null);
  }, [dropUrl, releaseMedia, tick]);

  const start = useCallback(() => {
    const devices = typeof navigator !== "undefined" ? navigator.mediaDevices : undefined;

    if (!devices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError(
        "이 브라우저에서는 녹음할 수 없습니다(마이크는 HTTPS 또는 이 컴퓨터 주소에서만 열립니다). 녹음 파일을 '녹취 올리기' 로 올려 주세요.",
      );
      return;
    }

    const run = ++runRef.current;

    setError(null);
    setStatus("starting");
    devices
      .getUserMedia({ audio: true })
      .then((stream) => {
        if (run !== runRef.current) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        // 마이크를 먼저 맡아 둔다. 녹음기를 만들거나 시작하다 실패하면 바로 끈다(켜진 채 남지 않게).
        streamRef.current = stream;

        const chunks: Blob[] = [];
        let recorder: MediaRecorder;

        try {
          recorder = new MediaRecorder(stream);
        } catch {
          releaseMedia();
          setError("이 브라우저에서 녹음을 시작하지 못했습니다. 녹음 파일을 '녹취 올리기' 로 올려 주세요.");
          setStatus("idle");
          return;
        }

        recorderRef.current = recorder;
        recorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) chunks.push(event.data);
        };
        recorder.onstop = () => {
          if (run !== runRef.current) return;

          // 장치가 빠지는 등으로 저절로 멈춰도 시계를 멈춘다.
          tick(false);

          const type = recorder.mimeType || "audio/webm";
          const blob = new Blob(chunks, { type });

          dropUrl();
          urlRef.current = URL.createObjectURL(blob);
          setUrl(urlRef.current);
          setFile(new File([blob], fileName(type, new Date()), { type }));
          setStatus("done");
          streamRef.current?.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        };
        try {
          recorder.start();
        } catch {
          releaseMedia();
          setError("이 브라우저에서 녹음을 시작하지 못했습니다. 녹음 파일을 '녹취 올리기' 로 올려 주세요.");
          setStatus("idle");
          return;
        }

        setSeconds(0);
        tick(true);
        setStatus("recording");
      })
      .catch((reason: unknown) => {
        if (run !== runRef.current) return;

        const denied = reason instanceof DOMException && reason.name === "NotAllowedError";

        setError(denied ? "마이크 사용을 허락하지 않아 녹음할 수 없습니다." : "마이크를 열지 못했습니다.");
        setStatus("idle");
      });
  }, [dropUrl, releaseMedia, tick]);

  const pause = useCallback(() => {
    const recorder = recorderRef.current;

    if (!recorder || recorder.state !== "recording") return;
    recorder.pause();
    tick(false);
    setStatus("paused");
  }, [tick]);

  const resume = useCallback(() => {
    const recorder = recorderRef.current;

    if (!recorder || recorder.state !== "paused") return;
    recorder.resume();
    tick(true);
    setStatus("recording");
  }, [tick]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;

    if (!recorder || recorder.state === "inactive") return;
    tick(false);
    setStatus("stopping");
    recorder.stop();
  }, [tick]);

  // 화면을 떠나면 마이크를 끄고 녹음을 버린다.
  useEffect(
    () => () => {
      runRef.current += 1;
      tick(false);
      releaseMedia();
      dropUrl();
    },
    [dropUrl, releaseMedia, tick],
  );

  return { status, seconds, url, file, error, start, pause, resume, stop, reset };
}
