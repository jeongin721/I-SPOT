// 통계(Stats) 화면 값. useCaseOverview(mode "sessions") 의 사례 · 회차를 기간으로 걸러 센다.
//
// 11/02 디자인(통계 — 기간 직접 선택 · 원형 · 가로 세로 막대 · 표)에 맞춰, 지금 Backend 값으로 셀 수 있는 것만 센다:
//  - 신고 접수(KPI · 추이): 사례의 신고접수일(report_date, 서식 4 ①). 신고접수일을 넣지 않은 사례는 빼고 몇 건인지 알린다.
//  - 학대 피해 아동 연령 비율: 기간 안에 신고 접수된 사례의 아동 나이(신고접수 해 - 출생연도). 출생연도 없는 사례는 뺀다.
//  - 사례관리 기간: 기간 끝 날짜에 진행 중인 사례를 사례연계일(없으면 신고접수일 → 사례 등록일)부터 센다. 종결일이 서버에 없어
//    지금 진행 중(ACTIVE)인 사례만 '관리 중' 으로 본다. 상담원별 표는 담당 상담원 이름으로 묶는다(상담사는 자기 사례만 온다).
//    1인당 적정 사례 수는 화면 상태다(기본 25, 저장하지 않음).
//  - 서비스: 서버에 기록이 있는 것은 상담 회차뿐이라 '상담 · 교육' 줄만 센다(상담일 기준, 승인 완료 = 완료). 다른 서비스는 '—'.
// 학대 판단 · 재신고, 유형 · 행위자 · 지역(공동사례관리) 분포, AI 요약은 원천 데이터가 서버에 없어 '—' · 준비 중으로 둔다.
//
// 10/21 디자인: 시작 · 종료일이 글자 입력(YYYY-MM-DD) + 달력 단추의 연 → 월 → 일 팝업(디자인 dpBuild)으로 바뀌었다.
// 글자 입력은 치는 동안 '2026-0' 같은 값이 들어오므로, 칸에 보이는 입력(fromDraft · toDraft)과 셈에 쓰는 기간(from · to)을 나누고
// 실제 있는 날짜이고 고를 수 있는 범위(모은 자료의 가장 이른 날 ~ 오늘) 안일 때만 기간에 넣는다(그 밖은 셈이 멈추지 않게 버린다).

import { NOT_PROVIDED } from "../caseRows";
import { pad2 } from "../time";
import type { AuthSession } from "../useAuthSession";
import type { CaseOverviewState } from "../useCaseOverview";
import { NOT_READY, screenNotice, sidebarValues } from "./common";

const DAY_MS = 864e5;
/** 사례관리 기간 표의 1인당 적정 사례 수 기본값(디자인 값). */
export const DEFAULT_CASE_STANDARD = 25;
const AGE_BINS: [string, number, number][] = [
  ["0~3세", 0, 3],
  ["4~6세", 4, 6],
  ["7~9세", 7, 9],
  ["10~12세", 10, 12],
  ["13~17세", 13, 17],
];
const AGE_COLORS = ["#3F72AF", "#B04A2F", "#C8941E", "#7D62B8", "#3E8A5C"];
const MANAGE_BINS: [string, number, number][] = [
  ["3개월 미만", 0, 3],
  ["3~6개월", 3, 6],
  ["6개월~1년", 6, 12],
  ["1년 이상", 12, 999],
];
/** 디자인의 서비스 줄(이름 · 대상). 서버에 기록이 있는 것은 상담 회차('상담 · 교육')뿐이다. */
const SERVICES: [string, string][] = [
  ["상담 · 교육", "아동 · 보호자"],
  ["심리치료", "아동"],
  ["의료 지원", "아동"],
  ["가족기능 강화", "가족"],
  ["부모교육", "보호자"],
  ["기관 연계", "아동 · 가족"],
];
const pct = (x: number, n: number) => `${n ? Math.round((x / n) * 1000) / 10 : 0}%`;

type DateField = "from" | "to";

/** 날짜 칸 옆 달력 팝업(연 → 월 → 일)의 상태. */
export interface StatsPickerState {
  field: DateField;
  mode: "y" | "m" | "d";
  /** 팝업에 보이는 해 · 달(1~12). */
  y: number;
  m: number;
}

/** 화면만의 상태: 기간 프리셋 · 시작/종료일 · 달력. */
export interface StatsUiState {
  preset: "m1" | "m3" | "all" | "custom";
  /** YYYY-MM-DD. preset 이 "all" 이면 쓰지 않는다(모은 자료의 가장 이른 날부터). 늘 올바른 날짜만 넣는다. */
  from: string;
  to: string;
  /** 시작 · 종료일 칸에 치고 있는 글자. null 이면 칸에 지금 기간을 보인다(칸을 나가면 null 로 돌린다). */
  fromDraft: string | null;
  toDraft: string | null;
  /** 열린 날짜 팝업. null 이면 닫혀 있다. */
  dp: StatsPickerState | null;
  cal: boolean;
  /** 달력에 보이는 해 · 달(0~11). */
  cy: number;
  cm: number;
  /** 달력에서 0 이면 시작일, 1 이면 종료일을 고를 차례. */
  pickStage: 0 | 1;
  /** 사례관리 기간 표의 1인당 적정 사례 수(칸에 친 글자 그대로, 11/02 디자인). */
  mgStd: string;
}

/** 사용자 시간대의 오늘(YYYY-MM-DD). */
export function localToday(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

/** 'YYYY-MM-DD' 를 그날 0시(UTC)의 밀리초로. 날짜끼리 빼고 더하는 데만 쓴다. */
const dayOf = (date: string) => Date.parse(date);
const iso = (t: number) => new Date(t).toISOString().slice(0, 10);

/** 'YYYY-MM-DD' 가 실제 있는 날짜면 그날 0시(UTC)의 밀리초, 아니면(입력 중인 '2026-0' · 2월 30일 등) null. */
export function parseDay(text: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!match) return null;

  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const t = Date.UTC(y, m - 1, d);
  const back = new Date(t);

  // 13월 · 31일 없는 달처럼 넘쳐서 다른 날이 되면(0~99년이 1900년대가 되는 것도) 틀린 날짜다.
  return back.getUTCFullYear() === y && back.getUTCMonth() === m - 1 && back.getUTCDate() === d ? t : null;
}

/** 밀리초 → 해 · 달(1~12) · 날. */
const ymdOf = (t: number) => {
  const date = new Date(t);
  return { y: date.getUTCFullYear(), m: date.getUTCMonth() + 1, d: date.getUTCDate() };
};

const DOWS = ["일", "월", "화", "수", "목", "금", "토"];

/**
 * 날짜 칸 옆 달력 팝업(디자인 dpBuild): 연도 → 월 → 일 순으로 고른다. min ~ max 밖의 달 · 날은 막는다.
 * value 는 지금 기간의 그 끝(시작 또는 종료) 날짜, pick 은 고른 날을 기간에 넣고 팝업을 닫는다.
 */
function pickerValues(input: {
  field: DateField;
  value: number;
  min: number;
  max: number;
  dp: StatsPickerState | null;
  setUi: (patch: Partial<StatsUiState>) => void;
  pick: (t: number) => void;
}) {
  const { field, value, dp, setUi, pick } = input;
  const open = dp !== null && dp.field === field;
  const cur = ymdOf(value);
  const mn = ymdOf(input.min);
  const mx = ymdOf(input.max);
  const key = (y: number, m: number, d: number) => y * 10000 + m * 100 + d;
  const mnK = key(mn.y, mn.m, mn.d);
  const mxK = key(mx.y, mx.m, mx.d);
  const vy = open ? dp.y : cur.y;
  const vm = open ? dp.m : cur.m;
  const mode = open ? dp.mode : "y";
  const go = (patch: Partial<StatsPickerState>) => {
    if (open) setUi({ dp: { ...dp, ...patch } });
  };

  const years = [];
  for (let y = mx.y; y >= mn.y; y--) {
    years.push({ label: String(y), cls: y === vy ? "on" : "", on: y === vy, pick: () => go({ y, mode: "m" }) });
  }
  const months = Array.from({ length: 12 }, (_, index) => {
    const m = index + 1;
    const dis = key(vy, m, 31) < mnK || key(vy, m, 1) > mxK;
    const on = cur.y === vy && cur.m === m;
    return { label: `${m}월`, cls: on ? "on" : "", dis, pick: () => !dis && go({ m, mode: "d" }) };
  });
  const first = new Date(Date.UTC(vy, vm - 1, 1)).getUTCDay();
  const last = new Date(Date.UTC(vy, vm, 0)).getUTCDate();
  const days = [];
  for (let i = 0; i < first; i++) days.push({ blank: true, n: 0, aria: "", cls: "", dis: true, pick: () => {} });
  for (let d = 1; d <= last; d++) {
    const k = key(vy, vm, d);
    const dis = k < mnK || k > mxK;
    const on = cur.y === vy && cur.m === vm && cur.d === d;
    days.push({
      blank: false,
      n: d,
      aria: `${vy}년 ${vm}월 ${d}일`,
      cls: on ? "on" : "",
      dis,
      pick: () => !dis && pick(Date.UTC(vy, vm - 1, d)),
    });
  }
  const prevY = vm === 1 ? vy - 1 : vy;
  const prevM = vm === 1 ? 12 : vm - 1;
  const nextY = vm === 12 ? vy + 1 : vy;
  const nextM = vm === 12 ? 1 : vm + 1;

  return {
    open,
    isY: mode === "y",
    isM: mode === "m",
    isD: mode === "d",
    /** 연도 목록이 보일 때 고른 해로 목록을 굴리는 데 쓴다(바뀌면 다시 굴린다). */
    scrollKey: open && mode === "y" ? `${field}-${vy}` : "",
    toggle: () => setUi({ dp: open ? null : { field, mode: "y", y: cur.y, m: cur.m } }),
    close: () => setUi({ dp: null }),
    toY: () => go({ mode: "y" }),
    toM: () => go({ mode: "m" }),
    years,
    months,
    days,
    dows: DOWS,
    yLabel: `${vy}년`,
    ymLabel: `${vy}년 ${vm}월`,
    prevDis: key(prevY, prevM, 31) < mnK,
    nextDis: key(nextY, nextM, 1) > mxK,
    prev: () => go({ y: prevY, m: prevM }),
    next: () => go({ y: nextY, m: nextM }),
  };
}

function presetRange(preset: "m1" | "m3", today: string): [string, string] {
  const [y, m, d] = today.split("-").map(Number);

  if (preset === "m1") return [`${y}-${pad2(m)}-01`, today];

  // 최근 3개월: 석 달 전 같은 날의 다음 날부터 오늘까지(디자인 예: 7/13 ~ 10/12).
  return [iso(Date.UTC(y, m - 1 - 3, d + 1)), today];
}

export function initialStatsState(today: string = localToday()): StatsUiState {
  const [from, to] = presetRange("m3", today);
  const [y, m] = today.split("-").map(Number);

  return {
    preset: "m3",
    from,
    to,
    fromDraft: null,
    toDraft: null,
    dp: null,
    cal: false,
    cy: y,
    cm: m - 1,
    pickStage: 0,
    mgStd: String(DEFAULT_CASE_STANDARD),
  };
}

interface Bar {
  /** 칸의 건수. 아직 못 불러왔거나 불러오지 못했으면 NOT_PROVIDED. */
  v: number | string;
  h: string;
  label: string;
  tip: string;
}

/** 날짜 목록을 기간 a~b 의 칸(62일 이하는 주별, 넘으면 월별)으로 센다. */
export function trendBars(dates: number[], a: number, b: number, unit: string): { bars: Bar[]; weekly: boolean } {
  const days = Math.round((b - a) / DAY_MS) + 1;
  const weekly = days <= 62;
  const bins: [number, number][] = [];

  if (weekly) {
    for (let t = a; t <= b; t += 7 * DAY_MS) bins.push([t, Math.min(b, t + 6 * DAY_MS)]);
  } else {
    let y = new Date(a).getUTCFullYear();
    let m = new Date(a).getUTCMonth();
    while (Date.UTC(y, m, 1) <= b) {
      bins.push([Math.max(a, Date.UTC(y, m, 1)), Math.min(b, Date.UTC(y, m + 1, 0))]);
      m++;
      if (m > 11) {
        m = 0;
        y++;
      }
    }
  }

  const values = bins.map(([x, y]) => dates.filter((t) => t >= x && t <= y).length);
  const max = Math.max(1, ...values);
  const bars = bins.map(([x, y], index) => {
    const v = values[index];
    const label = weekly
      ? `${new Date(x).getUTCMonth() + 1}/${new Date(x).getUTCDate()}~`
      : `${new Date(x).getUTCMonth() + 1}월`;

    return { v, h: `${Math.round((v / max) * 150)}px`, label, tip: `${iso(x)} ~ ${iso(y)} · ${unit} ${v}건` };
  });

  return { bars, weekly };
}

interface StatsInput {
  session: AuthSession;
  overview: CaseOverviewState;
  ui: StatsUiState;
  setUi: (patch: Partial<StatsUiState>) => void;
  /** 오늘(YYYY-MM-DD). 시험할 때만 넘긴다. */
  today?: string;
}

export function statsValues(input: StatsInput) {
  const { session, overview, ui: s, setUi } = input;
  const today = input.today ?? localToday();
  const todayT = dayOf(today);
  const items = overview.data?.items ?? [];

  // 상담 일시가 있는 회차만 상담일로 센다(없으면 등록일로 대신하지 않는다). 오늘 뒤 날짜(앞으로 할 상담)도 기간 밖이면 빠진다.
  const sessions = items.flatMap((item) => item.sessions);
  const consulted = sessions.filter((row) => row.consultedDate !== NOT_PROVIDED).map((row) => dayOf(row.consultedDate));
  const undated = sessions.length - consulted.length;
  const created = items.filter((item) => item.createdDate).map((item) => dayOf(item.createdDate));

  // '전체' 는 모은 자료의 가장 이른 날부터 오늘까지.
  // (펼쳐 넘기면 회차가 아주 많을 때 인자 수 한도를 넘으므로 하나씩 비교한다.)
  const earliest = [...created, ...consulted].reduce((min, t) => (t < min ? t : min), todayT);
  // from · to 는 올바른 날짜만 들어오지만, 혹시 틀린 값이면 셈이 멈추지 않게 오늘로 본다.
  const lo = s.preset === "all" ? earliest : (parseDay(s.from) ?? todayT);
  const hi = s.preset === "all" ? todayT : (parseDay(s.to) ?? todayT);
  const a = Math.min(lo, hi);
  const b = Math.max(lo, hi);
  const days = Math.round((b - a) / DAY_MS) + 1;
  const inRange = (t: number) => t >= a && t <= b;

  const loaded = overview.data !== null;
  const num = (value: number | string, unit: string) => (loaded ? `${value}${unit}` : NOT_PROVIDED);

  // 신고 접수: 신고접수일(report_date)이 기간 안인 사례.
  const reported = items.filter((item) => item.caseRow.reportDate !== NOT_PROVIDED);
  const noReportDate = items.length - reported.length;
  const R = reported.filter((item) => inRange(dayOf(item.caseRow.reportDate)));
  const reportTrend = trendBars(R.map((item) => dayOf(item.caseRow.reportDate)), a, b, "접수");
  // 아직 못 불러왔거나 불러오지 못했으면 칸 이름만 두고 값은 '—' 로 둔다(조회한 결과 0건과 구별되게).
  const unloadedText = overview.error ? "사례 정보를 불러오지 못해 추이를 보일 수 없습니다." : "불러오는 중…";
  const trend = loaded
    ? reportTrend.bars
    : reportTrend.bars.map((t) => ({ ...t, v: NOT_PROVIDED, h: "0px", tip: `${t.tip.split(" · ")[0]} · ${unloadedText}` }));

  // 서비스: 상담 회차(상담일이 기간 안) — 승인 완료면 완료.
  const sessionsIn = sessions.filter((row) => row.consultedDate !== NOT_PROVIDED && inRange(dayOf(row.consultedDate)));
  const sessionsDone = sessionsIn.filter((row) => row.status === "APPROVED").length;
  const k = {
    total: num(R.length, ""),
    perDay: loaded ? (R.length / days).toFixed(1) : NOT_PROVIDED,
    judged: NOT_PROVIDED,
    judgedPct: NOT_PROVIDED,
    repeat: NOT_PROVIDED,
    services: num(sessionsIn.length, ""),
    donePct: loaded ? pct(sessionsDone, sessionsIn.length) : NOT_PROVIDED,
  };
  const svcMax = Math.max(1, sessionsIn.length);
  const svc = SERVICES.map(([label, target], index) => {
    if (index === 0 && loaded) {
      return {
        label,
        target,
        v: sessionsIn.length,
        h: `${Math.round((sessionsIn.length / svcMax) * 150)}px`,
        tip: `${label} ${sessionsIn.length}회(상담 회차, 상담일 기준)`,
        done: String(sessionsDone),
        ing: String(sessionsIn.length - sessionsDone),
        rate: pct(sessionsDone, sessionsIn.length),
      };
    }
    return { label, target, v: NOT_PROVIDED, h: "0px", tip: `${label} · ${NOT_READY}`, done: NOT_PROVIDED, ing: NOT_PROVIDED, rate: NOT_PROVIDED };
  });

  // 연령: 기간 안 신고 접수 사례의 아동 나이(신고접수 해 - 출생연도).
  const aged = R.flatMap((item) => {
    const year = item.caseRow.birthYear;
    return year ? [Number(item.caseRow.reportDate.slice(0, 4)) - year] : [];
  });
  const noBirthYear = R.length - aged.length;
  let angle = -Math.PI / 2;
  const ageTotal = Math.max(1, aged.length);
  const ages = AGE_BINS.map(([name, lo2, hi2], index) => {
    const v = aged.filter((age) => age >= lo2 && age <= hi2).length;
    const sweep = (v / ageTotal) * Math.PI * 2;
    const a0 = angle;
    const a1 = angle + sweep;
    angle = a1;
    const P = (r: number, t: number) => `${(100 + r * Math.cos(t)).toFixed(2)} ${(100 + r * Math.sin(t)).toFixed(2)}`;
    const d =
      v === 0 ? "" : sweep >= Math.PI * 2 - 1e-6 ? "M100 10 A90 90 0 1 1 99.99 10 Z" : `M100 100 L${P(90, a0)} A90 90 0 ${sweep > Math.PI ? 1 : 0} 1 ${P(90, a1)} Z`;
    return { name, v, p: pct(v, aged.length), c: AGE_COLORS[index], d, tip: `${name} ${v}명 (${pct(v, aged.length)})` };
  });

  // 사례관리 기간: 기간 끝(b)에 진행 중인 사례. 시작 = 사례연계일 → 신고접수일 → 사례 등록일.
  const startOf = (item: (typeof items)[number]) => {
    const row = item.caseRow;
    const text = row.linkedDate !== NOT_PROVIDED ? row.linkedDate : row.reportDate !== NOT_PROVIDED ? row.reportDate : item.createdDate;
    return text ? dayOf(text) : NaN;
  };
  const open = items
    .filter((item) => item.caseRow.status === "ACTIVE")
    .map((item) => ({ item, start: startOf(item) }))
    .filter(({ start }) => !Number.isNaN(start) && start <= b)
    .map(({ item, start }) => ({ who: item.caseRow.counselorName, linked: item.caseRow.linkedDate !== NOT_PROVIDED, mon: (b - start) / (DAY_MS * 30.44) }));
  const noLinked = open.filter((c) => !c.linked).length;
  const binMax = Math.max(1, ...MANAGE_BINS.map(([, x, y]) => open.filter((c) => c.mon >= x && c.mon < y).length));
  const mgBins = MANAGE_BINS.map(([name, x, y]) => {
    const v = open.filter((c) => c.mon >= x && c.mon < y).length;
    return { name, v, p: pct(v, open.length), w: `${Math.round((v / binMax) * 100)}%`, tip: `${name} ${v}건` };
  });
  const std = Math.max(1, Math.round(Number(s.mgStd)) || DEFAULT_CASE_STANDARD);
  const avgMonths = (arr: typeof open) =>
    arr.length ? `${(arr.reduce((sum, c) => sum + c.mon, 0) / arr.length).toFixed(1)}개월` : NOT_PROVIDED;
  const staffNames = [...new Set(open.map((c) => c.who))];
  const mgStaff = staffNames
    .map((name) => {
      const sub = open.filter((c) => c.who === name);
      const v = sub.length;
      const ratio = v / std;
      return {
        name,
        v,
        w: `${Math.min(100, Math.round(ratio * 100))}%`,
        bar: ratio > 1 ? "#A33B2E" : "#C2A36B",
        state: ratio > 1 ? `${v - std}건 초과` : ratio >= 0.9 ? "적정 근접" : "적정",
        cls: ratio > 1 ? "c-hi" : ratio >= 0.9 ? "c-mid" : "c-lo",
        m6: sub.filter((c) => c.mon >= 6).length,
        y1: sub.filter((c) => c.mon >= 12).length,
        avg: avgMonths(sub),
      };
    })
    .sort((p, q) => q.v - p.v);
  const over = mgStaff.filter((x) => x.v > std).length;
  const mgKpi = [
    { label: "관리 중 사례", v: num(open.length, "건"), note: loaded ? `상담원 ${staffNames.length}명` : "" },
    { label: "평균 관리 기간", v: loaded ? avgMonths(open) : NOT_PROVIDED, note: "사례연계일부터" },
    {
      label: "6개월 이상",
      v: num(open.filter((c) => c.mon >= 6).length, "건"),
      note: loaded ? `1년 이상 ${open.filter((c) => c.mon >= 12).length}건` : "",
    },
    {
      label: "1인당 평균",
      v: loaded && staffNames.length ? `${(open.length / staffNames.length).toFixed(1)}건` : NOT_PROVIDED,
      note: loaded ? (over ? `적정 초과 ${over}명` : "모두 적정 이내") : "",
    },
  ];

  const scope = overview.wholeOrg ? "기관 전체 사례" : "담당 사례";
  const notes: string[] = [];
  if (loaded && undated) notes.push(`상담 일시를 넣지 않은 상담 회차 ${undated}회는 서비스 제공에서 뺐습니다.`);
  if (loaded && noReportDate) notes.push(`신고접수일을 넣지 않은 사례 ${noReportDate}건은 신고 접수 · 연령에서 뺐습니다.`);
  if (loaded && noBirthYear) notes.push(`출생연도가 없는 사례 ${noBirthYear}건은 연령 비율에서 뺐습니다.`);
  if (loaded && noLinked) notes.push(`사례연계일이 없는 관리 중 사례 ${noLinked}건은 신고접수일(없으면 등록일)부터 셌습니다.`);
  if (overview.data?.casesTruncated) {
    notes.push(`사례가 많아 최근 등록한 ${items.length}건만 셌습니다(전체 ${overview.data.caseTotal}건).`);
  }
  if (overview.data?.sessionsTruncated) notes.push("회차가 아주 많은 사례는 최근 회차만 셌습니다.");

  // 기간 프리셋 · 달력(디자인 그대로, 10/21 디자인 순서: 전체 · 이번 달 · 최근 3개월 · 직접 선택). 처음 기간은 그대로 최근 3개월.
  const presets = (
    [
      ["all", "전체"],
      ["m1", "이번 달"],
      ["m3", "최근 3개월"],
      ["custom", "직접 선택"],
    ] as const
  ).map(([value, label]) => ({
    label,
    cls: s.preset === value ? "on" : "",
    pick: () => {
      if (value === "custom") setUi({ preset: value, cal: true, pickStage: 0 });
      else if (value === "all") setUi({ preset: value, cal: false });
      else {
        const [from, to] = presetRange(value, today);
        setUi({ preset: value, from, to, cal: false });
      }
    },
  }));

  // 시작 · 종료일 칸(글자 입력 + 날짜 팝업). 고를 수 있는 날: 모은 자료의 가장 이른 날(지금 기간이 더 이르면 그날) ~ 오늘.
  const minT = Math.min(earliest, a);
  const allowed = (text: string) => {
    const t = parseDay(text);
    return t !== null && t >= minT && t <= todayT ? t : null;
  };
  // 한쪽 끝을 바꾸면 다른 쪽은 지금 보이는 기간 그대로 두고 '직접 선택' 으로 바꾼다(시작이 종료보다 늦으면 셈에서 뒤바꿔 본다).
  const rangeWith = (field: DateField, t: number): Partial<StatsUiState> =>
    field === "from" ? { preset: "custom", from: iso(t), to: iso(b) } : { preset: "custom", from: iso(a), to: iso(t) };
  const dateField = (field: DateField) => {
    const draft = field === "from" ? s.fromDraft : s.toDraft;
    const draftPatch = (text: string | null): Partial<StatsUiState> =>
      field === "from" ? { fromDraft: text } : { toDraft: text };

    return {
      value: draft ?? iso(field === "from" ? a : b),
      // 치는 글자는 칸에 그대로 두고, 올바른 날짜가 되었을 때만 기간에 넣는다.
      // 휴대폰 숫자 자판(inputMode numeric)에는 '-' 가 없을 수 있어 숫자 8자리(20260930)는 YYYY-MM-DD 로 바꿔 받는다.
      onChange: (e: { target: { value: string } }) => {
        const raw = e.target.value.slice(0, 10);
        const text = /^\d{8}$/.test(raw) ? `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6)}` : raw;
        const t = allowed(text);
        setUi(t === null ? draftPatch(text) : { ...draftPatch(text), ...rangeWith(field, t) });
      },
      // 칸을 나가면 친 글자를 버리고 지금 기간을 보인다(다 치지 않았거나 틀린 날짜면 원래 날짜로 돌아간다).
      onBlur: () => setUi(draftPatch(null)),
      picker: pickerValues({
        field,
        value: field === "from" ? a : b,
        min: minT,
        max: todayT,
        dp: s.dp,
        setUi,
        pick: (t) => setUi({ ...rangeWith(field, t), ...draftPatch(null), dp: null }),
      }),
    };
  };
  const badDraft = [s.fromDraft, s.toDraft].some((d) => d !== null && d.length === 10 && allowed(d) === null);
  const first = new Date(Date.UTC(s.cy, s.cm, 1)).getUTCDay();
  const dim = new Date(Date.UTC(s.cy, s.cm + 1, 0)).getUTCDate();
  const cal = [];
  for (let i = 0; i < Math.ceil((first + dim) / 7) * 7; i++) {
    const dd = i - first + 1;
    const ok = dd >= 1 && dd <= dim;
    const t = Date.UTC(s.cy, s.cm, dd);
    const future = t > todayT;
    const edge = ok && (t === a || t === b);
    cal.push({
      n: ok ? String(dd) : "",
      off: !ok || future,
      aria: ok ? iso(t) : "빈 칸",
      bg: edge ? "#2B2A26" : ok && inRange(t) ? "#F1EADA" : "transparent",
      fg: edge ? "#EADBB5" : future ? "#CFC9BB" : "#2B2A26",
      fw: edge ? 700 : 400,
      pick: () => {
        if (!ok || future) return;
        const d = iso(t);
        if (s.pickStage === 0) setUi({ preset: "custom", from: d, to: d, pickStage: 1 });
        else {
          const before = t < dayOf(s.from);
          setUi({ preset: "custom", from: before ? d : s.from, to: before ? s.from : d, pickStage: 0 });
        }
      },
    });
  }
  const fmt = (t: number) => `${new Date(t).getUTCFullYear()}.${new Date(t).getUTCMonth() + 1}.${new Date(t).getUTCDate()}`;

  return {
    ...sidebarValues(session),
    notice: screenNotice({ session, loading: overview.loading, error: overview.error, retry: overview.reload }),
    scopeLabel: `${scope} 기준`,
    notes,
    presets,
    rangeLabel: `${fmt(a)} ~ ${fmt(b)} · ${days}일`,
    showCal: s.cal,
    calCls: s.cal ? "btn-p" : "btn-s",
    toggleCal: () => setUi({ cal: !s.cal, pickStage: 0 }),
    fromField: dateField("from"),
    toField: dateField("to"),
    dateHint: badDraft
      ? `날짜는 YYYY-MM-DD(또는 숫자 8자리)로 ${iso(minT)} ~ ${today} 사이에서 넣어 주세요. 칸을 나가면 원래 날짜로 돌아갑니다.`
      : "",
    calLabel: `${s.cy}년 ${s.cm + 1}월`,
    cal,
    pickHint: s.pickStage === 1 ? "종료일 선택" : "",
    calPrev: () => setUi(s.cm === 0 ? { cy: s.cy - 1, cm: 11 } : { cm: s.cm - 1 }),
    calNext: () => setUi(s.cm === 11 ? { cy: s.cy + 1, cm: 0 } : { cm: s.cm + 1 }),
    k,
    trend,
    binLabel: reportTrend.weekly ? "주별" : "월별",
    trendAria: loaded ? trend.map((t) => `${t.label} ${t.v}건`).join(", ") : unloadedText,
    types: [] as { name: string; v: number; p: string; w: string; tip: string }[],
    ages,
    ageAria: loaded ? ages.map((x) => `${x.name} ${x.p}`).join(", ") : unloadedText,
    actors: [] as { name: string; v: number; p: string; w: string; top: string }[],
    regions: [] as { name: string; org: string; v: number; p: string; w: string; away: number; joint: number }[],
    joints: [] as { cg: string; co: string; pg: string; po: string; v: number }[],
    noJoint: false,
    rgSum: "",
    mgAsOf: fmt(b),
    mgStd: s.mgStd,
    setMgStd: (e: { target: { value: string } }) => setUi({ mgStd: e.target.value.slice(0, 2) }),
    mgKpi,
    mgBins,
    mgStaff,
    svc,
    svcAria: svc.map((x) => `${x.label} ${x.v}회`).join(", "),
    insights: [] as string[],
    pendingNote: `${NOT_READY}입니다(학대 유형 · 행위자 자료가 서버에 없음).`,
    regionNote: `${NOT_READY}입니다(아동 · 보호자 거주 지역과 관할 기관 자료가 서버에 없음).`,
    notReadyNote: `${NOT_READY}입니다(원천 데이터와 지표 정의가 팀 결정 전).`,
  };
}
