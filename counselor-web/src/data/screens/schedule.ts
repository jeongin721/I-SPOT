// 일정(Schedule) 화면 값. useCaseOverview(mode "sessions") 의 회차 중 상담 일시가 있는 것을 달력에 '상담 회차' 로 놓는다.
//
// 회차의 상담 일시(consulted_at) · 장소(location)만 쓴다(specs 대응표 Schedule 줄 '보완'). 누르면 회차 상세로 간다.
// 상담 일시를 넣지 않은 회차는 등록일로 대신하지 않고 달력에서 뺀다(몇 건인지 알린다).
// 일정과 회차의 관계 · 개인/기관 일정 · 일정 추가 · 중요 표시 · 팀 공유 · 브리핑 자동 준비는 팀 결정 전이라 준비 중이다.

import { NOT_PROVIDED } from "../caseRows";
import { pad2 } from "../time";
import type { AuthSession } from "../useAuthSession";
import type { CaseOverviewState } from "../useCaseOverview";
import { NOT_READY, screenNotice, sidebarValues } from "./common";
import { screenHref } from "./links";

export type ScheduleFilter = "all" | "c" | "p" | "i";

/** 화면만의 상태: 보이는 해 · 달(0~11), 고른 날, 보기 종류. */
export interface ScheduleUiState {
  y: number;
  m: number;
  sel: number;
  filter: ScheduleFilter;
}

export function initialScheduleState(now: Date = new Date()): ScheduleUiState {
  return { y: now.getFullYear(), m: now.getMonth(), sel: now.getDate(), filter: "all" };
}

const DAYS = ["일", "월", "화", "수", "목", "금", "토"];
const HOLIDAYS: Record<string, string> = { "2026-9-3": "개천절", "2026-9-9": "한글날" };

/** 달력에 놓는 상담 회차 하나. */
export interface SessionEvent {
  /** YYYY-MM-DD(사용자 시간대). */
  date: string;
  /** HH:mm. */
  time: string;
  title: string;
  sub: string;
  href: string;
}

interface ScheduleInput {
  session: AuthSession;
  overview: CaseOverviewState;
  ui: ScheduleUiState;
  setUi: (patch: Partial<ScheduleUiState>) => void;
  /** 오늘. 시험할 때만 넘긴다. */
  now?: Date;
}

export function sessionEvents(overview: CaseOverviewState): { events: SessionEvent[]; undated: number } {
  const events: SessionEvent[] = [];
  let undated = 0;

  for (const item of overview.data?.items ?? []) {
    for (const row of item.sessions) {
      if (row.consultedAt === NOT_PROVIDED) {
        undated++;
        continue;
      }
      const place = row.location === NOT_PROVIDED ? `장소 ${NOT_PROVIDED}` : row.location;
      events.push({
        date: row.consultedDate,
        time: row.consultedAt.slice(11, 16),
        title: `${item.caseRow.alias} · ${row.numberLabel}`,
        // 관리자는 여러 상담사의 회차를 함께 보므로 담당자를 붙인다.
        sub: overview.wholeOrg ? `${place} · ${item.caseRow.counselorName}` : place,
        href: screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.id }),
      });
    }
  }

  events.sort((p, q) => (p.date + p.time).localeCompare(q.date + q.time));

  return { events, undated };
}

// 상담 회차 표시(디자인의 '상담' 일정 모양). 중요 표시는 준비 중이라 빨간 모양은 쓰지 않는다.
const SESSION_STYLE = { bg: "#F2EFE8", fg: "#2B2A26", dot: "#7A776F", radius: "50%", tagBg: "#F2EFE8", tagFg: "#66625A" };

export function scheduleValues(input: ScheduleInput) {
  const { session, overview, ui: s, setUi } = input;
  const now = input.now ?? new Date();
  const { events, undated } = sessionEvents(overview);
  const loaded = overview.data !== null;
  const showsSessions = s.filter === "all" || s.filter === "c";
  const ymd = (d: number) => `${s.y}-${pad2(s.m + 1)}-${pad2(d)}`;
  const onDay = (d: number) => (showsSessions ? events.filter((e) => e.date === ymd(d)) : []);

  const first = new Date(s.y, s.m, 1).getDay();
  const dim = new Date(s.y, s.m + 1, 0).getDate();
  const total = Math.ceil((first + dim) / 7) * 7;
  const cells = [];
  for (let i = 0; i < total; i++) {
    const d = i - first + 1;
    const valid = d >= 1 && d <= dim;
    const dow = i % 7;
    const evs = valid ? onDay(d) : [];
    const isToday = valid && now.getFullYear() === s.y && now.getMonth() === s.m && now.getDate() === d;
    const isSel = valid && d === s.sel;
    const hol = valid ? HOLIDAYS[`${s.y}-${s.m}-${d}`] || "" : "";
    cells.push({
      num: valid ? String(d) : "",
      holiday: hol,
      aria: valid ? `${s.m + 1}월 ${d}일 상담 회차 ${evs.length}건` : "빈 칸",
      bg: valid ? (isSel ? "#F1EADA" : "#FFFFFF") : "#F7F6F2",
      ring: isSel ? "inset 0 0 0 2px #2B2A26" : "none",
      numBg: isToday ? "#2B2A26" : "transparent",
      numFg: isToday ? "#FFFFFF" : hol || dow === 0 ? "#7A776F" : "#2B2A26",
      fw: isToday || isSel ? 700 : 400,
      pills: evs.slice(0, 3).map((e) => ({
        label: `${e.time} ${e.title}`,
        bg: SESSION_STYLE.bg,
        fg: SESSION_STYLE.fg,
        fw: 400,
        dot: SESSION_STYLE.dot,
        radius: SESSION_STYLE.radius,
      })),
      more: evs.length > 3 ? `+${evs.length - 3}건 더` : "",
      pick: () => {
        if (valid) setUi({ sel: d });
      },
    });
  }

  const dayEvents = onDay(s.sel).map((e) => ({
    time: e.time,
    title: e.title,
    sub: e.sub,
    tag: "상담 회차",
    href: e.href,
    dot: SESSION_STYLE.dot,
    radius: SESSION_STYLE.radius,
    tagBg: SESSION_STYLE.tagBg,
    tagFg: SESSION_STYLE.tagFg,
  }));
  const monthPrefix = `${s.y}-${pad2(s.m + 1)}-`;

  let emptyText = "이 날 상담 회차가 없습니다.";
  if (s.filter === "p") emptyText = `개인 · 기관 일정은 ${NOT_READY}입니다.`;
  else if (s.filter === "i") emptyText = `중요 표시는 ${NOT_READY}입니다.`;
  else if (!loaded) emptyText = "";

  const notes: string[] = [];
  if (undated) notes.push(`상담 일시를 넣지 않은 회차 ${undated}건은 달력에 없습니다.`);
  if (overview.data?.casesTruncated) {
    notes.push(`사례가 많아 최근 등록한 ${overview.data.items.length}건의 회차만 보입니다(전체 ${overview.data.caseTotal}건).`);
  }
  if (overview.data?.sessionsTruncated) notes.push("회차가 아주 많은 사례는 최근 회차만 보입니다.");

  const pick = (filter: ScheduleFilter) => () => setUi({ filter });
  const selDate = new Date(s.y, s.m, s.sel);

  return {
    ...sidebarValues(session),
    notice: screenNotice({ session, loading: overview.loading, error: overview.error, retry: overview.reload }),
    scopeLabel: overview.wholeOrg ? "기관 전체 사례의 상담 회차" : "담당 사례의 상담 회차",
    notes,
    notReadyNote: `개인 · 기관 일정, 일정 추가 · 중요 표시 · 팀 공유는 ${NOT_READY}입니다(일정과 상담 회차의 관계가 팀 결정 전).`,
    monthLabel: `${s.y}년 ${s.m + 1}월`,
    cells,
    dayEvents,
    noEvents: dayEvents.length === 0 && emptyText !== "",
    emptyText,
    selLabel: `${s.m + 1}월 ${s.sel}일 ${DAYS[selDate.getDay()]}요일`,
    countC: loaded ? `${events.filter((e) => e.date.startsWith(monthPrefix)).length}건` : NOT_PROVIDED,
    countP: NOT_READY,
    countI: NOT_READY,
    fAllCls: s.filter === "all" ? "on" : "",
    fCCls: s.filter === "c" ? "on" : "",
    fPCls: s.filter === "p" ? "on" : "",
    fICls: s.filter === "i" ? "on" : "",
    showAll: pick("all"),
    showC: pick("c"),
    showP: pick("p"),
    showI: pick("i"),
    prevMonth: () => setUi(s.m === 0 ? { y: s.y - 1, m: 11, sel: 1 } : { m: s.m - 1, sel: 1 }),
    nextMonth: () => setUi(s.m === 11 ? { y: s.y + 1, m: 0, sel: 1 } : { m: s.m + 1, sel: 1 }),
    goToday: () => {
      const n = new Date();
      setUi({ y: n.getFullYear(), m: n.getMonth(), sel: n.getDate() });
    },
    notReady: NOT_READY,
  };
}
