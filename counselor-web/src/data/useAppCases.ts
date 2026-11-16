// 상담사 앱(폰)의 아이 고르기 목록: 내 진행 중 사례(GET /cases?status=ACTIVE&with_child_name=true).
// 불러오지 못하면(연결 없음) 이 폰에 기억해 둔 마지막 목록을 쓴다(appOffline.ts). 그래서 연결 없이도 녹음할 아이를 고를 수 있다.

import { useEffect, useState } from "react";

import { cases } from "../api/endpoints";
import type { CaseListItem } from "../api/types";
import { cachedCases, rememberCases, type CachedCase } from "./appOffline";

/** 서버에서 받았으면 사례 목록 줄 전체, 연결이 없어 기억한 목록이면 ID · 이름 · 별칭만. */
export type AppCaseRow = CachedCase & Partial<CaseListItem>;

export interface AppCasesState {
  rows: AppCaseRow[];
  loading: boolean;
  /** 서버 대신 기억해 둔 목록을 보이는 중. */
  offline: boolean;
  error: string | null;
}

export function childLabelOf(row: AppCaseRow): string {
  return row.child_name || row.child_alias;
}

// 같은 화면에서 여러 곳(머리의 '담당 N명' · 본문)이 함께 불러도 서버에는 한 번만 묻는다(실명 목록 열람 기록이 겹치지 않게).
let inflight: { at: number; promise: ReturnType<typeof cases.list> } | null = null;

function loadCases(): ReturnType<typeof cases.list> {
  if (inflight && Date.now() - inflight.at < 5000) return inflight.promise;

  const promise = cases.list({ status: "ACTIVE", with_child_name: true, page_size: 100 });

  inflight = { at: Date.now(), promise };
  promise.catch(() => {
    inflight = null;
  });

  return promise;
}

export function useAppCases(userId: string | null): AppCasesState {
  const [state, setState] = useState<AppCasesState>({ rows: [], loading: true, offline: false, error: null });

  useEffect(() => {
    if (!userId) return undefined;

    let live = true;
    const saved = cachedCases(userId);

    // 기억해 둔 목록을 먼저 보인다(연결이 느려도 바로 고를 수 있게). 서버 값이 오면 바꾼다.
    if (saved) setState({ rows: saved, loading: false, offline: false, error: null });

    loadCases()
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
