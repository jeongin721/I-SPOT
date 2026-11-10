// 사례 상세 탭 3 · 상담 전 브리핑(PreBriefing) 화면 값. 10/27 디자인(counselor-design/screens/PreBriefing.dc.html)의 칸에
// 서버 값을 넣는다. 머리 · 탭은 caseHeaderValues, 값은 분석이 끝난 가장 최근 회차(useCaseSignals)에서 온다.
//
// 디자인 칸 → 서버 값:
//  - 제목 위 줄('오늘 16:00 · 9회차 정기상담 · 면담실 B'): 다음 회차 번호(지금 회차 수 + 1)만 안다. 상담 일시 · 유형 · 장소는
//    일정 기능이 서버에 없어 '—'.
//  - 먼저 볼 것: '아이가 보낸 말'(가장 최근 아이가 쓴 글) · '체크인 응답 변화'(가장 최근 답에서 지난번과 달라진 답)는
//    콩콩 아이 앱 값이다(11/10 연결, childAppHighlights). 담당 상담사만 보인다.
//    '처음 나온 이야기'(2026-10-29)는 분석이 끝난 가장 최근 회차의 대화 주제 중 앞 회차들에 없던 것(signal-history topics,
//    signalHistoryRows.newTopicsIn) — 주제 · 그 첫 아동 발화 · 회차와 시각. AI 제안이다.
//  - 확인할 사항: 그 회차 확인 사항을 저장했으면(18.1절, 2026-10-30) '브리핑에 넣기' 로 체크한 것만, 저장 전이면
//    AI 확인 메모 초안에 다음 상담 체크리스트(19절)의 확인 사항을 합친 목록(4 · 다음 상담 준비 화면과 같은 mergeCheckItems)을
//    읽기 전용으로. 저장한 줄 중 rag 에서 온 것(고치지 않음)은 목록을 지금 체크리스트가 끝난 뒤에 저장했을 때만 근거 위치를
//    rag 의 사례 근거로 보인다(아니면 저장한 발화 번호로 — ragCheckAnnotations).
//    근거는 '그 회차 · 몇 분 · 누구' 이고 누르면 STT 검수의 그 발화로 간다. 디자인의 체크(브리핑에 넣기)는 저장할 API 가
//    없어 두지 않는다(가짜 체크 없음).
//  - 추가 질문: 그 회차에서 상담사가 승인한 질문 목록(GET …/followup-questions, 18절)을 디자인의 줄(.rq)로 보인다.
//    승인 전 AI 초안은 보이지 않는다. '질문 수정' 은 그 회차의 4 · 추가 확인 화면으로 간다.
//  - 인쇄 · PDF: 브라우저 인쇄(window.print)로 지금 화면을 그대로 인쇄한다.

import type { ChildAppCase } from "../../api/types";
import { childAppHighlights } from "./childDetail";
import type { CaseDetailState } from "../useCaseDetail";
import type { AuthSession } from "../useAuthSession";
import type { CaseSignalsState } from "../useCaseSignals";
import type { FollowupChecklistState } from "../useFollowupChecklist";
import type { FollowupChecksState } from "../useFollowupChecks";
import type { FollowupQuestionsState } from "../useFollowupQuestions";
import type { SignalHistoryState } from "../useSignalHistory";
import { newTopicsIn } from "../signalHistoryRows";
import { formatClock } from "../time";
import { NOT_PROVIDED } from "../caseRows";
import { caseHeaderValues } from "./caseDetail";
import { NOT_READY } from "./common";
import {
  checklistValues,
  mergeCheckItems,
  ragCheckAnnotations,
  savedVsMade,
  settleCheckItems,
  toFollowupItems,
} from "./followupQ";
import { questionChip } from "./followupQuestions";
import { screenHref } from "./links";

export interface BriefingScreenInput {
  session: AuthSession;
  detail: CaseDetailState;
  caseId: string | null;
  signals: CaseSignalsState;
  /** 값을 가져온 회차(signals.session)의 승인한 추가 질문. */
  questions: FollowupQuestionsState;
  /** 값을 가져온 회차의 다음 상담 체크리스트(19절). 없으면 메모만. */
  checklist?: FollowupChecklistState;
  /** 사례 신호 이력(대화 주제). 없으면 '처음 나온 이야기' 는 준비 중으로 둔다. */
  history?: SignalHistoryState;
  /** 그 회차(signals.session)의 저장한 확인 사항(18.1절). 저장했으면 '브리핑에 넣기' 로 체크한 것만 보인다. */
  checks?: FollowupChecksState;
  /** 콩콩 아이 앱(GET /cases/{id}/child-app). 꺼져 있거나 못 받았으면 null. */
  childApp?: ChildAppCase | null;
}

export interface FirstCard {
  key: string;
  title: string;
  /** 칸이 비었을 때의 안내(값이 있으면 ''). */
  note: string;
  /** 디자인 lead-q(주제) · lead-main(발화) · src(근거 위치). */
  q?: string;
  main?: string;
  src?: string;
}

/** '아이가 보낸 말' · '체크인 응답 변화' 카드(콩콩). */
function childAppCards(app: ChildAppCase | null | undefined): FirstCard[] {
  const child = { key: "child", title: "아이가 보낸 말" };
  const checkin = { key: "checkin", title: "체크인 응답 변화" };
  if (app === undefined || app === null) return [{ ...child, note: `${NOT_READY} · 아이 앱이 꺼져 있음` }, { ...checkin, note: `${NOT_READY} · 아이 앱이 꺼져 있음` }];
  const found = childAppHighlights(app);
  if (!found) return [{ ...child, note: "담당 상담사만 볼 수 있어요." }, { ...checkin, note: "담당 상담사만 볼 수 있어요." }];
  if (!found.linked && found.answeredCount === 0) {
    return [{ ...child, note: "아이 앱이 연결되지 않았어요." }, { ...checkin, note: "아이 앱이 연결되지 않았어요." }];
  }
  const first = found.changes[0];
  return [
    found.written
      ? { ...child, note: "", main: `"${found.written.text}"`, src: `${found.written.at} · 아이 앱` }
      : { ...child, note: "아이가 쓴 글이 아직 없어요." },
    first
      ? {
          ...checkin,
          note: "",
          q: `${first.question}${found.changes.length > 1 ? ` 외 ${found.changes.length - 1}개` : ""}`,
          main: `${first.from} → ${first.to}`,
          src: `${found.changedAt} 응답 · 아이 앱`,
        }
      : { ...checkin, note: found.answeredCount ? "지난번과 달라진 답이 없어요." : "아직 받은 답이 없어요." },
  ];
}

/** '처음 나온 이야기' 카드. */
function firstStoryCard(source: { id: string } | null, history: SignalHistoryState | undefined): FirstCard {
  const base = { key: "first", title: "처음 나온 이야기" };

  if (!history) return { ...base, note: `${NOT_READY} · 회차 간 비교 값이 서버에 없음` };
  if (history.error) return { ...base, note: history.error };
  if (!history.loaded) return { ...base, note: history.loading ? "불러오는 중…" : "" };
  if (!source) return { ...base, note: "AI 분석이 끝난 회차가 없습니다." };

  const found = newTopicsIn(history.sessions, source.id);
  if (!found.tagged) return { ...base, note: "이 회차에는 AI 주제 분류가 없습니다(이 기능 전 분석이거나 분류 실패)." };
  if (found.skipped > 0)
    return { ...base, note: `앞 회차 중 ${found.skipped}개는 주제 분류가 없어 처음 나온 이야기인지 비교할 수 없습니다.` };
  if (!found.comparable) return { ...base, note: "주제 분류가 있는 앞 회차가 없어 비교할 수 없습니다." };
  if (found.items.length === 0) return { ...base, note: "앞 회차에 없던 주제가 없습니다." };

  const item = found.items[0];
  const more = found.items.length > 1 ? ` 외 ${found.items.length - 1}개` : "";
  const at = [`${item.sessionNumber}회차`, formatClock(item.startMs)].filter(Boolean).join(" ");

  return {
    ...base,
    note: "",
    q: `${item.topic}${more}`,
    main: item.quote ? `"${item.quote}"` : item.topic,
    src: `${at} · AI 제안`,
  };
}

export function preBriefingValues(input: BriefingScreenInput) {
  const { detail, signals } = input;
  const header = caseHeaderValues(input);
  const info = detail.caseInfo;
  const source = signals.session;
  const view = signals.analysis.analysis;
  const completed = view !== null && view.status === "COMPLETED";
  const ids = source ? { caseId: source.caseId, sessionId: source.id } : { caseId: input.caseId };

  const rag = checklistValues(input.checklist, view, completed, ids);
  // 다음 상담 준비 화면과 같은 목록 · 같은 발화 번호(원문에 없는 번호를 빼고 위치를 다시 잡음 — settleCheckItems).
  const merged = completed
    ? settleCheckItems(
        mergeCheckItems(toFollowupItems(view.followupCheckPoints ?? [], signals.signals.locate, ids), rag.items),
        signals.signals.locate,
        signals.signals.sourceReady,
        ids,
      )
    : [];
  // 저장한 줄의 rag 표시는 목록을 지금 체크리스트가 끝난 뒤에 저장했을 때만(다음 상담 준비 화면과 같은 규칙, #125 재검증 M1).
  const { annotate } = ragCheckAnnotations(merged, {
    saved: Boolean(input.checks?.saved),
    order: savedVsMade(input.checks?.updatedAt, rag.completedAt),
  });
  const prefixed = (why: string) => `${source?.numberLabel ?? ""} ${why}`.trim();
  // 확인 사항을 저장했으면(18.1절) 그중 '브리핑에 넣기' 로 체크한 것만, 저장 전이면 AI 확인 메모 + rag 확인 사항 초안(2026-10-30).
  const savedChecks = source && input.checks?.saved ? input.checks.items.filter((item) => item.in_briefing) : null;
  const checks = savedChecks
    ? toFollowupItems(
        savedChecks.map((item) => ({
          text: item.text,
          segment_ids: item.segment_ids,
          previous_session_label: item.previous_session_label ?? undefined,
        })),
        signals.signals.locate,
        ids,
      ).map((item, index) => {
        const extra = annotate(savedChecks[index]);

        return {
          key: item.key,
          text: item.text,
          why: extra?.why ?? (item.fromPrevious ? item.why : prefixed(item.why)),
          href: extra && extra.why !== undefined ? extra.href ?? null : item.href,
          rag: Boolean(extra),
        };
      })
    : merged.map((item) => ({
        key: item.key,
        text: item.text,
        // rag 근거 위치는 이미 '8회차 01:08' 처럼 회차가 붙어 있다.
        why: item.fromPrevious || item.origin === "rag" ? item.why : prefixed(item.why),
        href: item.href,
        rag: item.origin === "rag" || item.sources.length > 0,
      }));

  let checksNote = "";
  if (!source && signals.truncated) checksNote = `최근 ${signals.shownCount}회차 안에 AI 분석이 끝난 회차가 없습니다.`;
  else if (!source) checksNote = info ? "AI 분석이 끝난 회차가 없습니다. 회차를 분석하면 확인할 사항이 생깁니다." : "";
  else if (signals.analysis.error) checksNote = signals.analysis.error;
  else if (!completed) checksNote = "확인할 사항을 불러오는 중…";
  else if (savedChecks && checks.length === 0)
    checksNote = `${source.numberLabel}에서 브리핑에 넣기로 체크한 확인 사항이 없습니다. '다음 상담 준비' 에서 체크해 주세요.`;
  else if (savedChecks) checksNote = `${source.numberLabel} '다음 상담 준비' 에서 브리핑에 넣기로 체크한 확인 사항입니다.`;
  else if (checks.length === 0) checksNote = `${source.numberLabel} AI 분석에 확인 메모가 없습니다.`;
  else if (checks.some((item) => item.rag))
    checksNote = `${source.numberLabel} AI 확인 메모와 공식 근거를 함께 본 AI 초안입니다(아직 고르지 않음). '다음 상담 준비' 에서 체크한 것만 브리핑에 남길 수 있습니다.`;
  else
    checksNote = `${source.numberLabel} AI 분석의 확인 메모입니다(아직 고르지 않음). '다음 상담 준비' 에서 체크한 것만 브리핑에 남길 수 있습니다.`;

  const questions = source
    ? input.questions.questions.map((question, index) => ({
        key: `${index}-${question.approved_at}`,
        chip: questionChip(question),
        text: question.text,
      }))
    : [];

  let questionNote = "";
  if (!source) questionNote = "";
  else if (input.questions.loadError) questionNote = input.questions.loadError;
  else if (!input.questions.loaded) questionNote = "추가 질문을 불러오는 중…";
  else if (questions.length === 0) questionNote = `${source.numberLabel}에 승인한 추가 질문이 없습니다. '질문 수정' 에서 승인해 주세요.`;

  const nextNumber = info ? `${info.sessionCount + 1}회차` : "";

  return {
    ...header,
    lead: info ? `다음 상담 ${nextNumber} · 상담 일시 ${NOT_PROVIDED}` : "",
    firstCards: [
      ...childAppCards(input.childApp),
      firstStoryCard(source, input.history),
    ] as FirstCard[],
    checks,
    checksNote,
    checksError: completed ? signals.signals.evidenceError : null,
    questions,
    questionNote,
    questionHref: source ? screenHref("/FollowupQ", ids) : null,
    print: () => window.print(),
  };
}
