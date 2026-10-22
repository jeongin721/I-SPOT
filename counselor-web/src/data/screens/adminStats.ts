// 통계 · 보고(AdminStats) 값. 디자인 counselor-design/screens/AdminStats.dc.html(기관 단위).
//
// 서버 연결: useCaseOverview(mode "sessions") — 관리자가 볼 수 있는 사례(기관 전체)와 사례마다 회차를 모은다(집계 API 없음).
// 상담원 목록은 useAdminAccounts(GET /auth/users).
// 지금 서버 값으로 셀 수 있는 것만 센다:
//  - 기간 안 사례 등록 수 · 등록 추이: 사례 등록일(created_at) 기준이다. **신고접수일이 아니다** — '신규 접수' 라고 부르지 않는다.
//  - 기간 안 상담 회차 수: 상담 일시 기준. 상담 일시를 넣지 않은 회차는 등록일로 대신하지 않고 뺀다.
//  - 종결: 사례에 종결일이 없어 기간으로 거를 수 없다. 지금 종결 상태인 사례 수만 보인다.
//  - 상담원별 지금 담당(진행 중) · 기간 안 상담 회차 · 지금 종결: 사례 응답에 담당자 ID 가 없어(사례 행은 이름만) 담당 상담사
//    이름으로 모은다. 이름이 같은 계정이 둘 이상이면 섞이지 않게 그 줄은 '—' 로 둔다.
//  - 아동 연령대: 출생연도로 센 나이(기간 끝 해 − 출생연도)라 만 나이와 한 살 다를 수 있다. 기간 안 등록 사례 기준.
// 서버에 없어 '—' · 준비 중: 학대 판단 · 재신고율 · 평균 사례관리 기간 · 72시간 내 초기 개입 · 아이 앱 응답률 · 일지 기한 내 작성률,
// 학대 유형별 · 위험도별(사례 단위 판단 · 위험도 규칙 없음 — AI 신호로 대신 세지 않는다), 행위자 관계 · 신고자 · 조치 결과 ·
// 서비스 · 종결 사유 분포, 엑셀 · PDF 내려받기(양식 미정). 디자인의 기간별 숫자(올해 값에 계수를 곱한 예시)는 옮기지 않는다.

import type { AdminAccountsState } from "../useAdminAccounts";
import type { AuthSession } from "../useAuthSession";
import type { CaseOverviewState } from "../useCaseOverview";
import { NOT_PROVIDED } from "../caseRows";
import { NOT_READY, screenNotice } from "./common";
import { localDate, segButton } from "./admin";

export type StatsPeriod = "month" | "quarter" | "year";

export interface AdminStatsUiState {
  period: StatsPeriod;
}

export const INITIAL_ADMIN_STATS_UI: AdminStatsUiState = { period: "month" };

interface PeriodBin {
  label: string;
  from: string;
  to: string;
}

export interface PeriodRange {
  /** "이번 달" · "3분기" · "올해 누적". */
  label: string;
  /** YYYY-MM-DD(사용자 시간대), 양 끝 포함. */
  from: string;
  to: string;
  /** 추이 막대 칸(이번 달은 주별, 분기 · 올해는 월별). */
  bins: PeriodBin[];
}

const pad = (value: number) => String(value).padStart(2, "0");
const ymd = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`;
/** 그 달(1~12)의 마지막 날. */
const lastDay = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate();

/** 기간 단추 → 날짜 범위. 분기는 이번 분기가 아니라 바로 앞의 다 끝난 분기다(디자인: 10월에 '3분기'). */
export function statsPeriodRange(period: StatsPeriod, now: Date): PeriodRange {
  const today = localDate(now);
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  const d = now.getDate();

  if (period === "month") {
    const bins: PeriodBin[] = [];

    for (let start = 1; start <= d; start += 7) {
      const end = Math.min(d, start + 6);
      bins.push({
        label: start === end ? `${m}/${start}` : `${m}/${start}~${end}`,
        from: ymd(y, m, start),
        to: ymd(y, m, end),
      });
    }

    return { label: "이번 달", from: ymd(y, m, 1), to: today, bins };
  }

  if (period === "quarter") {
    const current = Math.floor((m - 1) / 3);
    const qy = current === 0 ? y - 1 : y;
    const q = current === 0 ? 3 : current - 1;
    const months = [q * 3 + 1, q * 3 + 2, q * 3 + 3];

    return {
      label: qy === y ? `${q + 1}분기` : `${qy}년 ${q + 1}분기`,
      from: ymd(qy, months[0], 1),
      to: ymd(qy, months[2], lastDay(qy, months[2])),
      bins: months.map((month) => ({
        label: `${month}월`,
        from: ymd(qy, month, 1),
        to: ymd(qy, month, lastDay(qy, month)),
      })),
    };
  }

  return {
    label: "올해 누적",
    from: ymd(y, 1, 1),
    to: today,
    bins: Array.from({ length: m }, (_, index) => {
      const month = index + 1;

      return { label: `${month}월`, from: ymd(y, month, 1), to: month === m ? today : ymd(y, month, lastDay(y, month)) };
    }),
  };
}

/** 'YYYY-MM-DD' 가 from ~ to 안인가. 날짜가 없으면(NOT_PROVIDED · 빈 문자열) 아니다. */
function within(date: string, from: string, to: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(date) && date >= from && date <= to;
}

const AGE_GROUPS: readonly { label: string; min: number; max: number }[] = [
  { label: "0~5세", min: 0, max: 5 },
  { label: "6~9세", min: 6, max: 9 },
  { label: "10~13세", min: 10, max: 13 },
  { label: "14~17세", min: 14, max: 17 },
];

/** 서버에 원천 데이터가 없어 비워 두는 카드. 디자인의 자리만 남긴다. */
const PENDING_CARDS = {
  types: { title: "학대 유형별", note: "학대 판단 사례 기준", text: "사례 단위 학대 판단을 입력 · 저장하는 곳이 없습니다. AI 신호로 대신 세지 않습니다." },
  risk: { title: "위험도별", note: "학대 판단 시점 기준", text: "사례 단위 위험도 규칙이 없습니다(회차 · 유형별 상담원 판단만 있음)." },
  more: [
    { title: "학대 행위자 관계별", note: "", text: "행위자 관계를 저장하는 칸이 없습니다(보호자 유형과 다름)." },
    { title: "신고자 유형별", note: "", text: "신고자 정보를 저장하는 칸이 없습니다." },
    { title: "조치 결과", note: "피해 아동 기준", text: "조치 결과를 저장하는 칸이 없습니다." },
    { title: "서비스 제공 (회)", note: "", text: "서비스 제공 실적을 저장하는 곳이 없습니다." },
    { title: "종결 사유", note: "종결 사례 기준", text: "종결 사유 · 종결일을 저장하는 칸이 없습니다." },
  ],
};

export function adminStatsValues(input: {
  session: AuthSession;
  overview: CaseOverviewState;
  accounts: AdminAccountsState;
  ui: AdminStatsUiState;
  setUi: (patch: Partial<AdminStatsUiState>) => void;
  /** 오늘(그릴 때). 시험에서 바꿔 넣는다. */
  now?: Date;
}) {
  const { session, overview, accounts, ui, setUi } = input;
  const range = statsPeriodRange(ui.period, input.now ?? new Date());
  const data = overview.data;
  const items = data?.items ?? [];
  const has = data !== null;
  const count = (value: number, unit: string) => (has ? `${value.toLocaleString()}${unit}` : NOT_PROVIDED);

  const registered = items.filter((item) => within(item.createdDate, range.from, range.to));
  const allSessions = items.flatMap((item) => item.sessions);
  const sessionsIn = allSessions.filter((row) => within(row.consultedDate, range.from, range.to));
  const undated = allSessions.filter((row) => !/^\d{4}-\d{2}-\d{2}$/.test(row.consultedDate)).length;
  const closedNow = items.filter((item) => item.caseRow.status === "CLOSED").length;

  // ---------------- 핵심 지표 ----------------
  const kpis = [
    { label: "사례 등록", v: count(registered.length, "건"), sub: `${range.label} · 등록일 기준(신고접수일 아님)` },
    { label: "학대 판단", v: NOT_PROVIDED, sub: NOT_READY },
    { label: "종결", v: count(closedNow, "건"), sub: "지금 종결 상태 · 종결일이 없어 기간과 무관" },
    { label: "상담 회차", v: count(sessionsIn.length, "회"), sub: `${range.label} · 상담 일시 기준` },
    { label: "재신고율", v: NOT_PROVIDED, sub: NOT_READY },
    { label: "평균 사례관리 기간", v: NOT_PROVIDED, sub: NOT_READY },
    { label: "72시간 내 초기 개입", v: NOT_PROVIDED, sub: NOT_READY },
    { label: "아이 앱 응답률", v: NOT_PROVIDED, sub: NOT_READY },
  ];

  // ---------------- 사례 등록 추이 ----------------
  const binCounts = range.bins.map(
    (bin) => registered.filter((item) => within(item.createdDate, bin.from, bin.to)).length,
  );
  const binMax = Math.max(0, ...binCounts);
  const trend = range.bins.map((bin, index) => ({
    key: bin.from,
    label: bin.label,
    a: has ? String(binCounts[index]) : NOT_PROVIDED,
    ha: has && binMax > 0 ? `${Math.round((binCounts[index] / binMax) * 160)}px` : "0px",
    tip: has ? `${bin.label} 사례 등록 ${binCounts[index]}건` : `${bin.label} ${NOT_PROVIDED}`,
  }));
  const trendAria = has
    ? range.bins.map((bin, index) => `${bin.label} 사례 등록 ${binCounts[index]}건`).join(", ")
    : "사례 등록 추이를 아직 불러오지 못했습니다";

  // ---------------- 상담원별 ----------------
  // 이름으로 모으므로 같은 이름의 계정이 있으면 그 줄은 세지 않는다.
  const nameCount = new Map<string, number>();
  for (const row of accounts.rows) nameCount.set(row.name, (nameCount.get(row.name) ?? 0) + 1);

  const counselorRows = accounts.rows.filter((row) => row.role === "COUNSELOR");
  const staffCounts = counselorRows.map((row) => {
    if (!has || nameCount.get(row.name) !== 1) return null;

    const mine = items.filter((item) => item.caseRow.counselorName === row.name);

    return {
      active: mine.filter((item) => item.caseRow.status === "ACTIVE").length,
      sessions: mine
        .flatMap((item) => item.sessions)
        .filter((s) => within(s.consultedDate, range.from, range.to)).length,
      closed: mine.filter((item) => item.caseRow.status === "CLOSED").length,
    };
  });
  const sessionMax = Math.max(0, ...staffCounts.map((value) => value?.sessions ?? 0));
  const staff = counselorRows.map((row, index) => {
    const value = staffCounts[index];

    return {
      key: row.id,
      name: row.name,
      rank: row.active ? row.roleLabel : `${row.roleLabel} · 비활성`,
      cases: value ? `${value.active}건` : NOT_PROVIDED,
      ses: value ? `${value.sessions}회` : NOT_PROVIDED,
      w: value && sessionMax > 0 ? `${Math.round((value.sessions / sessionMax) * 100)}%` : "0%",
      rate: NOT_PROVIDED,
      closed: value ? `${value.closed}건` : NOT_PROVIDED,
    };
  });
  const staffText = accounts.loading && accounts.rows.length === 0
    ? "불러오는 중…"
    : accounts.rows.length === 0 && accounts.error
      ? accounts.error
      : staff.length === 0
        ? "상담원 계정이 없습니다."
        : "";
  const sameName = counselorRows.some((row) => nameCount.get(row.name) !== 1);

  // ---------------- 아동 연령대 ----------------
  const ageCounts = AGE_GROUPS.map(() => 0);
  let noBirthYear = 0;
  let outside = 0;
  const endYear = Number(range.to.slice(0, 4));

  for (const item of registered) {
    const match = /^(\d{4})년생$/.exec(item.caseRow.birthYearLabel);

    if (!match) {
      noBirthYear += 1;
      continue;
    }

    const age = endYear - Number(match[1]);
    const group = AGE_GROUPS.findIndex((g) => age >= g.min && age <= g.max);

    if (group < 0) outside += 1;
    else ageCounts[group] += 1;
  }

  const ageTotal = ageCounts.reduce((sum, value) => sum + value, 0);
  const ageMax = Math.max(0, ...ageCounts);
  const ages = AGE_GROUPS.map((g, index) => ({
    key: g.label,
    name: g.label,
    v: has ? `${ageCounts[index]}건` : NOT_PROVIDED,
    p: has && ageTotal > 0 ? `${Math.round((ageCounts[index] / ageTotal) * 1000) / 10}%` : NOT_PROVIDED,
    w: has && ageMax > 0 ? `${Math.round((ageCounts[index] / ageMax) * 100)}%` : "0%",
    tip: has ? `${g.label} ${ageCounts[index]}건` : g.label,
  }));
  const ageNote = has && noBirthYear + outside > 0 ? `출생연도 없음 ${noBirthYear}건 · 그 밖 나이 ${outside}건은 빼고 셈` : "";

  // ---------------- 안내 ----------------
  const notes = [
    data?.casesTruncated ? "사례가 많아 최근 등록한 사례까지만 셌습니다." : "",
    data?.sessionsTruncated ? "회차가 많은 사례는 최근 회차까지만 셌습니다." : "",
    has && undated > 0 ? `상담 일시를 넣지 않은 회차 ${undated}건은 회차 수에서 뺐습니다.` : "",
  ].filter(Boolean);

  return {
    notice: screenNotice({ session, loading: overview.loading, error: overview.error, retry: overview.reload }),
    periodLabel: range.label,
    rangeLabel: `${range.from} ~ ${range.to}`,
    scopeLabel: `기관 전체 · ${range.label}`,
    periods: [
      segButton("month", "이번 달", ui.period === "month", () => setUi({ period: "month" })),
      segButton("quarter", statsPeriodRange("quarter", input.now ?? new Date()).label, ui.period === "quarter", () =>
        setUi({ period: "quarter" }),
      ),
      segButton("year", "올해 누적", ui.period === "year", () => setUi({ period: "year" })),
    ],
    notReady: NOT_READY,
    kpis,
    trend,
    trendAria,
    pendingTypes: PENDING_CARDS.types,
    pendingRisk: PENDING_CARDS.risk,
    staff,
    staffText,
    staffNote: sameName
      ? "담당 상담사 이름으로 모았습니다. 이름이 같은 계정이 있어 그 줄은 — 로 둡니다."
      : "담당 상담사 이름으로 모았습니다. 담당 · 종결은 지금 상태, 상담 회차는 기간 안 상담 일시 기준입니다.",
    ages,
    ageNote,
    pendingMore: PENDING_CARDS.more,
    notesText: notes.join(" "),
  };
}
