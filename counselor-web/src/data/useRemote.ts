// 서버 값 하나를 불러와 들고 있는 공용 훅. 회차 · 전사 · 분석 · 요약 · 문서 훅이 이 위에 얹힌다.
//
//  - key 가 바뀌면(다른 회차) 앞 값을 바로 비우고 새로 부른다. 늦게 온 앞 회차 응답은 버린다.
//  - reload()  는 '불러오는 중' 을 보이며 다시 부른다(사용자가 누른 새로고침).
//  - refresh() 는 값을 그대로 둔 채 조용히 다시 부른다(처리 중 상태를 되풀이 조회할 때).
//  - setData() 로 수정 · 승인 응답을 바로 반영한다(다시 부르지 않아도 되게).
//  - 같은 탭의 다른 훅이 회차 상태를 바꾸면(sessionEvents) 조용히 다시 부른다.
//
// 처리 중(원문 변환 · AI 분석) 되풀이 조회는 usePolling 으로 한다(API_CONTRACT 1.4, 권장 2~3초).

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { onSessionChanged, type SessionChange } from "./sessionEvents";

/** 처리 중 상태를 다시 조회하는 간격. API_CONTRACT 1.4 권장(2~3초). */
export const POLL_INTERVAL_MS = 2500;

export interface RemoteState<T> {
  data: T | null;
  /** 처음 불러오는 중이거나 reload() 로 다시 불러오는 중. refresh() 중에는 false 다. */
  loading: boolean;
  error: string | null;
  /** 조회 · 반영이 끝난 횟수. usePolling 의 version 으로 넘긴다. */
  settled: number;
  reload: () => void;
  refresh: () => void;
  setData: (value: T) => void;
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
  const [data, setDataState] = useState<T | null>(null);
  const [loading, setLoading] = useState(key !== null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [settled, setSettled] = useState(0);
  // 이번 조회가 조용한 refresh 인가. 조회를 시작할 때 읽고 되돌린다.
  const silent = useRef(false);
  // 최근 조회 번호. 늦게 온 앞 조회의 응답을 버리는 데 쓴다.
  const latest = useRef(0);
  // load 가 그릴 때마다 새 함수여도 다시 부르지 않게 마지막 것만 들고 있는다.
  const loadRef = useRef(load);
  loadRef.current = load;

  const reload = useCallback(() => {
    silent.current = false;
    setTick((value) => value + 1);
  }, []);

  const refresh = useCallback(() => {
    silent.current = true;
    setTick((value) => value + 1);
  }, []);

  // 다른 대상으로 바뀌면 앞 값을 먼저 비운다(잠깐이라도 다른 회차의 내용이 보이지 않게).
  useEffect(() => {
    setDataState(null);
    setError(null);
  }, [key]);

  useEffect(() => {
    const quiet = silent.current;

    silent.current = false;

    if (key === null) {
      latest.current += 1;
      setLoading(false);
      return;
    }

    const requestId = ++latest.current;

    if (!quiet) {
      setLoading(true);
      setError(null);
    }

    loadRef
      .current(key)
      .then((value) => {
        if (requestId !== latest.current) return;

        setDataState(value);
        setError(null);
        setLoading(false);
        setSettled((count) => count + 1);
      })
      .catch((caught) => {
        if (requestId !== latest.current) return;

        // 조용한 refresh 가 실패하면 들고 있던 값은 두고 오류만 알린다.
        if (!quiet) setDataState(null);
        setError(errorMessage(caught, fallback));
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

  // 화면을 떠나면 늦게 온 응답을 버린다.
  useEffect(
    () => () => {
      latest.current += 1;
    },
    [],
  );

  const setData = useCallback((value: T) => {
    // 진행 중인 조회가 있으면 그 응답이 방금 반영한 값을 덮지 않게 버린다.
    latest.current += 1;
    setDataState(value);
    setError(null);
    setLoading(false);
    setSettled((count) => count + 1);
  }, []);

  const waitingFirst = key !== null && data === null && error === null;

  return { data, loading: loading || waitingFirst, error, settled, reload, refresh, setData };
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
