// 4 · 추가 확인 · 질문(FollowupQ) 화면 값. 10/27 디자인(counselor-design/screens/FollowupQ.dc.html)의 칸에 서버 값을 넣는다.
//
// 디자인 칸 → 서버 값:
//  - 다음 상담 전 확인할 사항: AI 분석 결과의 선택 필드 followup_check_points(AI 확인 메모)를 읽기 전용으로 보인다
//    (10/26 까지는 유형별 위험도 화면에 있던 카드). 질문 은행의 질문이 아니고 아이에게 할 질문으로 보이지 않는다
//    ('AI 확인 메모 · 질문 아님' 으로만 보이면 원칙 7 과 어긋나지 않는다는 2026-10-26 결정).
//    근거 · 위치는 segment_ids 를 원문에서 찾아 '몇 분 · 누구' 로 보이고 누르면 STT 검수의 그 발화로 간다.
//    서버가 segment_ids 를 비워 보내면(2026-10-27 #84 이전에 저장된 결과) '근거 위치 없음' 이고, 근거가 지난 회차 확정 요약뿐인
//    메모(previous_session_label, 2026-10-28)는 '근거 · 7회차 확정 요약' 이다.
//    다음 상담 체크리스트(GET/POST …/followup-checklist, 19절)가 켜져 있으면 rag 확인 사항을 메모와 한 목록으로 합친다
//    (mergeCheckItems — 메모 먼저, 같은 문장은 한 번, 공식 근거는 검토를 통과한 것만 '공식 근거 N' 칩과 펼침으로).
//    꺼져 있으면(enabled=false) 지금처럼 메모만이다.
//  - 브리핑에 넣기 체크 · 수정 · 확인 사항 직접 추가: 저장할 API 가 없어 보이지 않고 준비 중이라고만 쓴다(가짜 저장 없음).
//  - 추가 질문: AI 초안(분석 결과 followup_questions) · 승인 목록(GET/PUT …/followup-questions, 18절)을 디자인의 카드 ·
//    [승인] · [수정] · [+ 질문 직접 추가] 로 보인다(followupQuestions.ts). '아이 앱으로 먼저' 탭은 준비 중이다.
//  - 아래 'n회차 처리 완료 · 브리핑 보기': 회차 상태에 '질문 처리 완료' 가 없고 상담 전 브리핑은 아직 예시 화면이라
//    회차 상세로 가는 단추로 둔다.

import type { ChecklistItem, ChecklistKind, FollowupCheckPoint, QuestionEvidence, SessionStatus } from "../../api/types";
import type { FollowupChecklistState } from "../useFollowupChecklist";
import type { FollowupQuestionsState } from "../useFollowupQuestions";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { NOT_READY } from "./common";
import { caseWhy, officialSources, type SourceView } from "./followupEvidence";
import { questionValues, type QuestionUiState } from "./followupQuestions";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";
import { segmentHref } from "./sttReview";

export interface FollowupScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
  questions: FollowupQuestionsState;
  /** 다음 상담 체크리스트(19절). 없으면(이전 호출부) 메모만 보인다. */
  checklist?: FollowupChecklistState;
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
/** rag 확인 사항이 함께 보일 때의 카드 머리 칩. 여전히 질문이 아니다. */
export const FOLLOWUP_RAG_CHIP = "AI 참고 · 질문 아님";

/** '다음 상담 전 확인할 사항' 한 항목. */
export interface FollowupItem {
  key: string;
  text: string;
  /** 근거 위치("01:08 아동"). 원문을 못 받았으면 "발화 seg_003", 번호가 없으면 "근거 위치 없음". */
  why: string;
  /** 근거 발화로 가는 STT 검수 주소. 번호가 없으면 null. */
  href: string | null;
  /** 근거가 지난 회차 확정 요약뿐인가(why 가 'N회차 확정 요약'). */
  fromPrevious: boolean;
  /** memo: AI 확인 메모(분석 followup_check_points), rag: 다음 상담 체크리스트(19절). */
  origin: "memo" | "rag";
  /** 항목 머리 칩. 공식 근거 칩은 실제로 붙은 공식 근거가 있을 때만(개수로 센다). */
  chips: string[];
  /** 확인이 필요한 이유(rag). 메모는 빈 문자열. */
  reason: string;
  /** 검토를 통과한 공식 근거(rag). 같은 문장의 메모와 합쳐지면 메모 쪽으로 옮겨 붙는다. */
  sources: SourceView[];
}

/** rag 확인 사항 종류 → 칩 글자(19절 kind). */
export const CHECK_KIND_LABELS: Record<ChecklistKind, string> = {
  info_gap: "정보 공백",
  plan_followup: "계획 이행",
  change: "변화",
  inconsistency: "기록 불일치",
  checklist_gap: "체크리스트",
};

/** 공식 근거 칩 글자. 개수는 실제로 붙은 공식 근거 수다. */
export const sourceChip = (count: number): string => `공식 근거 ${count}`;

/**
 * followup_check_points → 항목. text 가 빈 문자열이 아닌 항목만 쓰고 다른 키는 보지 않는다.
 * locate 는 useRiskSignals 의 원문 찾기다(segment_ids 를 '몇 분 · 누구' 로).
 */
export function toFollowupItems(
  points: FollowupCheckPoint[],
  locate: RiskSignalsState["locate"],
  ids: { caseId?: string | null; sessionId?: string | null },
): FollowupItem[] {
  const items: FollowupItem[] = [];

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

    items.push({
      key: `f${index}`,
      text,
      why: located.label || (previous ? `${previous} 확정 요약` : "근거 위치 없음"),
      href: first ? segmentHref(ids, first) : null,
      fromPrevious: Boolean(previous),
      origin: "memo",
      chips: [],
      reason: "",
      sources: [],
    });
  });

  return items;
}

/**
 * 다음 상담 체크리스트(19절)의 check_items → 항목. 근거가 없거나 모양이 틀린 항목은 쓰지 않는다(서버가 이미 뺐지만 한 번 더).
 * 공식 근거는 서버가 검토를 통과한 것만 보낸다. 칩의 공식 근거 수는 실제로 붙은 수다.
 */
export function ragCheckItems(
  items: ChecklistItem[] | null | undefined,
  ids: { caseId?: string | null; sessionId?: string | null },
): FollowupItem[] {
  const rows: FollowupItem[] = [];

  (Array.isArray(items) ? items : []).forEach((item, index) => {
    if (!item || typeof item !== "object" || !Array.isArray(item.basis) || item.basis.length === 0) return;

    const text = typeof item.text === "string" ? item.text.trim() : "";

    if (!text) return;

    const where = caseWhy(item.basis, ids);
    const sources = officialSources(item.basis, `r${index}`);
    const chips = ["AI 초안", CHECK_KIND_LABELS[item.kind] ?? "확인"];

    if (item.priority === "high") chips.push("우선");

    rows.push({
      key: `r${index}`,
      text,
      why: where.text,
      href: where.href,
      fromPrevious: false,
      origin: "rag",
      chips,
      reason: typeof item.reason === "string" ? item.reason.trim() : "",
      sources,
    });
  });

  // 우선(high) 먼저, 같으면 받은 순서.
  return rows
    .map((row, order) => ({ row, order, rank: row.chips.includes("우선") ? 0 : 1 }))
    .sort((a, b) => a.rank - b.rank || a.order - b.order)
    .map(({ row }) => row);
}

/** 중복 비교용: 공백 · 문장부호를 뺀 문장. */
export function normalizeCheckText(text: string): string {
  return text.replace(/[\s.,·…!?'"“”‘’()[\]{}~\-–—:;/]/g, "");
}

/**
 * AI 확인 메모와 rag 확인 사항을 한 목록으로(팀장님 10/29 결정 ③ — 메모를 없애지 않고 합치고 중복을 없앤다).
 * 순서는 메모 먼저(받은 순서), 그 뒤 rag. 같은 문장(공백 · 문장부호를 빼고 같음)이면 메모를 남기고 rag 쪽 공식 근거를 메모에 붙인다.
 * rag 항목이 하나라도 있으면 메모에 'AI 확인 메모' 칩을 달아 둘을 구분한다. 공식 근거 칩은 여기서 마지막에 센다.
 */
export function mergeCheckItems(memo: FollowupItem[], rag: FollowupItem[]): FollowupItem[] {
  const merged = memo.map((item) => ({ ...item, chips: [...item.chips], sources: [...item.sources] }));
  const byText = new Map(merged.map((item) => [normalizeCheckText(item.text), item]));
  const extra: FollowupItem[] = [];

  rag.forEach((item) => {
    const same = byText.get(normalizeCheckText(item.text));

    if (same) {
      const seen = new Set(same.sources.map((source) => `${source.label}|${source.excerpt}`));
      item.sources.forEach((source) => {
        if (!seen.has(`${source.label}|${source.excerpt}`)) same.sources.push(source);
      });
      return;
    }

    extra.push({ ...item, chips: [...item.chips], sources: [...item.sources] });
  });

  const all = [...merged, ...extra];

  if (extra.length > 0 || all.some((item) => item.sources.length > 0)) {
    merged.forEach((item) => {
      if (!item.chips.includes("AI 확인 메모")) item.chips.unshift("AI 확인 메모");
    });
  }

  all.forEach((item) => {
    if (item.sources.length > 0) item.chips.push(sourceChip(item.sources.length));
  });

  return all;
}

/** 다음 상담 체크리스트 상태 줄 · 단추(19절). 꺼져 있으면 모두 비어 있다(화면은 AI 확인 메모만). */
export interface ChecklistView {
  /** 지금 분석으로 만든 결과의 확인 사항. 아니면 []. */
  items: FollowupItem[];
  /** 지금 분석으로 만든 결과의 질문 공식 근거. 아니면 []. */
  questionEvidence: QuestionEvidence[];
  /** 상태 한 줄('만드는 중' · 실패 문구 · '아직 없음' · '분석이 바뀌었습니다'). 없으면 빈 문자열. */
  status: string;
  /** 서버 안내(고정 문구). */
  notice: string;
  error: string | null;
  /** 만들기 · 다시 만들기 단추 글자. 보이지 않으면 빈 문자열. */
  runLabel: string;
  runDisabled: boolean;
  run: () => void;
}

export function checklistValues(
  state: FollowupChecklistState | undefined,
  analysis: { id: string; status: string } | null,
  analyzed: boolean,
  ids: { caseId?: string | null; sessionId?: string | null },
): ChecklistView {
  const none: ChecklistView = {
    items: [],
    questionEvidence: [],
    status: "",
    notice: "",
    error: null,
    runLabel: "",
    runDisabled: true,
    run: () => {},
  };

  if (!state || !state.loaded) return { ...none, error: state?.error ?? null };
  if (!state.enabled) return none;

  const completed = analyzed && analysis !== null && analysis.status === "COMPLETED";
  const row = state.checklist;
  const sameAnalysis = row !== null && completed && row.analysis_id === analysis?.id;
  const processing = row?.status === "PROCESSING";
  const run = () => void state.run();
  const base = { ...none, error: state.error, run, runDisabled: !completed || processing || state.submitting };

  if (!completed) return { ...base, runLabel: "" };

  if (row === null) {
    if (state.waiting) return { ...base, status: "공식 근거 확인 사항을 만들기 시작하는 중입니다…", runLabel: "" };
    return { ...base, status: "공식 근거를 본 확인 사항이 아직 없습니다.", runLabel: "만들기" };
  }

  if (processing) return { ...base, status: "공식 근거를 본 확인 사항을 만드는 중입니다…", runLabel: "다시 만들기" };

  if (!sameAnalysis) {
    return { ...base, status: "AI 분석이 바뀌었습니다. 공식 근거 확인 사항을 다시 만들어 주세요.", runLabel: "다시 만들기" };
  }

  if (row.status === "FAILED") return { ...base, status: row.error?.message ?? "만들지 못했습니다.", runLabel: "다시 만들기" };

  const result = row.result;

  return {
    ...base,
    items: ragCheckItems(result?.check_items, ids),
    questionEvidence: Array.isArray(result?.question_evidence) ? result.question_evidence : [],
    notice: result?.notice ?? "",
    runLabel: "다시 만들기",
  };
}

export function followupQValues(input: FollowupScreenInput) {
  const { analysis, signals } = input;
  const header = processHeaderValues(input, 3);
  const ids = header.ids;
  const status = analysis.sessionStatus;
  const view = analysis.analysis;
  const analyzed = status === "AI_REVIEW_REQUIRED" || status === "APPROVED";
  const completed = analyzed && view !== null && view.status === "COMPLETED";
  const rag = checklistValues(input.checklist, view, analyzed, ids);
  const checks = completed
    ? mergeCheckItems(toFollowupItems(view?.followupCheckPoints ?? [], signals.locate, ids), rag.items)
    : [];
  const withRag = checks.some((item) => item.origin === "rag" || item.sources.length > 0);

  let empty = "";

  if (status === "AI_PROCESSING") empty = "AI 분석 중입니다. 끝나면 확인 메모가 보입니다.";
  else if (!completed) empty = "AI 분석이 끝나면 확인 메모가 보입니다.";
  else if (checks.length === 0) empty = "AI 가 남긴 확인 메모가 없습니다.";

  const sessionLabel = input.detail.session?.numberLabel ?? "";

  return {
    ...header,
    chip: withRag ? FOLLOWUP_RAG_CHIP : FOLLOWUP_CHIP,
    checkNote: withRag
      ? "AI 확인 메모와, 공식 근거(매뉴얼 · 체크리스트 · 법령 · 판례)를 함께 본 AI 초안입니다. 아이에게 할 질문이 아니고, 확인할지는 상담원이 정합니다."
      : "AI 가 다음 상담에서 확인해 두면 좋겠다고 남긴 메모입니다. 아이에게 할 질문이 아니고, 확인할지는 상담원이 정합니다.",
    checks,
    checksEmpty: empty,
    checkEditNote: `브리핑에 넣기 · 수정 · 확인 사항 직접 추가는 ${NOT_READY}입니다(저장할 서버 기능이 없음).`,
    ragStatus: rag.status,
    ragNotice: rag.notice,
    ragError: rag.error,
    ragRunLabel: rag.runLabel,
    ragRunDisabled: rag.runDisabled,
    ragRun: rag.run,
    ...questionValues({
      state: input.state,
      setState: input.setState,
      drafts: completed ? view?.followupQuestions ?? [] : [],
      saved: input.questions,
      locate: signals.locate,
      ids,
      sessionLabel,
      blockedReason: questionBlockedReason(status),
      questionEvidence: rag.questionEvidence,
    }),
    error: analysis.error,
    signalError: completed ? signals.evidenceError : null,
    backHref: screenHref("/NoteWrite", ids),
    doneHref: screenHref("/SessionDetail", ids),
    doneLabel: sessionLabel ? `${sessionLabel} 보기 →` : "회차 보기 →",
  };
}
