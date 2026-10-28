// 4 · 추가 확인 · 질문 > '추가 질문' 칸 값(10/27 디자인 FollowupQ.dc.html 의 추가 질문 카드 · 승인 · 수정 · 직접 추가).
//
// 카드는 세 곳에서 온다.
//  - AI 초안: 분석 결과 followup_questions(#100 C-1 모듈 전에는 늘 비어 있다). 서버에 승인한 같은 질문이 있으면 '승인됨'.
//    고쳐서 승인한 질문은 문장이 달라 근거 번호(segment_ids) · 종류가 같은 것으로 짝짓는다('상담사 수정').
//  - 승인 목록(GET /sessions/{id}/followup-questions)에서 짝이 없는 질문: 상담사가 직접 쓴 질문 등. 모두 '승인됨'.
//  - 이 화면에서 쓰거나 고친 뒤 아직 승인하지 않은 질문: 화면 상태에만 있다(서버는 승인한 질문만 받는다).
// 디자인처럼 [승인] 을 누르면 승인 목록에 더해 저장하고, 다시 누르면 빼서 저장한다. [수정] → [확인] 에서 문장이 바뀐 승인 질문은
// 승인을 풀고(디자인 qOk), 새로 쓴 질문은 승인 전 카드로 더한다. 승인 목록이 바뀌었을 때만 PUT 한다.
// '아이 앱으로 먼저' 탭은 아이 앱 발송이 서버에 없어 준비 중이다(예시 질문을 보이지 않는다).

import type { FollowupQuestion, FollowupQuestionDraft, FollowupQuestionInput } from "../../api/types";
import type { FollowupQuestionsState } from "../useFollowupQuestions";
import type { RiskSignalsState } from "../useRiskSignals";
import { NOT_READY } from "./common";
import { segmentHref } from "./sttReview";

export type QuestionTab = "meet" | "app";

/** 승인 전 직접 쓴 · 고친 질문(화면 상태). */
export interface LocalQuestion {
  id: number;
  input: FollowupQuestionInput;
  edited: boolean;
}

export interface QuestionUiState {
  qTab: QuestionTab;
  qEditing: boolean;
  /** 수정 중인 카드 문장(카드 key → 문장). */
  qDraft: Record<string, string>;
  /** 수정 중 새로 쓰는 질문들. */
  qNew: string[];
  /** 승인 전 AI 초안을 고친 문장(카드 key → 문장). */
  localEdits: Record<string, string>;
  localExtras: LocalQuestion[];
  nextLocalId: number;
  /** 저장할 수 없어 [승인] · [확인] 이 멈췄을 때의 안내. 다음 동작에서 지운다. */
  qNotice: string | null;
}

export function initialQuestionState(): QuestionUiState {
  return { qTab: "meet", qEditing: false, qDraft: {}, qNew: [], localEdits: {}, localExtras: [], nextLocalId: 1, qNotice: null };
}

type Patch = Partial<QuestionUiState> | ((current: QuestionUiState) => Partial<QuestionUiState>);

export interface QuestionInput {
  state: QuestionUiState;
  setState: (patch: Patch) => void;
  drafts: FollowupQuestionDraft[];
  saved: FollowupQuestionsState;
  locate: RiskSignalsState["locate"];
  ids: { caseId?: string | null; sessionId?: string | null };
  /** "8회차". 근거 앞에 붙인다(디자인 '8회차 01:08'). */
  sessionLabel: string;
  /** 회차 상태가 저장을 받는가(원문 확정 뒤 · AI 분석 중 아님). 아니면 그 이유. */
  blockedReason: string | null;
}

/** 카드 하나(내부 모양). */
export interface QuestionCard {
  key: string;
  origin: "draft" | "saved" | "local";
  input: FollowupQuestionInput;
  approved: boolean;
  edited: boolean;
  /** origin=saved 면 승인 목록에서의 자리. */
  savedIndex: number | null;
  localId: number | null;
}

const sameIds = (a: string[], b: string[]) => a.length === b.length && a.every((id, index) => id === b[index]);

function draftInput(draft: FollowupQuestionDraft): FollowupQuestionInput {
  return {
    text: draft.text.trim(),
    kind: draft.kind === "BANK" ? "BANK" : "OPEN",
    source: "AI",
    segment_ids: Array.isArray(draft.segment_ids) ? draft.segment_ids : [],
    bank_code: draft.kind === "BANK" ? draft.bank_code ?? null : null,
  };
}

function savedInput(item: FollowupQuestion): FollowupQuestionInput {
  return { text: item.text, kind: item.kind, source: item.source, segment_ids: item.segment_ids, bank_code: item.bank_code };
}

/** AI 초안 · 승인 목록 · 화면에서 쓴 질문을 카드 목록으로 모은다. */
export function buildQuestionCards(
  drafts: FollowupQuestionDraft[],
  saved: FollowupQuestion[],
  state: Pick<QuestionUiState, "localEdits" | "localExtras">,
): QuestionCard[] {
  const used = new Set<number>();
  const cards: QuestionCard[] = [];

  drafts.forEach((draft, index) => {
    if (!draft || typeof draft.text !== "string" || !draft.text.trim()) return;

    const key = `ai-${index}`;
    const input = draftInput(draft);
    const pick = (match: (item: FollowupQuestion) => boolean) =>
      saved.findIndex((item, at) => !used.has(at) && item.source === "AI" && match(item));
    let at = pick((item) => item.text === input.text);
    let edited = false;

    if (at < 0) {
      at = pick((item) => item.kind === input.kind && input.segment_ids.length > 0 && sameIds(item.segment_ids, input.segment_ids));
      edited = at >= 0;
    }

    if (at >= 0) {
      used.add(at);
      cards.push({ key, origin: "draft", input: savedInput(saved[at]), approved: true, edited, savedIndex: at, localId: null });
      return;
    }

    const local = state.localEdits[key];
    cards.push({
      key,
      origin: "draft",
      input: local !== undefined ? { ...input, text: local } : input,
      approved: false,
      edited: local !== undefined,
      savedIndex: null,
      localId: null,
    });
  });

  saved.forEach((item, at) => {
    if (used.has(at)) return;

    cards.push({ key: `s-${at}-${item.approved_at}`, origin: "saved", input: savedInput(item), approved: true, edited: false, savedIndex: at, localId: null });
  });

  state.localExtras.forEach((local) => {
    cards.push({ key: `x-${local.id}`, origin: "local", input: local.input, approved: false, edited: local.edited, savedIndex: null, localId: local.id });
  });

  return cards;
}

/** 카드 머리 칩(디자인 q.id): 열린 질문 · 질문 은행 코드 · 직접 작성. */
export function questionChip(input: FollowupQuestionInput): string {
  if (input.source === "COUNSELOR") return "직접 작성";
  if (input.kind === "BANK") return input.bank_code || "질문 은행";
  return "열린 질문";
}

export function questionValues(input: QuestionInput) {
  const { state, setState, drafts, saved, locate, ids, sessionLabel, blockedReason } = input;
  const cards = buildQuestionCards(drafts, saved.questions, state);
  const savedInputs = saved.questions.map(savedInput);
  const canSave = saved.loaded && !saved.loadError && !saved.submitting && !blockedReason;
  // 저장할 수 없을 때 조용히 멈추지 않고 이유를 보인다(민규 #113 리뷰).
  const cannotSave = () =>
    setState({
      qNotice:
        blockedReason ??
        saved.loadError ??
        (saved.submitting ? "저장 중입니다. 잠시 뒤 다시 눌러 주세요." : "추가 질문을 불러온 뒤 다시 눌러 주세요."),
    });

  const why = (card: QuestionCard) => {
    if (card.input.source === "COUNSELOR" && card.input.segment_ids.length === 0) return { text: "상담사 직접 추가", href: null };

    const located = locate(card.input.segment_ids);
    const first = located.evidence[0]?.segmentId ?? null;

    if (!located.label) return { text: "근거 위치 없음", href: null };

    return { text: `${sessionLabel} ${located.label}`.trim(), href: first ? segmentHref(ids, first) : null };
  };

  const approve = (card: QuestionCard) => {
    if (!canSave) {
      cannotSave();
      return;
    }

    setState({ qNotice: null });

    if (card.approved && card.savedIndex !== null) {
      const next = savedInputs.filter((_, at) => at !== card.savedIndex);
      void saved.save(next).then((ok) => {
        if (!ok) return;
        // 승인을 풀어도 카드는 승인 전으로 남긴다(디자인 토글).
        if (card.origin === "saved") {
          setState((current) => ({
            localExtras: [...current.localExtras, { id: current.nextLocalId, input: card.input, edited: false }],
            nextLocalId: current.nextLocalId + 1,
          }));
        } else if (card.edited) {
          setState((current) => ({ localEdits: { ...current.localEdits, [card.key]: card.input.text } }));
        }
      });
      return;
    }

    void saved.save([...savedInputs, card.input]).then((ok) => {
      if (!ok) return;
      setState((current) => {
        const localEdits = { ...current.localEdits };
        delete localEdits[card.key];
        return { localEdits, localExtras: current.localExtras.filter((local) => local.id !== card.localId) };
      });
    });
  };

  const meetCards = cards.map((card) => {
    const where = why(card);
    return {
      key: card.key,
      id: questionChip(card.input),
      why: where.text,
      whyHref: where.href,
      text: card.input.text,
      ok: card.approved,
      st: "승인됨",
      // 승인 전 AI 초안은 'AI 초안' 칩을 단다(18절 표현 주의 · 05_RULES — AI 결과는 AI 표시).
      aiDraft: card.origin === "draft" && !card.approved,
      edited: card.edited,
      okCls: card.approved ? "btn-p" : "btn-s",
      okLabel: card.approved ? "승인됨 ✓" : "승인",
      draftText: state.qDraft[card.key] ?? "",
      approve: () => approve(card),
      setText: (value: string) => setState((current) => ({ qDraft: { ...current.qDraft, [card.key]: value } })),
    };
  });

  const draftAll = () => Object.fromEntries(cards.map((card) => [card.key, card.input.text]));

  const startQ = () => setState({ qEditing: true, qDraft: draftAll(), qNew: [], qNotice: null });

  const addQ = () =>
    setState((current) => ({
      qEditing: true,
      qDraft: current.qEditing ? current.qDraft : draftAll(),
      qNew: [...(current.qEditing ? current.qNew : []), ""],
    }));

  const qCancel = () => setState({ qEditing: false, qDraft: {}, qNew: [], qNotice: null });

  const qOk = () => {
    const localEdits = { ...state.localEdits };
    let localExtras = state.localExtras.slice();
    let nextLocalId = state.nextLocalId;
    const removeSaved = new Set<number>();

    cards.forEach((card) => {
      const text = (state.qDraft[card.key] ?? "").trim();

      if (!text || text === card.input.text) return;

      if (card.approved && card.savedIndex !== null) {
        // 문장을 고친 승인 질문은 승인을 푼다(디자인 qOk).
        removeSaved.add(card.savedIndex);

        if (card.origin === "draft") localEdits[card.key] = text;
        else localExtras.push({ id: nextLocalId++, input: { ...card.input, text }, edited: true });
      } else if (card.origin === "draft") {
        localEdits[card.key] = text;
      } else if (card.localId !== null) {
        localExtras = localExtras.map((local) =>
          local.id === card.localId ? { ...local, input: { ...local.input, text }, edited: true } : local,
        );
      }
    });

    state.qNew
      .map((text) => text.trim())
      .filter(Boolean)
      .forEach((text) => {
        localExtras.push({
          id: nextLocalId++,
          input: { text, kind: "OPEN", source: "COUNSELOR", segment_ids: [], bank_code: null },
          edited: false,
        });
      });

    const apply = () =>
      setState({ localEdits, localExtras, nextLocalId, qEditing: false, qDraft: {}, qNew: [], qNotice: null });

    if (removeSaved.size === 0) {
      apply();
      return;
    }

    // 승인한 질문을 고쳐 승인을 풀어야 하는데 저장할 수 없으면 수정 모드를 그대로 두고 이유를 보인다.
    if (!canSave) {
      cannotSave();
      return;
    }

    void saved.save(savedInputs.filter((_, at) => !removeSaved.has(at))).then((ok) => {
      if (ok) apply();
    });
  };

  const isMeet = state.qTab === "meet";

  let qNote = "";
  if (!isMeet) qNote = `아이 앱으로 먼저 보내기는 ${NOT_READY}입니다(아이 앱 발송이 서버에 없음).`;
  else if (saved.loading && !saved.loaded) qNote = "추가 질문을 불러오는 중…";
  else if (blockedReason) qNote = blockedReason;
  else if (cards.length === 0) qNote = "AI 추가 질문 초안이 없습니다. '+ 질문 직접 추가' 로 질문을 쓰고 승인해 주세요.";

  return {
    qs: isMeet ? meetCards : [],
    qNewRows: isMeet
      ? state.qNew.map((text, index) => ({
          key: `n-${index}`,
          text,
          setText: (value: string) =>
            setState((current) => ({ qNew: current.qNew.map((row, at) => (at === index ? value : row)) })),
        }))
      : [],
    qIsEdit: state.qEditing,
    qNotEdit: !state.qEditing,
    qActions: isMeet,
    addQ,
    startQ,
    qOk,
    qCancel,
    qNote,
    qError: saved.error ?? state.qNotice,
    qSaving: saved.submitting,
    meetCls: isMeet ? "on" : "",
    appCls: isMeet ? "" : "on",
    showMeet: () => setState({ qTab: "meet", qNotice: null }),
    showApp: () => setState({ qTab: "app", qEditing: false, qDraft: {}, qNew: [], qNotice: null }),
  };
}
