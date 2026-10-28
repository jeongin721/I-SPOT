// 법령 · 매뉴얼(LawGuide) 화면 값(10/27 디자인 counselor-design/screens/LawGuide.dc.html).
//
//  - 'AI에게 묻기' 는 POST /law-guide/questions(useLawGuide, API_CONTRACT 17절)에 붙는다. 디자인의 키워드 답변(예시)
//    대신 서버 답변을 보이고, 근거 조문은 '아동복지법 제17조 ↗' 칩(국가법령정보센터 조문 링크)으로 단다.
//    입력칸 글(draft)은 화면 상태, 말풍선 목록 · 기다림(pending)은 훅이 든다. 서버는 질문 · 답변을 저장하지 않는다.
//  - '업무 단계별 참고사항 · 주요 조문' 은 lawGuideRefs.ts 의 정리 문구를 그대로 보인다(서버 값 아님, 디자인 초안 문구).
//    펼침(open) · 분류(filter)는 화면 상태다. '매뉴얼 목차' 를 누르면 목차 항목을 펼치고 그 줄로 한 번 스크롤한다(scrollTo).
//  - '원문보기' · 원문 자료 링크는 국가법령정보센터(www.law.go.kr)로 간다.

import type { LawSource, ManualSource } from "../../api/types";
import { QUESTION_MAX, type LawGuideState } from "../useLawGuide";
import { LAW_GUIDE_REFS, LAW_SOURCES, type LawGuideRef, type LawKey } from "./lawGuideRefs";

export type LawGuideFilter = "all" | "step" | "cw" | "cp";

export interface LawGuideUiState {
  /** 펼친 항목(id → true). 처음엔 디자인대로 '신고접수 시 파악할 정보' 만 펼친다. */
  open: Record<string, boolean>;
  filter: LawGuideFilter;
  /** '매뉴얼 목차' 를 눌러 펼친 항목으로 한 번 스크롤할 DOM id. 화면이 스크롤한 뒤 clearScroll 로 비운다. */
  scrollTo: string | null;
  /** 질문 입력칸 글. */
  draft: string;
}

export function initialLawGuideState(): LawGuideUiState {
  return { open: { report: true }, filter: "all", scrollTo: null, draft: "" };
}

interface LawGuideInput {
  state: LawGuideUiState;
  chat: LawGuideState;
  /** Logic.setState. 함수를 넘기면 그때 상태로 바꿀 값을 만든다. */
  setState: (patch: Partial<LawGuideUiState> | ((current: LawGuideUiState) => Partial<LawGuideUiState>)) => void;
}

const FILTERS: [LawGuideFilter, string][] = [
  ["all", "전체"],
  ["step", "업무 단계"],
  ["cw", "아동복지법"],
  ["cp", "아동학대처벌법"],
];

/**
 * 예시 질문. 누르면 그 문장을 바로 묻는다.
 * 2026-10-28: 디자인의 예시 중 매뉴얼 2~5장(절차 · 신변안전)이 있어야 답할 수 있는 것(즉각분리 요건 · 신고자 응대 ·
 * 사례판단 기한 · 종결 절차 · 신변안전 수칙)은 지금 자료(아동복지법 · 아동학대처벌법 전문)로 답할 수 있는 질문으로
 * 바꿨다(경진 결정). 매뉴얼 사진은 기관 대외비라 매뉴얼에 기대는 예시는 두지 않는다.
 */
export const SUGGESTED_QUESTIONS = [
  "응급조치 기간은 얼마나 돼요?",
  "응급조치 다음엔 어떻게 해요?",
  "임시조치 종류가 궁금해요",
  "피해아동보호명령은 뭐예요?",
  "아동복지법 금지행위는?",
  "신고의무자는 누구예요?",
  "신고의무자가 신고 안 하면?",
  "신고인 신분은 어떻게 보호돼요?",
  "조사를 방해하면 처벌은?",
];

export const TOC_ID = "toc";

export function refDomId(id: string): string {
  return `ref-${id}`;
}

export function lawLink(pair: [LawKey, string]): { label: string; url: string } {
  const [name, url] = LAW_SOURCES[pair[0]];
  return { label: `${name} ${pair[1]}`, url };
}

/** 근거 조문 칩. 서버가 준 조문 링크가 없으면 법령 전문 링크, 그것도 모르면 링크 없는 칩. */
export function lawSourceChip(source: LawSource): { key: string; label: string; title: string; url: string | null } {
  const label = `${source.law_name} ${source.article}`.trim();
  // 서버의 법령 이름은 정식 이름(아동학대범죄의 처벌 등에 관한 특례법)일 수 있다.
  const name = source.law_name.replace(/\s+/g, "");
  const fallback = name.includes("아동학대범죄") ? LAW_SOURCES.cp[1] : name === "아동복지법" ? LAW_SOURCES.cw[1] : null;
  return { key: label, label, title: source.title ? `${label}(${source.title})` : label, url: source.portal_url || fallback };
}

/** 매뉴얼 근거 칩(지금은 매뉴얼을 AI 에 보내지 않아 보통 비어 있다). */
export function manualSourceChip(source: ManualSource): { key: string; label: string } {
  return { key: `${source.id}-${source.page}`, label: `매뉴얼 p.${source.page}` };
}

/** 분류 — all 전체 · step 업무 단계(kind 없음) · cw · cp 그 법령의 조문 항목만. */
export function filterRefs(refs: LawGuideRef[], filter: LawGuideFilter): LawGuideRef[] {
  if (filter === "all") return refs;
  if (filter === "step") return refs.filter((ref) => !ref.kind);
  return refs.filter((ref) => ref.kind === filter);
}

export function lawGuideValues(input: LawGuideInput) {
  const { state, setState, chat } = input;

  const filters = FILTERS.map(([key, label]) => ({
    key,
    label,
    cls: state.filter === key ? "on" : "",
    pressed: state.filter === key,
    pick: () => setState({ filter: key }),
  }));

  const refs = filterRefs(LAW_GUIDE_REFS, state.filter).map((ref) => {
    const open = Boolean(state.open[ref.id]);
    return {
      id: ref.id,
      domId: refDomId(ref.id),
      step: ref.step,
      stepCls: ref.kind ? "k-law" : "",
      title: ref.title,
      sum: ref.sum,
      pages: ref.pages,
      items: ref.items,
      laws: ref.laws.map(lawLink),
      open,
      cls: open ? "open" : "",
      toggle: () => setState((current) => ({ open: { ...current.open, [ref.id]: !current.open[ref.id] } })),
    };
  });

  const openToc = () =>
    setState((current) => ({ open: { ...current.open, [TOC_ID]: true }, filter: "all", scrollTo: refDomId(TOC_ID) }));

  const ask = (question: string) => {
    void chat.ask(question).then((sent) => {
      if (sent) setState({ draft: "" });
    });
  };

  const messages = chat.messages.map((message) => {
    const laws = message.laws.map(lawSourceChip);
    const manual = message.manual.map(manualSourceChip);
    return {
      key: message.id,
      cls: message.role === "user" ? "lg-u" : "lg-b",
      text: message.text,
      error: message.error,
      laws,
      manual,
      hasRefs: laws.length + manual.length > 0,
    };
  });

  const canSend = !chat.pending && state.draft.trim().length > 0;

  return {
    title: "법령 · 매뉴얼",
    sub: "2026 아동학대 대응 업무 매뉴얼 · 아동복지법 · 아동학대처벌법",
    chat: {
      lead:
        // 2026-10-28: 매뉴얼 사진은 기관 대외비라 AI 에 보내지 않는다(MANUAL_QA_ATTACH_IMAGES 기본 끔, #107).
        // 그래서 AI 질문은 공개 법령만으로 답한다 — 디자인 문구의 '매뉴얼 · 매뉴얼 쪽수' 를 뺐다.
        "공개 법령인 아동복지법 · 아동학대범죄의 처벌 등에 관한 특례법을 참조해 답해요. " +
        "답변마다 근거 조문을 보여 드려요.",
      intro: "안녕하세요. 아동복지법 · 아동학대처벌법을 바탕으로 답해 드리는 자리예요.",
      messages,
      pending: chat.pending,
      pendingText: "법령에서 찾는 중",
      reset: () => {
        chat.reset();
        setState({ draft: "" });
      },
      suggs: SUGGESTED_QUESTIONS.map((label) => ({ label, ask: () => ask(label) })),
      draft: state.draft,
      maxLength: QUESTION_MAX,
      setDraft: (value: string) => setState({ draft: value }),
      submit: () => ask(state.draft),
      canSend,
      placeholder: "예: 응급조치 기간은 얼마나 돼요?",
      note: "AI 답변은 참고용입니다. 최종 판단은 매뉴얼 원문과 법령을 확인해 주세요.",
    },
    refsLead: "자주 찾는 기준과 아동복지법 · 아동학대처벌법 주요 조문을 정리했어요. 줄을 누르면 펼쳐져요.",
    sources: [
      { label: "아동복지법", url: LAW_SOURCES.cw[1] },
      { label: "아동학대처벌법", url: LAW_SOURCES.cp[1] },
    ],
    openToc,
    filters,
    refs,
    scrollTo: state.scrollTo,
    clearScroll: () => setState({ scrollTo: null }),
    footNote:
      "요약과 조문은 2026 아동학대 대응 업무 매뉴얼(보건복지부)과 매뉴얼에 인용된 법령을 바탕으로 정리했습니다. " +
      "개정 여부는 국가법령정보센터 원문으로 확인하세요. 이 정리는 10/27 디자인의 초안 문구이며 팀이 확정한 기준이 아닙니다.",
  };
}
