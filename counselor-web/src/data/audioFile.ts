// 올릴 음성 파일을 보내기 전에 확인하는 함수들.
//
// 기준은 Backend 기본 설정(API_CONTRACT 6절)과 같다. 서버 설정(AUDIO_MAX_SIZE_MB · AUDIO_ALLOWED_EXTENSIONS)을 바꾸면
// 서버가 최종으로 거절하므로(AUDIO_TOO_LARGE · AUDIO_UNSUPPORTED_TYPE) 여기 값은 미리 알려 주는 용도다.

import { formatBytes } from "./time";

/** Backend 기본 허용 확장자(API_CONTRACT 6절). */
export const AUDIO_EXTENSIONS = [".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac", ".webm"] as const;

/** Backend 기본 최대 크기 200MB(AUDIO_MAX_SIZE_MB). */
export const AUDIO_MAX_BYTES = 200 * 1024 * 1024;

/** 파일 선택 창의 accept 값. */
export const AUDIO_ACCEPT = AUDIO_EXTENSIONS.join(",");

/** 화면에 적을 안내 문구. */
export const AUDIO_RULE_TEXT = `${AUDIO_EXTENSIONS.join(" ")} 파일, ${formatBytes(AUDIO_MAX_BYTES).replace(".0", "")}까지 올릴 수 있습니다.`;

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");

  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

/** 보내기 전에 걸러 낼 문제가 있으면 그 문장, 없으면 null. */
export function checkAudioFile(file: File): string | null {
  const extension = extensionOf(file.name);

  if (!extension) return "확장자가 없는 파일은 올릴 수 없습니다.";

  if (!(AUDIO_EXTENSIONS as readonly string[]).includes(extension)) {
    return `지원하지 않는 형식입니다(${extension}). ${AUDIO_RULE_TEXT}`;
  }

  if (file.size === 0) return "빈 파일입니다.";

  if (file.size > AUDIO_MAX_BYTES) {
    return `파일이 너무 큽니다(${formatBytes(file.size)}). ${AUDIO_RULE_TEXT}`;
  }

  return null;
}

/**
 * 브라우저가 읽을 수 있는 음성이면 길이(밀리초)를 알아낸다. 못 읽으면 undefined.
 * WAV 는 서버가 직접 재므로 보내지 않아도 된다. 그 밖의 형식은 이 값을 올릴 때 같이 보내야 길이가 남는다.
 */
export function readAudioDuration(file: File, timeoutMs = 5000): Promise<number | undefined> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();
    let settled = false;

    const finish = (value: number | undefined) => {
      if (settled) return;

      settled = true;
      window.clearTimeout(timer);
      audio.removeAttribute("src");
      audio.load();
      URL.revokeObjectURL(url);
      resolve(value);
    };

    const timer = window.setTimeout(() => finish(undefined), timeoutMs);

    audio.preload = "metadata";
    audio.onloadedmetadata = () => {
      // 스트리밍으로 녹음한 webm 은 길이가 Infinity 로 오기도 한다. 그때는 모른다고 둔다.
      finish(Number.isFinite(audio.duration) && audio.duration > 0 ? Math.round(audio.duration * 1000) : undefined);
    };
    audio.onerror = () => finish(undefined);
    audio.src = url;
  });
}
