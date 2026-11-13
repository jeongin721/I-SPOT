// 내담자 정보 › '사례 한눈에 보기'(2026-11-13, 멘토 피드백 "담당자가 바뀌어도 사례를 한 번에 파악").
// 디자인에 없던 칸이다(경진님 확인, 1안: 이미 저장된 값만 모은다 — 새 API · 새 AI 없음).
//
// 상담 전 브리핑은 '가장 최근 분석 회차' 하나로 다음 상담을 준비하는 칸이라, 사례를 처음 보는 사람에게 필요한
// 경위 · 흐름을 따로 모은다. 값은 내담자 정보 화면이 이미 부르는 것만 쓴다.
//  - 사례 경위: 신고접수일 · 사례연계일 · 사례연계 경위(초기면접지 ①, 상담원이 적은 글)
//  - 진행: 회차 수 · 첫 상담일 ~ 최근 상담일 · 담당 상담원
//  - 문제력 · 상담원 소견(초기면접지 ②, 상담원이 적은 글)
//  - 위험도 판단 추이: 회차별 회차 전체 상담원 판단(signal-history counselor_level) + 사례 위험도(우선)
//  - 학대 유형: 상담원이 유형별로 판단한 것(가장 최근 판단)과 AI 가 신호를 낸 회차 수 — AI 쪽은 'AI 제안' 표시
//  - 안전 플래그: 분석이 끝난 가장 최근 회차의 AI 확인 후보(safety_flags). 판정이 아니다.
//  - 아이 앱: 연결 여부 · 응답 수 · 주의 응답 수 · 최근 응답(담당 상담사만 보임)
//  - 남은 확인 사항: 아래 브리핑 '확인할 사항' 의 수
// 값이 없으면 '아직 없음' 으로 두고 다른 값으로 채우지 않는다.

import { ABUSE_TYPES, ABUSE_TYPE_LABELS, RISK_LEVEL_LABELS, type ChildAppCase, type RiskLevel } from "../../api/types";
import { NOT_PROVIDED } from "../caseRows";
import type { CaseDetailState } from "../useCaseDetail";
import type { CaseSignalsState } from "../useCaseSignals";
import type { SignalHistoryState } from "../useSignalHistory";
import { toDateOnly } from "../time";
import { childAppHighlights } from "./childDetail";
import { screenHref } from "./links";

const RISK_CHIP: Record<RiskLevel, string> = { HIGH: "c-hi", MEDIUM: "c-mid", LOW: "c-lo" };
/** 글 칸은 길면 앞부분만 보이고 초기면접지에서 전부 본다. */
const TEXT_LIMIT = 160;

export interface OverviewChip {
  text: string;
  cls: string;
}

export interface OverviewRow {
  label: string;
  /** 본문 글. 비었으면 empty 를 note 로 보인다. */
  text: string;
  empty: boolean;
  chips: OverviewChip[];
  /** 값의 출처(회색 작은 글). */
  source: string;
  ai: boolean;
}

export interface CaseOverviewInput {
  detail: CaseDetailState;
  history: SignalHistoryState;
  signals: CaseSignalsState;
  childApp: ChildAppCase | null | undefined;
  /** 아래 브리핑 '확인할 사항' 의 줄 수. */
  checksCount: number;
  caseId: string | null;
}

function cut(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > TEXT_LIMIT ? `${flat.slice(0, TEXT_LIMIT)}…` : flat;
}

function shortDate(value: string | null | undefined): string {
  const m = /^\d{4}-(\d{2})-(\d{2})$/.exec(toDateOnly(value ?? null) || "");
  return m ? `${Number(m[1])}/${Number(m[2])}` : "";
}

function row(label: string, text: string, source: string, extra: Partial<OverviewRow> = {}): OverviewRow {
  return { label, text, empty: !text && !(extra.chips?.length ?? 0), chips: [], source, ai: false, ...extra };
}

export function caseOverviewValues(input: CaseOverviewInput) {
  const info = input.detail.caseInfo;
  if (!info) return { ready: false, rows: [] as OverviewRow[], intakeHref: "", historyHref: "" };

  const form = info.caseForm;
  const valueOr = (value: string) => (value && value !== NOT_PROVIDED ? value : "");
  const intakeHref = input.caseId ? screenHref("/CaseIntake", { caseId: input.caseId }) : "";
  const historyHref = input.caseId ? screenHref("/CaseHistory", { caseId: input.caseId }) : "";
  const rows: OverviewRow[] = [];

  // 사례 경위
  const dates = [
    valueOr(info.reportDate) ? `신고접수 ${info.reportDate}` : "",
    valueOr(info.linkedDate) ? `사례연계 ${info.linkedDate}` : "",
  ].filter(Boolean);
  const background = form.linkedBackground ? cut(form.linkedBackground) : "";
  rows.push(
    row("사례 경위", [dates.join(" · "), background].filter(Boolean).join(" — "), "초기면접지 ① · 상담원 기록"),
  );

  // 진행
  const consulted = input.detail.sessions
    .map((s) => s.consultedDate)
    .filter((d) => d && d !== NOT_PROVIDED)
    .sort();
  const span = consulted.length ? `${consulted[0]} ~ ${consulted[consulted.length - 1]}` : "";
  const progress = info.sessionCount > 0 ? `${info.sessionCount}회 상담${span ? ` · ${span}` : ""}` : "";
  const counselor = valueOr(info.counselorName) ? ` · 담당 ${info.counselorName}` : "";
  rows.push(row("진행", progress ? progress + counselor : "", "회차 기록"));

  // 문제력 · 소견
  rows.push(row("문제력", form.problem ? cut(form.problem) : "", "초기면접지 ② · 상담원 기록"));
  rows.push(row("상담원 소견", form.opinion ? cut(form.opinion) : "", "초기면접지 ② · 상담원 기록"));

  // 위험도 판단 추이(회차 전체 상담원 판단). 사례 위험도(우선)가 있으면 앞에 둔다.
  const judged = input.history.sessions.filter((s) => s.counselor_level);
  const trend: OverviewChip[] = judged.map((s) => ({
    text: `${s.session_number}회차 ${RISK_LEVEL_LABELS[s.counselor_level as RiskLevel]}`,
    cls: `chip ${RISK_CHIP[s.counselor_level as RiskLevel]}`,
  }));
  const caseLevel = form.riskLevel as RiskLevel | "";
  if (caseLevel && RISK_LEVEL_LABELS[caseLevel]) {
    trend.unshift({ text: `사례 위험도(우선) ${RISK_LEVEL_LABELS[caseLevel]}`, cls: `chip ${RISK_CHIP[caseLevel]}` });
  }
  rows.push(
    row("위험도 판단", "", "상담원 판단 · 회차별", {
      chips: trend,
      empty: trend.length === 0,
    }),
  );

  // 학대 유형: 상담원 유형별 판단(가장 최근) 먼저, 판단 없이 AI 신호만 있는 유형은 'AI 신호 n회차'.
  const typeChips: OverviewChip[] = [];
  let typeAi = false;
  for (const type of ABUSE_TYPES) {
    const rowsOfType = input.history.sessions.flatMap((s) =>
      s.types.filter((t) => t.abuse_type === type).map((t) => ({ number: s.session_number, ...t })),
    );
    const lastJudged = [...rowsOfType].reverse().find((t) => t.counselor_level);
    const aiCount = rowsOfType.filter((t) => t.detected === true).length;
    if (lastJudged?.counselor_level) {
      typeChips.push({
        text: `${ABUSE_TYPE_LABELS[type]} ${RISK_LEVEL_LABELS[lastJudged.counselor_level]} (${lastJudged.number}회차 판단)`,
        cls: `chip ${RISK_CHIP[lastJudged.counselor_level]}`,
      });
    } else if (aiCount > 0) {
      typeAi = true;
      typeChips.push({ text: `${ABUSE_TYPE_LABELS[type]} · AI 신호 ${aiCount}개 회차`, cls: "chip c-normal" });
    }
  }
  rows.push(
    row("학대 유형", "", typeAi ? "상담원 유형별 판단 · 판단 전 유형은 AI 신호" : "상담원 유형별 판단", {
      chips: typeChips,
      empty: typeChips.length === 0,
      ai: typeAi,
    }),
  );

  // 안전 플래그(가장 최근 분석 회차의 AI 확인 후보)
  const view = input.signals.analysis.analysis;
  const completed = view !== null && view.status === "COMPLETED";
  const flags = completed ? (view.safetyFlags ?? []) : [];
  const flagSource = input.signals.session ? `${input.signals.session.numberLabel} AI 확인 후보 · 판정 아님` : "AI 확인 후보";
  rows.push(
    row("안전 플래그", "", flagSource, {
      chips: flags.slice(0, 4).map((f) => ({
        text: `${f.text}${f.certainty === "CHECK" ? " (확인 필요)" : ""}`,
        cls: "chip c-normal",
      })),
      empty: flags.length === 0,
      text: flags.length > 4 ? `외 ${flags.length - 4}개` : "",
      ai: flags.length > 0,
    }),
  );

  // 아이 앱
  const app = childAppHighlights(input.childApp);
  let appText = "";
  if (app) {
    appText = app.linked ? "연결됨" : "연결 전";
    if (app.answeredCount > 0) {
      appText += ` · 응답 ${app.answeredCount}회`;
      if (app.flaggedCount > 0) appText += ` · 주의 응답 ${app.flaggedCount}회`;
      const last = shortDate(app.lastAt);
      if (last) appText += ` · 최근 ${last}`;
    }
  }
  rows.push(row("아이 앱", appText, "콩콩 아이 앱"));

  // 남은 확인 사항
  rows.push(
    row("남은 확인 사항", input.checksCount > 0 ? `아래 브리핑 '확인할 사항' ${input.checksCount}개` : "", "다음 상담 준비"),
  );

  return { ready: true, rows, intakeHref, historyHref };
}
