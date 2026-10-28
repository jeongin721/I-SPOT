// 상담 이력 '지금까지 상담' 의 누적 요약 재료 — 승인 완료한 최근 회차들의 상담 요약 4칸(GET /sessions/{id}/summary).
//
// AI 가 새로 만든 요약이 아니라 상담원이 확정(승인)한 문장을 모은 것이다(2026-10-28 민규 님 합의 — 화면에 출처를 밝힌다).
// 회차 목록은 사례 단위 신호 이력(useSignalHistory)의 status 로 고른다. 요청 수를 묶어 두려고 최근 MAX_APPROVED 회차만 부른다.

import { useEffect, useMemo, useState } from "react";

import { summary as summaryApi } from "../api/endpoints";
import type { SignalHistorySession, SummaryAssessment } from "../api/types";
import { errorMessage } from "./useRemote";

/** 누적 요약에 모으는 최근 승인 회차 수. */
export const MAX_APPROVED = 4;

export interface ApprovedSummary {
  sessionId: string;
  sessionNumber: number;
  consultedAt: string | null;
  assessment: SummaryAssessment | null;
}

export interface ApprovedSummariesState {
  /** 회차 번호 오름차순. */
  items: ApprovedSummary[];
  /** 승인 회차가 MAX_APPROVED 보다 많아 앞쪽을 뺐는가. */
  truncated: boolean;
  loading: boolean;
  error: string | null;
}

export function useApprovedSummaries(
  sessions: SignalHistorySession[],
  { enabled = true }: { enabled?: boolean } = {},
): ApprovedSummariesState {
  const approved = useMemo(() => sessions.filter((row) => row.status === "APPROVED"), [sessions]);
  const picked = useMemo(() => approved.slice(-MAX_APPROVED), [approved]);
  const key = enabled ? picked.map((row) => row.session_id).join(",") : "";
  const [state, setState] = useState<{ key: string; items: ApprovedSummary[]; error: string | null }>({
    key: "",
    items: [],
    error: null,
  });

  useEffect(() => {
    if (!key) return undefined;

    let alive = true;

    Promise.all(picked.map((row) => summaryApi.get(row.session_id)))
      .then((envelopes) => {
        if (!alive) return;
        setState({
          key,
          error: null,
          items: picked.map((row, index) => ({
            sessionId: row.session_id,
            sessionNumber: row.session_number,
            consultedAt: row.consulted_at,
            assessment: envelopes[index]?.summary?.assessment ?? null,
          })),
        });
      })
      .catch((caught: unknown) => {
        if (!alive) return;
        setState({ key, items: [], error: errorMessage(caught, "승인된 회차 요약을 불러오지 못했습니다.") });
      });

    return () => {
      alive = false;
    };
    // picked 는 key 와 함께 바뀐다(같은 회차 목록이면 다시 부르지 않는다).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const current = state.key === key;

  return {
    items: key && current ? state.items : [],
    truncated: approved.length > picked.length,
    loading: Boolean(key) && !current,
    error: key && current ? state.error : null,
  };
}
