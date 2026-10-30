// 종결 검토 › ① 전체 상담 내역 검토(ClosureReview) 화면 값 — ?case=<사례 ID> 로 열면 그 사례의 서버 값(2026-10-30).
//
// 디자인 칸 → 서버 값:
//  - 머리: 별칭 · 사례번호 · 출생연도 · 회차 범위 · 기간(첫 회차 ~ 마지막 회차 상담일, 없으면 등록일).
//  - 한눈에 '상담': 회차 수와 상담 유형별 수(consultation_type). '새 학대 진술': 신호 이력(signal-history)에서 AI 관련 신호가
//    나온 회차 — 있으면 그 회차들, 없으면 '없음'(분석한 회차 기준, AI 제안). '아이 연계 응답' · '위험수준 척도' 는 아이 앱 ·
//    기관 서식 기록이 서버에 없어 준비 중.
//  - 회차별 흐름: 회차 · 날짜 · 유형 · 핵심(승인한 상담 요약 4칸 중 처음 채워진 칸, 상담원 확정 문장) · 근거(그 칸 이름 또는
//    AI 관련 신호). 승인 전 회차는 핵심 '승인 전'.
//  - 핵심 요약 · 서로 다른 진술(여러 회차를 묶는 AI) · 아이 연계는 아직 없어 준비 중 — 실제 사례 옆에 예시 문장을 보이지 않는다.

import { CONSULTATION_TYPE_LABELS, type ConsultationType } from "../../api/types";
import { NOT_PROVIDED } from "../caseRows";
import type { ApprovedSummariesState } from "../useApprovedSummaries";
import type { CaseDetailState } from "../useCaseDetail";
import type { SignalHistoryState } from "../useSignalHistory";
import { detectedTypeLabels } from "../signalHistoryRows";
import { NOT_READY } from "./common";
import { screenHref } from "./links";

const SUMMARY_ORDER = [
  ["safety_risks", "위험요인"],
  ["strengths_resources", "강점과 자원"],
  ["safety_changes", "조사 후 변화"],
  ["desired_changes", "원하는 변화"],
] as const;

const clip = (text: string, max: number) => (text.length > max ? `${text.slice(0, max)}…` : text);
/** 'YYYY-MM-DD' → 'M/D'(디자인 '4/10'). */
const shortDate = (date: string) => {
  const matched = /^\d{4}-(\d{2})-(\d{2})/.exec(date || "");
  return matched ? `${Number(matched[1])}/${Number(matched[2])}` : "";
};

export interface ClosureReviewInput {
  caseId: string | null;
  detail: CaseDetailState;
  history: SignalHistoryState;
  approved: ApprovedSummariesState;
  /** 회차별 흐름을 모두 펼쳤는가. */
  all: boolean;
}

export function closureReviewValues(input: ClosureReviewInput) {
  const { caseId, detail, history, approved } = input;
  const info = detail.caseInfo;
  const sessions = [...detail.sessions].sort((a, b) => a.sessionNumber - b.sessionNumber);
  const historyBy = new Map((history.loaded ? history.sessions : []).map((row) => [row.session_id, row]));
  const summaryBy = new Map(approved.items.map((item) => [item.sessionId, item]));

  const dateOf = (row: (typeof sessions)[number]) => (row.consultedDate !== NOT_PROVIDED ? row.consultedDate : row.createdDate);
  const first = sessions[0];
  const last = sessions[sessions.length - 1];
  const range = first ? `${first.sessionNumber}~${last.sessionNumber}회차 (${shortDate(dateOf(first))} ~ ${shortDate(dateOf(last))})` : "회차 없음";

  // 한눈에 · 상담: 유형별 수.
  const kindCounts = new Map<ConsultationType, number>();
  sessions.forEach((row) => {
    if (row.consultationType) kindCounts.set(row.consultationType, (kindCounts.get(row.consultationType) ?? 0) + 1);
  });
  const kindText = [...kindCounts.entries()].map(([kind, count]) => `${CONSULTATION_TYPE_LABELS[kind]} ${count}`).join(" · ");

  // 한눈에 · 새 학대 진술: AI 관련 신호가 나온 회차.
  const analyzed = sessions.filter((row) => historyBy.get(row.id)?.analysis_status === "COMPLETED");
  const flagged = analyzed.filter((row) => detectedTypeLabels(historyBy.get(row.id)!).length > 0);
  const signalValue = !history.loaded ? "…" : analyzed.length === 0 ? NOT_PROVIDED : flagged.length === 0 ? "없음" : `${flagged.length}회차`;
  const signalSrc = !history.loaded
    ? "불러오는 중"
    : analyzed.length === 0
      ? "AI 분석한 회차가 없습니다"
      : flagged.length === 0
        ? `AI 분석한 ${analyzed.length}회차 · 관련 신호 없음(AI 제안)`
        : `${flagged.map((row) => row.numberLabel).join(" · ")} · AI 제안`;

  const rowsAll = sessions.map((row) => {
    const item = summaryBy.get(row.id);
    const filled = SUMMARY_ORDER.map(([key, label]) => ({ label, text: item?.assessment?.[key]?.text?.trim() ?? "" })).find(
      (field) => field.text,
    );
    const signals = historyBy.get(row.id) ? detectedTypeLabels(historyBy.get(row.id)!) : [];
    let key = "";
    let src = "";
    if (row.status === "APPROVED") {
      if (item?.failed) key = "요약을 불러오지 못했습니다";
      else if (filled) {
        key = clip(filled.text, 60);
        src = `승인 요약 · ${filled.label}`;
      } else key = item ? "요약 4칸이 비어 있습니다" : approved.loading ? "불러오는 중…" : NOT_PROVIDED;
    } else key = `승인 전 · ${row.statusLabel}`;
    if (signals.length) src = [src, `AI 신호 · ${signals.join(" · ")}`].filter(Boolean).join(" / ");

    return { no: row.numberLabel, date: shortDate(dateOf(row)), kind: row.kindLabel, key, src: src || NOT_PROVIDED };
  });
  const folded = rowsAll.length > 6 ? rowsAll.slice(0, 4).concat(rowsAll.slice(-2)) : rowsAll;

  let notice = "";
  if (!caseId) notice = "종결 검토 목록에서 사례를 골라 주세요.";
  else if (detail.error) notice = detail.error;
  else if (detail.loading && !info) notice = "불러오는 중…";

  return {
    notice,
    connected: Boolean(caseId && info),
    crumb: info ? info.alias : "",
    title: info ? `${info.alias} · 전체 상담 내역 검토` : "전체 상담 내역 검토",
    sub: info ? [info.caseNumber, info.birthYearLabel, range].join(" · ") : "",
    historyHref: screenHref("/CaseHistory", { caseId }),
    detailHref: screenHref("/ClosureDetail", { caseId }),
    reviewHref: screenHref("/ClosureReview", { caseId }),
    kpis: [
      { label: "상담", value: `${sessions.length}회`, src: kindText || "상담 유형 기록 없음" },
      { label: "새 학대 진술", value: signalValue, src: signalSrc },
      { label: "아이 연계 응답", value: NOT_PROVIDED, src: `${NOT_READY} · 아이 앱이 서버에 없음` },
      { label: "위험수준 척도 (위험요인)", value: NOT_PROVIDED, src: `${NOT_READY} · 기관 서식 기록이 서버에 없음` },
    ],
    rows: input.all ? rowsAll : folded,
    canFold: rowsAll.length > 6,
    tlLabel: input.all ? "접기" : `${rowsAll.length}회차 모두 보기`,
    flowNote: approved.truncated ? "승인 회차가 많아 최근 회차 요약만 불러왔습니다." : approved.error ?? "",
    aiNote: `여러 회차를 묶는 종결 요약 AI 가 아직 없어 ${NOT_READY}입니다. 회차별 흐름의 '핵심' 은 상담원이 승인한 회차 요약입니다.`,
  };
}
