// 사례 문서함 훅. 사례의 회차마다 회차 상세(음성 · 원문 상태) + 문서 목록(GET /sessions/{id}/documents)을 불러 모은다.
//
// 사례 단위 문서 API 는 없어서(specs 대응표 CaseDocs 줄 '보완: 사례의 회차들을 조회해 문서함 구성') 회차 목록은
// useCaseDetail 에서 받아 넘긴다. 회차가 많으면 요청이 회차 수 × 2~3 개라 한 번에 DOCS_CONCURRENCY 회차씩 부른다.
// 회차 목록이 바뀌면(새 회차 · 상태 변경) 다시 부른다.
//
// Backend 에 없는 것(화면이 준비 중으로 둔다): 기관 서식 6종의 작성 기록, 상담 전 브리핑, 외부 파일(PDF · HWPX) 올리기 · 열기.

import { useMemo, useRef } from "react";

import { documents as documentsApi } from "../api/endpoints";
import type { SessionRow } from "./sessionRows";
import { toDocumentRow, type DocumentRow } from "./useSessionDocuments";
import { loadSessionDetail, type SessionDetailView } from "./useSessionDetail";
import { useRemote } from "./useRemote";

/** 한 번에 함께 부르는 회차 수. */
export const DOCS_CONCURRENCY = 4;

export interface SessionDocs {
  session: SessionDetailView;
  /** 만든 순서(오래된 것부터). */
  documents: DocumentRow[];
}

export interface CaseDocumentsState {
  /** 최신 회차부터(회차 목록과 같은 순서). */
  items: SessionDocs[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** items 를 limit 개씩 나눠 차례로 부른다. 결과 순서는 items 와 같다. */
async function mapLimited<T, R>(items: T[], limit: number, run: (item: T) => Promise<R>): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;

  async function worker() {
    while (next < items.length) {
      const index = next++;
      results[index] = await run(items[index]);
    }
  }

  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));

  return results;
}

async function loadSessionDocs(sessionId: string): Promise<SessionDocs> {
  const [session, list] = await Promise.all([loadSessionDetail(sessionId), documentsApi.list(sessionId)]);

  return { session, documents: list.map(toDocumentRow) };
}

/**
 * @param caseId   사례 ID. 회차 목록(sessions)이 이 사례의 것일 때만 부른다.
 * @param sessions useCaseDetail 의 회차 줄(최신부터). 아직 못 받았으면 null.
 */
export function useCaseDocuments(
  caseId: string | null | undefined,
  sessions: SessionRow[] | null,
  { enabled = true }: { enabled?: boolean } = {},
): CaseDocumentsState {
  // 회차 ID 와 상태가 바뀔 때만 다시 부른다(사례 상세가 처리 중 회차를 되풀이 조회해도 상태가 같으면 그대로).
  const signature = useMemo(
    () => (sessions ? sessions.map((row) => `${row.id}:${row.status}`).join(",") : null),
    [sessions],
  );
  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;

  const ready = enabled && caseId && signature !== null && (sessions ?? []).every((row) => row.caseId === caseId);
  const remote = useRemote<SessionDocs[]>(
    ready ? `${caseId}|${signature}` : null,
    () => mapLimited((sessionsRef.current ?? []).map((row) => row.id), DOCS_CONCURRENCY, loadSessionDocs),
    "문서함을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    (change, _key, data) => Boolean(data?.some((item) => item.session.id === change.sessionId)),
  );

  return { items: remote.data ?? [], loading: remote.loading, error: remote.error, reload: remote.reload };
}
