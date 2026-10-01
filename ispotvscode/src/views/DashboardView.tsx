import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { SESSION_INFO_KEY } from "../api/client";
import { cases as casesApi, tasks as tasksApi } from "../api/endpoints";
import { NOT_PROVIDED, describeApiError } from "../api/adapters";
import {
  readSignedInUser,
  sortByRecentSession,
  toDashboardStats,
  toDashboardTaskRow,
  toKoreanDateHeading,
  toManagedCase,
  type DashboardTaskRow,
  type ManagedCase,
} from "../api/dashboardAdapters";
import type { TaskSummary } from "../api/types";

// 숫자와 업무 목록은 처리 대기 업무 API(GET /tasks, GET /tasks/summary)에서, 사례 수와 최근 상담 사례는
// 사례 목록(GET /cases)에서 온다. 상담사는 담당 사례만, 관리자는 전체가 보인다.
// 오늘 예정 상담 · 작성 대기 문서는 여러 사례에 걸친 조회가 Backend 에 없어 "—" 로 둔다.
// 위험도는 사례 단위로 없어서 "확인 필요 우선 검토"(위험도순) 대신 최근 상담순 사례를 보여 준다.

/** 나의 업무 목록에 보여 줄 개수. Backend 가 오래 기다린 순으로 준다. */
const TASK_PREVIEW_SIZE = 5;
/** 최근 상담순으로 다시 정렬하려고 한 번에 받는 사례 수(Backend 최대 100). */
const CASE_PAGE_SIZE = 100;
const RECENT_CASE_COUNT = 5;

export default function DashboardView() {
  const navigate = useNavigate();
  const user = readSignedInUser(localStorage.getItem(SESSION_INFO_KEY));

  const [summary, setSummary]           = useState<TaskSummary | null>(null);
  const [taskRows, setTaskRows]         = useState<DashboardTaskRow[]>([]);
  const [taskTotal, setTaskTotal]       = useState<number | null>(null);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [tasksError, setTasksError]     = useState<string | null>(null);

  const [recentCases, setRecentCases]   = useState<ManagedCase[]>([]);
  const [caseTotal, setCaseTotal]       = useState<number | null>(null);
  const [activeTotal, setActiveTotal]   = useState<number | null>(null);
  const [casesLoading, setCasesLoading] = useState(true);
  const [casesError, setCasesError]     = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      tasksApi.summary(),
      tasksApi.list({ page: 1, page_size: TASK_PREVIEW_SIZE }),
    ])
      .then(([counts, page]) => {
        if (cancelled) return;
        setSummary(counts);
        setTaskRows(page.items.map(toDashboardTaskRow));
        setTaskTotal(page.meta.total);
      })
      .catch((caught) => {
        if (!cancelled) setTasksError(describeApiError(caught, "업무 목록을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setTasksLoading(false);
      });

    Promise.all([
      casesApi.list({ page: 1, page_size: CASE_PAGE_SIZE }),
      casesApi.list({ status: "ACTIVE", page: 1, page_size: 1 }),
    ])
      .then(([all, active]) => {
        if (cancelled) return;
        // Backend 는 등록순으로 주므로 최근 상담순은 화면에서 다시 정렬한다.
        setRecentCases(sortByRecentSession(all.items.map(toManagedCase)).slice(0, RECENT_CASE_COUNT));
        setCaseTotal(all.meta.total);
        setActiveTotal(active.meta.total);
      })
      .catch((caught) => {
        if (!cancelled) setCasesError(describeApiError(caught, "사례 목록을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setCasesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const stats = toDashboardStats({ isAdmin: user.isAdmin, summary, caseTotal, activeCaseTotal: activeTotal });
  const statsLoading = tasksLoading || casesLoading;
  const roleLabel = user.isAdmin ? "관리자" : "상담사";
  // 이름이 이미 역할로 끝나면(예: 데모 계정 "데모 상담사") 한 번만 붙인다.
  const userLabel = user.name.endsWith(roleLabel) ? user.name : `${user.name} ${roleLabel}`;

  return (
    <div className="p-6 space-y-5 overflow-y-auto flex-1" style={{ maxWidth: "1100px" }}>
      <div>
        <h1 className="text-[22px] font-semibold text-[#172033]">대시보드</h1>
        <p className="text-[14px] text-[#64748B] mt-0.5">
          {toKoreanDateHeading(new Date())}{user.name ? ` · ${userLabel}` : ""}
        </p>
      </div>

      {(tasksError || casesError) && (
        <div className="bg-[#FEF2F2] border border-[#FECACA] rounded-[8px] px-4 py-3 text-[13px] text-red-600 space-y-0.5">
          {tasksError && <p>{tasksError}</p>}
          {casesError && <p>{casesError}</p>}
        </div>
      )}

      {/* 5-item stat strip */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="grid divide-x divide-[#E2E8F0]" style={{ gridTemplateColumns: "repeat(5,1fr)" }}>
          {stats.map(stat => (
            <div key={stat.label} className="px-5 py-4">
              <p className="text-[12px] font-semibold text-[#64748B] mb-2">{stat.label}</p>
              <p className="text-[28px] font-semibold leading-none mb-1 text-[#172033]">
                {statsLoading && stat.fromServer && stat.value === NOT_PROVIDED ? "…" : stat.value}
              </p>
              <p className="text-[12px] text-[#94A3B8]">{stat.note || " "}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Today's sessions */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
          <span className="text-[14px] font-semibold text-[#172033]">오늘 예정 상담</span>
          <span className="text-[12px] text-[#94A3B8]">{NOT_PROVIDED}</span>
        </div>
        <div className="px-5 py-4 text-[13px] text-[#94A3B8]">
          여러 사례에 걸친 상담 일정 조회가 아직 서버에 없습니다. 사례별 회기는 사례 상세에서 확인해 주세요.
        </div>
      </div>

      {/* Main panels */}
      <div className="grid grid-cols-5 gap-5">
        <div className="col-span-3 bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
            <span className="text-[14px] font-semibold text-[#172033]">{user.isAdmin ? "전체 업무 목록" : "나의 업무 목록"}</span>
            <span className="text-[12px] text-[#94A3B8]">{taskTotal !== null ? `${taskTotal}건 미처리` : NOT_PROVIDED}</span>
          </div>
          <div className="divide-y divide-[#F1F5F9]">
            {taskRows.map(task => (
              <div key={task.sessionId} className="flex items-center gap-3 px-5 py-3.5 hover:bg-[#F8FAFC] transition-colors">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${task.isOverdue ? "bg-[#DC2626]" : "bg-[#CBD5E1]"}`} />
                <span className="text-[14px] text-[#172033] flex-1 min-w-0 truncate">
                  {task.taskLabel}
                  <span className="text-[12px] text-[#94A3B8] ml-2">{task.childName} · {task.sessionNumber}회기</span>
                </span>
                {task.isOverdue && (
                  <span className="shrink-0 text-[11px] font-semibold px-1.5 py-0.5 rounded border border-[#FECACA] text-[#B91C1C] bg-[#FEF2F2]">지연</span>
                )}
                {user.isAdmin && <span className="text-[12px] text-[#94A3B8] shrink-0">{task.counselor}</span>}
                <span className="text-[12px] text-[#94A3B8] font-mono shrink-0">{task.caseNumber}</span>
                <button
                  onClick={() => navigate(task.link)}
                  className="text-[13px] text-[#2563EB] font-medium hover:text-[#1D4ED8] transition-colors shrink-0"
                >
                  처리
                </button>
              </div>
            ))}
            {tasksLoading && (
              <div className="px-5 py-8 text-center text-[13px] text-[#94A3B8]">업무 목록을 불러오는 중...</div>
            )}
            {!tasksLoading && tasksError && (
              <div className="px-5 py-8 text-center text-[13px] text-red-600">{tasksError}</div>
            )}
            {!tasksLoading && !tasksError && taskRows.length === 0 && (
              <div className="px-5 py-8 text-center text-[13px] text-[#94A3B8]">지금 처리할 업무가 없습니다.</div>
            )}
          </div>
        </div>

        <div className="col-span-2 bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
            <span className="text-[14px] font-semibold text-[#172033]">최근 상담 사례</span>
            <button onClick={() => navigate("/cases")} className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium transition-colors">전체보기</button>
          </div>
          <div className="divide-y divide-[#F1F5F9]">
            {recentCases.map(c => (
              <button
                key={c.backendId}
                onClick={() => navigate(`/cases/${c.backendId}`)}
                className="w-full text-left px-5 py-3 hover:bg-[#F8FAFC] transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-[14px] font-semibold text-[#172033]">{c.childName}</span>
                    <span className="text-[12px] text-[#94A3B8] ml-2">{c.ageLabel}</span>
                  </div>
                  <span className="text-[12px] text-[#64748B] font-mono shrink-0">{c.lastSession || "상담 기록 없음"}</span>
                </div>
                <div className="flex items-center gap-1 mt-1.5">
                  <span className="text-[11px] text-[#64748B]">{c.statusLabel}</span>
                  <span className="text-[11px] text-[#94A3B8] font-mono ml-1">{c.caseNumber}</span>
                </div>
              </button>
            ))}
            {casesLoading && (
              <div className="px-5 py-8 text-center text-[13px] text-[#94A3B8]">사례 목록을 불러오는 중...</div>
            )}
            {!casesLoading && casesError && (
              <div className="px-5 py-8 text-center text-[13px] text-red-600">{casesError}</div>
            )}
            {!casesLoading && !casesError && recentCases.length === 0 && (
              <div className="px-5 py-8 text-center text-[13px] text-[#94A3B8]">담당 사례가 없습니다.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
