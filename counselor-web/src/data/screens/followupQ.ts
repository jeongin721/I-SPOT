// 4 · 추가 확인 · 질문(FollowupQ) 화면 값. 10/27 디자인(counselor-design/screens/FollowupQ.dc.html)의 칸에 서버 값을 넣는다.
//
// 디자인 칸 → 서버 값:
//  - 다음 상담 전 확인할 사항: 다음 상담 체크리스트(GET /followup-suggestions, 19절)의 check_items · speaker_check_items.
//    rag 가 이번 회차 아동 발화 · 이전 회차 기록에서 확인이 덜 된 부분을 뽑은 AI 초안이고 근거 칩(followupEvidence.ts)을 단다.
//    체크리스트가 없거나(만들기 전 · 실패 · 꺼짐) 비었으면 AI 분석 결과의 followup_check_points(AI 확인 메모)를 읽기 전용으로
//    보인다(10/26 까지는 유형별 위험도 화면에 있던 카드). 메모는 질문 은행의 질문이 아니고 아이에게 할 질문으로 보이지 않는다
//    ('AI 확인 메모 · 질문 아님' 으로만 보이면 원칙 7 과 어긋나지 않는다는 2026-10-26 결정).
//    메모의 근거 · 위치는 segment_ids 를 원문에서 찾아 '몇 분 · 누구' 로 보이고 누르면 STT 검수의 그 발화로 간다.
//    서버가 segment_ids 를 비워 보내면(2026-10-27 #84 이전에 저장된 결과) '근거 위치 없음' 이고, 근거가 지난 회차 확정 요약뿐인
//    메모(previous_session_label, 2026-10-28)는 '근거 · 7회차 확정 요약' 이다.
//  - 브리핑에 넣기 체크 · 수정 · 확인 사항 직접 추가: 저장할 API 가 없어 보이지 않고 준비 중이라고만 쓴다(가짜 저장 없음).
//  - 추가 질문: AI 초안(분석 결과 followup_questions) · 승인 목록(GET/PUT …/followup-questions, 18절)을 디자인의 카드 ·
//    [승인] · [수정] · [+ 질문 직접 추가] 로 보인다(followupQuestions.ts). 다음 상담 체크리스트(19절)의 상담 질문 초안도 분석 결과
//    초안 뒤에 같은 AI 초안 카드로 붙는다('공식 근거' 칩 · 이유 · 공식 근거 칩). 근거 번호는 이번 회차 발화만 넘긴다(18절 규칙).
//    공식 근거를 보고 AI 가 쓴 질문이라 질문 은행에서만 고르던 원칙 7 과 방향이 달라 팀 합의가 필요하다(RAG_MAP.md §3-1).
//    '아이 앱으로 먼저' 탭은 발송이 준비 중이고, 체크리스트의 아이 앱 질문 초안만 읽기 전용으로 보인다.
//  - 아래 'n회차 처리 완료 · 브리핑 보기': 회차 상태에 '질문 처리 완료' 가 없고 상담 전 브리핑은 아직 예시 화면이라
//    회차 상세로 가는 단추로 둔다.

import type {
  FollowupCheckItem,
  FollowupCheckPoint,
  FollowupQuestionDraft,
  FollowupSuggestionQuestion,
  SessionStatus,
} from "../../api/types";
import type { FollowupQuestionsState } from "../useFollowupQuestions";
import type { FollowupSuggestionsState } from "../useFollowupSuggestions";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { NOT_READY } from "./common";
import { caseEvidence, cleanText, sourceEvidence, type FollowupEvidence } from "./followupEvidence";
import { questionValues, type AppDraft, type DraftExtra, type QuestionUiState } from "./followupQuestions";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";
import { segmentHref } from "./sttReview";

export interface FollowupScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
  questions: FollowupQuestionsState;
  /** 다음 상담 체크리스트(19절). */
  followup: FollowupSuggestionsState;
  state: QuestionUiState;
  setState: (patch: Partial<QuestionUiState> | ((current: QuestionUiState) => Partial<QuestionUiState>)) => void;
}

/** 승인한 추가 질문을 저장할 수 있는 회차 상태(API_CONTRACT 18절). */
const QUESTION_EDITABLE: SessionStatus[] = ["STT_CONFIRMED", "AI_REVIEW_REQUIRED", "AI_FAILED", "APPROVED"];

/** 저장할 수 없는 상태면 그 이유. 상태를 아직 모르면 null(서버가 409 로 거른다). */
export function questionBlockedReason(status: SessionStatus | null | undefined): string | null {
  if (!status || QUESTION_EDITABLE.includes(status)) return null;
  if (status === "AI_PROCESSING") return "AI 분석 중에는 질문을 승인할 수 없습니다. 분석이 끝난 뒤 승인해 주세요.";
  return "원문(STT)을 확정한 뒤 질문을 승인할 수 있습니다.";
}

/** 카드 머리 칩. 질문이 아니라 메모임을 늘 밝힌다(원칙 7). */
export const FOLLOWUP_CHIP = "AI 확인 메모 · 질문 아님";
/** 다음 상담 체크리스트(19절) 칩. */
export const SUGGESTION_CHIP = "AI 초안 · 공식 근거";

/** '다음 상담 전 확인할 사항' 한 항목. */
export interface FollowupItem {
  key: string;
  text: string;
  /** 근거 칩. 비었으면 화면은 '근거 위치 없음'. */
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

const KIND_LABELS: Record<string, string> = {
  info_gap: "정보 공백",
  plan_followup: "계획 이행",
  change: "변화",
  inconsistency: "기록 불일치",
  checklist_gap: "체크리스트",
  uncertain_speaker: "화자 확인",
};

function checkItems(items: FollowupCheckItem[], caseId: string | null | undefined, prefix: string): FollowupItem[] {
  return items
    .filter((item) => item && typeof item === "object" && cleanText(item.item))
    .map((item, index) => ({
      key: `${prefix}${index}`,
      text: cleanText(item.item),
      evidence: caseEvidence(item.basis, caseId, `${prefix}${index}`),
      kindLabel: KIND_LABELS[item.kind] ?? "",
      priorityHigh: item.priority === "high",
      reason: cleanText(item.reason),
    }));
}

/**
 * 체크리스트의 상담 질문 → 18절 AI 초안 카드 입력(drafts) + 카드에만 붙는 정보(extras).
 * 근거 번호는 이번 회차 발화만 넘긴다(승인 목록은 그 회차 최신 전사본의 번호만 받는다 — 18절).
 * 분석 결과 초안과 문장이 같은 질문은 빼서 카드가 겹치지 않게 한다.
 */
function suggestionDrafts(
  items: FollowupSuggestionQuestion[],
  existing: FollowupQuestionDraft[],
  ids: { caseId?: string | null; sessionId?: string | null },
): { drafts: FollowupQuestionDraft[]; extras: DraftExtra[]; app: AppDraft[] } {
  const seen = new Set(existing.map((draft) => cleanText(draft?.text)));
  const drafts: FollowupQuestionDraft[] = [];
  const extras: DraftExtra[] = [];
  const app: AppDraft[] = [];

  items.forEach((item, index) => {
    const text = cleanText(item?.question);
    if (!item || typeof item !== "object" || !text) return;

    const basis = (item.basis ?? []).filter((entry) => entry && typeof entry === "object");
    const evidence = caseEvidence(basis, ids.caseId, `r${index}`);
    const sources = sourceEvidence(basis, ids.caseId, `r${index}`);
    const rationale = cleanText(item.rationale);

    if (item.audience === "child_app") {
      app.push({ key: `app-${index}`, text, rationale, evidence, sources });
      return;
    }

    if (seen.has(text)) return;
    seen.add(text);

    const current = basis.filter((entry) => entry.type === "case" && entry.session_id === ids.sessionId && cleanText(entry.segment_id));
    const segmentIds = Array.from(new Set(current.map((entry) => cleanText(entry.segment_id))));
    const others = basis.filter((entry) => entry.type === "case" && !current.includes(entry));

    drafts.push({ text, kind: "OPEN", segment_ids: segmentIds, reason: rationale, bank_code: null });
    extras.push({
      originLabel: "공식 근거",
      rationale,
      evidence: caseEvidence(others, ids.caseId, `r${index}o`),
      sources,
    });
  });

  return { drafts, extras, app };
}

/** 추가 질문 카드가 원문 근거 위치를 찾아야 하는가(체크리스트 상담 질문에 이번 회차 근거 번호가 있음). */
export function suggestionsNeedEvidence(followup: FollowupSuggestionsState, sessionId: string | null | undefined): boolean {
  return (followup.view?.result?.items ?? []).some(
    (item) =>
      item?.audience === "counselor" &&
      (item.basis ?? []).some((entry) => entry?.type === "case" && entry.session_id === sessionId && cleanText(entry.segment_id)),
  );
}

/**
 * followup_check_points → 항목. text 가 빈 문자열이 아닌 항목만 쓰고 다른 키는 보지 않는다.
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

    const text = typeof point.text === "string" ? point.text.trim() : "";

    if (!text) return;

    const located = locate(point.segment_ids);
    const first = located.evidence[0]?.segmentId ?? null;
    // 근거가 지난 회차 확정 요약뿐인 메모(previous_session_label, #100 §7 답 3).
    const previous =
      !first && typeof point.previous_session_label === "string" && point.previous_session_label
        ? point.previous_session_label
        : "";

    const label = located.label || (previous ? `${previous} 확정 요약` : "");
    const href = first ? segmentHref(ids, first) : null;

    items.push({
      key: `f${index}`,
      text,
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
  const suggestion = followup.view;
  const result = suggestion?.result ?? null;
  const suggestedChecks = result
    ? [...checkItems(result.check_items ?? [], ids.caseId, "c"), ...checkItems(result.speaker_check_items ?? [], ids.caseId, "s")]
    : [];
  const useSuggestion = suggestedChecks.length > 0;
  const checks: FollowupItem[] = useSuggestion
    ? suggestedChecks
    : completed
      ? toFollowupItems(view?.followupCheckPoints ?? [], signals.locate, ids)
      : [];

  let empty = "";

  if (status === "AI_PROCESSING") empty = "AI 분석 중입니다. 끝나면 확인할 사항이 보입니다.";
  else if (!completed) empty = "AI 분석이 끝나면 확인할 사항이 보입니다.";
  else if (followup.processing) empty = "공식 근거를 찾아 확인할 사항을 만드는 중입니다.";
  else if (checks.length === 0) empty = "확인할 사항이 없습니다.";

  // 다음 상담 체크리스트 상태 한 줄(만드는 중 · 실패 · 아직 없음).
  let suggestionStatus = "";

  if (followup.processing) suggestionStatus = "다음 상담 체크리스트를 만드는 중입니다(1분 안팎). 끝나면 바로 보입니다.";
  else if (suggestion?.status === "FAILED") suggestionStatus = suggestion.errorMessage ?? "다음 상담 체크리스트를 만들지 못했습니다.";
  else if (completed && suggestion === null && !followup.loading) suggestionStatus = "다음 상담 체크리스트가 아직 없습니다.";

  const sessionLabel = input.detail.session?.numberLabel ?? "";
  const analysisDrafts = completed ? view?.followupQuestions ?? [] : [];
  const extra = completed ? suggestionDrafts(result?.items ?? [], analysisDrafts, ids) : { drafts: [], extras: [], app: [] };

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
    suggestionNotice: cleanText(result?.notice),
    canRegenerate: completed && !followup.processing && !followup.submitting && !followup.loading,
    regenerating: followup.submitting,
    regenerate: () => {
      void followup.run();
    },
    suggestionError: followup.error,
    ...questionValues({
      state: input.state,
      setState: input.setState,
      drafts: [...analysisDrafts, ...extra.drafts],
      extras: [...analysisDrafts.map(() => undefined), ...extra.extras],
      appDrafts: extra.app,
      saved: input.questions,
      locate: signals.locate,
      ids,
      sessionLabel,
      blockedReason: questionBlockedReason(status),
    }),
    error: analysis.error,
    signalError: completed ? signals.evidenceError : null,
    backHref: screenHref("/NoteWrite", ids),
    doneHref: screenHref("/SessionDetail", ids),
    doneLabel: sessionLabel ? `${sessionLabel} 보기 →` : "회차 보기 →",
  };
}
