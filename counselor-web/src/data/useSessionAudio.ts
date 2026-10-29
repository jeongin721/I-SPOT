// 회차 음성 파일을 받아 재생용 Blob URL 을 만드는 훅(GET /sessions/{id}/audio/file, API_CONTRACT 6절).
//
// 서버는 Authorization 헤더로만 인증하므로 `<audio src>` 에 주소를 바로 넣지 못한다. 그래서 처음 재생을 누를 때
// fetch 로 파일을 받아 Blob URL 을 만들고(load), 회차가 바뀌거나 화면을 떠나면 URL 을 거둔다(메모리).
// 파일이 클 수 있어(최대 200MB) 화면을 열자마자 받지 않고 필요할 때 받는다.

import { useCallback, useEffect, useRef, useState } from "react";

import { sessions } from "../api/endpoints";
import { errorMessage } from "./useRemote";

export interface SessionAudioState {
  /** 재생할 수 있는 Blob URL. 아직 안 받았으면 null. */
  url: string | null;
  loading: boolean;
  error: string | null;
  /** 파일을 받는다(이미 받았으면 바로). 돌려주는 URL 이 null 이면 못 받은 것(error 에 이유). */
  load: () => Promise<string | null>;
}

interface AudioOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export function useSessionAudio(
  sessionId: string | null | undefined,
  { enabled = true }: AudioOptions = {},
): SessionAudioState {
  const key = enabled && sessionId ? sessionId : null;
  const [state, setState] = useState<{ key: string | null; url: string | null; loading: boolean; error: string | null }>({
    key,
    url: null,
    loading: false,
    error: null,
  });
  // 진행 중인 받기. 같은 회차에서 재생을 연달아 눌러도 한 번만 받는다.
  const pending = useRef<{ key: string; promise: Promise<string | null> } | null>(null);
  const keyRef = useRef(key);
  keyRef.current = key;
  // 만든 URL. 회차가 바뀌거나 화면을 떠나면 거둔다.
  const urlRef = useRef<{ key: string; url: string } | null>(null);

  const revoke = () => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current.url);
      urlRef.current = null;
    }
  };

  useEffect(() => {
    if (urlRef.current && urlRef.current.key !== key) revoke();
    pending.current = null;
    setState({ key, url: null, loading: false, error: null });

    return () => {
      revoke();
      pending.current = null;
    };
  }, [key]);

  const load = useCallback(async (): Promise<string | null> => {
    const current = keyRef.current;

    if (!current) return null;
    if (urlRef.current && urlRef.current.key === current) return urlRef.current.url;
    if (pending.current && pending.current.key === current) return pending.current.promise;

    const promise = (async () => {
      setState((previous) => ({ ...previous, key: current, loading: true, error: null }));

      try {
        const blob = await sessions.getAudioFile(current);

        // 받는 사이 다른 회차로 옮겼으면 버린다.
        if (keyRef.current !== current) return null;

        revoke();
        const url = URL.createObjectURL(blob);
        urlRef.current = { key: current, url };
        setState({ key: current, url, loading: false, error: null });

        return url;
      } catch (caught) {
        if (keyRef.current !== current) return null;

        setState({
          key: current,
          url: null,
          loading: false,
          error: errorMessage(caught, "녹음 파일을 받지 못했습니다. 잠시 후 다시 시도해 주세요."),
        });

        return null;
      } finally {
        if (pending.current && pending.current.key === current) pending.current = null;
      }
    })();

    pending.current = { key: current, promise };

    return promise;
  }, []);

  return { url: state.key === key ? state.url : null, loading: state.loading, error: state.error, load };
}
