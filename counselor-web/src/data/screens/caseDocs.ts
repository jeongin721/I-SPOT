// 사례 상세 탭 5(CaseDocs · 문서함) 화면 값. 머리는 useCaseDetail, 표는 useCaseDocuments(회차마다 음성 · 원문 · 문서)로 그린다.
//
// 녹음 · 원문(STT) · 상담일지를 회차별로 한 줄씩 보이고, 누르면 그 회차의 검수 · 일지 화면으로 간다.
// Backend 에 없는 것은 지어내지 않고 준비 중으로 둔다(specs 대응표 CaseDocs 줄 — 팀 결정 · 구현 필요):
//  - 기관 서식 6종의 작성 기록 · 상태(서식 구조 · 저장 의미가 팀 결정 전). 서식 이름 · 작성 시점은 매뉴얼 기준이라 그대로 둔다.
//  - 상담 전 브리핑(다회차 브리핑 저장이 없다), 외부 문서(PDF · HWPX) 올리기 · 열기(첨부 파일 기능이 없다).

import { NOT_PROVIDED } from "../caseRows";
import type { CaseDocumentsState, SessionDocs } from "../useCaseDocuments";
import type { CaseDetailState } from "../useCaseDetail";
import { findConsultationRecord } from "../useSessionDocuments";
import type { AuthSession } from "../useAuthSession";
import { caseHeaderValues } from "./caseDetail";
import { NOT_READY, notice } from "./common";
import { screenHref } from "./links";

export type DocsFilter = "all" | "rec" | "note" | "brief" | "ext";

const FILTERS: [DocsFilter, string][] = [
  ["all", "전체"],
  ["rec", "녹취"],
  ["note", "상담 일지"],
  ["brief", "브리핑"],
  ["ext", "외부 문서"],
];

/** 「아동학대 대응 업무 매뉴얼」 서식 목록(이름 · 번호 · 작성 시점). 작성 기록은 서버에 없어 모두 준비 중이다. */
const FORMS = [
  ["초기면접지 (아동용)", "서식 4", "사례 등록 · 최초면접"],
  ["사정기록지 · 안전영역", "서식 6", "초기 사정 · 재사정"],
  ["사례관리 점검표", "서식 27", "3개월마다"],
  ["위험수준별 개입 사정 척도", "참고자료 3", "사정 · 재사정"],
  ["축약형 가족관계 척도", "참고자료 1", "초기 · 종결"],
  ["사례관리 종결보고서", "서식 29", "종결 검토 등록 후"],
];

export interface DocRow {
  name: string;
  kind: string;
  ses: string;
  date: string;
  st: string;
  stCls: string;
  /** 누르면 갈 화면. 열 화면이 없으면 null(go 를 글자로만 보인다). */
  href: string | null;
  go: string;
  filter: DocsFilter;
}

const dateOf = (dateTime: string) => (dateTime ? dateTime.slice(0, 10) : NOT_PROVIDED);

/**
 * 회차 하나의 줄: 녹음 → 원문(STT) → 문서(만든 순서).
 * 요약 · 일지 작성 화면(NoteWrite)은 회차의 가장 최근 상담일지 하나만 연다(useSessionDocuments.findConsultationRecord).
 * 그래서 그 문서 줄만 그 화면으로 보내고, 이전 상담일지 · 다른 유형 문서는 열 화면이 없어 준비 중으로 둔다
 * (다른 문서를 누르고 최신 일지가 열리지 않게).
 */
export function sessionDocRows({ session, documents }: SessionDocs): DocRow[] {
  const ids = { caseId: session.caseId, sessionId: session.id };
  const ses = session.numberLabel;
  const rows: DocRow[] = [];

  rows.push(
    session.hasAudio
      ? {
          name: session.audio?.fileName ?? "녹음 파일",
          kind: "녹음",
          ses,
          date: dateOf(session.audio?.uploadedAt ?? ""),
          st: "올림",
          stCls: "chip c-ok",
          href: screenHref("/SessionDetail", ids),
          go: "회차 보기",
          filter: "rec",
        }
      : {
          name: "녹음 없음",
          kind: "녹음",
          ses,
          date: NOT_PROVIDED,
          st: "업로드 대기",
          stCls: "chip c-check",
          href: screenHref("/UploadModal", ids),
          go: "녹취 올리기",
          filter: "rec",
        },
  );

  if (session.hasAudio) {
    // 원문 변환 단계(대기 · 진행 · 실패)면 그 상태를, 변환이 끝났으면 검수 상태를 보인다.
    let st = NOT_PROVIDED;
    let stCls = "chip c-normal";
    if (session.step === "stt") {
      st = session.statusLabel;
      stCls = session.phase === "failed" ? "chip c-urgent" : "chip c-sky";
    } else if (session.hasTranscript) {
      st = session.transcriptConfirmed ? "검수 완료" : "검수 필요";
      stCls = session.transcriptConfirmed ? "chip c-ok" : "chip c-check";
    }
    rows.push({
      name: `${ses} STT 원문${session.transcriptVersion ? ` (v${session.transcriptVersion})` : ""}`,
      kind: "원문",
      ses,
      date: dateOf(session.sttCompletedAt),
      st,
      stCls,
      href: screenHref("/SttReview", ids),
      go: st === "검수 필요" ? "STT 검수" : "열기",
      filter: "rec",
    });
  }

  const openable = findConsultationRecord(documents);

  for (const document of documents) {
    const opens = openable !== null && document.id === openable.id;
    rows.push({
      name: document.title,
      kind: document.docTypeLabel,
      ses,
      date: dateOf(document.approvedAt || document.updatedAt),
      st: document.statusLabel,
      stCls: document.editable ? "chip c-check" : "chip c-ok",
      href: opens ? screenHref("/NoteWrite", ids) : null,
      go: opens ? "열기" : `열기 ${NOT_READY}`,
      filter: "note",
    });
  }

  return rows;
}

interface CaseDocsInput {
  session: AuthSession;
  detail: CaseDetailState;
  docs: CaseDocumentsState;
  caseId: string | null;
  filter: DocsFilter;
  setFilter: (filter: DocsFilter) => void;
}

export function caseDocsValues(input: CaseDocsInput) {
  const { detail, docs, filter, setFilter } = input;
  const header = caseHeaderValues(input);
  const all = docs.items.flatMap(sessionDocRows);
  const rows = all.filter((row) => filter === "all" || row.filter === filter);

  let rowsNote = "";
  if (filter === "brief") rowsNote = `상담 전 브리핑 보관은 ${NOT_READY}입니다(서버에 아직 없는 기능).`;
  else if (filter === "ext") rowsNote = `외부 문서(PDF · HWPX) 올리기 · 열기는 ${NOT_READY}입니다(서버에 아직 없는 기능).`;
  else if (detail.caseInfo && !docs.loading && !docs.error && docs.items.length === 0) {
    rowsNote = "회차가 없습니다. 녹취를 올리면 회차가 생깁니다.";
  } else if (detail.sessionTotal !== null && detail.sessionTotal > detail.sessions.length) {
    rowsNote = `최근 ${detail.sessions.length}회차의 문서만 보입니다(전체 ${detail.sessionTotal}회차).`;
  }

  // 사례 머리(로그인 · 사례 ID · 사례 조회)에 안내가 없을 때만 문서 조회 상태를 보인다.
  let docsNotice = header.notice;
  if (!docsNotice && docs.error) docsNotice = notice(docs.error, { alert: true, retry: docs.reload });
  else if (!docsNotice && docs.loading) docsNotice = notice("문서를 불러오는 중…");

  return {
    ...header,
    notice: docsNotice,
    rows,
    rowsNote,
    filters: FILTERS.map(([key, label]) => ({ label, cls: filter === key ? "on" : "", pick: () => setFilter(key) })),
    forms: FORMS.map(([name, no, when]) => ({
      name,
      no,
      when,
      date: NOT_PROVIDED,
      st: NOT_READY,
      stCls: "chip c-normal",
      href: null as string | null,
      go: "",
    })),
    formsNote: `기관 서식 작성 · 보관은 ${NOT_READY}입니다(서식 구조가 팀 결정 전).`,
    uploadNote: `지금은 녹음만 올릴 수 있습니다. 외부 문서 올리기는 ${NOT_READY}.`,
  };
}
