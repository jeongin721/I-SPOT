// 다음 상담 체크리스트(API_CONTRACT 19절)의 근거(basis) → 화면 근거 칩.
//
// 추가 확인 · 질문 화면의 '다음 상담 전 확인할 사항'(followupQ.ts)과 '추가 질문' AI 초안 카드(followupQuestions.ts)가 같이 쓴다.
//  - 회차 발화(session_id + segment_id) → STT 검수의 그 발화
//  - 이전 회차 요약 · 확인 사항(session_id) → 그 회차 상세
//  - 아이 앱 응답 → 링크 없음(응답 하나를 가리키는 화면이 아직 없다)
//  - 법령 · 판례 → 국가법령정보센터(새 창)
//  - 매뉴얼 · 체크리스트 → 원본 PDF 를 올리지 않아 발췌(excerpt)를 그 자리에서 펼친다

import type { FollowupBasis } from "../../api/types";
import { screenHref } from "./links";
import { segmentHref } from "./sttReview";

export interface FollowupEvidence {
  key: string;
  label: string;
  /** 화면 안 주소(/SttReview · /SessionDetail). */
  href: string | null;
  /** 바깥 주소(국가법령정보센터). 새 창으로 연다. */
  url: string | null;
  /** 근거 원문 발췌. 없으면 null(화자 미확정 발화는 내용을 싣지 않는다). */
  excerpt: string | null;
}

export function cleanText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function toEvidence(basis: FollowupBasis, caseId: string | null | undefined, key: string): FollowupEvidence {
  const excerpt = cleanText(basis.excerpt) || null;

  if (basis.type === "case") {
    const sessionId = cleanText(basis.session_id) || null;
    const segmentId = cleanText(basis.segment_id);
    let href: string | null = null;

    if (sessionId && segmentId) href = segmentHref({ caseId: caseId ?? null, sessionId }, segmentId);
    else if (sessionId && basis.source !== "app_response") href = screenHref("/SessionDetail", { caseId: caseId ?? null, sessionId });

    return { key, label: cleanText(basis.label) || "사례 기록", href, url: null, excerpt };
  }

  const url = cleanText(basis.url);

  return { key, label: cleanText(basis.label) || "공식 근거", href: null, url: /^https?:\/\//.test(url) ? url : null, excerpt };
}

/** 근거 목록 중 사례 기록(type case)만 칩으로. */
export function caseEvidence(basis: FollowupBasis[] | undefined, caseId: string | null | undefined, prefix: string): FollowupEvidence[] {
  return (basis ?? [])
    .filter((entry) => entry && typeof entry === "object" && entry.type === "case")
    .map((entry, at) => toEvidence(entry, caseId, `${prefix}-c${at}`));
}

/** 근거 목록 중 공식 근거(매뉴얼 · 체크리스트 · 법령 · 판례)만 칩으로. */
export function sourceEvidence(basis: FollowupBasis[] | undefined, caseId: string | null | undefined, prefix: string): FollowupEvidence[] {
  return (basis ?? [])
    .filter((entry) => entry && typeof entry === "object" && entry.type !== "case")
    .map((entry, at) => toEvidence(entry, caseId, `${prefix}-s${at}`));
}
