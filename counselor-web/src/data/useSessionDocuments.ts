// 회차 문서(상담일지 등) 훅(GET · POST /sessions/{id}/documents, PATCH …/{document_id}, POST …/approve).
//
// 문서는 파일이 아니라 제목 · 본문 텍스트다. 항상 초안(DRAFT)으로 만들어지고, 승인하면 고칠 수 없다.
//  - 회차 상태와 상관없이 만들고 고치고 승인할 수 있다. 문서를 승인해도 회차 상태는 바뀌지 않는다
//    (요약 승인과 따로 동작한다 — API_CONTRACT 10절). 관리자 결재나 종결 심의가 아니다.
//  - 문서 하나를 따로 조회하는 API 는 없다. 목록에서 찾는다(findConsultationRecord).
//  - 사정기록지 · 종결 보고서 같은 기관 서식은 구조가 팀 결정 전이다. 지금 정해진 유형은 상담일지 하나다.

import { useCallback, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { documents as documentsApi } from "../api/endpoints";
import {
  DOC_TYPE_CONSULTATION_RECORD,
  type Document as SessionDocument,
  type DocumentStatus,
  type DocumentType,
} from "../api/types";
import { toDateTime } from "./time";
import { errorMessage, useRemote, type RemoteTicket } from "./useRemote";

export const DOC_TYPE_LABELS: Record<string, string> = {
  [DOC_TYPE_CONSULTATION_RECORD]: "상담일지",
};

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  DRAFT: "작성 중",
  APPROVED: "승인",
};

/** Backend 제한(API_CONTRACT 10절). */
export const DOCUMENT_TITLE_MAX = 200;
export const DOCUMENT_CONTENT_MAX = 50000;

export interface DocumentRow {
  id: string;
  docType: DocumentType;
  /** 정해진 유형이면 한글 이름, 아니면 서버 값 그대로. */
  docTypeLabel: string;
  title: string;
  content: string;
  status: DocumentStatus;
  statusLabel: string;
  /** 초안이라 고치고 승인할 수 있는가. */
  editable: boolean;
  createdAt: string;
  updatedAt: string;
  /** 승인 일시. 승인 전이면 빈 문자열. */
  approvedAt: string;
}

export function toDocumentRow(source: SessionDocument): DocumentRow {
  return {
    id: source.id,
    docType: source.doc_type,
    docTypeLabel: DOC_TYPE_LABELS[source.doc_type] ?? source.doc_type,
    title: source.title,
    content: source.content,
    status: source.status,
    statusLabel: DOCUMENT_STATUS_LABELS[source.status],
    editable: source.status === "DRAFT",
    createdAt: toDateTime(source.created_at),
    updatedAt: toDateTime(source.updated_at),
    approvedAt: toDateTime(source.approved_at),
  };
}

/** 가장 최근에 만든 상담일지. 없으면 null. */
export function findConsultationRecord(rows: DocumentRow[]): DocumentRow | null {
  const records = rows.filter((row) => row.docType === DOC_TYPE_CONSULTATION_RECORD);

  return records.length > 0 ? records[records.length - 1] : null;
}

/** 보내기 전에 걸러 낼 문제가 있으면 그 문장, 없으면 null. 서버가 최종으로 거절한다(422). */
export function checkDocumentInput(input: { title?: string; content?: string }): string | null {
  if (input.title !== undefined) {
    const title = input.title.trim();

    if (!title) return "제목을 입력해 주세요.";
    if (title.length > DOCUMENT_TITLE_MAX) return `제목은 ${DOCUMENT_TITLE_MAX}자까지 쓸 수 있습니다.`;
  }

  if (input.content !== undefined && input.content.length > DOCUMENT_CONTENT_MAX) {
    return `본문은 ${DOCUMENT_CONTENT_MAX.toLocaleString()}자까지 쓸 수 있습니다.`;
  }

  return null;
}

/**
 * 이 회차에 보낸 만들기가 아직 목록에 잡히지 않았는가. mark 는 만들기 요청이 안 끝났으면 null,
 * 끝났지만 응답을 목록에 넣지 못했으면 만든 문서 ID(다시 부른 목록에 그 문서가 들어오면 끝), 보낸 것이 없으면 undefined.
 */
function createPending(mark: string | null | undefined, list: SessionDocument[] | null): boolean {
  if (mark === undefined) return false;
  if (mark === null) return true;

  return !(list ?? []).some((document) => document.id === mark);
}

export interface SessionDocumentsOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface SessionDocumentsState {
  /** 만든 순서(오래된 것부터). */
  rows: DocumentRow[];
  /** 가장 최근 상담일지. 없으면 null. */
  consultationRecord: DocumentRow | null;
  /** 요청 중이거나, 이 회차에 보낸 만들기가 아직 목록에 잡히지 않았다(그동안은 저장 · 승인을 보내지 않는다). */
  submitting: boolean;
  loading: boolean;
  error: string | null;
  /**
   * 새 문서(초안). 유형을 빼면 상담일지. 성공하면 만든 문서, 실패하면 null.
   * 요청한 뒤 대상이 바뀌어(다른 회차, 갔다 돌아옴, 다시 로그인, 화면을 떠남) 반영하지 못했어도 null 이다.
   */
  create: (input: { title: string; content?: string; docType?: DocumentType }) => Promise<DocumentRow | null>;
  /** 바꿀 칸만 넘긴다. 돌려주는 값은 create 와 같다. */
  update: (documentId: string, input: { title?: string; content?: string }) => Promise<DocumentRow | null>;
  approve: (documentId: string) => Promise<DocumentRow | null>;
  reload: () => void;
  /** 지금 대상의 표(useRemote). 화면 연쇄(저장 → 승인 · 이동)는 누를 때 잡아 두고 다음 요청 · 이동 전에 isCurrent 로 확인한다. */
  capture: () => RemoteTicket | null;
  isCurrent: (ticket: RemoteTicket | null) => boolean;
}

export function useSessionDocuments(
  sessionId: string | null | undefined,
  { enabled = true }: SessionDocumentsOptions = {},
): SessionDocumentsState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<SessionDocument[]>(key, documentsApi.list, "문서를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
  const [submitting, setSubmitting] = useState(false);
  // 요청 중인가. state 는 같은 순간의 두 번째 누름을 막지 못해 ref 로도 든다.
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);
  // 회차별 만들기 상태(createPending 의 mark). 세대가 바뀌어도 지우지 않는다. 같은 회차로 돌아오거나 다시 로그인한 뒤
  // 앞 만들기가 끝나기 전이나 그 문서가 목록에 들어오기 전에 저장하면, 문서가 없는 줄 알고 하나 더 만들게 되므로.
  const creating = useRef(new Map<string, string | null>());
  // creating 을 바꿀 때마다 다시 그려 waitingCreate 를 다시 계산한다. ref 만 바꾸면 회차를 오간 뒤 늦은 만들기가
  // 실패로 끝났을 때 아무도 다시 그리지 않아 '저장 중' 잠금이 남는다.
  const [, setCreatingVersion] = useState(0);
  const markCreating = useCallback((sessionKey: string, value: string | null | undefined) => {
    if (value === undefined) creating.current.delete(sessionKey);
    else creating.current.set(sessionKey, value);
    setCreatingVersion((version) => version + 1);
  }, []);
  // 누를 때 볼 지금 목록(perform 을 만든 그리기 뒤에 다시 부른 목록이 들어왔을 수 있어서 ref 로 든다).
  const latestList = useRef(remote.data);
  latestList.current = remote.data;

  // 대상 세대가 바뀌면(다른 회차, 로그아웃 · 다시 로그인, 다른 회차에 갔다 돌아옴) 앞 대상의 오류를 지우고,
  // 앞 대상에서 보낸 요청이 아직 안 끝났어도 새 대상에서는 보낼 수 있게 한다(그 요청의 응답은 반영하지 않는다).
  // 다만 같은 회차에 보낸 만들기가 아직 목록에 잡히지 않았으면 그때까지는 보내지 않는다(waitingCreate).
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setSubmitting(false);
  }

  const waitingCreate = key !== null && createPending(creating.current.get(key), remote.data);
  const rows = useMemo(() => (remote.data ?? []).map(toDocumentRow), [remote.data]);

  /**
   * 요청 하나를 보내고 결과 문서를 목록에 반영한다. 한 번에 하나만 보낸다(같은 순간 두 번 눌러도 두 번째는 null).
   * 요청한 뒤 대상이 바뀌었으면 결과를 지금 목록에 넣지 않고 null 을 돌려준다(문서는 요청한 회차에 만들어졌다).
   * 같은 회차로 돌아와 있으면 useRemote 가 목록을 다시 부르므로 만든 문서는 그 목록으로 들어온다.
   */
  const perform = useCallback(
    async (
      send: (sessionId: string) => Promise<SessionDocument>,
      fallback: string,
      creates = false,
    ): Promise<DocumentRow | null> => {
      const ticket = remote.capture();

      // 이 함수를 만든 그리기 뒤에 대상이 바뀌었으면(앞 회차 화면에서 이어 부른 승인 등) 보내지 않는다.
      if (!ticket || ticket.key !== key || inFlight.current) return null;
      // 이 회차에 보낸 만들기가 아직 목록에 잡히지 않았다. 지금 목록만 보고 저장하면 문서를 하나 더 만든다.
      if (createPending(creating.current.get(ticket.key), latestList.current)) return null;

      inFlight.current = true;
      setSubmitting(true);
      setActionError(null);
      if (creates) markCreating(ticket.key, null);

      try {
        const result = await send(ticket.key);

        const applied = remote.setData(ticket, (current) => {
          const list = current ?? [];

          return list.some((document) => document.id === result.id)
            ? list.map((document) => (document.id === result.id ? result : document))
            : [...list, result];
        });

        if (creates) markCreating(ticket.key, applied ? undefined : result.id);

        // 반영하지 못했으면 null. 화면 연쇄(저장 → 승인)가 다음 요청을 이어 보내지 않게 한다.
        return applied ? toDocumentRow(result) : null;
      } catch (caught) {
        if (creates) markCreating(ticket.key, undefined);

        // 대상이 바뀌었으면 오류 문구도 다시 조회도 하지 않는다(새로 부른 목록을 건드리지 않게).
        if (!remote.isCurrent(ticket)) return null;

        if (!(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, fallback));
        }

        // 다른 창에서 승인됐을 수 있다(409 ALREADY_APPROVED). 최신 목록을 다시 받는다.
        remote.refresh();

        return null;
      } finally {
        // 대상 세대가 바뀌었으면 그때 이미 풀었다. 새 대상에서 보낸 요청의 표시를 끄지 않는다.
        if (remote.sameGeneration(ticket)) {
          inFlight.current = false;
          setSubmitting(false);
        }
      }
    },
    [key, markCreating, remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.refresh],
  );

  const create = useCallback(
    (input: { title: string; content?: string; docType?: DocumentType }) => {
      const problem = checkDocumentInput(input);

      if (problem) {
        setActionError(problem);
        return Promise.resolve(null);
      }

      return perform(
        (id) =>
          documentsApi.create(id, {
            title: input.title.trim(),
            content: input.content,
            doc_type: input.docType ?? DOC_TYPE_CONSULTATION_RECORD,
          }),
        "문서를 만들지 못했습니다. 잠시 후 다시 시도해 주세요.",
        true,
      );
    },
    [perform],
  );

  const update = useCallback(
    (documentId: string, input: { title?: string; content?: string }) => {
      const problem =
        input.title === undefined && input.content === undefined ? "바꿀 내용이 없습니다." : checkDocumentInput(input);

      if (problem) {
        setActionError(problem);
        return Promise.resolve(null);
      }

      const payload = input.title === undefined ? input : { ...input, title: input.title.trim() };

      return perform(
        (id) => documentsApi.update(id, documentId, payload),
        "문서를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    },
    [perform],
  );

  const approve = useCallback(
    (documentId: string) =>
      perform((id) => documentsApi.approve(id, documentId), "문서를 승인하지 못했습니다. 잠시 후 다시 시도해 주세요."),
    [perform],
  );

  return {
    rows,
    consultationRecord: findConsultationRecord(rows),
    submitting: submitting || waitingCreate,
    loading: remote.loading,
    error: actionError ?? remote.error,
    create,
    update,
    approve,
    reload: remote.reload,
    capture: remote.capture,
    isCurrent: remote.isCurrent,
  };
}
