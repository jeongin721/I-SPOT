// 일정(Schedule) 화면 값. 11/02 디자인 '일정 · 월간 달력 + 일정 추가' 의 동작을 서버 일정(useSchedule, API_CONTRACT 19절)으로 그린다.
//
//  - 상담 일정(● 둥근 표시)은 사례 · 상담 유형, 개인 · 기관 일정(■ 네모 표시)은 분류 · 제목. 중요 일정은 빨간색.
//  - 최초접수의 법정 기한(판정 후 3일 유선 상담 · 7일 주변 인물 만남 · 30일 계획서 제출)은 행이 아니라 접수일로 계산하고,
//    기한마다 '완료 표시' 만 서버(deadline_done)에 남긴다. 기한은 접수 일정을 고치거나 지우면 같이 바뀐다.
//    기한은 접수한 상담사(만든 사람) 달력 · 알림 종에만 놓는다. 최초접수는 팀 공유하지 않는다(서버도 막는다).
//  - 팀 공유한 남의 일정은 보기만 한다(editable=false — 수정 · 삭제 · 중요 표시를 막는다).
//  - 종결평가 회의 일정 잡기(종결보고서 화면)에서 오면 '사례회의 · 종결평가 회의' 추가 창이 열린 채로 시작하고, 달력에서 날을
//    고르면 그 날로 잡힌다(?case= 사례를 붙인다).
// '상담 전날 브리핑 자동 준비' 는 서버에 없는 기능이라 준비 중이다(체크 상자를 막아 둔다).

import {
  SCHEDULE_CATEGORY_LABELS,
  SCHEDULE_CONSULT_LABELS,
  type ScheduleCategory,
  type ScheduleConsultType,
  type ScheduleEvent,
  type ScheduleEventCreate,
} from "../../api/types";
import { pad2 } from "../time";
import type { AuthSession } from "../useAuthSession";
import type { ScheduleState } from "../useSchedule";
import { NOT_READY, screenNotice, sidebarValues } from "./common";

export type ScheduleFilter = "all" | "c" | "p" | "i";

/** 화면에 놓는 일정 하나를 가리킨다. 법정 기한은 접수 일정 id + 기한 일 수. */
export interface ScheduleViewKey {
  id: string;
  dl?: number;
}

export interface ScheduleForm {
  child: string;
  ctype: ScheduleConsultType;
  pcat: ScheduleCategory;
  title: string;
  date: string;
  time: string;
  place: string;
  imp: boolean;
  shared: boolean;
  /** 개인 · 기관 일정(최초접수 밖)에 붙는 사례 — 종결평가 회의 일정 잡기에서 온 것 · 고치는 일정의 것만. 창에는 칸이 없다. */
  link: string;
}

/** 화면만의 상태: 보이는 해 · 달(0~11), 고른 날, 보기 종류, 추가 · 수정 창, 보는 일정, 삭제 확인. */
export interface ScheduleUiState {
  y: number;
  m: number;
  sel: number;
  filter: ScheduleFilter;
  adding: boolean;
  kind: "c" | "p";
  form: ScheduleForm;
  view: ScheduleViewKey | null;
  /** 고치는 일정 id(없으면 새 일정). */
  edit: { id: string; allDay: boolean } | null;
  delAsk: boolean;
}

const EMPTY_FORM: ScheduleForm = {
  child: "",
  ctype: "REGULAR",
  pcat: "AGENCY_MEETING",
  title: "",
  date: "",
  time: "10:00",
  place: "",
  imp: false,
  shared: false,
  link: "",
};

/** 종결평가 회의 일정 잡기(종결보고서 화면 링크의 preset). */
export const CLOSURE_MEETING_PRESET = "closure-meeting";
export const PRESET_PARAM = "preset";
export const CLOSURE_MEETING_TITLE = "종결평가 회의";
/** 그 날 달력으로 바로 가기(알림 종의 법정 기한 알림): ?date=YYYY-MM-DD. */
export const DATE_PARAM = "date";

/** ?date= 값을 사용자 달력 날짜로. 형식이 틀리면 null. */
export function dateFromParam(value: string | null): Date | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [y, m, d] = value.split("-").map((part) => parseInt(part, 10));
  const date = new Date(y, m - 1, d);
  return date.getMonth() === m - 1 ? date : null;
}

export function initialScheduleState(
  now: Date = new Date(),
  preset: { preset: string | null; caseId: string | null } = { preset: null, caseId: null },
): ScheduleUiState {
  const base: ScheduleUiState = {
    y: now.getFullYear(),
    m: now.getMonth(),
    sel: now.getDate(),
    filter: "all",
    adding: false,
    kind: "c",
    form: { ...EMPTY_FORM },
    view: null,
    edit: null,
    delAsk: false,
  };

  if (preset.preset === CLOSURE_MEETING_PRESET) {
    return {
      ...base,
      adding: true,
      kind: "p",
      form: { ...EMPTY_FORM, pcat: "CASE_MEETING", title: CLOSURE_MEETING_TITLE, link: preset.caseId ?? "" },
    };
  }
  return base;
}

const DAYS = ["일", "월", "화", "수", "목", "금", "토"];
const HOLIDAYS: Record<string, string> = { "2026-9-3": "개천절", "2026-9-9": "한글날" };

/** 최초접수 뒤 법정 기한(일 · 할 일). backend INTAKE_DEADLINE_DAYS 와 같다. */
export const INTAKE_TASKS: [number, string][] = [
  [3, "아동과 유선(전화) 상담"],
  [7, "아동 주변 인물 만남"],
  [30, "계획서 제출"],
];

/** 보이는 달을 덮는 조회 기간(앞뒤 7일 — 달력 첫 주 · 마지막 주). */
export function scheduleRange(y: number, m: number): { from: string; to: string } {
  const start = new Date(y, m, 1 - 7);
  const end = new Date(y, m + 1, 7);
  const ymd = (d: Date) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  return { from: ymd(start), to: ymd(end) };
}

/** 달력에 놓는 일정 하나(서버 일정 또는 법정 기한). y · m(0~11) · d 는 사용자 달력 날짜. */
export interface CalendarItem {
  key: ScheduleViewKey;
  y: number;
  m: number;
  d: number;
  /** 'HH:MM' · '종일' · '기한'. */
  time: string;
  t: "c" | "p";
  title: string;
  sub: string;
  tag: string;
  imp: boolean;
  event: ScheduleEvent;
  dl?: number;
  done?: boolean;
  place: string;
}

function parseYmd(value: string): { y: number; m: number; d: number } {
  const [y, m, d] = value.split("-").map((part) => parseInt(part, 10));
  return { y, m: m - 1, d };
}

/** 서버 일정 → 달력 일정(최초접수는 법정 기한 3건이 따라붙는다). 남의 공유 일정은 만든 사람을 붙인다. */
export function calendarItems(events: ScheduleEvent[], myId: string | null): CalendarItem[] {
  const items: CalendarItem[] = [];

  for (const event of events) {
    const { y, m, d } = parseYmd(event.date);
    const alias = event.child_alias ?? "";
    const place = event.place ?? "";
    const others = myId && event.owner_id !== myId && event.owner_name ? ` · ${event.owner_name}` : "";
    const time = event.time ?? "종일";

    if (event.kind === "CONSULT") {
      const type = event.consult_type ? SCHEDULE_CONSULT_LABELS[event.consult_type] : "상담";
      items.push({
        key: { id: event.id }, y, m, d, time, t: "c", event, place,
        title: alias ? `${alias} · ${type}` : type,
        sub: (place || "장소 미정") + others,
        tag: "상담",
        imp: event.important,
      });
      continue;
    }

    const category = event.category ? SCHEDULE_CATEGORY_LABELS[event.category] : "기타";

    if (event.category === "INTAKE") {
      items.push({
        key: { id: event.id }, y, m, d, time, t: "p", event, place,
        title: `${alias || "—"} · 최초접수`,
        sub: (place ? `최초접수 · ${place}` : "최초접수 · 학대 판정 후 이관") + others,
        tag: "최초접수",
        imp: event.important,
      });
      // 법정 기한은 접수한 상담사(만든 사람)의 할 일 — 관리자 · 다른 상담사 달력에는 접수 일정만 놓는다(민규 #131 리뷰).
      if (!myId || event.owner_id !== myId) continue;
      for (const [days, task] of INTAKE_TASKS) {
        const due = new Date(y, m, d + days);
        const done = Boolean(event.deadline_done[String(days)]);
        items.push({
          key: { id: event.id, dl: days },
          y: due.getFullYear(), m: due.getMonth(), d: due.getDate(),
          time: "기한", t: "p", event, place: "",
          title: `${done ? "✓ " : ""}${alias || "—"} · ${task}`,
          sub: `판정 후 ${days}일 이내 · ${m + 1}/${d} 접수`,
          tag: "법정 기한",
          imp: !done,
          dl: days,
          done,
        });
      }
      continue;
    }

    const name = event.title || category;
    items.push({
      key: { id: event.id }, y, m, d, time, t: "p", event, place,
      title: alias ? `${alias} · ${name}` : name,
      sub: (place ? `${category} · ${place}` : category) + others,
      tag: category,
      imp: event.important,
    });
  }
  return items;
}

const timeRank = (time: string) => (time === "종일" ? 0 : time === "기한" ? 1 : 2);
export const byTime = (a: CalendarItem, b: CalendarItem) => timeRank(a.time) - timeRank(b.time) || a.time.localeCompare(b.time);

const sameKey = (a: ScheduleViewKey | null, b: ScheduleViewKey) => Boolean(a) && a!.id === b.id && (a!.dl ?? 0) === (b.dl ?? 0);

function itemStyle(e: CalendarItem) {
  return e.imp
    ? { bg: "#F7E4DF", fg: "#A33B2E", dot: "#A33B2E", radius: e.t === "c" ? "50%" : "2px", tagBg: "#F7E4DF", tagFg: "#A33B2E", fw: 700 }
    : e.t === "c"
      ? { bg: "#F2EFE8", fg: "#2B2A26", dot: "#7A776F", radius: "50%", tagBg: "#F2EFE8", tagFg: "#66625A", fw: 400 }
      : { bg: "#F7F6F2", fg: "#66625A", dot: "#B9B2A2", radius: "2px", tagBg: "#F7F6F2", tagFg: "#66625A", fw: 400 };
}

interface ScheduleInput {
  session: AuthSession;
  schedule: ScheduleState;
  ui: ScheduleUiState;
  setUi: (patch: Partial<ScheduleUiState>) => void;
  /** 오늘. 시험할 때만 넘긴다. */
  now?: Date;
}

export function scheduleValues(input: ScheduleInput) {
  const { session, schedule, ui: s, setUi } = input;
  const now = input.now ?? new Date();
  const me = session.status === "signedIn" ? session.me : null;
  const data = schedule.data;
  const all = calendarItems(data?.events ?? [], me?.id ?? null);
  const caseOptions = data?.cases ?? [];
  const show = (e: CalendarItem) => s.filter === "all" || (s.filter === "i" ? e.imp : e.t === s.filter);
  const onDay = (d: number) => all.filter((e) => e.y === s.y && e.m === s.m && e.d === d && show(e)).sort(byTime);
  const busy = schedule.busy;

  const open = (key: ScheduleViewKey, d: number) => setUi({ sel: d, view: key, adding: false, edit: null, delAsk: false });

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
      aria: valid ? `${s.m + 1}월 ${d}일 일정 ${evs.length}건` : "빈 칸",
      bg: valid ? (isSel ? "#F1EADA" : "#FFFFFF") : "#F7F6F2",
      ring: isSel ? "inset 0 0 0 2px #2B2A26" : "none",
      numBg: isToday ? "#2B2A26" : "transparent",
      numFg: isToday ? "#FFFFFF" : hol || dow === 0 ? "#7A776F" : "#2B2A26",
      fw: isToday || isSel ? 700 : 400,
      pills: evs.slice(0, 3).map((e) => {
        const st = itemStyle(e);
        return {
          label: `${e.time === "종일" ? "" : `${e.time} `}${e.title}`,
          bg: st.bg,
          fg: st.fg,
          fw: st.fw,
          dot: st.dot,
          radius: st.radius,
          tip: `${e.title} · 자세히 보기`,
          open: (ev?: { stopPropagation?: () => void }) => {
            ev?.stopPropagation?.();
            open(e.key, d);
          },
        };
      }),
      more: evs.length > 3 ? `+${evs.length - 3}건 더` : "",
      // 추가 · 수정 창이 열려 있으면 그대로 두고 날만 바꾼다(종결평가 회의 일정 잡기: 날을 고르면 그 날로 잡힌다).
      pick: () => {
        if (valid) setUi({ sel: d, view: null, delAsk: false });
      },
    });
  }

  const patch = (e: CalendarItem, body: Parameters<ScheduleState["update"]>[1]) => {
    if (!busy && e.event.editable) void schedule.update(e.event.id, body);
  };

  const dayEvents = onDay(s.sel).map((e) => {
    const st = itemStyle(e);
    const on = e.imp;
    const go = () => open(e.key, s.sel);
    const stop = (fn: () => void) => (ev?: { stopPropagation?: () => void }) => {
      ev?.stopPropagation?.();
      fn();
    };
    const row = {
      time: e.time,
      title: e.title,
      sub: e.sub,
      tag: e.tag,
      dot: st.dot,
      radius: st.radius,
      tagBg: st.tagBg,
      tagFg: st.tagFg,
      fw: on ? 700 : 500,
      titleFg: on ? "#A33B2E" : "#2B2A26",
      impOn: on ? "true" : "false",
      impLabel: on ? "! 중요" : "중요 표시",
      impBg: on ? "#A33B2E" : "#FFFFFF",
      impFg: on ? "#FFFFFF" : "#7A776F",
      impBd: on ? "#A33B2E" : "#DAD5C9",
      impDisabled: !e.event.editable || busy,
      toggleImp: stop(() => patch(e, { important: !e.event.important })),
      open: go,
      key: (ev: { key?: string; preventDefault?: () => void }) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault?.();
          go();
        }
      },
      aria: `${e.title} 자세히 보기`,
    };
    if (e.dl) {
      const dn = Boolean(e.done);
      return {
        ...row,
        fw: dn ? 500 : 700,
        titleFg: dn ? "#7A776F" : "#A33B2E",
        impOn: dn ? "true" : "false",
        impLabel: dn ? "✓ 완료" : "완료 표시",
        impBg: dn ? "#2B2A26" : "#FFFFFF",
        impFg: dn ? "#FFFFFF" : "#7A776F",
        impBd: dn ? "#2B2A26" : "#DAD5C9",
        toggleImp: stop(() => patch(e, { deadline_done: { [String(e.dl)]: !dn } })),
      };
    }
    return row;
  });

  const monthEv = all.filter((e) => e.y === s.y && e.m === s.m);
  const vItem = s.view ? all.find((e) => sameKey(s.view, e.key)) ?? null : null;
  const dLabel = (e: { y: number; m: number; d: number }) =>
    `${e.y}년 ${e.m + 1}월 ${e.d}일 ${DAYS[new Date(e.y, e.m, e.d).getDay()]}요일`;
  const isC = s.kind === "c";
  const setForm = (patchForm: Partial<ScheduleForm>) => setUi({ form: { ...s.form, ...patchForm } });
  const setF = (k: keyof ScheduleForm) => (ev: { target: { value: string } }) => setForm({ [k]: ev.target.value } as Partial<ScheduleForm>);

  let v: Record<string, unknown> = {};
  if (vItem) {
    const e = vItem;
    const st = itemStyle(e);
    const isDl = Boolean(e.dl);
    const intake = e.event.category === "INTAKE";
    const rows: [string, string][] = [
      ["날짜", dLabel(e)],
      ["시간", isDl ? "마감일" : e.time],
    ];
    if (isDl) {
      rows.push(["내용", e.sub]);
      rows.push(["상태", e.done ? "완료" : "진행 전"]);
    } else if (e.t === "c") {
      rows.push(["아이", e.event.child_alias ?? "—"]);
      rows.push(["상담 유형", e.event.consult_type ? SCHEDULE_CONSULT_LABELS[e.event.consult_type] : "—"]);
      rows.push(["장소", e.place || "—"]);
    } else {
      if (e.event.child_alias) rows.push(["아이", e.event.child_alias]);
      rows.push(["분류", e.tag]);
      rows.push(["장소", e.place || "—"]);
    }
    rows.push(["중요", e.imp && !isDl ? "중요 일정" : "—"]);
    if (e.event.shared) rows.push(["공유", e.event.editable ? "팀 일정으로 공유" : `팀 공유 · ${e.event.owner_name ?? "—"}`]);
    const ask = s.delAsk;
    const canEdit = !isDl && e.event.editable;
    v = {
      kind: isDl ? "법정 기한" : e.t === "c" ? "상담 일정" : "개인 · 기관 일정",
      title: e.title,
      dot: st.dot,
      radius: st.radius,
      titleFg: e.imp ? "#A33B2E" : "inherit",
      rows: rows.map(([k, val]) => ({ k, v: val })),
      isDl,
      canEdit,
      ask,
      noAsk: !ask,
      askNote: intake && !isDl ? "최초접수와 함께 만들어진 법정 기한 일정 3건도 같이 삭제되고, 알림에서도 빠져요." : "삭제하면 되돌릴 수 없어요.",
      doneLabel: e.done ? "✓ 완료 취소" : "완료 표시",
      doneCls: e.done ? "btn-s" : "btn-p",
      toggleDone: () => patch(e, { deadline_done: { [String(e.dl)]: !e.done } }),
      goBase: () => {
        const base = parseYmd(e.event.date);
        setUi({ y: base.y, m: base.m, sel: base.d, view: { id: e.event.id } });
      },
      askDel: () => setUi({ delAsk: true }),
      cancelDel: () => setUi({ delAsk: false }),
      del: async () => {
        if (busy || !canEdit) return;
        if (await schedule.remove(e.event.id)) setUi({ view: null, delAsk: false });
      },
      edit: () => {
        const ev = e.event;
        setUi({
          adding: true,
          kind: ev.kind === "CONSULT" ? "c" : "p",
          form: {
            child: ev.case_id ?? "",
            ctype: ev.consult_type ?? "REGULAR",
            pcat: ev.category ?? "AGENCY_MEETING",
            title: ev.title ?? "",
            date: ev.date,
            time: ev.time ?? "",
            place: ev.place ?? "",
            imp: ev.important,
            shared: ev.shared,
            link: ev.kind === "OTHER" && ev.category !== "INTAKE" ? ev.case_id ?? "" : "",
          },
          edit: { id: ev.id, allDay: ev.time === null },
          delAsk: false,
        });
      },
    };
  }

  const selDate = new Date(s.y, s.m, s.sel);
  const isIntake = !isC && s.form.pcat === "INTAKE";
  const needsCase = isC || isIntake;
  const chosenCase = s.form.child || caseOptions[0]?.id || "";

  const save = async () => {
    if (busy) return;
    const f = s.form;
    const caseId = needsCase ? chosenCase : f.link || null;
    if (needsCase && !caseId) return;
    const date = s.edit ? f.date || `${s.y}-${pad2(s.m + 1)}-${pad2(s.sel)}` : `${s.y}-${pad2(s.m + 1)}-${pad2(s.sel)}`;
    const time = f.time || (s.edit?.allDay ? null : "10:00");
    const body: ScheduleEventCreate = isC
      ? { kind: "CONSULT", date, time, place: f.place, important: f.imp, case_id: caseId, consult_type: f.ctype }
      : {
          kind: "OTHER",
          date,
          time,
          place: f.place,
          important: f.imp,
          case_id: caseId,
          category: f.pcat,
          title: isIntake ? null : f.title,
          shared: !isIntake && f.shared,
        };
    const saved = s.edit ? await schedule.update(s.edit.id, body) : await schedule.create(body);
    if (!saved) return;
    const at = parseYmd(saved.date);
    setUi({
      adding: false,
      edit: null,
      view: s.edit ? null : s.view,
      y: at.y,
      m: at.m,
      sel: at.d,
      form: { ...EMPTY_FORM, ctype: f.ctype, pcat: f.pcat === "INTAKE" ? "AGENCY_MEETING" : f.pcat },
    });
  };

  const pick = (filter: ScheduleFilter) => () => setUi({ filter });

  let saveNote = "";
  if (needsCase && caseOptions.length === 0 && data) saveNote = "일정에 붙일 진행 중 사례가 없습니다.";

  return {
    ...sidebarValues(session),
    notice: screenNotice({
      session,
      loading: schedule.loading,
      error: schedule.error ?? schedule.actionError,
      retry: schedule.error ? schedule.reload : undefined,
    }),
    monthLabel: `${s.y}년 ${s.m + 1}월`,
    cells,
    dayEvents,
    noEvents: dayEvents.length === 0,
    selLabel: `${s.m + 1}월 ${s.sel}일 ${DAYS[selDate.getDay()]}요일`,
    countC: monthEv.filter((e) => e.t === "c").length,
    countP: monthEv.filter((e) => e.t === "p").length,
    countI: monthEv.filter((e) => e.imp).length,
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
    adding: s.adding,
    notAdding: !s.adding && !vItem,
    viewing: !s.adding && Boolean(vItem),
    v,
    vBack: () => setUi({ view: null, delAsk: false }),
    isEdit: Boolean(s.edit),
    formTitle: s.edit ? "일정 수정" : "일정 추가",
    formDateLabel: s.edit ? "" : `${s.m + 1}월 ${s.sel}일 ${DAYS[selDate.getDay()]}요일`,
    setDate: setF("date"),
    openAdd: () => setUi({ adding: true, edit: null, form: { ...s.form, title: "", place: "", imp: false, shared: false, link: "" } }),
    cancelAdd: () => setUi({ adding: false, edit: null }),
    isC,
    isP: !isC,
    isIntake,
    notIntake: !isIntake,
    caseOptions: caseOptions.map((c) => ({ value: c.id, label: c.alias })),
    consultOptions: (Object.keys(SCHEDULE_CONSULT_LABELS) as ScheduleConsultType[]).map((k) => ({ value: k, label: SCHEDULE_CONSULT_LABELS[k] })),
    categoryOptions: (Object.keys(SCHEDULE_CATEGORY_LABELS) as ScheduleCategory[]).map((k) => ({ value: k, label: SCHEDULE_CATEGORY_LABELS[k] })),
    dlPreview: INTAKE_TASKS.map(([n, task]) => {
      const dd = new Date(s.y, s.m, s.sel + n);
      return { n: `${n}일 이내`, task, due: `${dd.getMonth() + 1}/${dd.getDate()}(${DAYS[dd.getDay()]})` };
    }),
    kindC: () => setUi({ kind: "c" }),
    kindP: () => setUi({ kind: "p" }),
    kcBorder: isC ? "#2B2A26" : "#DAD5C9",
    kcBg: isC ? "#F1EADA" : "#FFFFFF",
    kpBorder: !isC ? "#2B2A26" : "#DAD5C9",
    kpBg: !isC ? "#F1EADA" : "#FFFFFF",
    form: { ...s.form, child: chosenCase },
    formImpOn: s.form.imp ? "true" : "false",
    formImpBd: s.form.imp ? "#A33B2E" : "#DAD5C9",
    formImpBg: s.form.imp ? "#F7E4DF" : "#FFFFFF",
    formImpFg: s.form.imp ? "#A33B2E" : "#66625A",
    formImpBox: s.form.imp ? "#A33B2E" : "#FFFFFF",
    formImpMark: s.form.imp ? "✓" : "",
    toggleFormImp: () => setForm({ imp: !s.form.imp }),
    toggleShared: () => !isIntake && setForm({ shared: !s.form.shared }),
    // 최초접수는 팀 공유하지 않는다(법정 기한은 접수한 상담사 것 — 서버도 shared=false 로 저장).
    sharedDisabled: isIntake,
    sharedOn: !isIntake && s.form.shared,
    setChild: setF("child"),
    setCtype: setF("ctype"),
    setPcat: setF("pcat"),
    setTitle: setF("title"),
    setTime: setF("time"),
    setPlace: setF("place"),
    briefNote: `상담 전날 브리핑 자동 준비는 ${NOT_READY}입니다.`,
    saveNote,
    canSave: !busy && !(needsCase && !chosenCase),
    saveLabel: busy ? "저장 중…" : "저장",
    save,
  };
}
