// 사례 상세 탭 1(CaseDetail · 내담자 정보)과 탭 2(CaseHistory · 상담 이력) 화면 값. 둘 다 useCaseDetail 하나로 그린다.
//
// Backend 에 없는 값은 지어내지 않고 '—' 또는 준비 중으로 둔다(specs 대응표 '팀 결정 — 사례 · 개인정보 / AI 신호 · 검수').
//  - 실명 · 생년월일(출생연도만 있음) · 사례관리대상자 · 가족유형 · 신고접수일 · 사례연계일 · 아이 앱 · 다음 상담 일정
//  - 위험도 · 학대 유형 · 주요 키워드 · 사정결과, 서비스 이행, 기관 서식 진행, 종결 검토 등록
//  - 상담 유형(정기 · 방문), 회차별 신호 채택 · 보류 수, 누적 AI 요약 · 주제 비중 · 회차별 세부 신호
// 사례관리대상자는 보호자와 같은 뜻이 아니어서 보호자 유형(guardian_type)으로 채우지 않는다.

import { NOT_PROVIDED } from "../caseRows";
import type { CaseDetailState } from "../useCaseDetail";
import type { AuthSession } from "../useAuthSession";
import { NOT_READY, TONE_CHIP, notice, screenNotice, sidebarValues } from "./common";
import { COLUMN_OF, PROCESS_COLUMNS, continueLink } from "./flow";
import { screenHref } from "./links";

interface CaseScreenInput {
  session: AuthSession;
  detail: CaseDetailState;
  caseId: string | null;
}

/** 주소에 사례 ID 가 없을 때 안내. */
export const MISSING_CASE = notice("사례가 정해지지 않았습니다. 사례 관리에서 사례를 골라 주세요.", {
  href: "/CaseList",
  hrefLabel: "사례 관리로",
});

/** 사례 상세 탭 공통: 위치 표시 · 머리 · 탭 링크 · 녹취 올리기 링크. */
export function caseHeaderValues({ session, detail, caseId }: CaseScreenInput) {
  const info = detail.caseInfo;
  const ids = { caseId };

  return {
    ...sidebarValues(session),
    notice: screenNotice({
      session,
      missing: caseId ? null : MISSING_CASE,
      loading: detail.loading,
      error: detail.error,
      retry: detail.reload,
    }),
    crumb: info ? `${info.alias} ${info.caseNumber}` : "",
    title: info ? info.alias : "",
    sub: info ? info.birthYearLabel : "",
    riskChip: `위험도 ${NOT_PROVIDED}`,
    meta: info ? `${info.caseNumber} · 다음 상담 ${NOT_PROVIDED}` : "",
    uploadHref: screenHref("/UploadModal", ids),
    tabs: {
      detail: screenHref("/CaseDetail", ids),
      history: screenHref("/CaseHistory", ids),
      briefing: screenHref("/PreBriefing", ids),
      app: screenHref("/CaseApp", ids),
      docs: screenHref("/CaseDocs", ids),
    },
  };
}

const DOT_DONE = { background: "#F1EFE9", color: "#55606A" };
const DOT_CURRENT = { background: "#FFFFFF", border: "2px solid #A8C6E7", color: "#2E5687" };
const DOT_PENDING = { background: "#EEE8DA", color: "#6F7880" };

/** 탭 1 · 내담자 정보. */
export function caseDetailValues(input: CaseScreenInput) {
  const { detail } = input;
  const info = detail.caseInfo;
  const latest = detail.sessions[0] ?? null;
  const dash = NOT_PROVIDED;

  const basics: { label: string; value: string; strong?: boolean }[] = info
    ? [
        { label: "개별사건번호", value: info.caseNumber },
        { label: "이름", value: `${info.alias} (${info.genderLabel})` },
        { label: "생년월일", value: info.birthYearLabel },
        { label: "사례관리대상자", value: dash },
        { label: "가족유형", value: dash },
        { label: "담당 상담원", value: info.counselorName },
        { label: "신고접수일", value: dash },
        { label: "사례연계일", value: dash },
        { label: "상담 회차", value: `${info.sessionCount}회`, strong: true },
        { label: "최근 상담", value: info.lastSessionDate },
        { label: "아이 앱", value: dash },
      ]
    : [];

  // 현재 진행 상황: 가장 최근 회차가 어느 칸에 있는가.
  const column = latest ? COLUMN_OF[latest.step] : -1;
  const progress = PROCESS_COLUMNS.map((label, index) => {
    const done = latest !== null && index < column;
    const current = latest !== null && index === column && index < PROCESS_COLUMNS.length - 1;
    // '추가 확인 · 질문' 칸은 Backend 에 없어 늘 준비 중이다.
    const last = index === PROCESS_COLUMNS.length - 1;

    return {
      label,
      // 원래 화면처럼 '녹취 올림' 칸은 번호 없이, 나머지는 1 · 2 · 3 · 4.
      mark: done ? "✓" : index === 0 ? "↑" : String(index),
      dot: done ? DOT_DONE : current ? DOT_CURRENT : DOT_PENDING,
      done,
      current,
      pending: !done && !current,
      chip: current && latest ? latest.statusLabel : last ? NOT_READY : "",
    };
  });

  const next = latest ? continueLink(latest) : null;

  return {
    ...caseHeaderValues(input),
    basics,
    riskBy: dash,
    abuseTypes: [dash],
    keywords: [dash],
    assessment: dash,
    latestLabel: latest ? `${latest.numberLabel} · ${latest.statusLabel}` : info ? "회차 없음" : "",
    continueHref: next ? next.href : screenHref("/UploadModal", { caseId: input.caseId }),
    continueLabel: next ? next.label : "녹취 올려 시작하기",
    progress,
    services: [{ label: "서비스 계획 · 이행", value: dash }],
    nextSchedule: dash,
    briefingHref: screenHref("/PreBriefing", { caseId: input.caseId }),
    formsChip: NOT_READY,
    formsHref: screenHref("/CaseForm", { caseId: input.caseId }),
    notReady: NOT_READY,
  };
}

/** 탭 2 · 상담 이력. 누적 요약 · 주제 비중 · 세부 신호는 Backend 에 없어 빈 목록과 준비 중 안내를 준다. */
export function caseHistoryValues(input: CaseScreenInput) {
  const { detail } = input;
  const dash = NOT_PROVIDED;

  const sessions = detail.sessions.map((row) => ({
    no: row.numberLabel,
    // 상담 일시를 넣지 않은 회차는 등록일을 '등록' 이라고 밝혀 보여 준다(상담일로 대신하지 않는다).
    date: row.consultedDate !== NOT_PROVIDED ? row.consultedDate : `${row.createdDate} 등록`,
    kind: `상담 유형 ${dash}`,
    status: row.statusLabel,
    st: TONE_CHIP[row.tone],
    sig: `신호 ${dash}`,
    href: screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.id }),
  }));

  // 세부 신호 행렬의 열(회차). 오래된 회차부터.
  const cols = [...detail.sessions].reverse().map((row) => ({
    label: `${row.sessionNumber}회`,
    href: screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.id }),
  }));

  let sessionsNote = "";
  if (detail.caseInfo && sessions.length === 0) sessionsNote = "회차가 없습니다. 녹취를 올리면 회차가 생깁니다.";
  else if (detail.sessionTotal !== null && detail.sessionTotal > sessions.length) {
    sessionsNote = `최근 ${sessions.length}회차만 보입니다(전체 ${detail.sessionTotal}회차).`;
  }

  return {
    ...caseHeaderValues(input),
    overviewChip: `AI 분석 · ${NOT_READY}`,
    overviewNote: `지금까지 상담의 누적 요약 · 주제 비중은 ${NOT_READY}입니다(서버에 아직 없는 기능).`,
    periods: [] as { range: string; title: string; note: string }[],
    topics: [] as { label: string; width: string; pct: string }[],
    insights: [] as { title: string; text: string; src: string }[],
    sessions,
    sessionsNote,
    cols,
    mrows: [] as { type: string; name: string; cells: { v: string; tip: string; bg: string; fg: string; ring: string }[] }[],
    signalNote: `회차별 세부 신호는 ${NOT_READY}입니다(AI 위험 신호를 서버가 아직 주지 않음).`,
  };
}
