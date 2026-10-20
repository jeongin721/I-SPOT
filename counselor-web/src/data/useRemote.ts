// 서버 값 하나를 불러와 들고 있는 공용 훅. 회차 · 전사 · 분석 · 요약 · 문서 훅이 이 위에 얹힌다.
//
//  - key 가 바뀌면(다른 회차) 바뀐 첫 그리기부터 앞 값을 보이지 않고 새로 부른다. 늦게 온 앞 회차 응답은 버린다.
//  - key 가 null 이 되면(로그아웃 · 로그인 확인 중 · 다른 계정으로 바뀌는 중) 들고 있던 값 · 오류를 버린다.
//    다른 계정으로 같은 key(같은 사례 ID)에 돌아왔을 때 앞 계정이 불러온 값을 다시 보이지 않게 하려고서다.
//  - reload()  는 '불러오는 중' 을 보이며 다시 부른다(사용자가 누른 새로고침).
//  - refresh() 는 값을 그대로 둔 채 조용히 다시 부른다(처리 중 상태를 되풀이 조회할 때).
//  - setData(표, …) 로 수정 · 승인 응답을 바로 반영한다(다시 부르지 않아도 되게). 요청을 보내는 쪽은 보낼 때 capture() 로
//    표(key · 대상 세대 · 로그인 토큰)를 잡아 두고 응답이 오면 그 표로 반영한다. 그사이 대상이 바뀌었으면(A 회차에서 저장을
//    누르고 B 회차로 옮김, B 에 갔다 A 로 돌아옴, 다른 탭에서 다시 로그인함, 화면을 떠남) 반영하지 않는다.
//    응답 뒤 다른 상태(고친 칸 · 오류 문구)를 바꾸거나 다음 요청을 보낼 때도 isCurrent(표) 로 먼저 확인한다.
//    key 만 비교하면 같은 key 로 돌아온 경우(A → B → A, 로그아웃 · 다시 로그인)를 가리지 못한다.
//    반영하지 못했어도 화면이 아직 같은 key 를 보고 있으면(갔다 돌아옴, 다시 로그인) 조용히 다시 부른다.
//    쓰기는 서버에 반영됐는데 돌아와서 받은 값이 그 전 값일 수 있어서다.
//  - 같은 탭의 다른 훅이 회차 상태를 바꾸면(sessionEvents) 조용히 다시 부른다.
//
// 처리 중(원문 변환 · AI 분석) 되풀이 조회는 usePolling 으로 한다(API_CONTRACT 1.4, 권장 2~3초).

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, getToken } from "../api/client";
import { onSessionChanged, type SessionChange } from "./sessionEvents";

/** 처리 중 상태를 다시 조회하는 간격. API_CONTRACT 1.4 권장(2~3초). */
export const POLL_INTERVAL_MS = 2500;

/** 쓰기 요청을 보낼 때 잡아 두는 표(capture). 응답이 오면 이 표가 아직 지금 대상의 것인지(isCurrent) 보고 반영한다. */
export interface RemoteTicket {
  readonly key: string;
  /** 대상 세대. key 가 바뀔 때마다(null 포함) 1 씩 는다. */
  readonly generation: number;
  /** 보낼 때의 로그인 토큰. client 가 요청에 싣는 토큰과 같다. */
  readonly token: string | null;
}

export interface RemoteState<T> {
  data: T | null;
  /** 처음 불러오는 중이거나 reload() 로 다시 불러오는 중. refresh() 중에는 false 다. */
  loading: boolean;
  error: string | null;
  /** 조회 · 반영이 끝난 횟수. usePolling 의 version 으로 넘긴다. */
  settled: number;
  reload: () => void;
  refresh: () => void;
  /** 대상 세대(RemoteTicket.generation). 쓰기 훅은 이 값이 바뀐 그리기에서 앞 대상 요청의 진행 표시 · 오류를 푼다. */
  generation: number;
  /** 지금 대상의 표. 대상이 없거나(key 가 null) 화면을 떠났으면 null. */
  capture: () => RemoteTicket | null;
  /**
   * 표가 지금 대상이면 값을 반영하고 true. 대상이 바뀌었으면 반영하지 않고 false(값 · 오류 · settled 그대로).
   * 이때 화면이 아직 같은 key 를 보고 있으면(갔다 돌아옴, 다시 로그인) refresh() 로 조용히 다시 부른다
   * (쓰기는 서버에 반영됐는데 돌아와서 받은 값은 그 전 값일 수 있다. 다시 부르는 조회는 지금 로그인 토큰으로 나간다).
   * 값 대신 함수를 넘기면 지금 들고 있는 값으로 새 값을 만든다(요청을 보낼 때 읽은 값이 그사이 바뀌었을 수 있어서).
   */
  setData: (ticket: RemoteTicket, value: T | ((current: T | null) => T)) => boolean;
  /**
   * 화면이 아직 표의 key 를 보고 있으면(표가 지금 것이든, 갔다 돌아왔든, 다시 로그인했든) refresh() 로 조용히 다시 부른다.
   * 다른 key 이거나 화면을 떠났으면 아무것도 하지 않는다. 쓰기 응답을 값에 합치지 못할 때(setData 가 false, 또는 합칠 값이 아직 없음)
   * 서버에 반영된 값을 받아 오는 데 쓴다. 다시 부르는 조회는 지금 로그인 토큰으로 나가고, 옛 응답 본문은 쓰지 않는다.
   */
  resync: (ticket: RemoteTicket) => void;
  /** 표가 아직 지금 대상의 것인가(화면에 붙어 있고 key · 세대 · 로그인 토큰이 모두 같다). null 이면 false. */
  isCurrent: (ticket: RemoteTicket | null) => boolean;
  /**
   * 표를 잡은 뒤 세대가 그대로인가(로그인 토큰은 보지 않는다). 요청이 끝났을 때 진행 표시를 풀지 정하는 데 쓴다 —
   * 세대가 바뀌었으면 그때 이미 풀었고, 토큰만 바뀌었으면 이 요청이 풀어야 한다.
   */
  sameGeneration: (ticket: RemoteTicket) => boolean;
}

/** 오류를 화면에 보여 줄 문장으로. Backend 문구가 있으면 그대로, 없으면 fallback. */
export function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

/**
 * @param key   무엇을 부르는지(예: 회차 ID). null 이면 부르지 않는다(로그인 확인 전 등).
 * @param load  key 로 값을 불러오는 함수.
 * @param fallback 서버 문구가 없을 때 보여 줄 오류 문장.
 * @param affects 회차 변경 알림(sessionEvents)이 이 값과 관계있는지. 있으면 조용히 다시 부른다.
 *                기본은 '알림의 회차 ID 가 key 와 같음' 이다(key 가 회차 ID 인 훅).
 */
export function useRemote<T>(
  key: string | null,
  load: (key: string) => Promise<T>,
  fallback: string,
  affects: (change: SessionChange, key: string, data: T | null) => boolean = (change, current) =>
    change.sessionId === current,
): RemoteState<T> {
  // 값 · 오류는 어느 key 의 것인지와 함께 든다. key 가 바뀐 첫 그리기부터 앞 대상의 값 · 오류를 보이지 않게 하려고서다
  // (비우는 일을 effect 에서 하면 바뀐 key 로 한 번은 앞 대상의 값이 그려진다).
  const [entry, setEntry] = useState<{ key: string | null; data: T | null }>({ key, data: null });
  const [failure, setFailure] = useState<{ key: string | null; message: string | null }>({ key, message: null });
  const [loading, setLoading] = useState(key !== null);
  const [tick, setTick] = useState(0);
  const [settled, setSettled] = useState(0);
  // 이번 조회가 조용한 refresh 인가. 조회를 시작할 때 읽고 되돌린다.
  const silent = useRef(false);
  // 다시 부르기를 예약했고 아직 조회를 시작하지 않았는가. 그사이 refresh 가 또 불리면(쓰기 응답을 버린 setData 와
  // 회차 변경 알림이 함께 부름) 한 번만 부른다. 두 번 예약되면 앞 조회가 silent 를 써 버려 뒤 조회가
  // '불러오는 중' 을 보이며 오류 문구를 지운다.
  const queued = useRef(false);
  // 최근 조회 번호. 늦게 온 앞 조회의 응답을 버리는 데 쓴다.
  const latest = useRef(0);
  // load 가 그릴 때마다 새 함수여도 다시 부르지 않게 마지막 것만 들고 있는다.
  const loadRef = useRef(load);
  loadRef.current = load;
  // 지금 대상. 요청을 보낸 뒤 대상이 바뀌었는지 setData · isCurrent 가 본다.
  const keyRef = useRef(key);
  keyRef.current = key;
  // 대상 세대. key 가 바뀔 때마다(null 포함) 1 씩 늘린다. 그래서 같은 key 로 돌아와도(A → B → A, 로그아웃 · 다시 로그인)
  // 세대는 다르다. 그리는 중에 앞 그리기의 key 와 비교하므로 같은 key 로 두 번 그려도(StrictMode) 한 번만 는다.
  // reload · refresh · 되풀이 조회에는 올리지 않는다(올리면 처리 중 조회 사이에 저장한 결과를 버리게 된다).
  const generation = useRef(0);
  const generationKey = useRef(key);

  if (generationKey.current !== key) {
    generationKey.current = key;
    generation.current += 1;
  }
  // 화면에 붙어 있는가. 떠난 뒤에는 isCurrent 가 false 다(떠난 화면의 요청 결과를 돌려주지 않게).
  const mounted = useRef(false);

  const data = entry.key === key ? entry.data : null;
  const error = failure.key === key ? failure.message : null;

  const reload = useCallback(() => {
    queued.current = true;
    silent.current = false;
    setTick((value) => value + 1);
  }, []);

  const refresh = useCallback(() => {
    // 이미 예약한 조회(refresh · reload)가 있으면 그 조회가 부른다.
    if (queued.current) return;

    queued.current = true;
    silent.current = true;
    setTick((value) => value + 1);
  }, []);

  useEffect(() => {
    const quiet = silent.current;

    silent.current = false;
    queued.current = false;

    if (key === null) {
      latest.current += 1;
      setEntry({ key: null, data: null });
      setFailure({ key: null, message: null });
      setLoading(false);
      return;
    }

    const requestId = ++latest.current;

    if (!quiet) {
      setLoading(true);
      setFailure({ key, message: null });
    }

    loadRef
      .current(key)
      .then((value) => {
        if (requestId !== latest.current) return;

        setEntry({ key, data: value });
        setFailure({ key, message: null });
        setLoading(false);
        setSettled((count) => count + 1);
      })
      .catch((caught) => {
        if (requestId !== latest.current) return;

        // 조용한 refresh 가 실패하면 들고 있던 값은 두고 오류만 알린다.
        if (!quiet) setEntry({ key, data: null });
        setFailure({ key, message: errorMessage(caught, fallback) });
        setLoading(false);
        setSettled((count) => count + 1);
      });
  }, [key, tick, fallback]);

  // 같은 탭의 다른 훅이 이 대상의 회차 상태를 바꿨으면 조용히 다시 부른다(sessionEvents).
  const affectsRef = useRef(affects);
  affectsRef.current = affects;
  const dataRef = useRef(data);
  dataRef.current = data;

  useEffect(() => {
    if (key === null) return;

    return onSessionChanged((change) => {
      if (affectsRef.current(change, key, dataRef.current)) refresh();
    });
  }, [key, refresh]);

  // 화면을 떠나면 늦게 온 응답을 버리고, 보낸 요청의 결과도 지금 대상이 아닌 것으로 본다.
  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
      latest.current += 1;
    };
  }, []);

  const capture = useCallback((): RemoteTicket | null => {
    const current = keyRef.current;

    if (!mounted.current || current === null) return null;

    return { key: current, generation: generation.current, token: getToken() };
  }, []);

  // 로그인 토큰은 client 가 늦은 401 을 가리는 기준(보낼 때 토큰 = 지금 토큰)과 같게 본다.
  const isCurrent = useCallback(
    (ticket: RemoteTicket | null) =>
      ticket !== null &&
      mounted.current &&
      keyRef.current === ticket.key &&
      generation.current === ticket.generation &&
      getToken() === ticket.token,
    [],
  );

  const sameGeneration = useCallback((ticket: RemoteTicket) => generation.current === ticket.generation, []);

  const resync = useCallback(
    (ticket: RemoteTicket) => {
      if (mounted.current && keyRef.current === ticket.key) refresh();
    },
    [refresh],
  );

  const setData = useCallback(
    (ticket: RemoteTicket, value: T | ((current: T | null) => T)) => {
      // 요청을 보낸 뒤 대상이 바뀌었으면 앞 대상의 응답은 버린다(지금 대상의 값 · 오류 · settled 는 그대로).
      if (!isCurrent(ticket)) {
        // 같은 key 로 돌아왔으면 돌아와서 받은 값이 이 쓰기 전 값일 수 있다. 서버 값을 다시 받는다.
        resync(ticket);

        return false;
      }

      const forKey = ticket.key;

      // 진행 중인 조회가 있으면 그 응답이 방금 반영한 값을 덮지 않게 버린다.
      latest.current += 1;
      setEntry((current) => {
        const held = current.key === forKey ? current.data : null;

        return { key: forKey, data: typeof value === "function" ? (value as (current: T | null) => T)(held) : value };
      });
      setFailure({ key: forKey, message: null });
      setLoading(false);
      setSettled((count) => count + 1);

      return true;
    },
    [isCurrent, resync],
  );

  const waitingFirst = key !== null && data === null && error === null;

  return {
    data,
    loading: loading || waitingFirst,
    error,
    settled,
    reload,
    refresh,
    generation: generation.current,
    capture,
    setData,
    resync,
    isCurrent,
    sameGeneration,
  };
}

/**
 * active 인 동안 POLL_INTERVAL_MS 마다 refresh 를 부른다.
 * version 에는 RemoteState.settled 를 넘긴다. 조회가 끝날 때마다(실패해도) 다음 조회를 예약한다 —
 * 잠깐 연결이 끊겨 한 번 실패해도 되풀이 조회가 멈추지 않게.
 */
export function usePolling(active: boolean, refresh: () => void, version: unknown): void {
  useEffect(() => {
    if (!active) return;

    const timer = window.setTimeout(refresh, POLL_INTERVAL_MS);

    return () => window.clearTimeout(timer);
  }, [active, refresh, version]);
}
