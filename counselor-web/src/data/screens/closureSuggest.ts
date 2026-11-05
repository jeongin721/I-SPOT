// 종결 검토 › ② 종결보고서(서식 29)의 제안 칩 · 근거(11/04 디자인 'AI 제안' 자리) — 칸은 채우지 않는다(상담원이 고른다).
//
//  - 안전평가 11문항 · Key Person: closure-summary 의 AI 제안(summary.suggestions, 요약을 AI 로 만들 때 같이 나옴). 'AI 제안'.
//  - 종결사유: 기록으로 계산한 제안(AI 아님, '기록 제안').
//      1) 초기면접일 + 6개월이 지났고, 마지막으로 AI 관련 신호가 나온 회차 뒤에도 분석한 회차가 있으면 — 근거는 그 회차 · 6개월 날짜.
//      2) 위험수준 척도 확정 기록이 둘 이상이고 위험요인 합계가 첫 기록보다 줄었으면 — 근거는 '14점 → 6점 (4월 → 10월)'.
//      3) 출생연도로 만 18세를 넘었으면.
//  - 종결 상담일: 일정에 잡힌 이 사례의 '종결 상담'(가장 가까운 것). '일정' 칩.
//  - 학대유형: 회차 AI 관련 신호에 나온 유형 — 칸 값이 아니라 'AI 신호' 칩으로만 보이고 내보내기(인쇄)에는 나가지 않는다
//    (기관 문서에서 사례의 학대유형으로 읽히지 않게, 민규 #140 교차검증 11/05).
//  - 사례관리 제공 요약: 회차 기록의 상담 유형별 횟수 · 기간(계산, 상담원이 고쳐 저장한다).

import { CONSULTATION_TYPE_LABELS, type CaseForm, type ClosureSummaryBody, type ConsultationType, type ScheduleEvent } from "../../api/types";
import { NOT_PROVIDED } from "../caseRows";
import type { CaseDetailState } from "../useCaseDetail";
import { formRounds } from "../useCaseForms";
import type { SignalHistorySession } from "../../api/types";
import { detectedTypeLabels } from "../signalHistoryRows";

const LEVEL_LABEL = { HIGH: "높음", MEDIUM: "보통", LOW: "낮음" } as const;
const md = (date: string) => {
  const matched = /^\d{4}-(\d{2})-(\d{2})/.exec(date || "");
  return matched ? `${Number(matched[1])}/${Number(matched[2])}` : "";
};
const where = (sessions: number[]) => sessions.map((number) => `${number}회차`).join(" · ");

export interface ClosureSuggestInput {
  detail: CaseDetailState;
  history: SignalHistorySession[];
  forms: CaseForm[];
  events: ScheduleEvent[];
  summary: ClosureSummaryBody | null;
  /** 오늘(YYYY-MM-DD). 시험에서 고정한다. */
  today: string;
}

export interface Suggestion {
  chip: string;
  ev: string;
}

export function closureSuggestions(input: ClosureSuggestInput) {
  const { detail, history, forms, events, summary, today } = input;
  const info = detail.caseInfo;
  const sessions = [...detail.sessions].sort((a, b) => a.sessionNumber - b.sessionNumber);
  const historyBy = new Map(history.map((row) => [row.session_id, row]));
  const dateOf = (row: (typeof sessions)[number]) => (row.consultedDate !== NOT_PROVIDED ? row.consultedDate : row.createdDate);

  // --- 종결사유(기록 제안) ---
  const reasons: (Suggestion | null)[] = [null, null, null, null, null];
  const first = info?.firstInterviewDateValue ?? "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(first)) {
    const due = new Date(`${first}T00:00:00`);
    due.setMonth(due.getMonth() + 6);
    const dueText = `${due.getFullYear()}-${String(due.getMonth() + 1).padStart(2, "0")}-${String(due.getDate()).padStart(2, "0")}`;
    const analyzed = sessions.filter((row) => historyBy.get(row.id)?.analysis_status === "COMPLETED");
    const flagged = analyzed.filter((row) => detectedTypeLabels(historyBy.get(row.id)!).length > 0);
    const lastFlag = flagged[flagged.length - 1];
    const after = lastFlag ? analyzed.filter((row) => row.sessionNumber > lastFlag.sessionNumber) : analyzed;
    if (dueText <= today && after.length > 0) {
      const since = lastFlag
        ? `${lastFlag.numberLabel}(${md(dateOf(lastFlag))}) 이후 AI 관련 신호 없음`
        : `AI 분석한 ${analyzed.length}회차 모두 관련 신호 없음`;
      reasons[0] = { chip: "기록 제안", ev: `${since} (${md(dueText)}에 6개월 경과)` };
    }
  }
  const risk = formRounds(forms, "RISK_SCALE")
    .filter((row) => row.status === "APPROVED" && typeof row.totals?.risk_sum === "number")
    .sort((a, b) => a.round - b.round);
  if (risk.length >= 2) {
    const [a, b] = [risk[0], risk[risk.length - 1]];
    const month = (row: CaseForm) => `${Number((row.confirmed_at ?? row.updated_at).slice(5, 7))}월`;
    if (b.totals.risk_sum < a.totals.risk_sum) {
      reasons[1] = {
        chip: "기록 제안",
        ev: `위험수준 척도 위험요인 ${a.totals.risk_sum}점 → ${b.totals.risk_sum}점 (${month(a)} → ${month(b)})`,
      };
    }
  }
  const birth = info?.childBirthYear ?? null;
  if (birth !== null && Number(today.slice(0, 4)) - birth > 18) {
    reasons[2] = { chip: "기록 제안", ev: `출생연도 ${birth}년` };
  }

  // --- 안전평가 · Key Person(AI 제안) ---
  const ai = summary?.source === "AI" ? summary.suggestions ?? null : null;
  const safety: (Suggestion | null)[] = Array.from({ length: 11 }, () => null);
  (ai?.safety ?? []).forEach((row) => {
    if (row.index >= 0 && row.index < 11) safety[row.index] = { chip: `AI 제안 · ${LEVEL_LABEL[row.level]}`, ev: `${where(row.sessions)} · ${row.basis}` };
  });
  const keyPerson: Suggestion | null = ai?.key_person
    ? { chip: "AI 제안", ev: `${ai.key_person.text} · ${where(ai.key_person.sessions)}` }
    : null;

  // --- 종결 상담일(일정) ---
  const closing = events.filter((event) => event.kind === "CONSULT" && event.consult_type === "CLOSING");
  const pick = closing.find((event) => event.date >= today) ?? closing[closing.length - 1];
  const closingDate: Suggestion | null = pick ? { chip: "일정", ev: `${md(pick.date)} 종결 상담` } : null;

  // --- 학대유형(AI 관련 신호) ---
  const types = new Set<string>();
  history.forEach((row) => detectedTypeLabels(row).forEach((label) => types.add(label)));
  const abuseSignal = types.size ? `AI 신호 · ${[...types].join(" · ")}` : "";

  // --- 사례관리 제공 요약(회차 기록) ---
  const counts = new Map<ConsultationType, number>();
  sessions.forEach((row) => row.consultationType && counts.set(row.consultationType, (counts.get(row.consultationType) ?? 0) + 1));
  const kinds = [...counts.entries()].map(([kind, count]) => `${CONSULTATION_TYPE_LABELS[kind]} ${count}회`);
  const untyped = sessions.length - [...counts.values()].reduce((a, b) => a + b, 0);
  if (untyped > 0) kinds.push(`유형 미기록 ${untyped}회`);
  const services = sessions.length
    ? `상담 ${sessions.length}회 (${md(dateOf(sessions[0]))} ~ ${md(dateOf(sessions[sessions.length - 1]))}) · ${kinds.join(" · ")}`
    : "";

  return { reasons, safety, keyPerson, closingDate, abuseSignal, services, servicesChip: sessions.length ? `회차 기록 · ${sessions.length}회차` : "" };
}
