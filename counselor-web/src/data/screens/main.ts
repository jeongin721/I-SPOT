// 홈(Main) 화면 값. useHomeDashboard 하나로 진행 중 사례 수 · 미처리 업무를 그린다.
//
// Backend 에 없는 값은 지어내지 않는다(specs 대응표 Main 줄 — 팀 결정: 일정 · 아이 앱 긴급 상태 · 일지 대기 기준).
//  - 오늘 일정 · 다음 상담까지 남은 시간(11/02 연결): 일정(API_CONTRACT 20절)에서 오늘 일정 · 지금 뒤 첫 상담 일정을 찾는다.
//  - 긴급 업무(11/10 연결): 확인 안 한 콩콩 알림(GET /child-app-alerts/open). 긴급(긴급 알림 · 바로 확인 답 · 연락 요청) 수를 크게,
//    확인 필요(글 · 추가 질문 답)는 아래 줄에. 아이 앱이 꺼져 있거나 못 받으면 '—'.
//  - 진행 중 내담자 카드 아래 줄(10/30): 최근 등록 사례 3건의 마지막 회차 판단('n회차 판단 · 상') · 그 회차 상태. 디자인의
//    '오늘 16:00 상담' 같은 일정 문구는 쓰지 않는다(카드 줄은 회차 판단이 기준).
//  - 미처리 업무는 회차 처리 대기(/tasks)만 센다. 디자인의 '상담 일지 작성' · '앱 확인' 은 업무 종류에 없다.
//    오래 기다린 업무는 '지연' 이라고 쓴다(위험 신호와 헷갈리지 않게 '긴급' 이라고 쓰지 않는다 — API types TaskItem).
// 시계 · 빠른 실행은 서버와 상관없는 화면 상태다(빠른 실행 편집은 저장하지 않는다).

import { RISK_LEVEL_LABELS, type ChildOpenAlert, type RiskLevel, type TaskType } from "../../api/types";
import { NOT_PROVIDED } from "../caseRows";
import { HOME_TASK_COUNT, type HomeDashboardState, type HomeTask } from "../useHomeDashboard";
import type { ScheduleState } from "../useSchedule";
import { byTime, calendarItems, type CalendarItem } from "./schedule";
import type { AuthSession } from "../useAuthSession";
import { pad2 } from "../time";
import { SESSION_STATUS_LABELS } from "../sessionRows";
import { NOT_READY, screenNotice } from "./common";
import { STEP_SCREEN } from "./flow";
import { screenHref } from "./links";

const QUICK_POOL = {
  upload: { label: "녹취 올리기", icon: "↑", href: "/UploadModal" },
  schedule: { label: "일정 추가", icon: "+", href: "/Schedule" },
  closure: { label: "종결 검토", icon: "✓", href: "/Closure" },
  search: { label: "사례 찾기", icon: "⌕", href: "/CaseList" },
  stats: { label: "통계", icon: "▦", href: "/Stats" },
  briefing: { label: "상담 전 브리핑", icon: "☰", href: "/PreBriefing" },
} as const;

type QuickKey = keyof typeof QUICK_POOL;

const HOME_RISK_CHIP: Record<RiskLevel, string> = { HIGH: "c-hi", MEDIUM: "c-mid", LOW: "c-lo" };

export interface MainUiState {
  now: Date;
  editing: boolean;
  quick: QuickKey[];
}

export function initialMainState(): MainUiState {
  return { now: new Date(), editing: false, quick: ["upload", "schedule", "closure", "search"] };
}

/** 업무 종류 칩. 색만으로 구분하지 않도록 칩 글자는 늘 업무 이름이다. */
const TASK_CHIP: Record<TaskType, string> = {
  UPLOAD_AUDIO: "chip c-check",
  REQUEST_STT: "chip c-sky",
  REVIEW_TRANSCRIPT: "chip c-sand",
  REQUEST_ANALYSIS: "chip c-sky",
  REVIEW_ANALYSIS: "chip c-sand",
  RETRY_STT: "chip c-urgent",
  RETRY_ANALYSIS: "chip c-urgent",
};

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** 업무 한 줄 → 그 회차에서 이어서 할 화면. */
export function homeTaskHref(task: Pick<HomeTask, "step" | "caseId" | "sessionId">): string {
  return screenHref(STEP_SCREEN[task.step], { caseId: task.caseId, sessionId: task.sessionId });
}

interface MainScreenInput {
  session: AuthSession;
  home: HomeDashboardState;
  /** 오늘 ~ HOME_SCHEDULE_DAYS 일 뒤 일정(useSchedule, 사례 목록 없이). */
  schedule: ScheduleState;
  /** 확인 안 한 콩콩 알림. 꺼져 있거나 못 받았으면 null. */
  childAlerts?: ChildOpenAlert[] | null;
  state: MainUiState;
  setState: (patch: Partial<MainUiState>) => void;
}

/** 홈이 부르는 일정 기간(오늘부터). '다음 상담까지' 를 이 안에서 찾는다. */
export const HOME_SCHEDULE_DAYS = 14;

/** 홈 일정 기간(YYYY-MM-DD). */
export function homeScheduleRange(now: Date): { from: string; to: string } {
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + HOME_SCHEDULE_DAYS);
  const ymd = (d: Date) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  return { from: ymd(now), to: ymd(end) };
}

/** 일정 한 줄 → 누르면 갈 곳. 사례가 있는 상담 일정은 그 사례의 상담 전 브리핑, 그 밖은 일정 달력. */
function itemHref(e: CalendarItem): string {
  return e.t === "c" && e.event.case_id ? screenHref("/PreBriefing", { caseId: e.event.case_id }) : "/Schedule";
}

/** 홈 '긴급 업무' 카드. 알림을 못 받았으면 '—' 와 준비 중. */
/** 긴급 업무 줄 칩(11/11 디자인 '긴급 체크인' 줄). 긴급이 아닌 알림은 '확인 필요'. */
const ALERT_CHIP: Partial<Record<ChildOpenAlert["reason"], string>> = {
  ALERT: "긴급 알림",
  RED_ANSWER: "바로 확인",
  CONTACT_REQUEST: "연락 요청",
};

/** 긴급 업무 카드에 줄로 보이는 알림 수(긴급 먼저 · 최근 먼저). */
const HOME_ALERT_COUNT = 3;

function alertWhen(value: string, now: Date): string {
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return "";
  const time = `${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
  const sameDay = at.getFullYear() === now.getFullYear() && at.getMonth() === now.getMonth() && at.getDate() === now.getDate();
  return sameDay ? `오늘 ${time}` : `${at.getMonth() + 1}/${at.getDate()} ${time}`;
}

function urgentValues(alerts: ChildOpenAlert[] | null, now: Date) {
  if (!alerts) return { urgentCount: NOT_PROVIDED, urgentText: `아이 앱 연계 ${NOT_READY}`, urgentRows: [] };
  const urgent = alerts.filter((alert) => alert.urgent).length;
  const check = alerts.length - urgent;
  const at = (alert: ChildOpenAlert) => alert.last_at ?? alert.created_at;
  const urgentRows = [...alerts]
    .sort((a, b) => Number(b.urgent) - Number(a.urgent) || at(b).localeCompare(at(a)))
    .slice(0, HOME_ALERT_COUNT)
    .map((alert) => ({
      key: alert.id,
      href: screenHref("/CaseApp", { caseId: alert.case_id }),
      urgent: alert.urgent,
      chip: alert.urgent ? "chip c-urgent" : "chip c-check",
      label: alert.urgent ? ALERT_CHIP[alert.reason] ?? "긴급" : "확인 필요",
      text: [alert.child_alias, alertWhen(at(alert), now)].filter(Boolean).join(" · "),
    }));
  return {
    urgentCount: String(urgent),
    urgentText: alerts.length === 0 ? "확인 안 한 아이 앱 알림이 없어요" : check && !urgent ? `확인 필요 ${check}건` : "",
    urgentRows,
  };
}

/** '진행 중 내담자' 줄의 오른쪽 글(11/11 디자인 '서윤 · 오늘 16:00 상담'): 다가오는 그 사례 상담 일정, 없으면 마지막 회차 상태. */
function nextConsultText(items: CalendarItem[], caseId: string, now: Date): string | null {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const nowHm = `${pad2(now.getHours())}:${pad2(now.getMinutes())}`;
  const next = items
    .filter((e) => e.t === "c" && e.event.case_id === caseId)
    .filter((e) => {
      const day = new Date(e.y, e.m, e.d).getTime();
      return day > today || (day === today && (!/^\d\d:\d\d$/.test(e.time) || e.time >= nowHm));
    })
    .sort((a, b) => new Date(a.y, a.m, a.d).getTime() - new Date(b.y, b.m, b.d).getTime() || byTime(a, b))[0];
  if (!next) return null;
  const timed = /^\d\d:\d\d$/.test(next.time);
  const isToday = new Date(next.y, next.m, next.d).getTime() === today;
  if (isToday) return timed ? `오늘 ${next.time} 상담` : "오늘 상담";
  const body = next.title.split(" · ").slice(1).join(" · ") || "상담";
  return `${next.m + 1}/${next.d} ${body}`;
}

export function mainValues({ session, home, schedule, childAlerts, state, setState }: MainScreenInput) {
  const now = state.now;
  const me = session.me;
  const data = home.data;
  const wholeOrg = home.wholeOrg;

  const dateLabel = `${now.getFullYear()}년 ${now.getMonth() + 1}월 ${now.getDate()}일 ${WEEKDAYS[now.getDay()]}요일`;
  const clock = `${pad2(now.getHours())}:${pad2(now.getMinutes())}`;

  // 오늘 일정(11/02 연결): 9~18시 칸에 오늘 일정을 시각대로 놓는다. 종일 · 처리 기한 · 9시 전은 9시 칸, 18시 뒤는 18시 칸.
  const nowH = now.getHours();
  const items = calendarItems(schedule.data?.events ?? [], me?.id ?? null);
  const isToday = (e: CalendarItem) => e.y === now.getFullYear() && e.m === now.getMonth() && e.d === now.getDate();
  const today = items.filter(isToday).sort(byTime);
  const hourOf = (e: CalendarItem) => (/^\d\d:\d\d$/.test(e.time) ? Math.min(18, Math.max(9, parseInt(e.time, 10))) : 9);
  const hours = [];
  for (let h = 9; h <= 18; h++) {
    const isNowHour = h === nowH;
    hours.push({
      label: `${pad2(h)}:00`,
      events: today
        .filter((e) => hourOf(e) === h)
        .map((e) => ({
          time: e.time,
          // 중요 일정은 색만이 아니라 글자로도 알린다(달력의 '! 중요' 와 같게, 민규 #131 교차검증 R11).
          title: e.imp && !e.dl ? `! 중요 · ${e.title}` : e.title,
          sub: e.sub,
          href: itemHref(e),
          dot: e.imp ? "#A33B2E" : e.t === "c" ? "#7A776F" : "#DAD5C9",
          radius: e.t === "c" ? "50%" : "2px",
          bg: "#F7F6F2",
        })),
      isNowHour,
      bg: isNowHour ? "#F7F6F2" : "#FFFFFF",
      op: h < nowH ? 0.5 : 1,
      labelFg: isNowHour ? "#2B2A26" : "#7A776F",
      labelFw: isNowHour ? 700 : 400,
    });
  }

  // 다음 상담까지: 지금 뒤의 첫 상담 일정(오늘 ~ HOME_SCHEDULE_DAYS 일). 종일 상담은 시각이 없어 그날 0시로 센다.
  const startOf = (e: CalendarItem) => {
    const [hh, mm] = /^\d\d:\d\d$/.test(e.time) ? e.time.split(":").map(Number) : [0, 0];
    return new Date(e.y, e.m, e.d, hh, mm).getTime();
  };
  const next = items
    .filter((e) => e.t === "c" && startOf(e) > now.getTime())
    .sort((a, b) => startOf(a) - startOf(b))[0];
  let remain = schedule.data ? "남은 상담 없음" : NOT_PROVIDED;
  let nextTitle = schedule.data ? `앞으로 ${HOME_SCHEDULE_DAYS}일 안에 잡힌 상담 일정이 없습니다` : "";
  let briefHref = "/PreBriefing";
  if (next) {
    const diff = Math.floor((startOf(next) - now.getTime()) / 60000);
    const days = Math.floor(diff / 1440);
    const hh = Math.floor((diff % 1440) / 60);
    const mm = diff % 60;
    remain = days > 0 ? `${days}일 ${hh}시간 남음` : hh > 0 ? `${hh}시간 ${mm}분 남음` : `${mm}분 남음`;
    const when = isToday(next) ? "" : `${next.m + 1}/${next.d}(${WEEKDAYS[new Date(next.y, next.m, next.d).getDay()]}) `;
    nextTitle = `${when}${next.time === "종일" ? "" : `${next.time} `}${next.title}`;
    briefHref = itemHref(next);
  }

  // 10/30 디자인: 업무 종류별 한 줄 — 칩(업무 이름) · 가장 오래 기다린 회차('외' 는 더 있을 때) · 오른쪽 건수.
  const groups = data?.tasks ?? [];
  // 홈에서는 원문 검수를 단계 이름 '기록 확인' 으로 쓴다(관리자 화면은 디자인이 안 바뀌어 그대로).
  // 문서 회차의 검수 업무는 AI 결과가 아니라 문서에서 옮긴 상담일지 확인이다(2026-11-02).
  const homeLabel = (task: HomeTask) =>
    task.taskType === "REVIEW_TRANSCRIPT" ? "기록 확인" : task.fromDocument ? "상담일지 확인" : task.stageLabel;
  const todos = groups.slice(0, HOME_TASK_COUNT).map((task) => {
    const label = homeLabel(task);
    return {
      label,
      // 누르면 옆 작은 창에서 이 업무에 걸린 아동을 고른다(2026-11-11, TaskPickPopover). href 는 가장 오래 기다린 회차.
      taskType: task.taskType,
      chip: TASK_CHIP[task.taskType] ?? "chip c-normal",
      text: [`${task.childAlias} ${task.sessionNumber}회차${task.count > 1 ? " 외" : ""}`, wholeOrg ? task.counselorName : "", task.overdue ? "지연" : ""]
        .filter(Boolean)
        .join(" · "),
      waited: String(task.count),
      waitedTitle: `${label} ${task.count}건 — 가장 오래 기다린 회차는 ${task.waitingSinceFull}부터`,
      href: homeTaskHref(task),
    };
  });

  let todoNote = "";
  if (data) {
    if (data.summary.total === 0) todoNote = "처리할 업무가 없습니다.";
    else {
      const rest = groups.slice(HOME_TASK_COUNT).map((task) => `${homeLabel(task)} ${task.count}`);
      const parts = rest.length ? [`그 밖 ${rest.join(" · ")}`] : [];
      if (data.summary.overdue > 0) parts.push(`지연 ${data.summary.overdue}건`);
      todoNote = parts.join(" — ");
    }
  }

  const quick = state.quick.map((key) => ({
    ...QUICK_POOL[key],
    rmLabel: `${QUICK_POOL[key].label} 빼기`,
    remove: (event?: { preventDefault?: () => void }) => {
      if (event && event.preventDefault) event.preventDefault();
      setState({ quick: state.quick.filter((other) => other !== key) });
    },
  }));
  const addable = (Object.keys(QUICK_POOL) as QuickKey[])
    .filter((key) => !state.quick.includes(key))
    .map((key) => ({ label: QUICK_POOL[key].label, add: () => setState({ quick: [...state.quick, key] }) }));

  return {
    notice: screenNotice({ session, loading: home.loading, error: home.error, retry: home.reload }),
    greeting: me ? `안녕하세요, ${me.name} ${me.role === "ADMIN" ? "관리자" : "상담원"}님` : "안녕하세요",
    dateLabel,
    clock,
    hours,
    scheduleNote: schedule.error ?? (schedule.data && today.length === 0 ? "오늘 일정이 없습니다." : ""),
    casesLabel: wholeOrg ? "진행 중 사례 (전체)" : "진행 중 내담자",
    casesCount: data ? String(data.activeCases) : NOT_PROVIDED,
    tasksLabel: wholeOrg ? "미처리 업무 (전체 상담사)" : "미처리 업무",
    tasksCount: data ? String(data.summary.total) : NOT_PROVIDED,
    todos,
    todoNote,
    // '진행 중 내담자' 카드 아래 줄(11/11 디자인): '위험도 상 · 중 · 하' 칩(사례 목록과 같은 값, 없으면 '—') · 이름 ·
    // 다가오는 상담 일정(없으면 마지막 회차 상태).
    caseTodos: (data?.cases ?? []).map((item) => ({
      href: screenHref("/CaseDetail", { caseId: item.id }),
      chip: `chip ${item.level ? HOME_RISK_CHIP[item.level] : "c-normal"}`,
      label: `위험도 ${item.level ? RISK_LEVEL_LABELS[item.level] : "—"}`,
      text: `${item.name} · ${
        nextConsultText(items, item.id, now) ??
        (item.latest ? `${item.latest.number}회차 ${SESSION_STATUS_LABELS[item.latest.status]}` : "녹취를 올리면 회차가 생깁니다")
      }`,
    })),
    ...urgentValues(childAlerts ?? null, now),
    remain,
    nextTitle,
    briefHref,
    quick,
    addable,
    editing: state.editing,
    editLabel: state.editing ? "완료" : "편집",
    toggleEdit: () => setState({ editing: !state.editing }),
  };
}
