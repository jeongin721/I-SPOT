import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router";
import { NOTIFICATIONS, type Notification } from "../../data/mockData";

const TYPE_DOT: Record<Notification["type"], string> = {
  "검토필요": "bg-amber-400",
  "고위험":   "bg-red-500",
  "업무":     "bg-blue-400",
  "분석완료": "bg-green-400",
};

export default function NotificationPopover() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>(NOTIFICATIONS);
  const ref = useRef<HTMLDivElement>(null);

  const unreadCount = items.filter((n) => !n.read).length;

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

  function markRead(id: string) {
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
  }

  function markAllRead() {
    setItems((prev) => prev.map((n) => ({ ...n, read: true })));
  }

  function handleClick(n: Notification) {
    markRead(n.id);
    setOpen(false);
    navigate(n.link);
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-1.5 text-[#94A3B8] hover:text-[#64748B] transition-colors"
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
            <span className="text-[13px] font-semibold text-[#172033]">알림</span>
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
            {items.map((n) => (
              <button
                key={n.id}
                onClick={() => handleClick(n)}
                className={`w-full text-left flex items-start gap-3 px-4 py-3 hover:bg-[#F8FAFC] transition-colors ${
                  !n.read ? "bg-blue-50 border-l-2 border-l-blue-300" : "bg-white"
                }`}
              >
                <span className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${TYPE_DOT[n.type]}`} />
                <div className="flex-1 min-w-0">
                  <p className={`text-[13px] font-medium truncate ${!n.read ? "text-[#172033]" : "text-[#64748B]"}`}>
                    {n.title}
                  </p>
                  <p className="text-[11px] text-[#94A3B8] mt-0.5 leading-relaxed line-clamp-2">{n.body}</p>
                  <p className="text-[10px] text-[#94A3B8] mt-1 font-mono">{n.time}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
