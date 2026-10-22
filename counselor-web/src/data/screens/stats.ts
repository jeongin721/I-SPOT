// 통계(Stats) 화면 값. useCaseOverview(mode "sessions") 의 사례 · 회차를 기간으로 걸러 센다.
//
// 지금 Backend 로 셀 수 있는 것만 센다(specs 대응표 Stats 줄 '보완'):
//  - 사례 수 · 진행/종결 수(지금 상태), 기간 안에 등록한 사례 수(사례 등록일 created_at 기준), 기간 안의 상담 회차 수(상담 일시 기준).
//  - 사례 등록 추이(등록일별) · 상담 회차 추이(상담일별).
// 사례 등록일은 신고접수일이 아니다 — '신고 접수' 라고 부르지 않는다. 상담 일시를 넣지 않은 회차는 등록일로 대신하지 않고 뺀다.
// 디자인의 신고 접수 · 학대 판단 · 재신고 · 서비스 지표, 유형 · 연령 · 행위자 · 서비스 분포, AI 요약은 원천 데이터와 지표 정의가
// 팀 결정 전이라 '—' · 준비 중으로 둔다.
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

  return { preset: "m3", from, to, fromDraft: null, toDraft: null, dp: null, cal: false, cy: y, cm: m - 1, pickStage: 0 };
}

interface Bar {
  /** 칸의 건수. 아직 못 불러왔거나 불러오지 못했으면 NOT_PROVIDED. */
  v: number | string;
  h: string;
  label: string;
  tip: string;
}

/** 날짜 목록을 기간 a~b 의 칸(62일 이하는 주별, 넘으면 월별)으로 센다. */
function trendBars(dates: number[], a: number, b: number, unit: string): { bars: Bar[]; weekly: boolean } {
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

  const createdIn = created.filter(inRange).length;
  const consultedIn = consulted.filter(inRange).length;
  const active = items.filter((item) => item.caseRow.status === "ACTIVE").length;
  const closed = items.length - active;
  const caseTrend = trendBars(created.filter(inRange), a, b, "사례 등록");
  const sessionTrend = trendBars(consulted.filter(inRange), a, b, "상담 회차");

  const loaded = overview.data !== null;
  // 아직 못 불러왔거나 불러오지 못했으면 칸 이름만 두고 값은 '—' 로 둔다(조회한 결과 0건과 구별되게).
  const unloadedText = overview.error ? "사례 정보를 불러오지 못해 추이를 보일 수 없습니다." : "불러오는 중…";
  const trendValues = (bars: Bar[], unit: string) =>
    loaded
      ? { bars, aria: bars.map((t) => `${t.label} ${t.v}${unit}`).join(", ") }
      : {
          bars: bars.map((t) => ({ ...t, v: NOT_PROVIDED, h: "0px", tip: `${t.tip.split(" · ")[0]} · ${unloadedText}` })),
          aria: unloadedText,
        };
  const caseTrendView = trendValues(caseTrend.bars, "건");
  const sessionTrendView = trendValues(sessionTrend.bars, "회");
  const num = (value: number, unit: string) => (loaded ? `${value}${unit}` : NOT_PROVIDED);
  const scope = overview.wholeOrg ? "기관 전체 사례" : "담당 사례";
  const kpis = [
    {
      label: `사례 (${overview.wholeOrg ? "전체" : "담당"})`,
      value: num(items.length, "건"),
      note: loaded ? `지금 진행 ${active} · 종결 ${closed}` : "",
    },
    {
      label: "기간 안에 등록한 사례",
      value: num(createdIn, "건"),
      note: loaded ? `하루 평균 ${(createdIn / days).toFixed(1)}건 · 사례 등록일 기준` : "",
    },
    {
      label: "기간 안의 상담 회차",
      value: num(consultedIn, "회"),
      note: loaded ? `상담일 기준${undated ? ` · 상담 일시 없는 ${undated}회 뺌` : ""}` : "",
    },
  ];
  // 디자인의 지표 카드. 원천 데이터 · 지표 정의가 팀 결정 전이라 값을 만들지 않는다.
  const pendingKpis = ["신고 접수", "학대 판단 사례", "재신고 사례", "서비스 제공"].map((label) => ({
    label,
    value: NOT_PROVIDED,
    note: NOT_READY,
  }));

  const notes: string[] = [];
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
    kpis,
    pendingKpis,
    binLabel: caseTrend.weekly ? "주별" : "월별",
    caseTrend: caseTrendView.bars,
    caseTrendAria: caseTrendView.aria,
    sessionTrend: sessionTrendView.bars,
    sessionTrendAria: sessionTrendView.aria,
    caseTrendNote: "사례를 이 시스템에 등록한 날 기준입니다(신고접수일이 아닙니다).",
    sessionTrendNote: "회차에 넣은 상담 일시 기준입니다.",
    notReadyNote: `${NOT_READY}입니다(원천 데이터와 지표 정의가 팀 결정 전).`,
  };
}
