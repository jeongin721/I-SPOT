// 사례 단위 신호 이력(useSignalHistory) → 화면 칸 값. 유형별 위험도 '회차별 추이' 와 상담 이력 '회차 카드 · 세부 신호 행렬' 이 같이 쓴다.
//
//  - 칸 값: AI 심각도(1~5, ai_level)가 있으면 그 숫자, 없는데 관련 신호(detected)가 있으면 '확인 필요', 둘 다 없으면 '–'.
//    분석이 끝나지 않은 회차는 '분석 중' · '분석 전'. 모두 AI 제안이다(판정 아님).
//  - '위험도 (상담원)' 줄: 그 회차에서 상담원이 고른 유형별 판단(상 · 중 · 하) 중 가장 높은 것. AI 값으로 채우지 않는다.

import { RISK_LEVEL_LABELS, type AbuseType, type RiskLevel, type SignalHistorySession } from "../api/types";

/** 10/27 디자인 '회차별 추이' 의 줄 순서(신체 · 정서 · 방임 · 성). */
export const TREND_TYPES: AbuseType[] = ["PHYSICAL", "EMOTIONAL", "NEGLECT", "SEXUAL"];

export const TYPE_SHORT: Record<AbuseType, string> = { PHYSICAL: "신체", EMOTIONAL: "정서", SEXUAL: "성", NEGLECT: "방임" };

const LEVEL_ORDER: RiskLevel[] = ["HIGH", "MEDIUM", "LOW"];

export const DASH = "–";

export interface HistoryCell {
  text: string;
  /** 값이 없는 칸(–, 분석 전)이라 흐리게 보인다. */
  muted: boolean;
  /** AI 심각도 숫자(없으면 null) — 행렬 칸 색을 정한다. */
  level: number | null;
  /** 관련 신호가 있는가. */
  detected: boolean;
}

/** 분석이 끝나지 않아 값이 없는 회차의 칸 문구. 없으면 ''(값이 있는 회차). */
export function pendingLabel(session: SignalHistorySession): string {
  if (session.types.length > 0) return "";
  if (session.analysis_status === "PROCESSING") return "분석 중";
  if (session.analysis_status === "FAILED") return "분석 실패";
  return "분석 전";
}

export function historyCell(session: SignalHistorySession, type: AbuseType): HistoryCell {
  const pending = pendingLabel(session);
  if (pending) return { text: pending, muted: true, level: null, detected: false };

  const row = session.types.find((item) => item.abuse_type === type);
  const level = typeof row?.ai_level === "number" ? row.ai_level : null;
  const detected = row?.detected === true;

  if (level !== null) return { text: String(level), muted: false, level, detected };
  if (detected) return { text: "확인 필요", muted: true, level: null, detected };
  return { text: DASH, muted: true, level: null, detected: false };
}

/**
 * 그 회차의 상담원 판단. 회차 전체 판단(회차 줄 counselor_level, 11.1절 — #119 부터 화면은 이것만 저장)을 먼저 보고,
 * 없으면 예전 회차의 유형별 판단(types[].counselor_level, 11.2절) 가운데 가장 높은 것. 둘 다 없으면 null.
 */
export function counselorTop(session: SignalHistorySession): RiskLevel | null {
  if (session.counselor_level) return session.counselor_level;

  for (const level of LEVEL_ORDER) {
    if (session.types.some((item) => item.counselor_level === level)) return level;
  }

  return null;
}

export function counselorTopLabel(session: SignalHistorySession): string {
  const top = counselorTop(session);
  return top ? RISK_LEVEL_LABELS[top] : DASH;
}

/**
 * 관련 신호를 '없음' 으로 단정할 수 있는가 — 네 유형 모두 detected 가 false 일 때만.
 * 하나라도 null(근거 없어 서버가 뺀 유형 · 검출 미확인)이면 false — 화면은 '검출 여부 미확인' 으로 쓴다
 * (false 와 null 이 섞인 회차를 '없음' 으로 단정하지 않는다, 민규 #104 R2).
 */
export function signalsClearlyAbsent(session: SignalHistorySession): boolean {
  return session.types.length > 0 && session.types.every((item) => item.detected === false);
}

/** 관련 신호(AI)가 있는 유형의 짧은 이름. 줄 순서는 TREND_TYPES. */
export function detectedTypeLabels(session: SignalHistorySession): string[] {
  return TREND_TYPES.filter((type) => session.types.some((item) => item.abuse_type === type && item.detected === true)).map(
    (type) => TYPE_SHORT[type],
  );
}

// ------------------------------------------------------------
// 대화 주제(topics, 2026-10-29) — 상담 이력 '주제 비중' · '덜 다룬 부분', 상담 전 브리핑 '처음 나온 이야기'
// ------------------------------------------------------------
// 회차마다 AI 가 고정 주제 목록으로 나눈 아동 발화 수(topics[].count)를 더해 비율을 낸다. 주제 분류가 없는 회차(topics null —
// 이 기능 전 분석 · 분류 실패 · 분석 전)는 세지 않는다. 모두 AI 제안이다.
// '처음 나온 이야기' · '첫 언급' 은 그 회차 앞에 분석은 끝났는데 주제 분류가 없는 회차(analysis_status COMPLETED · topics null)가
// 있으면 단정하지 않는다 — 그 회차에 이미 나왔을 수 있어서다(민규 #122 리뷰). 분석 전 회차는 비교할 AI 값이 원래 없어 막지 않는다.

export interface TopicShare {
  topic: string;
  count: number;
  /** 0~100 정수(반올림). */
  pct: number;
}

export interface TopicMention {
  topic: string;
  sessionId: string;
  sessionNumber: number;
  quote: string;
  startMs: number | null;
  /** 이 회차 앞에 주제 분류가 없는 분석 회차가 없어 '첫 언급' 이라 할 수 있는가. */
  certain: boolean;
}

/** 주제 분류가 있는 회차(오름차순). */
export function taggedSessions(sessions: SignalHistorySession[]): SignalHistorySession[] {
  return [...sessions]
    .filter((session) => Array.isArray(session.topics))
    .sort((a, b) => a.session_number - b.session_number);
}

/** 분석은 끝났는데 주제 분류가 없는 회차(이 기능 전 분석 · 분류 실패). */
export function untaggedAnalyzed(sessions: SignalHistorySession[]): SignalHistorySession[] {
  return sessions.filter((session) => session.analysis_status === "COMPLETED" && !Array.isArray(session.topics));
}

/** 회차들을 더한 주제 비중(큰 것부터). 발화가 하나도 없으면 []. */
export function topicShares(sessions: SignalHistorySession[]): TopicShare[] {
  const counts = new Map<string, number>();

  for (const session of taggedSessions(sessions)) {
    for (const item of session.topics ?? []) counts.set(item.topic, (counts.get(item.topic) ?? 0) + item.count);
  }

  const total = [...counts.values()].reduce((sum, count) => sum + count, 0);
  if (total === 0) return [];

  return [...counts.entries()]
    .map(([topic, count]) => ({ topic, count, pct: Math.round((count / total) * 100) }))
    .sort((a, b) => b.count - a.count || a.topic.localeCompare(b.topic));
}

/** 주제마다 처음 나온 회차 · 그 발화. certain 은 그 앞에 주제 분류 없는 분석 회차가 없을 때만 true. */
export function firstMentions(sessions: SignalHistorySession[]): Map<string, TopicMention> {
  const first = new Map<string, TopicMention>();
  const gaps = untaggedAnalyzed(sessions).map((session) => session.session_number);

  for (const session of taggedSessions(sessions)) {
    for (const item of session.topics ?? []) {
      if (first.has(item.topic)) continue;
      first.set(item.topic, {
        topic: item.topic,
        sessionId: session.session_id,
        sessionNumber: session.session_number,
        quote: item.quote,
        startMs: item.start_ms,
        certain: !gaps.some((number) => number < session.session_number),
      });
    }
  }

  return first;
}

/**
 * 그 회차에서 처음 나온 주제(앞 회차들에 없던 것). 비교할 수 없으면 comparable 이 false 다:
 *  - 그 회차 앞에 주제 분류가 있는 회차가 없음(첫 회차의 모든 주제를 '처음' 이라 하지 않는다)
 *  - 그 회차 앞에 분석은 끝났는데 주제 분류가 없는 회차가 있음(skipped — 그 회차 수)
 */
export function newTopicsIn(
  sessions: SignalHistorySession[],
  sessionId: string,
): { comparable: boolean; tagged: boolean; skipped: number; items: TopicMention[] } {
  const tagged = taggedSessions(sessions);
  const index = tagged.findIndex((session) => session.session_id === sessionId);

  if (index < 0) return { comparable: false, tagged: false, skipped: 0, items: [] };

  const number = tagged[index].session_number;
  const skipped = untaggedAnalyzed(sessions).filter((session) => session.session_number < number).length;

  if (skipped > 0 || index === 0) return { comparable: false, tagged: true, skipped, items: [] };

  const first = firstMentions(sessions);
  const items = [...first.values()].filter((mention) => mention.sessionId === sessionId);

  return { comparable: true, tagged: true, skipped: 0, items };
}
