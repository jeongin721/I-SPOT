// 회차 문서(상담일지 등) 훅(GET · POST /sessions/{id}/documents, PATCH …/{document_id}, POST …/approve · …/reopen).
//
// 문서는 파일이 아니라 제목 · 본문 텍스트다. 항상 초안(DRAFT)으로 만들어지고, 승인하면 reopen() 으로 승인을 풀어야
// 고칠 수 있다(내용은 그대로 초안으로 돌아간다. 고친 뒤 다시 승인한다).
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
import { errorMessage, useRemote } from "./useRemote";

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

export interface SessionDocumentsOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface SessionDocumentsState {
  /** 만든 순서(오래된 것부터). */
  rows: DocumentRow[];
  /** 가장 최근 상담일지. 없으면 null. */
  consultationRecord: DocumentRow | null;
  submitting: boolean;
  loading: boolean;
  error: string | null;
  /** 새 문서(초안). 유형을 빼면 상담일지. 성공하면 만든 문서, 실패하면 null. */
  create: (input: { title: string; content?: string; docType?: DocumentType }) => Promise<DocumentRow | null>;
  /** 바꿀 칸만 넘긴다. */
  update: (documentId: string, input: { title?: string; content?: string }) => Promise<DocumentRow | null>;
  approve: (documentId: string) => Promise<DocumentRow | null>;
  /** 승인을 풀어 다시 고칠 수 있게 한다. 내용은 그대로 둔다. */
  reopen: (documentId: string) => Promise<DocumentRow | null>;
  reload: () => void;
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
  const [errorKey, setErrorKey] = useState(key);

  if (errorKey !== key) {
    setErrorKey(key);
    setActionError(null);
  }

  const rows = useMemo(() => (remote.data ?? []).map(toDocumentRow), [remote.data]);

  /**
   * 요청 하나를 보내고 결과 문서를 목록에 반영한다. 한 번에 하나만 보낸다(같은 순간 두 번 눌러도 두 번째는 null).
   * 요청한 뒤 다른 회차로 옮겼으면 결과를 지금 회차의 목록에 넣지 않는다(문서는 요청한 회차에 만들어졌다).
   */
  const perform = useCallback(
    async (send: (sessionId: string) => Promise<SessionDocument>, fallback: string): Promise<DocumentRow | null> => {
      if (!key || inFlight.current) return null;

      const forKey = key;

      inFlight.current = true;
      setSubmitting(true);
      setActionError(null);

      try {
        const result = await send(forKey);

        remote.setData(forKey, (current) => {
          const list = current ?? [];

          return list.some((document) => document.id === result.id)
            ? list.map((document) => (document.id === result.id ? result : document))
            : [...list, result];
        });

        return toDocumentRow(result);
      } catch (caught) {
        if (remote.isCurrent(forKey) && !(caught instanceof ApiError && caught.isUnauthorized)) {
          setActionError(errorMessage(caught, fallback));
        }

        // 다른 창에서 승인됐을 수 있다(409 ALREADY_APPROVED). 최신 목록을 다시 받는다.
        remote.refresh();

        return null;
      } finally {
        inFlight.current = false;
        setSubmitting(false);
      }
    },
    [key, remote.setData, remote.isCurrent, remote.refresh],
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

  const reopen = useCallback(
    (documentId: string) =>
      perform((id) => documentsApi.reopen(id, documentId), "문서를 수정 상태로 바꾸지 못했습니다. 잠시 후 다시 시도해 주세요."),
    [perform],
  );

  return {
    rows,
    consultationRecord: findConsultationRecord(rows),
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    create,
    update,
    approve,
    reopen,
    reload: remote.reload,
  };
}
