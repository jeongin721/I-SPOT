// 다음 상담 체크리스트(19절)의 근거(basis)를 화면 값으로 바꾼다. 4 · 추가 확인 · 질문과 상담 전 브리핑이 같이 쓴다.
//
//  - 사례 근거(type=case): 이번 회차 발화(segment_id)는 STT 검수의 그 발화로, 앞 회차는 그 회차 상세로 간다.
//  - 공식 근거(그 밖): 서버가 rag 의 검토(연결 → 코드 검사 → 검토)를 통과한 것만 보낸다. 법령 · 판례처럼 url 이 있으면
//    새 창으로 열고, 매뉴얼 · 체크리스트는 원본을 올릴 수 없어 발췌(excerpt)를 그 자리에서 펼쳐 보인다.
//    '공식 근거 N' 칩은 여기서 센 실제 개수다(고정 문구로 붙이지 않는다 — 닫힌 #117 교차검증 R7).

import type { ChecklistBasis } from "../../api/types";
import { screenHref } from "./links";
import { segmentHref } from "./sttReview";

/** 공식 근거 하나(펼침 · 새 창). */
export interface SourceView {
  key: string;
  /** "업무 매뉴얼.pdf · 상담·조사·사정 p.125" */
  label: string;
  /** 발췌. 없으면 빈 문자열. */
  excerpt: string;
  /** 질문에 붙인 근거의 연결 이유(검토 통과). 확인 사항 근거에는 없다. */
  why: string;
  /** http(s) 주소면 새 창으로. 아니면 null(발췌를 펼친다). */
  url: string | null;
}

/** 사례 근거 위치(디자인 '근거 · 8회차 01:08'). */
export interface CaseWhy {
  text: string;
  href: string | null;
}

const text = (value: unknown): string => (typeof value === "string" ? value.trim() : "");

export const isOfficial = (basis: ChecklistBasis): boolean => Boolean(basis) && text(basis.type) !== "" && basis.type !== "case";

function safeUrl(value: unknown): string | null {
  const url = text(value);

  return /^https?:\/\//i.test(url) ? url : null;
}

function pageLabel(basis: ChecklistBasis): string {
  const label = text(basis.label);

  if (label) return label;

  const source = text(basis.source);
  const page = basis.page === null || basis.page === undefined || basis.page === "" ? "" : ` p.${basis.page}`;

  return `${source || "공식 근거"}${page}`;
}

/** 공식 근거만 골라 화면 값으로. 같은 근거(ref · 이름 · 발췌가 같음)는 한 번만. */
export function officialSources(basis: ChecklistBasis[] | null | undefined, prefix = "src"): SourceView[] {
  const seen = new Set<string>();
  const views: SourceView[] = [];

  (Array.isArray(basis) ? basis : []).forEach((entry, index) => {
    if (!entry || typeof entry !== "object" || !isOfficial(entry)) return;

    const label = pageLabel(entry);
    const excerpt = text(entry.excerpt);
    const identity = `${text(entry.ref)}|${label}|${excerpt}`;

    if (seen.has(identity)) return;
    seen.add(identity);

    views.push({ key: `${prefix}-${index}`, label, excerpt, why: text(entry.why), url: safeUrl(entry.url) });
  });

  return views;
}

/**
 * 사례 근거 첫 번째의 위치. 발화 번호가 있으면 그 회차 STT 검수의 그 발화로, 회차만 있으면(앞 회차 요약 등) 그 회차 상세로 간다.
 * ids.caseId 는 지금 화면의 사례다. 사례 근거가 없으면 '근거 위치 없음'.
 */
export function caseWhy(
  basis: ChecklistBasis[] | null | undefined,
  ids: { caseId?: string | null; sessionId?: string | null },
): CaseWhy {
  const first = (Array.isArray(basis) ? basis : []).find((entry) => entry && entry.type === "case");

  if (!first) return { text: "근거 위치 없음", href: null };

  const label = text(first.label) || (first.session_no ? `${first.session_no}회차` : "사례 기록");
  const sessionId = text(first.session_id);
  const segmentId = text(first.segment_id);

  const target = { caseId: ids.caseId ?? null, sessionId: sessionId || null };

  if (segmentId && sessionId) return { text: label, href: segmentHref(target, segmentId) };
  if (sessionId) return { text: label, href: screenHref("/SessionDetail", target) };

  return { text: label, href: null };
}
