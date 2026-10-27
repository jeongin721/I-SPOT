// 법령 · 매뉴얼(LawGuide) 화면 값(10/27 디자인 counselor-design/screens/LawGuide.dc.html).
//
//  - 'AI에게 묻기' 는 서버에 법령 · 매뉴얼 질의 API 가 아직 없어 준비 중이다(이경진 님 제안서
//    I-SPOT_DOCS/docs/PROPOSAL_law_guide_api.md, AI 모듈은 PR #83). 디자인의 키워드 답변(예시)은 옮기지 않았다 —
//    안내 말풍선 · 예시 질문 · 입력칸은 디자인대로 보이되 모두 꺼 둔다. API 가 생기면 훅을 더해 여기서 messages 를 만든다.
//  - '업무 단계별 참고사항 · 주요 조문' 은 lawGuideRefs.ts 의 정리 문구를 그대로 보인다(서버 값 아님, 디자인 초안 문구).
//    펼침(open) · 분류(filter)는 화면 상태다. '매뉴얼 목차' 를 누르면 목차 항목을 펼치고 그 줄로 한 번 스크롤한다(scrollTo).
//  - '원문보기' · 원문 자료 링크는 국가법령정보센터(www.law.go.kr)로 간다.

import { NOT_READY } from "./common";
import { LAW_GUIDE_REFS, LAW_SOURCES, type LawGuideRef, type LawKey } from "./lawGuideRefs";

export type LawGuideFilter = "all" | "step" | "cw" | "cp";

export interface LawGuideUiState {
  /** 펼친 항목(id → true). 처음엔 디자인대로 '신고접수 시 파악할 정보' 만 펼친다. */
  open: Record<string, boolean>;
  filter: LawGuideFilter;
  /** '매뉴얼 목차' 를 눌러 펼친 항목으로 한 번 스크롤할 DOM id. 화면이 스크롤한 뒤 clearScroll 로 비운다. */
  scrollTo: string | null;
}

export function initialLawGuideState(): LawGuideUiState {
  return { open: { report: true }, filter: "all", scrollTo: null };
}

interface LawGuideInput {
  state: LawGuideUiState;
  /** Logic.setState. 함수를 넘기면 그때 상태로 바꿀 값을 만든다. */
  setState: (patch: Partial<LawGuideUiState> | ((current: LawGuideUiState) => Partial<LawGuideUiState>)) => void;
}

const FILTERS: [LawGuideFilter, string][] = [
  ["all", "전체"],
  ["step", "업무 단계"],
  ["cw", "아동복지법"],
  ["cp", "아동학대처벌법"],
];

/** 디자인의 예시 질문. 질의 API 가 없는 동안은 눌리지 않는다. */
export const SUGGESTED_QUESTIONS = [
  "즉각분리 요건이 뭐예요?",
  "응급조치 기간은 얼마나 돼요?",
  "현장에서 신고자를 물어보면?",
  "사례판단은 언제까지 해야 해요?",
  "사례 종결 절차 알려주세요",
  "가정방문 때 신변안전 수칙은?",
  "아동복지법 금지행위는?",
  "임시조치 종류가 궁금해요",
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

/** 분류 — all 전체 · step 업무 단계(kind 없음) · cw · cp 그 법령의 조문 항목만. */
export function filterRefs(refs: LawGuideRef[], filter: LawGuideFilter): LawGuideRef[] {
  if (filter === "all") return refs;
  if (filter === "step") return refs.filter((ref) => !ref.kind);
  return refs.filter((ref) => ref.kind === filter);
}

export function lawGuideValues(input: LawGuideInput) {
  const { state, setState } = input;

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

  return {
    title: "법령 · 매뉴얼",
    sub: "2026 아동학대 대응 업무 매뉴얼 · 아동복지법 · 아동학대처벌법",
    chat: {
      lead:
        "2026 아동학대 대응 업무 매뉴얼 · 아동복지법 · 아동학대범죄의 처벌 등에 관한 특례법을 함께 참조해 답해요. " +
        "답변마다 매뉴얼 쪽수와 조문을 근거로 보여 드려요.",
      intro: "안녕하세요. 2026 아동학대 대응 업무 매뉴얼과 아동복지법 · 아동학대처벌법을 바탕으로 답해 드리는 자리예요.",
      notReadyChip: NOT_READY,
      notReady:
        `AI 질문은 ${NOT_READY}입니다. 서버에 법령 · 매뉴얼 질의 API 가 아직 없습니다(설계 제안서 검토 중). ` +
        "그때까지는 아래 참고사항과 원문 자료를 보세요.",
      notReadyShort: `${NOT_READY}입니다. 법령 · 매뉴얼 질의 API 가 아직 없습니다.`,
      suggs: SUGGESTED_QUESTIONS,
      placeholder: "예: 즉각분리 요건이 뭐예요?",
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
