import { useState, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router";
import { tasks as tasksApi } from "../../api/endpoints";
import { TASK_LABELS, type TaskItem } from "../../api/types";
import { toLocalDate, toLocalTime, toTaskLink } from "../../api/dashboardAdapters";

// 알림은 처리 대기 업무(GET /tasks)에서 만든다. Backend 에 알림 기능이 따로 없어서,
// "지금 내가 처리할 차례인 일" 가운데 오래 기다린 것부터 보여 준다.
// 읽음 표시는 이 화면에서만 들고 있다(새로고침하면 다시 새 알림으로 보인다).

const SHOW_COUNT = 8;

type Kind = "검토필요" | "지연" | "업무";

const TYPE_DOT: Record<Kind, string> = {
  "검토필요": "bg-amber-400",
  "지연":     "bg-red-500",
  "업무":     "bg-blue-400",
};

function kindOf(item: TaskItem): Kind {
  if (item.is_overdue) return "지연";
  if (item.task_type === "REVIEW_TRANSCRIPT" || item.task_type === "REVIEW_ANALYSIS") return "검토필요";
  return "업무";
}

export default function NotificationPopover() {
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<TaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const [loadError, setLoadError] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 화면을 옮길 때마다 다시 센다(업무를 처리하고 돌아오면 목록이 줄어든다).
  useEffect(() => {
    let cancelled = false;

    tasksApi
      .list({ page: 1, page_size: SHOW_COUNT })
      .then((page) => {
        if (cancelled) return;
        setItems(page.items);
        setTotal(page.meta.total);
        setLoadError(false);
      })
      .catch(() => {
        // 401 이면 client 가 로그인 화면으로 보낸다. 그 밖의 실패는 알림을 비워 둔다.
        if (!cancelled) setLoadError(true);
      });

    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  const unreadCount = items.filter((n) => !readIds.has(n.session_id)).length;

  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function markAllRead() {
    setReadIds(new Set(items.map((n) => n.session_id)));
  }

  function handleClick(n: TaskItem) {
    setReadIds((prev) => new Set(prev).add(n.session_id));
    setOpen(false);
    navigate(toTaskLink(n));
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-1.5 text-[#94A3B8] hover:text-[#64748B] transition-colors"
        aria-label={unreadCount > 0 ? `알림 ${unreadCount}건` : "알림"}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 01-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-0.5 right-0.5 w-4 h-4 bg-[#DC2626] rounded-full text-white text-[9px] font-bold flex items-center justify-center leading-none">
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 bg-white border border-[#E2E8F0] rounded-[8px] shadow-sm z-50 overflow-hidden"
          style={{ width: "360px" }}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#E2E8F0]">
            <span className="text-[13px] font-semibold text-[#172033]">
              알림{total > items.length ? ` · 오래된 ${items.length}건 / 전체 ${total}건` : ""}
            </span>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-[11px] text-[#2563EB] hover:text-[#1D4ED8] font-medium transition-colors"
              >
                모두 읽음 처리
              </button>
            )}
          </div>
          <div className="divide-y divide-[#F1F5F9]">
            {loadError && (
              <p className="px-4 py-6 text-center text-[12px] text-[#94A3B8]">알림을 불러오지 못했습니다.</p>
            )}
            {!loadError && items.length === 0 && (
              <p className="px-4 py-6 text-center text-[12px] text-[#94A3B8]">처리할 업무가 없습니다.</p>
            )}
            {items.map((n) => {
              const read = readIds.has(n.session_id);
              const kind = kindOf(n);
              return (
                <button
                  key={n.session_id}
                  onClick={() => handleClick(n)}
                  className={`w-full text-left flex items-start gap-3 px-4 py-3 hover:bg-[#F8FAFC] transition-colors ${
                    !read ? "bg-blue-50 border-l-2 border-l-blue-300" : "bg-white"
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${TYPE_DOT[kind]}`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-[13px] font-medium truncate ${!read ? "text-[#172033]" : "text-[#64748B]"}`}>
                      {TASK_LABELS[n.task_type]}{n.is_overdue ? " · 지연" : ""}
                    </p>
                    <p className="text-[11px] text-[#94A3B8] mt-0.5 leading-relaxed line-clamp-2">
                      {n.child_alias} · {n.case_number} · {n.session_number}회차
                    </p>
                    <p className="text-[10px] text-[#94A3B8] mt-1 font-mono">
                      {toLocalDate(n.waiting_since)} {toLocalTime(n.waiting_since)}부터 대기
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
