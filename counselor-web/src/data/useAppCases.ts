// 상담사 앱(폰)의 아이 고르기 목록: 내 진행 중 사례(GET /cases?status=ACTIVE&with_child_name=true).
// 불러오지 못하면(연결 없음) 이 폰에 기억해 둔 마지막 목록을 쓴다(appOffline.ts). 그래서 연결 없이도 녹음할 아이를 고를 수 있다.

import { useEffect, useState } from "react";

import { cases } from "../api/endpoints";
import { cachedCases, rememberCases, type CachedCase } from "./appOffline";

export interface AppCasesState {
  rows: CachedCase[];
  loading: boolean;
  /** 서버 대신 기억해 둔 목록을 보이는 중. */
  offline: boolean;
  error: string | null;
}

export function childLabelOf(row: CachedCase): string {
  return row.child_name || row.child_alias;
}

export function useAppCases(userId: string | null): AppCasesState {
  const [state, setState] = useState<AppCasesState>({ rows: [], loading: true, offline: false, error: null });

  useEffect(() => {
    if (!userId) return undefined;

    let live = true;
    const saved = cachedCases(userId);

    // 기억해 둔 목록을 먼저 보인다(연결이 느려도 바로 고를 수 있게). 서버 값이 오면 바꾼다.
    if (saved) setState({ rows: saved, loading: false, offline: false, error: null });

    cases
      .list({ status: "ACTIVE", with_child_name: true, page_size: 100 })
      .then((page) => {
        if (!live) return;
        rememberCases(userId, page.items);
        setState({ rows: page.items, loading: false, offline: false, error: null });
      })
      .catch(() => {
        if (!live) return;
        setState(
          saved
            ? { rows: saved, loading: false, offline: true, error: null }
            : { rows: [], loading: false, offline: true, error: "사례 목록을 불러오지 못했어요. 연결을 확인해 주세요." },
        );
      });

    return () => {
      live = false;
    };
  }, [userId]);

  return state;
}
