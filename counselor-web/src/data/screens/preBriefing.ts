// 사례 상세 탭 3 · 상담 전 브리핑(PreBriefing) 화면 값. 10/27 디자인(counselor-design/screens/PreBriefing.dc.html)의 칸에
// 서버 값을 넣는다. 머리 · 탭은 caseHeaderValues, 값은 분석이 끝난 가장 최근 회차(useCaseSignals)에서 온다.
//
// 디자인 칸 → 서버 값:
//  - 제목 위 줄('오늘 16:00 · 9회차 정기상담 · 면담실 B'): 다음 회차 번호(지금 회차 수 + 1)만 안다. 상담 일시 · 유형 · 장소는
//    일정 기능이 서버에 없어 '—'.
//  - 먼저 볼 것: '아이가 보낸 말' · '체크인 응답 변화' 는 아이 앱이, '처음 나온 이야기' 는 회차 간 비교 값이 서버에 없어
//    준비 중이다(예시 문장을 보이지 않는다).
//  - 확인할 사항(AI 초안): 그 회차의 followup_check_points(AI 확인 메모)에 다음 상담 체크리스트(19절)의 확인 사항을 합친 목록
//    (4 · 추가 확인 화면과 같은 mergeCheckItems)을 읽기 전용으로.
//    근거는 '그 회차 · 몇 분 · 누구' 이고 누르면 STT 검수의 그 발화로 간다. 디자인의 체크(브리핑에 넣기)는 저장할 API 가
//    없어 두지 않는다(가짜 체크 없음).
//  - 추가 질문: 그 회차에서 상담사가 승인한 질문 목록(GET …/followup-questions, 18절)을 디자인의 줄(.rq)로 보인다.
//    승인 전 AI 초안은 보이지 않는다. '질문 수정' 은 그 회차의 4 · 추가 확인 화면으로 간다.
//  - 인쇄 · PDF: 브라우저 인쇄(window.print)로 지금 화면을 그대로 인쇄한다.

import type { CaseDetailState } from "../useCaseDetail";
import type { AuthSession } from "../useAuthSession";
import type { CaseSignalsState } from "../useCaseSignals";
import type { FollowupChecklistState } from "../useFollowupChecklist";
import type { FollowupQuestionsState } from "../useFollowupQuestions";
import { NOT_PROVIDED } from "../caseRows";
import { caseHeaderValues } from "./caseDetail";
import { NOT_READY } from "./common";
import { checklistValues, mergeCheckItems, toFollowupItems } from "./followupQ";
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
  const checks = completed
    ? mergeCheckItems(toFollowupItems(view.followupCheckPoints ?? [], signals.signals.locate, ids), rag.items).map(
        (item) => ({
          key: item.key,
          text: item.text,
          // rag 근거 위치는 이미 '8회차 01:08' 처럼 회차가 붙어 있다.
          why: item.fromPrevious || item.origin === "rag" ? item.why : `${source?.numberLabel ?? ""} ${item.why}`.trim(),
          href: item.href,
        }),
      )
    : [];

  let checksNote = "";
  if (!source) checksNote = info ? "AI 분석이 끝난 회차가 없습니다. 회차를 분석하면 확인할 사항이 생깁니다." : "";
  else if (signals.analysis.error) checksNote = signals.analysis.error;
  else if (!completed) checksNote = "확인할 사항을 불러오는 중…";
  else if (checks.length === 0) checksNote = `${source.numberLabel} AI 분석에 확인 메모가 없습니다.`;
  else checksNote = `${source.numberLabel} AI 분석의 확인 메모입니다. 아이에게 할 질문이 아니고, 확인할지는 상담원이 정합니다.`;

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
      { key: "child", title: "아이가 보낸 말", note: `${NOT_READY} · 아이 앱이 서버에 없음` },
      { key: "checkin", title: "체크인 응답 변화", note: `${NOT_READY} · 아이 앱 체크인이 서버에 없음` },
      { key: "first", title: "처음 나온 이야기", note: `${NOT_READY} · 회차 간 비교 값이 서버에 없음` },
    ],
    checks,
    checksNote,
    checksError: completed ? signals.signals.evidenceError : null,
    questions,
    questionNote,
    questionHref: source ? screenHref("/FollowupQ", ids) : null,
    print: () => window.print(),
  };
}
