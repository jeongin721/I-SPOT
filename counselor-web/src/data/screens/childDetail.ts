// 아이 상세 화면 값(11/09 디자인 '아이 연계 › 아이 상세', 콩콩 앱 서버 값, API_CONTRACT 24절).
//
// 디자인은 매일 체크인 예시지만 콩콩은 상담사가 고른 질문에 아이가 답하는 구조다. 그래서 '최근 답 한 묶음'을 이번 답변으로,
// 같은 질문의 이전 답(최대 3번)을 지난 답변으로 보인다. AI 초안은 서버가 만든 것만 보이고, 추가 질문은 상담사가 승인해야 앱으로 간다.

import type { ChildAppCase, ChildAppEvent } from "../../api/types";
import { URGENT_ALERT_REASONS } from "../useCaseChildApp";

interface AnswerItem {
  question_id: string;
  question: string;
  answer: string;
  level: string;
  wrote_text?: boolean;
  /** 아이가 직접 쓴 글. 이 칸이 생기기 전 답은 없고 answer 만 있다. */
  written?: string;
}

const MAX_PREVIOUS = 3;
const RECENT_DAYS = 21;

export function childDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function itemsOf(event: ChildAppEvent): AnswerItem[] {
  return Array.isArray(event.payload.items) ? (event.payload.items as AnswerItem[]) : [];
}

function nextLabel(next: ChildAppCase["next_consult"]): string {
  if (!next) return "—";
  const [, month, day] = next.date.split("-").map(Number);
  return `${month}/${day}${next.time ? ` ${next.time}` : ""}`;
}

function statusChip(data: ChildAppCase, latest: ChildAppEvent | undefined): { reason: string; rCls: string } {
  if (data.open_alerts.some((alert) => URGENT_ALERT_REASONS.has(alert.reason)) || latest?.level === "RED") {
    return { reason: "긴급", rCls: "chip c-urgent" };
  }
  if (data.open_alerts.length > 0 || latest?.level === "AMBER") return { reason: "확인 필요", rCls: "chip c-check" };
  // 답이 없는 것은 안전하다는 뜻이 아니다(민규 #165 리뷰 3).
  if (!latest) return { reason: "답 없음", rCls: "chip c-normal" };
  return { reason: "정상", rCls: "chip c-normal" };
}

export interface ChildAiActions {
  saveNote: (draftId: string, questionId: string, text: string) => void;
  saveQuestion: (draftId: string, id: string, text: string, options: string[]) => void;
  setApproval: (draftId: string, id: string, approved: boolean) => void;
}

/** 최근 답에 AI 초안이 필요한 항목이 있으면 그 답 묶음의 event id, 아니면 null. */
export function aiDraftNeeded(data: ChildAppCase): string | null {
  if (!data.ai_enabled || data.ai_draft) return null;
  const latest = data.feed.find((event) => event.kind === "ANSWERS");
  return latest && itemsOf(latest).some((item) => item.level === "RED" || item.level === "AMBER") ? latest.id : null;
}

/** 서버 값을 디자인 화면의 값 묶음으로 바꾼다. now 는 시험을 위해 받는다. */
export function childDetailValues(
  data: ChildAppCase,
  info: { name: string; initial: string; caseNumber: string; birthYearLabel: string },
  actions?: ChildAiActions,
  now: number = Date.now(),
) {
  const answered = data.feed.filter((event) => event.kind === "ANSWERS");
  const latest = answered[0];
  const earlier = answered.slice(1);
  const bank = new Map(data.bank.map((item) => [item.id, item]));
  const lastLabel = childDateTime(data.last_response_at);
  const recent = answered.filter((event) => now - new Date(event.created_at).getTime() <= RECENT_DAYS * 86400000).length;

  const previousOf = (questionId: string): string[] =>
    earlier
      .flatMap((event) => itemsOf(event).filter((item) => item.question_id === questionId))
      .slice(0, MAX_PREVIOUS)
      .map((item) => item.answer)
      .reverse();

  const rows = latest
    ? itemsOf(latest).map((item) => ({
        item,
        category: bank.get(item.question_id)?.category ?? "",
        question: bank.get(item.question_id)?.text ?? item.question,
        previous: previousOf(item.question_id),
        flagged: item.level === "RED" || item.level === "AMBER",
      }))
    : [];

  const writtenEvent = answered.find((event) => itemsOf(event).some((item) => item.wrote_text));
  const writtenItem = writtenEvent ? itemsOf(writtenEvent).find((item) => item.wrote_text) : undefined;

  const draft = data.ai_draft && latest && data.ai_draft.event_id === latest.id ? data.ai_draft : null;
  const flaggedRows = rows.filter((row) => row.flagged);
  const draftItems = flaggedRows.map((row) => draft?.items.find((item) => item.question_id === row.item.question_id) ?? null);
  const aiQuestions = draftItems.flatMap((item, index) =>
    (item?.questions ?? []).map((question) => ({
      id: "추가",
      text: question.text,
      opts: question.options,
      why: `${flaggedRows[index].category || "이번"} 답변`,
      edited: question.edited,
      approved: question.approved,
      sendNote: question.answered ? "아이가 답함" : "앱으로 보냄",
      setApproved: (next: boolean) => {
        if (draft) actions?.setApproval(draft.id, question.id, next);
      },
      save: (text: string, options: string[]) => {
        if (draft) actions?.saveQuestion(draft.id, question.id, text, options);
      },
      flagIndex: index,
    })),
  );

  return {
    name: info.name,
    short: info.name,
    short0: info.initial,
    age: info.birthYearLabel,
    types: "",
    id: info.caseNumber,
    ...statusChip(data, latest),
    last: lastLabel,
    count: `응답 ${recent}번`,
    next: nextLabel(data.next_consult),
    quote: writtenItem ? writtenItem.written ?? writtenItem.answer : "",
    quoteAt: writtenEvent ? childDateTime(writtenEvent.created_at) : "",
    prevLabel: "지난 답변 (오래된 순)",
    flowLabel: "이전 → 이번",
    answers: rows.map((row) => [
      row.category,
      row.question,
      row.item.answer,
      row.flagged,
      row.previous,
      row.item.level === "RED" ? "바로 확인" : "확인 필요",
    ]),
    flags: rows
      .filter((row) => row.flagged)
      .map((row) => ({
        q: row.category ? `${row.question} (${row.category})` : row.question,
        flow: [...row.previous, row.item.answer],
        src: `${childDateTime(latest?.created_at)} 응답`,
        qi: aiQuestions.flatMap((question, questionIndex) =>
          question.flagIndex === flaggedRows.indexOf(row) ? [questionIndex] : [],
        ),
      })),
    notes: draftItems.map((item) =>
      item
        ? {
            text: item.note,
            edited: item.note_edited,
            save: (text: string) => {
              if (draft) actions?.saveNote(draft.id, item.question_id, text);
            },
          }
        : null,
    ),
    qs: aiQuestions,
  };
}
