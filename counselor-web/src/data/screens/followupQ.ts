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
//  - 브리핑에 넣기 체크 · 수정 · 확인 사항 직접 추가(2026-10-30): GET/PUT …/followup-checks(18.1절)에 저장(followupChecks.ts).
//    저장 전 초안은 AI 확인 메모 + rag 확인 사항을 합친 목록이고(rag 항목도 source AI 로 저장), 저장한 뒤에는 저장 목록이 기준이다.
//    저장한 줄의 rag 표시(칩 · 이유 · 공식 근거 · 근거 위치)는 문장 · 근거 발화 번호가 같고 목록을 지금 체크리스트가 끝난 뒤에
//    저장했을 때만 붙인다(ragCheckAnnotations). 목록을 저장한 뒤 체크리스트를 만들면(다시 만들기 · 재분석) 저장한 줄은 저장한 값으로만
//    보이고, 목록에 없는 rag 항목은 [목록에 더하기] 로 넣는다(2026-11-02, #128 위에 맞춤 · #125 재검증 M1 · M2 · L1).
//  - 추가 질문: AI 초안(분석 결과 followup_questions) · 승인 목록(GET/PUT …/followup-questions, 18절)을 디자인의 카드 ·
//    [승인] · [수정] · [+ 질문 직접 추가] 로 보인다(followupQuestions.ts). '아이 앱으로 먼저' 탭은 준비 중이다.
//  - 아래 'n회차 처리 완료 · 브리핑 보기': 회차 상태에 '질문 처리 완료' 가 없고 상담 전 브리핑은 아직 예시 화면이라
//    회차 상세로 가는 단추로 둔다.

import type {
  ChecklistItem,
  ChecklistKind,
  FollowupCheck,
  FollowupCheckPoint,
  QuestionEvidence,
  SessionStatus,
} from "../../api/types";
import type { FollowupChecklistState } from "../useFollowupChecklist";
import type { FollowupChecksState } from "../useFollowupChecks";
import type { FollowupQuestionsState } from "../useFollowupQuestions";
import type { RiskSignalsState } from "../useRiskSignals";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import { checkValues, type CheckAnnotation, type CheckUiState } from "./followupChecks";
import { caseWhy, officialSources, type SourceView } from "./followupEvidence";
import { questionValues, type QuestionUiState } from "./followupQuestions";
import { briefingHref } from "./caseDetail";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";
import { segmentHref } from "./sttReview";
import { parseBackendTime } from "../time";

export interface FollowupScreenInput extends SessionScreenInput {
  analysis: SessionAnalysisState;
  signals: RiskSignalsState;
  questions: FollowupQuestionsState;
  /** 다음 상담 체크리스트(19절). 없으면(이전 호출부) 메모만 보인다. */
  checklist?: FollowupChecklistState;
  checks: FollowupChecksState;
  state: QuestionUiState & CheckUiState;
  setState: (
    patch:
      | Partial<QuestionUiState & CheckUiState>
      | ((current: QuestionUiState & CheckUiState) => Partial<QuestionUiState & CheckUiState>),
  ) => void;
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
  /** rag 확인 사항이거나 같은 문장의 rag 항목과 합쳐진 메모인가(저장 뒤 새 항목 안내에 쓴다). */
  withRag: boolean;
  /** 항목 머리 칩. 공식 근거 칩은 실제로 붙은 공식 근거가 있을 때만(개수로 센다). */
  chips: string[];
  /** 확인이 필요한 이유(rag). 메모는 빈 문자열. */
  reason: string;
  /** 검토를 통과한 공식 근거(rag). 같은 문장의 메모와 합쳐지면 메모 쪽으로 옮겨 붙는다. */
  sources: SourceView[];
  /** 저장(18.1)할 때 넣을 이번 회차 발화 번호. 메모는 segment_ids, rag 는 이번 회차 사례 근거의 segment_id(합치면 합집합). */
  segmentIds: string[];
  /** 근거가 지난 회차 확정 요약뿐인 메모의 회차 이름('7회차'). rag 는 null. */
  previousLabel: string | null;
  /**
   * 사례 근거가 모두 18.1 저장 값(segmentIds · previousLabel)에 남는가. 메모는 늘 true, rag 는 사례 근거가 모두 이번 회차
   * 발화일 때만 true(앞 회차 · 아이 앱 근거는 18.1 에 남길 칸이 없다). 합친 줄은 모두 true 일 때만 true.
   */
  exact: boolean;
  /** rag 근거 위치(why · href)가 가리키는 이번 회차 발화 번호. 그 발화가 원문에 없으면 위치를 다시 잡는다. 아니면 null. */
  whereSegment: string | null;
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
      withRag: false,
      chips: [],
      reason: "",
      sources: [],
      segmentIds: Array.isArray(point.segment_ids) ? point.segment_ids.filter((id) => typeof id === "string") : [],
      previousLabel: previous || null,
      exact: true,
      whereSegment: null,
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
    const cases = item.basis.filter((basis) => basis && basis.type === "case");
    const current = (basis: (typeof cases)[number]) =>
      basis.session_id === ids.sessionId && typeof basis.segment_id === "string" && basis.segment_id !== "";
    const firstCase = cases[0];
    const chips = ["AI 초안", CHECK_KIND_LABELS[item.kind] ?? "확인"];

    if (item.priority === "high") chips.push("우선");

    rows.push({
      key: `r${index}`,
      text,
      why: where.text,
      href: where.href,
      fromPrevious: false,
      origin: "rag",
      withRag: true,
      chips,
      reason: typeof item.reason === "string" ? item.reason.trim() : "",
      sources,
      // 저장은 그 회차 최신 전사본의 번호만 받는다(18.1). 이번 회차 사례 근거의 발화 번호만 넣는다.
      segmentIds: Array.from(new Set(cases.filter(current).map((basis) => basis.segment_id as string))),
      previousLabel: null,
      exact: cases.every(current),
      whereSegment: firstCase && current(firstCase) ? (firstCase.segment_id as string) : null,
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
 * 순서는 메모 먼저(받은 순서), 그 뒤 rag. 같은 문장(공백 · 문장부호를 빼고 같음)이면 메모를 남기고 rag 쪽 공식 근거를 메모에 붙인다
 * (저장할 발화 번호는 합집합). rag 항목이 하나라도 있으면 메모에 'AI 확인 메모' 칩을 달아 둘을 구분한다. 공식 근거 칩은 여기서 마지막에 센다.
 * 근거 위치(why · href)는 settleCheckItems 가 마지막 번호로 다시 잡는다.
 */
export function mergeCheckItems(memo: FollowupItem[], rag: FollowupItem[]): FollowupItem[] {
  const merged = memo.map((item) => ({
    ...item,
    chips: [...item.chips],
    sources: [...item.sources],
    segmentIds: [...item.segmentIds],
  }));
  const byText = new Map(merged.map((item) => [normalizeCheckText(item.text), item]));
  const extra: FollowupItem[] = [];

  rag.forEach((item) => {
    const same = byText.get(normalizeCheckText(item.text));

    if (same) {
      same.withRag = true;
      // 저장할 번호는 둘의 합집합(메모에 번호가 없어도 rag 의 이번 회차 근거가 남게), 앞 회차 근거가 섞이면 exact 가 아니다.
      same.segmentIds = Array.from(new Set([...same.segmentIds, ...item.segmentIds]));
      same.exact = same.exact && item.exact;
      const seen = new Set(same.sources.map((source) => `${source.label}|${source.excerpt}`));
      item.sources.forEach((source) => {
        if (!seen.has(`${source.label}|${source.excerpt}`)) same.sources.push(source);
      });
      return;
    }

    // 더한 rag 항목도 색인에 넣어 뒤에 오는 같은 문장(rag 끼리)이 한 번만 보이게 한다(#125 교차검증 R2).
    const added = { ...item, chips: [...item.chips], sources: [...item.sources], segmentIds: [...item.segmentIds] };
    extra.push(added);
    byText.set(normalizeCheckText(item.text), added);
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

/**
 * 합친 목록의 발화 번호를 원문(최신 전사본)에 있는 것만 남기고 근거 위치를 남은 번호로 다시 잡는다.
 * 18.1 은 그 회차 최신 전사본의 번호만 받으므로 하나 때문에 목록 전체 저장이 422 로 막히지 않게 하고(#125 재검증 L2),
 * 저장에서 뺀 발화로 가는 링크가 남지 않게 한다(L4). 원문을 못 받았으면(sourceReady false) 번호를 지우지 않는다(서버가 거른다).
 *  - 메모(와 합쳐진 rag): 원문 위치 → 지난 회차 확정 요약 → '근거 위치 없음'(toFollowupItems 와 같은 규칙).
 *  - rag 줄: rag 사례 근거의 위치를 쓰되, 그 위치가 이번 회차 발화인데 원문에 없으면 남은 번호(없으면 '근거 위치 없음')로 바꾼다.
 * 뺀 번호가 하나라도 있으면 exact 를 끈다 — 그 근거는 18.1 값에 남지 않으므로 저장한 뒤에는 rag 표시를 붙이지 않는다(#125 재검증 5 L6).
 */
export function settleCheckItems(
  items: FollowupItem[],
  locate: RiskSignalsState["locate"],
  sourceReady: boolean,
  ids: { caseId?: string | null; sessionId?: string | null },
): FollowupItem[] {
  return items.map((item) => {
    const segmentIds = sourceReady
      ? locate(item.segmentIds).evidence.filter((entry) => entry.found).map((entry) => entry.segmentId)
      : item.segmentIds;
    const exact = item.exact && item.segmentIds.every((id) => segmentIds.includes(id));

    if (item.origin === "rag" && !(sourceReady && item.whereSegment && !segmentIds.includes(item.whereSegment))) {
      return { ...item, segmentIds, exact };
    }

    const located = locate(segmentIds);
    const first = located.evidence[0]?.segmentId ?? null;
    const previous = !first && item.previousLabel ? item.previousLabel : "";

    return {
      ...item,
      segmentIds,
      exact,
      why: located.label || (previous ? `${previous} 확정 요약` : "근거 위치 없음"),
      href: first ? segmentHref(ids, first) : null,
      fromPrevious: Boolean(previous),
      whereSegment: item.origin === "rag" ? first : null,
    };
  });
}

/** 합친 목록(mergeCheckItems) → 18.1 저장 꼴 초안. 모두 source AI 이고 아직 고르지 않음(in_briefing false). */
export function checksFromItems(items: FollowupItem[]): FollowupCheck[] {
  return items.map((item) => ({
    text: item.text,
    source: "AI" as const,
    segment_ids: item.segmentIds,
    edited: false,
    in_briefing: false,
    // 18.1 의 지난 회차 이름은 근거가 지난 회차 확정 요약'뿐'인 메모에만(발화 번호가 있으면 넣지 않는다).
    previous_session_label:
      item.segmentIds.length === 0 && item.previousLabel && /^[0-9]{1,4}회차$/.test(item.previousLabel)
        ? item.previousLabel
        : null,
  }));
}

/** 서버 시각 → 마이크로초(서버는 소수 6자리까지 준다. Date 는 밀리초까지라 나머지를 따로 더한다 — #125 재검증 L3). */
function backendMicros(iso: string): number | null {
  const fraction = /\.(\d+)/.exec(iso)?.[1] ?? "";
  const at = parseBackendTime(iso.replace(/\.\d+/, ""));

  if (!at) return null;

  return at.getTime() * 1000 + Number(`${fraction}000000`.slice(0, 6));
}

/**
 * 저장한 확인 사항(18.1 updated_at)과 지금 체크리스트(19절 completed_at) 중 무엇이 나중인가. 둘 중 하나라도 시각을 모르면 null.
 * 같은 서버 시계라 비교할 수 있다(시간대 표시가 없으면 UTC — parseBackendTime). 같은 시각이면 저장이 나중으로 본다.
 */
export function savedVsMade(
  savedAt: string | null | undefined,
  madeAt: string | null | undefined,
): "saved-later" | "made-later" | null {
  const saved = savedAt ? backendMicros(savedAt) : null;
  const made = madeAt ? backendMicros(madeAt) : null;

  if (saved === null || made === null) return null;

  return saved >= made ? "saved-later" : "made-later";
}

const sameIds = (a: string[], b: string[]): boolean => {
  const left = new Set(a);
  const right = new Set(b);

  return left.size === right.size && Array.from(left).every((id) => right.has(id));
};

/**
 * 확인 사항 줄(18.1 초안 · 저장 목록)에 rag 표시를 붙인다. 상담사가 고치지 않은 AI 줄 중 문장(공백 · 문장부호를 뺀 것)과
 * 근거 발화 번호가 합친 목록의 항목과 같은 줄에만 칩(메모 줄은 rag 와 함께일 때 'AI 확인 메모') · 이유 · 공식 근거를 붙이고,
 * rag 에서 온 줄은 근거 위치도 rag 의 사례 근거로 보인다(앞 회차 근거는 그 회차로 간다). 고친 문장은 검토를 거치지 않았다.
 * merged 는 지금 분석으로 만든 체크리스트만 담는다.
 *
 * 저장한 목록(saved)은 그 줄이 어느 체크리스트에서 왔는지 남기지 않으므로, 목록을 지금 체크리스트가 끝난 뒤에 저장했을 때(order
 * 'saved-later')만 붙인다. 목록을 저장한 뒤 체크리스트를 만들었으면(다시 만들기 · 재분석, 'made-later') 저장한 줄은 저장한 값으로만
 * 보이고 — 같은 문장의 새 결과가 근거를 바꿔 보이지 않게(#125 재검증 M1) — pending 이 목록에 없는 rag 항목(같은 문장으로 메모와
 * 합쳐진 것 포함, M2)을 [목록에 더하기] 로 내놓는다. 저장 뒤 새로 만들지 않았으면 pending 은 없다(고친 rag 원문을 다시 권하지 않는다, L1).
 * 또 저장한 줄은 그 항목의 사례 근거가 모두 18.1 값에 남을 때(exact — 이번 회차 발화뿐)만 붙인다. 앞 회차 · 아이 앱 근거는 18.1 에
 * 남지 않아, 같은 문장 · 같은 번호라도 근거가 바뀌었는지 알 수 없다(메모와 합쳐진 rag 포함 — #125 재검증 4 M1).
 */
export function ragCheckAnnotations(
  merged: FollowupItem[],
  { saved = false, order = null }: { saved?: boolean; order?: "saved-later" | "made-later" | null } = {},
) {
  const byText = new Map(merged.map((item) => [normalizeCheckText(item.text), item]));

  const annotate = (check: FollowupCheck): CheckAnnotation | null => {
    if (check.source !== "AI" || check.edited) return null;
    if (saved && order !== "saved-later") return null;

    const item = byText.get(normalizeCheckText(check.text));

    // 메모 줄도 rag 항목과 함께 보일 때는 'AI 확인 메모' 칩이 붙어 있다(mergeCheckItems) — 둘을 구분하려고 그대로 쓴다.
    if (!item || (item.chips.length === 0 && item.sources.length === 0)) return null;
    // 문장만 같고 근거 발화가 다른 항목에는 붙이지 않는다.
    if (!sameIds(Array.isArray(check.segment_ids) ? check.segment_ids : [], item.segmentIds)) return null;
    // 저장한 줄은 사례 근거가 모두 저장 값에 남는 항목만(앞 회차 · 아이 앱 근거가 섞이면 같은 항목인지 알 수 없다).
    if (saved && !item.exact) return null;

    return {
      chips: item.chips,
      reason: item.reason,
      sources: item.sources,
      ...(item.origin === "rag" ? { why: item.why, href: item.href } : {}),
    };
  };

  const pending = (items: FollowupCheck[]): FollowupCheck[] => {
    if (!saved || order !== "made-later") return [];

    const have = new Set(items.map((check) => normalizeCheckText(check.text)));

    return checksFromItems(merged.filter((item) => item.withRag && !have.has(normalizeCheckText(item.text))));
  };

  return { annotate, pending };
}

/** 체크리스트 확인 사항에 이번 회차 발화 근거가 있는가 — 있으면 원문을 받아 근거 위치를 찾고 없는 번호를 거른다. */
export function checklistNeedsEvidence(
  checklist: FollowupChecklistState["checklist"] | undefined,
  sessionId: string | null | undefined,
): boolean {
  if (!checklist || checklist.status !== "COMPLETED" || !sessionId) return false;

  const items = Array.isArray(checklist.result?.check_items) ? checklist.result.check_items : [];

  return items.some(
    (item) =>
      Array.isArray(item?.basis) &&
      item.basis.some((basis) => basis?.type === "case" && basis.session_id === sessionId && Boolean(basis.segment_id)),
  );
}

/** 다음 상담 체크리스트 상태 줄 · 단추(19절). 꺼져 있으면 모두 비어 있다(화면은 AI 확인 메모만). */
export interface ChecklistView {
  /** 지금 분석으로 만든 결과의 확인 사항. 아니면 []. */
  items: FollowupItem[];
  /** 지금 분석으로 만든 결과의 질문 공식 근거. 아니면 []. */
  questionEvidence: QuestionEvidence[];
  /** 지금 분석으로 만든 결과가 끝난 시각(서버 completed_at). 아니면 null. */
  completedAt: string | null;
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
    completedAt: null,
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
    completedAt: row.completed_at ?? null,
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
  // 저장 전 초안 · 줄 표시에 쓰는 합친 목록(AI 확인 메모 + rag 확인 사항, 메모 먼저 · 같은 문장 한 번).
  // 발화 번호는 원문에 있는 것만 남기고 근거 위치를 다시 잡는다(settleCheckItems — 상담 전 브리핑과 같은 목록).
  const merged = completed
    ? settleCheckItems(
        mergeCheckItems(toFollowupItems(view?.followupCheckPoints ?? [], signals.locate, ids), rag.items),
        signals.locate,
        signals.sourceReady,
        ids,
      )
    : [];
  const withRag = rag.items.length > 0;
  const annotations = ragCheckAnnotations(merged, {
    saved: input.checks.saved,
    order: savedVsMade(input.checks.updatedAt, rag.completedAt),
  });
  const checkCard = checkValues({
    state: input.state,
    setState: input.setState,
    checks: input.checks,
    points: completed ? view?.followupCheckPoints ?? [] : [],
    drafts: completed ? checksFromItems(merged) : [],
    annotate: annotations.annotate,
    pending: annotations.pending(input.checks.items),
    locate: signals.locate,
    ids,
    status,
  });

  let empty = "";

  if (checkCard.checks.length > 0 || input.checks.saved) empty = input.checks.saved && checkCard.checks.length === 0 ? "저장한 확인 사항이 없습니다." : "";
  else if (status === "AI_PROCESSING") empty = "AI 분석 중입니다. 끝나면 확인 메모가 보입니다.";
  else if (!completed) empty = "AI 분석이 끝나면 확인 메모가 보입니다.";
  else empty = "AI 가 남긴 확인 메모가 없습니다. '+ 확인 사항 직접 추가' 로 쓸 수 있습니다.";

  const sessionLabel = input.detail.session?.numberLabel ?? "";

  return {
    ...header,
    chip: withRag ? FOLLOWUP_RAG_CHIP : FOLLOWUP_CHIP,
    checkNote: withRag
      ? "AI 확인 메모와, 공식 근거(매뉴얼 · 체크리스트 · 법령 · 판례)를 함께 본 AI 초안입니다. 아이에게 할 질문이 아니고, 확인할지는 상담원이 정합니다."
      : "AI 가 다음 상담에서 확인해 두면 좋겠다고 남긴 메모입니다. 아이에게 할 질문이 아니고, 확인할지는 상담원이 정합니다.",
    ...checkCard,
    checksEmpty: empty,
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
    // 10/29 디자인: 마지막 단추는 상담 전 브리핑(내담자 정보 탭 안)으로 간다.
    doneHref: briefingHref(ids.caseId ?? null),
    doneLabel: sessionLabel ? `${sessionLabel} 처리 완료 · 브리핑 보기` : "처리 완료 · 브리핑 보기",
  };
}
