// 4 · 추가 확인 · 질문(FollowupQ) 화면 값. 10/27 디자인(counselor-design/screens/FollowupQ.dc.html)의 칸에 서버 값을 넣는다.
//
// 디자인 칸 → 서버 값:
//  - 다음 상담 전 확인할 사항: 다음 상담 체크리스트(GET /followup-suggestions, API_CONTRACT 18절)의 check_items ·
//    speaker_check_items. rag 가 이번 회차 아동 발화 · 이전 회차 기록에서 확인이 덜 된 부분을 뽑은 AI 초안이다.
//    체크리스트가 없거나(만들기 전 · 실패 · 꺼짐) 비었으면 전처럼 AI 분석의 followup_check_points(AI 확인 메모)를 보인다.
//    근거 칩: 회차 발화 → STT 검수의 그 발화, 이전 회차 기록 → 그 회차 상세, 법령 · 판례 → 국가법령정보센터(새 창),
//    매뉴얼 · 체크리스트 → 원본을 올리지 않아 발췌를 그 자리에서 펼친다.
//  - 추가 질문(다음 상담에서 직접 · 아이 앱으로 먼저): 체크리스트의 items. 공식 근거를 찾아 AI 가 쓰고 규칙 · LLM 검토를
//    통과한 초안이다. 질문을 질문 은행에서만 고르던 화면 원칙 7 과 방향이 달라 팀 합의가 필요하다(RAG_MAP.md §3-1).
//    그래서 'AI 초안 · 상담원 확인' 을 늘 밝힌다.
//  - 승인 · 브리핑에 넣기 · 수정 · 직접 추가 · 아이 앱 발송: 저장할 API 가 없어 보이지 않고 준비 중이라고만 쓴다(가짜 저장 없음).
//  - 아래 'n회차 처리 완료 · 브리핑 보기': 회차 상태에 '질문 처리 완료' 가 없고 상담 전 브리핑은 아직 예시 화면이라
//    회차 상세로 가는 단추로 둔다.

import type { FollowupBasis, FollowupCheckItem, FollowupCheckPoint, FollowupQuestion } from "../../api/types";
import type { FollowupSuggestionsState } from "../useFollowupSuggestions";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { NOT_READY } from "./common";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";
import { segmentHref } from "./sttReview";

export type FollowupAudience = "counselor" | "child_app";

export interface FollowupScreenState {
  /** 추가 질문 탭. */
  audience: FollowupAudience;
}

export const INITIAL_FOLLOWUP_STATE: FollowupScreenState = { audience: "counselor" };

export interface FollowupScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
  followup: FollowupSuggestionsState;
  state?: FollowupScreenState;
  setState?: (patch: Partial<FollowupScreenState>) => void;
}

/** AI 확인 메모 칩. 질문이 아니라 메모임을 늘 밝힌다(원칙 7). */
export const FOLLOWUP_CHIP = "AI 확인 메모 · 질문 아님";
/** 체크리스트(rag) 칩. */
export const SUGGESTION_CHIP = "AI 초안 · 공식 근거";

/** 근거 칩 하나. */
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

/** '다음 상담 전 확인할 사항' 한 항목. */
export interface FollowupItem {
  key: string;
  text: string;
  /** 근거 칩. 비었으면 '근거 위치 없음'. */
  evidence: FollowupEvidence[];
  /** 분류(정보 공백 · 계획 이행 …). AI 확인 메모는 빈 문자열. */
  kindLabel: string;
  priorityHigh: boolean;
  /** 왜 확인해야 하는지(체크리스트만). */
  reason: string;
}

/** AI 확인 메모 항목. 상담 전 브리핑(preBriefing.ts)이 쓰는 칸(why · href · fromPrevious)도 함께 든다. */
export interface FollowupMemoItem extends FollowupItem {
  /** 근거 위치("01:08 아동"). 원문을 못 받았으면 "발화 seg_003", 번호가 없으면 "근거 위치 없음". */
  why: string;
  /** 근거 발화로 가는 STT 검수 주소. 번호가 없으면 null. */
  href: string | null;
  /** 근거가 지난 회차 확정 요약뿐인가(why 가 'N회차 확정 요약'). */
  fromPrevious: boolean;
}

/** 추가 질문 한 항목. */
export interface FollowupQuestionItem {
  key: string;
  audience: FollowupAudience;
  text: string;
  typeLabel: string;
  priorityHigh: boolean;
  /** 검토를 못 거쳤으면 그 표시. 통과했으면 빈 문자열. */
  reviewLabel: string;
  rationale: string;
  /** 사례 근거 칩(회차 발화 · 이전 회차 기록 · 아이 앱 응답). */
  evidence: FollowupEvidence[];
  /** 공식 근거(매뉴얼 · 체크리스트 · 법령 · 판례). */
  sources: FollowupEvidence[];
}

const KIND_LABELS: Record<string, string> = {
  info_gap: "정보 공백",
  plan_followup: "계획 이행",
  change: "변화",
  inconsistency: "기록 불일치",
  checklist_gap: "체크리스트",
  uncertain_speaker: "화자 확인",
};

const QUESTION_TYPE_LABELS: Record<string, string> = { open: "열린 질문", clarify: "확인 질문" };

const REVIEW_LABELS: Record<string, string> = {
  not_reviewed: "검토 못 함",
  fallback: "대체 질문",
};

const AUDIENCE_NOTES: Record<FollowupAudience, string> = {
  counselor:
    "공식 근거(업무 매뉴얼 · 체크리스트 · 법령 · 판례)를 찾아 AI 가 쓴 질문 초안입니다. 유도 · 판단 표현은 걸렀지만, 쓰기 전에 상담원이 확인해 주세요.",
  child_app: "상담 전에 아이 앱으로 먼저 보낼 만한 질문 초안입니다. 특정 사건이나 행위는 묻지 않습니다.",
};

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** 근거 → 칩. 회차 발화는 STT 검수의 그 발화, 이전 회차 기록은 그 회차 상세로 간다. */
export function toEvidence(basis: FollowupBasis, caseId: string | null | undefined, key: string): FollowupEvidence {
  const excerpt = text(basis.excerpt) || null;

  if (basis.type === "case") {
    const sessionId = text(basis.session_id) || null;
    const segmentId = text(basis.segment_id);
    let href: string | null = null;

    if (sessionId && segmentId) href = segmentHref({ caseId: caseId ?? null, sessionId }, segmentId);
    else if (sessionId && basis.source !== "app_response") href = screenHref("/SessionDetail", { caseId: caseId ?? null, sessionId });

    return { key, label: text(basis.label) || "사례 기록", href, url: null, excerpt };
  }

  const url = text(basis.url);

  return { key, label: text(basis.label) || "공식 근거", href: null, url: /^https?:\/\//.test(url) ? url : null, excerpt };
}

function checkItems(items: FollowupCheckItem[], caseId: string | null | undefined, prefix: string): FollowupItem[] {
  return items
    .filter((item) => item && typeof item === "object" && text(item.item))
    .map((item, index) => ({
      key: `${prefix}${index}`,
      text: text(item.item),
      evidence: (item.basis ?? [])
        .filter((basis) => basis && basis.type === "case")
        .map((basis, at) => toEvidence(basis, caseId, `${prefix}${index}-${at}`)),
      kindLabel: KIND_LABELS[item.kind] ?? "",
      priorityHigh: item.priority === "high",
      reason: text(item.reason),
    }));
}

function questionItems(items: FollowupQuestion[], caseId: string | null | undefined): FollowupQuestionItem[] {
  return items
    .filter((item) => item && typeof item === "object" && text(item.question))
    .map((item, index) => {
      const basis = (item.basis ?? []).filter((entry) => entry && typeof entry === "object");

      return {
        key: `q${index}`,
        audience: item.audience === "child_app" ? ("child_app" as const) : ("counselor" as const),
        text: text(item.question),
        typeLabel: QUESTION_TYPE_LABELS[item.question_type] ?? "질문",
        priorityHigh: item.priority === "high",
        reviewLabel: REVIEW_LABELS[item.review_status] ?? "",
        rationale: text(item.rationale),
        evidence: basis.filter((entry) => entry.type === "case").map((entry, at) => toEvidence(entry, caseId, `q${index}-c${at}`)),
        sources: basis.filter((entry) => entry.type !== "case").map((entry, at) => toEvidence(entry, caseId, `q${index}-s${at}`)),
      };
    });
}

/**
 * followup_check_points(AI 확인 메모) → 항목. 체크리스트가 없을 때 쓴다. text 가 빈 문자열이 아닌 항목만 쓴다.
 * locate 는 useRiskSignals 의 원문 찾기다(segment_ids 를 '몇 분 · 누구' 로).
 */
export function toFollowupItems(
  points: FollowupCheckPoint[],
  locate: RiskSignalsState["locate"],
  ids: { caseId?: string | null; sessionId?: string | null },
): FollowupMemoItem[] {
  const items: FollowupMemoItem[] = [];

  points.forEach((point, index) => {
    if (!point || typeof point !== "object") return;

    const body = text(point.text);

    if (!body) return;

    const located = locate(point.segment_ids);
    const first = located.evidence[0]?.segmentId ?? null;
    // 근거가 지난 회차 확정 요약뿐인 메모(previous_session_label, #100 §7 답 3).
    const previous = !first && text(point.previous_session_label) ? text(point.previous_session_label) : "";
    const label = located.label || (previous ? `${previous} 확정 요약` : "");
    const href = first ? segmentHref(ids, first) : null;

    items.push({
      key: `f${index}`,
      text: body,
      evidence: label ? [{ key: `f${index}-0`, label, href, url: null, excerpt: null }] : [],
      kindLabel: "",
      priorityHigh: false,
      reason: "",
      why: label || "근거 위치 없음",
      href,
      fromPrevious: Boolean(previous),
    });
  });

  return items;
}

export function followupQValues(input: FollowupScreenInput) {
  const { analysis, signals, followup } = input;
  const header = processHeaderValues(input, 3);
  const ids = header.ids;
  const status = analysis.sessionStatus;
  const view = analysis.analysis;
  const analyzed = status === "AI_REVIEW_REQUIRED" || status === "APPROVED";
  const completed = analyzed && view !== null && view.status === "COMPLETED";
  const state = input.state ?? INITIAL_FOLLOWUP_STATE;

  const suggestion = followup.view;
  const result = suggestion?.result ?? null;
  const suggestedChecks = result
    ? [...checkItems(result.check_items ?? [], ids.caseId, "c"), ...checkItems(result.speaker_check_items ?? [], ids.caseId, "s")]
    : [];
  const useSuggestion = suggestedChecks.length > 0;
  const checks = useSuggestion
    ? suggestedChecks
    : completed
      ? toFollowupItems(view?.followupCheckPoints ?? [], signals.locate, ids)
      : [];

  let empty = "";

  if (status === "AI_PROCESSING") empty = "AI 분석 중입니다. 끝나면 확인할 사항이 보입니다.";
  else if (!completed) empty = "AI 분석이 끝나면 확인할 사항이 보입니다.";
  else if (followup.processing) empty = "공식 근거를 찾아 확인할 사항을 만드는 중입니다.";
  else if (checks.length === 0) empty = "확인할 사항이 없습니다.";

  // 체크리스트 상태 한 줄(만드는 중 · 실패 · 안내).
  let suggestionStatus = "";

  if (followup.processing) suggestionStatus = "다음 상담 체크리스트를 만드는 중입니다(1분 안팎). 끝나면 바로 보입니다.";
  else if (suggestion?.status === "FAILED") suggestionStatus = suggestion.errorMessage ?? "다음 상담 체크리스트를 만들지 못했습니다.";
  else if (completed && suggestion === null && !followup.loading) suggestionStatus = "다음 상담 체크리스트가 아직 없습니다.";

  const questions = questionItems(result?.items ?? [], ids.caseId);
  const shown = questions.filter((question) => question.audience === state.audience);

  let questionsEmpty = "";

  if (!completed) questionsEmpty = "AI 분석이 끝나면 질문 초안이 보입니다.";
  else if (followup.processing) questionsEmpty = "질문 초안을 만드는 중입니다.";
  else if (!result) questionsEmpty = "질문 초안이 아직 없습니다.";
  else if (shown.length === 0) questionsEmpty = "이 대상에 맞는 질문 초안이 없습니다.";

  const setAudience = (audience: FollowupAudience) => input.setState?.({ audience });
  const sessionLabel = input.detail.session?.numberLabel ?? "";

  return {
    ...header,
    chip: useSuggestion ? SUGGESTION_CHIP : FOLLOWUP_CHIP,
    checkNote: useSuggestion
      ? "이번 회차 아동 발화와 이전 회차 기록에서 확인이 덜 된 부분을 AI 가 정리한 초안입니다. 근거를 눌러 원문을 확인하고, 확인할지는 상담원이 정합니다."
      : "AI 가 다음 상담에서 확인해 두면 좋겠다고 남긴 메모입니다. 아이에게 할 질문이 아니고, 확인할지는 상담원이 정합니다.",
    checks,
    checksEmpty: empty,
    checkEditNote: `브리핑에 넣기 · 수정 · 확인 사항 직접 추가는 ${NOT_READY}입니다(저장할 서버 기능이 없음).`,
    suggestionStatus,
    suggestionNotice: text(result?.notice),
    canRegenerate: completed && !followup.processing && !followup.submitting && !followup.loading,
    regenerating: followup.submitting,
    regenerate: () => {
      void followup.run();
    },
    suggestionError: followup.error,
    tabs: [
      { key: "counselor" as const, label: "다음 상담에서 직접" },
      { key: "child_app" as const, label: "아이 앱으로 먼저" },
    ].map((tab) => ({
      ...tab,
      count: questions.filter((question) => question.audience === tab.key).length,
      on: tab.key === state.audience,
      select: () => setAudience(tab.key),
    })),
    questions: shown,
    questionsEmpty,
    questionNote: result ? AUDIENCE_NOTES[state.audience] : "",
    questionActionNote: `질문 승인 · 브리핑에 넣기 · 아이 앱 발송은 ${NOT_READY}입니다(저장할 서버 기능이 없음).`,
    error: analysis.error,
    signalError: completed && !useSuggestion ? signals.evidenceError : null,
    backHref: screenHref("/NoteWrite", ids),
    doneHref: screenHref("/SessionDetail", ids),
    doneLabel: sessionLabel ? `${sessionLabel} 보기 →` : "회차 보기 →",
  };
}
