// 문서(상담일지) 화면이 쓰는 변환. (갈래 B)
//
// DocumentWritePage 와 CaseDetailPage 의 "문서" 탭이 쓴다.
// Backend 문서는 파일이 아니라 제목 · 본문 텍스트다(POST /sessions/{id}/documents).
// 상담일지 초안은 상담사가 검수하는 요약(GET /sessions/{id}/summary)에서 만들고,
// Backend 에 없는 항목(상담형태, 아동 상태 등)은 빈 칸으로 두어 상담사가 채운다.

import { SPEAKER_LABELS, toTimestamp, pad2, parseBackendTime } from "./adapters";
import { DOC_TYPE_CONSULTATION_RECORD } from "./types";
import type {
  Document,
  DocumentStatus,
  DocumentType,
  Session,
  Summary,
  SummaryEvidenceItem,
  Transcript,
} from "./types";

/** 본문 최대 길이. Backend DocumentCreateRequest · DocumentUpdateRequest 의 content max_length 와 같다. */
export const DOCUMENT_CONTENT_MAX = 50000;

// =========================================================
// 시각
// =========================================================
//
// adapters.ts 의 시각 변환(parseBackendTime)은 밖으로 내보내지 않아 같은 규칙을 여기에 둔다.
// Backend 는 UTC 로 저장하고 시간대 표시 없이 주므로, 표시가 없으면 UTC 로 읽는다.

/** 사용자 시간대의 "YYYY-MM-DD HH:MM". 값이 없으면 빈 문자열. */
export function toLocalDateTime(iso: string | null): string {
  if (!iso) return "";

  const at = parseBackendTime(iso);

  if (!at) return iso.slice(0, 16).replace("T", " ");

  return `${at.getFullYear()}-${pad2(at.getMonth() + 1)}-${pad2(at.getDate())} ${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
}

// =========================================================
// 문서 유형 · 상태
// =========================================================

/** 문서 유형 → 화면 이름. Backend 는 유형을 자유 문자열로 받으므로 모르는 유형은 코드를 그대로 보여 준다. */
const DOC_TYPE_LABELS: Record<string, string> = {
  [DOC_TYPE_CONSULTATION_RECORD]: "상담일지",
};

export function toDocTypeLabel(docType: DocumentType): string {
  return DOC_TYPE_LABELS[docType] ?? docType;
}

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  DRAFT: "임시저장",
  APPROVED: "승인 완료",
};

/** 문서가 아직 없는 회기의 상태 문구. */
export const DOCUMENT_NOT_WRITTEN = "미작성";

/** 새 상담일지의 제목. Backend 는 제목을 1~200자로 받는다. */
export function defaultRecordTitle(sessionNumber: number): string {
  return `상담일지 ${sessionNumber}회차`;
}

/**
 * 회기의 문서 목록에서 상담일지를 고른다.
 * 목록은 만든 순서(created_at 오름차순)로 오므로, 여러 개면 가장 나중에 만든 것을 쓴다.
 */
export function pickConsultationRecord(docs: Document[]): Document | null {
  const records = docs.filter((doc) => doc.doc_type === DOC_TYPE_CONSULTATION_RECORD);

  return records.length > 0 ? records[records.length - 1] : null;
}

// =========================================================
// 상담일지 초안
// =========================================================

/**
 * 요약으로 상담일지 초안 본문을 만든다. 요약이 없으면 빈 문자열(화면이 안내를 보여 준다).
 *
 * 요약 본문 · 항목 · 상담사 메모만 옮기고, Backend 에 없는 항목은 제목만 두고 비워 둔다.
 * 상담일시는 상담 일시(consulted_at)가 있을 때만 적는다 — 등록 시각은 상담 시각이 아니다.
 */
export function buildConsultationDraft(summary: Summary | null, session: Session | null): string {
  if (!summary) return "";

  const heading = summary.status === "APPROVED"
    ? "[상담 일지 - 승인된 요약 기반 초안]"
    : "[상담 일지 - AI 생성 초안]";
  const lines: string[] = [
    heading,
    "",
    `상담일시: ${toLocalDateTime(session?.consulted_at ?? null)}`,
    "상담형태: ",
    `상담 장소: ${session?.location ?? ""}`,
    "",
    "■ 아동 상태 및 태도",
    "",
    "",
    "■ 주요 상담 내용",
  ];

  if (summary.overview.trim()) lines.push(summary.overview.trim());

  for (const point of summary.key_points) {
    if (point.trim()) lines.push(`- ${point.trim()}`);
  }

  if (summary.counselor_note?.trim()) {
    lines.push("", "■ 상담사 메모", summary.counselor_note.trim());
  }

  lines.push("", "■ 아동 안전 여부", "", "", "■ 다음 회차 계획", "");

  return lines.join("\n");
}

// =========================================================
// 작성 근거 (요약 항목의 근거 발화)
// =========================================================

/** 작성 근거 한 건. 발화 하나에 요약 항목 여러 개가 연결될 수 있다. */
export interface UiDocumentEvidence {
  /** Backend 의 segment_id. */
  id: string;
  /** "mm:ss". 전사본에서 발화를 찾지 못하면 "—". */
  timestamp: string;
  speaker: string;
  /** 발화 원문. 전사본에서 찾지 못하면 null. */
  quote: string | null;
  /** 이 발화를 근거로 든 AI 요약 항목. */
  keyPoints: string[];
  startMs: number;
}

/**
 * 요약 근거(summary_evidence)를 발화 단위로 묶고, 발화 원문을 전사본에서 찾아 붙인다.
 * 순서는 발화 시각 순이고, 전사본에 없는 발화(분석 뒤 전사본이 바뀐 경우)는 뒤로 보낸다.
 */
export function toUiDocumentEvidence(
  evidence: SummaryEvidenceItem[],
  transcript: Transcript | null,
): UiDocumentEvidence[] {
  const segments = new Map((transcript?.segments ?? []).map((seg) => [seg.segment_id, seg]));
  const bySegment = new Map<string, UiDocumentEvidence>();

  for (const item of evidence) {
    for (const segmentId of item.segment_ids) {
      let entry = bySegment.get(segmentId);

      if (!entry) {
        const seg = segments.get(segmentId);

        entry = {
          id: segmentId,
          timestamp: seg ? toTimestamp(seg.start_ms) : "—",
          speaker: seg ? SPEAKER_LABELS[seg.speaker] ?? seg.speaker : "—",
          quote: seg ? seg.text : null,
          keyPoints: [],
          startMs: seg ? seg.start_ms : Number.POSITIVE_INFINITY,
        };
        bySegment.set(segmentId, entry);
      }

      if (item.key_point && !entry.keyPoints.includes(item.key_point)) {
        entry.keyPoints.push(item.key_point);
      }
    }
  }

  return [...bySegment.values()].sort((a, b) => a.startMs - b.startMs);
}

// =========================================================
// 사례 상세 "문서" 탭
// =========================================================

/** 문서 탭 표 한 줄. 상담일지가 없는 회기는 "미작성" 자리 한 줄로 보인다. */
export interface UiDocumentRow {
  key: string;
  sessionId: string;
  sessionNumber: number;
  title: string;
  typeLabel: string;
  statusLabel: string;
  /** 수정 시각 "YYYY-MM-DD HH:MM". 미작성 자리는 빈 문자열. */
  updatedAt: string;
  /** 작성 화면에서 열리는 문서인가(그 회기의 상담일지이거나 미작성 자리). */
  openable: boolean;
  /** 아직 상담일지가 없는 회기 자리. */
  placeholder: boolean;
}

/** 회기 하나의 문서 목록을 표의 줄로 바꾼다. 최근에 고친 문서가 위로 온다. */
export function toUiDocumentRows(
  sessionId: string,
  sessionNumber: number,
  docs: Document[],
): UiDocumentRow[] {
  const record = pickConsultationRecord(docs);
  const rows: UiDocumentRow[] = [...docs]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .map((doc) => ({
      key: doc.id,
      sessionId,
      sessionNumber,
      title: doc.title,
      typeLabel: toDocTypeLabel(doc.doc_type),
      statusLabel: DOCUMENT_STATUS_LABELS[doc.status] ?? doc.status,
      updatedAt: toLocalDateTime(doc.updated_at),
      // 작성 화면은 회기의 상담일지 하나만 연다. 다른 유형이나 예전 상담일지는 열 곳이 없다.
      openable: record !== null && doc.id === record.id,
      placeholder: false,
    }));

  if (!record) {
    rows.push({
      key: `${sessionId}-record`,
      sessionId,
      sessionNumber,
      title: defaultRecordTitle(sessionNumber),
      typeLabel: toDocTypeLabel(DOC_TYPE_CONSULTATION_RECORD),
      statusLabel: DOCUMENT_NOT_WRITTEN,
      updatedAt: "",
      openable: true,
      placeholder: true,
    });
  }

  return rows;
}
