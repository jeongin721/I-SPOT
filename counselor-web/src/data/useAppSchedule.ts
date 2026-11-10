// 상담사 앱(폰)의 일정 읽기 · 쓰기(GET · POST · PATCH · DELETE /schedule, 웹 일정과 같은 서버 값).
// 홈(이번 주 · 오늘 상담 수) · 사례 목록(다음 상담) · 일정 화면 · 알림('오늘 남은 상담')이 같이 쓴다.

import { useCallback, useEffect, useState } from "react";

import { schedule } from "../api/endpoints";
import type { ScheduleEvent } from "../api/types";
import { errorMessage } from "./useRemote";

/** 이 폰 시각 기준 YYYY-MM-DD. */
export function ymd(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function parseYmd(text: string): Date {
  const [y, m, d] = text.split("-").map(Number);

  return new Date(y, m - 1, d);
}

export function addDays(date: Date, days: number): Date {
  const next = new Date(date);

  next.setDate(date.getDate() + days);

  return next;
}

/** 그 날이 든 주의 월요일. */
export function mondayOf(date: Date): Date {
  const day = (date.getDay() + 6) % 7;

  return addDays(new Date(date.getFullYear(), date.getMonth(), date.getDate()), -day);
}

/** 날짜 · 시간 순(종일은 그날 맨 앞). */
export function byWhen(a: ScheduleEvent, b: ScheduleEvent): number {
  return a.date.localeCompare(b.date) || (a.time ?? "").localeCompare(b.time ?? "");
}

export interface AppScheduleState {
  items: ScheduleEvent[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** from ~ to(YYYY-MM-DD, 둘 다 포함) 일정. enabled 가 false 면 부르지 않는다. */
export function useAppSchedule(enabled: boolean, from: string, to: string): AppScheduleState {
  const [state, setState] = useState<{ key: string; items: ScheduleEvent[]; loading: boolean; error: string | null }>({
    key: "",
    items: [],
    loading: true,
    error: null,
  });
  const [tick, setTick] = useState(0);
  const key = `${from}~${to}`;

  useEffect(() => {
    if (!enabled) return undefined;

    let live = true;

    setState((prev) => ({ ...prev, loading: true, error: null }));
    schedule
      .list({ from, to })
      .then((page) => live && setState({ key, items: [...page.items].sort(byWhen), loading: false, error: null }))
      .catch((caught) => live && setState({ key, items: [], loading: false, error: errorMessage(caught, "일정을 불러오지 못했어요.") }));

    return () => {
      live = false;
    };
  }, [enabled, from, to, key, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);

  return { items: state.key === key ? state.items : [], loading: state.loading, error: state.error, reload };
}
