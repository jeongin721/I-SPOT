// 홈(Main) 화면 값. useHomeDashboard 하나로 진행 중 사례 수 · 미처리 업무를 그린다.
//
// Backend 에 없는 값은 지어내지 않는다(specs 대응표 Main 줄 — 팀 결정: 일정 · 아이 앱 긴급 상태 · 일지 대기 기준).
//  - 오늘 일정 · 다음 상담까지 남은 시간(11/02 연결): 일정(API_CONTRACT 20절)에서 오늘 일정 · 지금 뒤 첫 상담 일정을 찾는다.
//  - 긴급 업무(아이 앱 체크인): 아이 앱 연계가 없다. '—'(10/30 디자인의 머리 링크 '아이 연계 ›' 만 둔다).
//  - 진행 중 내담자 카드 아래 줄(10/30): 최근 등록 사례 3건의 마지막 회차 판단('n회차 판단 · 상') · 그 회차 상태. 디자인의
//    '오늘 16:00 상담' 같은 일정 문구는 쓰지 않는다(카드 줄은 회차 판단이 기준).
//  - 미처리 업무는 회차 처리 대기(/tasks)만 센다. 디자인의 '상담 일지 작성' · '앱 확인' 은 업무 종류에 없다.
//    오래 기다린 업무는 '지연' 이라고 쓴다(위험 신호와 헷갈리지 않게 '긴급' 이라고 쓰지 않는다 — API types TaskItem).
// 시계 · 빠른 실행은 서버와 상관없는 화면 상태다(빠른 실행 편집은 저장하지 않는다).

import { RISK_LEVEL_LABELS, type RiskLevel, type TaskType } from "../../api/types";
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

export function mainValues({ session, home, schedule, state, setState }: MainScreenInput) {
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
    // '진행 중 내담자' 카드 아래 줄(10/30 디자인): 마지막 회차의 상담원 판단 · 별칭 · 그 회차 상태.
    // 사례 단위 위험도로 읽히지 않게 칩에 'n회차 판단' 을 밝힌다(민규 #122 리뷰 — 사례 위험도는 팀 결정 전).
    caseTodos: (data?.cases ?? []).map((item) => ({
      href: screenHref("/CaseDetail", { caseId: item.id }),
      chip: `chip ${item.level ? HOME_RISK_CHIP[item.level] : "c-normal"}`,
      label: item.latest
        ? item.level
          ? `${item.latest.number}회차 판단 · ${RISK_LEVEL_LABELS[item.level]}`
          : `${item.latest.number}회차 판단 전`
        : "회차 없음",
      text: `${item.alias} · ${item.latest ? SESSION_STATUS_LABELS[item.latest.status] : "녹취를 올리면 회차가 생깁니다"}`,
    })),
    urgentCount: NOT_PROVIDED,
    urgentText: `아이 앱 연계 ${NOT_READY}`,
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
