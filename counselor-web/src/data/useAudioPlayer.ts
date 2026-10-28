// 녹음 재생기 훅. useSessionAudio 가 만든 Blob URL 을 HTMLAudioElement 에 물려 재생 · 일시정지 · 정지 · 5초 이동 ·
// 위치 이동을 한다. STT 검수의 시간 단추('그 발화부터 듣기')와 하단 재생 바가 쓴다.
//
// 요소는 화면에 두지 않고 훅 안에서 만든다(소리만 필요). 회차가 바뀌어 URL 이 바뀌면 src 를 갈아 끼우고 위치를 0 으로 돌린다.
// 브라우저는 사용자 조작 직후에만 재생을 허용하므로, 시간 단추를 눌렀을 때 파일을 아직 못 받았으면 받고 나서 재생을
// 시도하고, 막히면(NotAllowedError) 안내 문장을 돌려준다(notice). 그래서 화면은 원문이 보이면 파일을 미리 받아 둔다(prefetch).

import { useCallback, useEffect, useRef, useState } from "react";

import type { SessionAudioState } from "./useSessionAudio";

export interface AudioPlayerState {
  /** 재생할 수 있는가(파일을 받았거나 받을 수 있고, 오류가 없다). */
  ready: boolean;
  /** 파일을 받는 중. */
  loading: boolean;
  /** 파일을 못 받은 이유. */
  error: string | null;
  /** 브라우저가 재생을 막았을 때 등 한 번 보여 줄 안내. */
  notice: string | null;
  playing: boolean;
  currentMs: number;
  /** 파일이 알려 준 길이. 아직 모르면 null. */
  durationMs: number | null;
  /** 그 시각부터 재생한다(필요하면 파일을 먼저 받는다). */
  playFrom: (ms: number) => Promise<void>;
  /** 재생 ↔ 일시정지. 아직 안 받았으면 받아서 처음부터 재생한다. */
  toggle: () => Promise<void>;
  /** 멈추고 처음으로. */
  stop: () => void;
  /** 지금 위치에서 deltaMs 만큼 이동(음수면 뒤로). */
  skip: (deltaMs: number) => void;
  seek: (ms: number) => void;
}

interface PlayerOptions {
  /** true 면 파일을 미리 받아 둔다(원문이 보일 때). */
  prefetch?: boolean;
}

const BLOCKED_NOTICE = "브라우저가 재생을 막았습니다. 재생 단추를 한 번 더 눌러 주세요.";

/** 길이를 알 때까지(loadedmetadata) 기다린다. 이미 알면 바로. */
function whenReady(element: HTMLAudioElement): Promise<void> {
  if (element.readyState >= 1) return Promise.resolve();

  return new Promise((resolve) => {
    const done = () => {
      element.removeEventListener("loadedmetadata", done);
      element.removeEventListener("error", done);
      resolve();
    };

    element.addEventListener("loadedmetadata", done);
    element.addEventListener("error", done);
  });
}

export function useAudioPlayer(audio: SessionAudioState, { prefetch = false }: PlayerOptions = {}): AudioPlayerState {
  const element = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentMs, setCurrentMs] = useState(0);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { url, load, loading, error } = audio;

  useEffect(() => {
    const audioElement = new Audio();
    audioElement.preload = "auto";
    element.current = audioElement;

    const onTime = () => setCurrentMs(Math.round(audioElement.currentTime * 1000));
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onMeta = () =>
      setDurationMs(Number.isFinite(audioElement.duration) ? Math.round(audioElement.duration * 1000) : null);

    audioElement.addEventListener("timeupdate", onTime);
    audioElement.addEventListener("seeked", onTime);
    audioElement.addEventListener("play", onPlay);
    audioElement.addEventListener("pause", onPause);
    audioElement.addEventListener("ended", onPause);
    audioElement.addEventListener("loadedmetadata", onMeta);
    audioElement.addEventListener("durationchange", onMeta);

    return () => {
      audioElement.pause();
      audioElement.removeEventListener("timeupdate", onTime);
      audioElement.removeEventListener("seeked", onTime);
      audioElement.removeEventListener("play", onPlay);
      audioElement.removeEventListener("pause", onPause);
      audioElement.removeEventListener("ended", onPause);
      audioElement.removeEventListener("loadedmetadata", onMeta);
      audioElement.removeEventListener("durationchange", onMeta);
      audioElement.removeAttribute("src");
      audioElement.load();
      element.current = null;
    };
  }, []);

  // 받은 파일(URL)을 물린다. 회차가 바뀌어 URL 이 없어지면 비운다.
  useEffect(() => {
    const audioElement = element.current;

    if (!audioElement) return;

    if (url) {
      if (audioElement.src !== url) {
        audioElement.src = url;
        audioElement.load();
        setCurrentMs(0);
        setDurationMs(null);
      }
    } else {
      audioElement.pause();
      audioElement.removeAttribute("src");
      audioElement.load();
      setPlaying(false);
      setCurrentMs(0);
      setDurationMs(null);
    }

    setNotice(null);
  }, [url]);

  useEffect(() => {
    if (prefetch && !url && !loading && !error) void load();
  }, [prefetch, url, loading, error, load]);

  /** 파일을 물린 요소를 돌려준다(필요하면 받는다). 못 받으면 null. */
  const prepare = useCallback(async (): Promise<HTMLAudioElement | null> => {
    const ready = url ?? (await load());
    const audioElement = element.current;

    if (!ready || !audioElement) return null;

    if (audioElement.src !== ready) {
      audioElement.src = ready;
      audioElement.load();
    }

    await whenReady(audioElement);

    return audioElement;
  }, [url, load]);

  const play = useCallback(async (audioElement: HTMLAudioElement) => {
    try {
      await audioElement.play();
      setNotice(null);
    } catch (caught) {
      // 사용자 조작에서 너무 늦게 불렸거나(파일 받는 데 오래 걸림) 자동 재생이 막혔다. 다시 누르면 된다.
      setNotice(caught instanceof DOMException && caught.name === "NotAllowedError" ? BLOCKED_NOTICE : "재생하지 못했습니다.");
    }
  }, []);

  const playFrom = useCallback(
    async (ms: number) => {
      const audioElement = await prepare();

      if (!audioElement) return;

      audioElement.currentTime = Math.max(0, ms) / 1000;
      setCurrentMs(Math.max(0, ms));
      await play(audioElement);
    },
    [prepare, play],
  );

  const toggle = useCallback(async () => {
    const audioElement = element.current;

    if (audioElement && audioElement.src && !audioElement.paused) {
      audioElement.pause();
      return;
    }

    const prepared = await prepare();

    if (prepared) await play(prepared);
  }, [prepare, play]);

  const stop = useCallback(() => {
    const audioElement = element.current;

    if (!audioElement || !audioElement.src) return;

    audioElement.pause();
    audioElement.currentTime = 0;
    setCurrentMs(0);
  }, []);

  const seek = useCallback((ms: number) => {
    const audioElement = element.current;

    if (!audioElement || !audioElement.src) return;

    const limit = Number.isFinite(audioElement.duration) ? audioElement.duration * 1000 : Number.POSITIVE_INFINITY;
    const next = Math.min(Math.max(0, ms), limit);

    audioElement.currentTime = next / 1000;
    setCurrentMs(Math.round(next));
  }, []);

  const skip = useCallback(
    (deltaMs: number) => {
      const audioElement = element.current;

      if (!audioElement || !audioElement.src) return;

      seek(audioElement.currentTime * 1000 + deltaMs);
    },
    [seek],
  );

  return {
    ready: error === null,
    loading,
    error,
    notice,
    playing,
    currentMs,
    durationMs,
    playFrom,
    toggle,
    stop,
    skip,
    seek,
  };
}
