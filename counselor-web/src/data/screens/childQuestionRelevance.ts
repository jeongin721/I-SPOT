// 콩콩 '질문 보내기' 문항 가운데 이 회차 AI 분석과 관련 있는 문항 고르기(2026-11-24).
//
// 4단계 '추가 질문 › 아이 앱으로 먼저' 탭에서만 쓴다. 문항 · 문장 · 보기는 서버 고정 값 그대로이고
// (Backend child_app_service.QUESTION_BANK) 여기서는 **어느 문항을 위에 올리고 왜인지**만 정한다.
// AI 가 문항을 고르지 않는다 — 체크는 상담사가 한다. 화면에는 'AI 분석 참고' 로 표시한다.
//
// 기준(사람이 읽고 따져 볼 수 있게 표 하나와 점수 하나로 둔다):
//  - 문항마다 관련 있다고 보는 AI 신호 유형 · 대화 주제를 BANK_RELEVANCE 에 적는다.
//  - 검출된 AI 신호 하나에 SIGNAL_SCORE 점, 대화 주제는 그 주제로 나눈 아동 발화 수(TOPIC_SCORE_MAX 까지)만큼 더한다.
//  - RELATED_MIN_SCORE 점 이상인 문항만, 점수 높은 순으로 RELATED_MAX 개까지 올린다. 점수가 같으면 아이가 그 주제를 더 많이
//    이야기한 문항이 먼저다.
//    (주제가 한 번 스친 것만으로는 올리지 않는다 — 한 회차에 주제가 여러 개 잡혀 거의 모든 문항이 '관련' 이 되는 것을 막는다.)
// 표는 화면 표시용 기준이다. 문항이 바뀌면(서버 QUESTION_BANK) 여기도 같이 본다. 모르는 문항 id 는 올리지 않는다.

import type { AbuseSignal, AbuseType, AnalysisTopicTag } from "../../api/types";

const SIGNAL_SCORE = 3;
const TOPIC_SCORE_MAX = 3;
const RELATED_MIN_SCORE = 2;
const RELATED_MAX = 3;
/** 문항 한 줄에 보이는 이유 수. */
const REASONS_SHOWN = 2;

/** 이유 문구에 쓰는 유형 이름('학대' 를 붙이지 않는다 — 판정처럼 읽히지 않게). */
const SIGNAL_NAMES: Record<AbuseType, string> = { PHYSICAL: "신체", EMOTIONAL: "정서", SEXUAL: "성", NEGLECT: "방임" };

/**
 * 문항 id(서버 QUESTION_BANK 와 같은 값) → 관련 있다고 보는 AI 신호 유형 · 대화 주제(AI 모듈 topic_tag_llm.TOPICS 이름).
 * free(전하고 싶은 말)는 어느 상담에나 쓰는 문항이라 넣지 않는다.
 */
const BANK_RELEVANCE: Record<string, { signals: AbuseType[]; topics: string[] }> = {
  sleep: { signals: ["NEGLECT"], topics: ["건강 · 병원"] },
  meal: { signals: ["NEGLECT"], topics: ["식사 · 돌봄"] },
  home: { signals: ["PHYSICAL", "EMOTIONAL"], topics: ["보호자 관계", "형제 · 가족", "신체 체벌 경험"] },
  safe: { signals: ["PHYSICAL", "SEXUAL"], topics: ["신체 체벌 경험", "성 관련 경험", "두려움 · 정서"] },
  school: { signals: [], topics: ["학교생활", "친구 관계"] },
  friend: { signals: ["EMOTIONAL"], topics: ["친구 관계", "두려움 · 정서"] },
  week: { signals: ["EMOTIONAL"], topics: ["두려움 · 정서"] },
};

export interface RelatedQuestions {
  /** 위에 올릴 문항 id(점수 높은 순, RELATED_MAX 개까지). 없으면 빈 배열. */
  ids: string[];
  /** 문항 id → 왜 올렸는지(화면에 그대로 보이는 문구, REASONS_SHOWN 개까지). */
  reasons: Record<string, string[]>;
}

/**
 * 이 회차의 AI 신호 · 대화 주제로 관련 문항을 고른다. 분석이 없거나(분석 전 · 문서 회차) 해당이 없으면 ids 가 빈 배열이다.
 * topicTags 가 null 이면(주제 분류가 없는 분석) 신호만으로 고른다.
 */
export function relatedBankQuestions(abuseSignals: AbuseSignal[], topicTags: AnalysisTopicTag[] | null): RelatedQuestions {
  const detected = new Set(abuseSignals.filter((signal) => signal.detected).map((signal) => signal.abuse_type));
  const topicCounts = new Map<string, number>();

  for (const tag of topicTags ?? []) {
    topicCounts.set(tag.topic, (topicCounts.get(tag.topic) ?? 0) + tag.segment_ids.length);
  }

  const scored: { id: string; score: number; talked: number; order: number; reasons: string[] }[] = [];

  Object.entries(BANK_RELEVANCE).forEach(([id, rule], order) => {
    // talked: 그 이유의 실제 크기(주제는 발화 수 그대로). 점수가 같은 문항 · 이유의 순서를 정할 때만 쓴다.
    const parts: { score: number; talked: number; text: string }[] = [];

    for (const type of rule.signals) {
      if (detected.has(type)) parts.push({ score: SIGNAL_SCORE, talked: SIGNAL_SCORE, text: `${SIGNAL_NAMES[type]} 관련 AI 신호` });
    }

    for (const topic of rule.topics) {
      const count = topicCounts.get(topic) ?? 0;

      if (count > 0) parts.push({ score: Math.min(count, TOPIC_SCORE_MAX), talked: count, text: `대화 주제 '${topic}' ${count}회` });
    }

    const score = parts.reduce((sum, part) => sum + part.score, 0);

    if (score < RELATED_MIN_SCORE) return;

    // 이유는 점수 큰 것부터(같으면 적은 순서 — 신호가 주제보다 먼저).
    const reasons = parts
      .map((part, index) => ({ ...part, index }))
      .sort((a, b) => b.score - a.score || a.index - b.index)
      .slice(0, REASONS_SHOWN)
      .map((part) => part.text);

    scored.push({ id, score, talked: parts.reduce((sum, part) => sum + part.talked, 0), order, reasons });
  });

  // 점수가 같으면 아이가 더 많이 이야기한 쪽을, 그것도 같으면 문항 순서대로.
  const top = scored.sort((a, b) => b.score - a.score || b.talked - a.talked || a.order - b.order).slice(0, RELATED_MAX);

  return { ids: top.map((item) => item.id), reasons: Object.fromEntries(top.map((item) => [item.id, item.reasons])) };
}
