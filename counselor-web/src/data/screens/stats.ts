// 통계(Stats) 화면 값. useCaseOverview(mode "sessions") 의 사례 · 회차를 기간으로 걸러 센다.
//
// 지금 Backend 로 셀 수 있는 것만 센다(specs 대응표 Stats 줄 '보완'):
//  - 사례 수 · 진행/종결 수(지금 상태), 기간 안에 등록한 사례 수(사례 등록일 created_at 기준), 기간 안의 상담 회차 수(상담 일시 기준).
//  - 사례 등록 추이(등록일별) · 상담 회차 추이(상담일별).
// 사례 등록일은 신고접수일이 아니다 — '신고 접수' 라고 부르지 않는다. 상담 일시를 넣지 않은 회차는 등록일로 대신하지 않고 뺀다.
// 디자인의 신고 접수 · 학대 판단 · 재신고 · 서비스 지표, 유형 · 연령 · 행위자 · 서비스 분포, AI 요약은 원천 데이터와 지표 정의가
// 팀 결정 전이라 '—' · 준비 중으로 둔다.

import { NOT_PROVIDED } from "../caseRows";
import { pad2 } from "../time";
import type { AuthSession } from "../useAuthSession";
import type { CaseOverviewState } from "../useCaseOverview";
import { NOT_READY, screenNotice, sidebarValues } from "./common";

const DAY_MS = 864e5;

/** 화면만의 상태: 기간 프리셋 · 시작/종료일 · 달력. */
export interface StatsUiState {
  preset: "m1" | "m3" | "all" | "custom";
  /** YYYY-MM-DD. preset 이 "all" 이면 쓰지 않는다(모은 자료의 가장 이른 날부터). */
  from: string;
  to: string;
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

function presetRange(preset: "m1" | "m3", today: string): [string, string] {
  const [y, m, d] = today.split("-").map(Number);

  if (preset === "m1") return [`${y}-${pad2(m)}-01`, today];

  // 최근 3개월: 석 달 전 같은 날의 다음 날부터 오늘까지(디자인 예: 7/13 ~ 10/12).
  return [iso(Date.UTC(y, m - 1 - 3, d + 1)), today];
}

export function initialStatsState(today: string = localToday()): StatsUiState {
  const [from, to] = presetRange("m3", today);
  const [y, m] = today.split("-").map(Number);

  return { preset: "m3", from, to, cal: false, cy: y, cm: m - 1, pickStage: 0 };
}

interface Bar {
  v: number;
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
  const lo = s.preset === "all" ? earliest : dayOf(s.from || today);
  const hi = s.preset === "all" ? todayT : dayOf(s.to || today);
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

  // 기간 프리셋 · 달력(디자인 그대로)
  const presets = (
    [
      ["m1", "이번 달"],
      ["m3", "최근 3개월"],
      ["all", "전체"],
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
    from: iso(a),
    to: iso(b),
    today,
    rangeLabel: `${fmt(a)} ~ ${fmt(b)} · ${days}일`,
    showCal: s.cal,
    calCls: s.cal ? "btn-p" : "btn-s",
    toggleCal: () => setUi({ cal: !s.cal, pickStage: 0 }),
    setFrom: (e: { target: { value: string } }) => e.target.value && setUi({ preset: "custom", from: e.target.value, to: iso(b) }),
    setTo: (e: { target: { value: string } }) => e.target.value && setUi({ preset: "custom", from: iso(a), to: e.target.value }),
    calLabel: `${s.cy}년 ${s.cm + 1}월`,
    cal,
    pickHint: s.pickStage === 1 ? "종료일 선택" : "",
    calPrev: () => setUi(s.cm === 0 ? { cy: s.cy - 1, cm: 11 } : { cm: s.cm - 1 }),
    calNext: () => setUi(s.cm === 11 ? { cy: s.cy + 1, cm: 0 } : { cm: s.cm + 1 }),
    kpis,
    pendingKpis,
    binLabel: caseTrend.weekly ? "주별" : "월별",
    caseTrend: caseTrend.bars,
    caseTrendAria: caseTrend.bars.map((t) => `${t.label} ${t.v}건`).join(", "),
    sessionTrend: sessionTrend.bars,
    sessionTrendAria: sessionTrend.bars.map((t) => `${t.label} ${t.v}회`).join(", "),
    caseTrendNote: "사례를 이 시스템에 등록한 날 기준입니다(신고접수일이 아닙니다).",
    sessionTrendNote: "회차에 넣은 상담 일시 기준입니다.",
    notReadyNote: `${NOT_READY}입니다(원천 데이터와 지표 정의가 팀 결정 전).`,
  };
}
