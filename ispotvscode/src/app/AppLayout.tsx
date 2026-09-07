import { Outlet, NavLink, useNavigate, Navigate } from "react-router";
import { useEffect, useState } from "react";
import NotificationPopover from "../components/ui/NotificationPopover";

const NAV_ITEMS = [
  { to: "/dashboard",  label: "대시보드",          icon: "grid",       group: null },
  { to: "/cases",      label: "통합 사례 목록",     icon: "folder",     group: "사례 관리" },
  { to: "/recording",  label: "상담 녹음",          icon: "mic",        group: "상담 업무" },
  { to: "/stt-cases",  label: "STT 검수",           icon: "transcript", group: "상담 업무", badge: 1 },
  { to: "/ai-cases",   label: "분석 결과 검토",     icon: "robot",      group: "상담 업무", badge: 2 },
  { to: "/plan-cases",    label: "사례관리 계획",      icon: "clipboard",  group: "상담 업무", badge: 0 },
  { to: "/closure-cases", label: "종결·가정복귀 검토", icon: "home",       group: "상담 업무", badge: 0 },
  { to: "/report-cases",  label: "보고서 생성",        icon: "document",   group: "문서",      badge: 0 },
];

function NavIcon({ id }: { id: string }) {
  const s = { width: 15, height: 15, viewBox: "0 0 24 24", fill: "none" as const, stroke: "currentColor", strokeWidth: "1.7" };
  const icons: Record<string, React.ReactNode> = {
    grid:       <svg {...s}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>,
    folder:     <svg {...s}><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>,
    mic:        <svg {...s}><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>,
    transcript: <svg {...s}><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="12" y2="17"/></svg>,
    robot:      <svg {...s}><rect x="3" y="11" width="18" height="10" rx="2"/><path d="M12 11V7"/><circle cx="12" cy="5" r="2"/><path d="M7 15h.01M17 15h.01M9 19h6"/></svg>,
    clipboard:  <svg {...s}><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>,
    home:       <svg {...s}><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>,
    document:   <svg {...s}><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>,
  };
  return <>{icons[id] ?? null}</>;
}

export default function AppLayout() {
  const navigate = useNavigate();
  const [auth, setAuth] = useState<{ role: string; name: string } | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const raw = localStorage.getItem("ispot_auth");
    if (raw) {
      try { setAuth(JSON.parse(raw)); } catch { /* ignore */ }
    }
    setChecked(true);
  }, []);

  if (!checked) return null;
  if (!auth) return <Navigate to="/login" replace />;

  function handleLogout() {
    localStorage.removeItem("ispot_auth");
    navigate("/login");
  }

  const initial = auth.name ? auth.name[0] : "?";

  const groups: { label: string | null; items: typeof NAV_ITEMS }[] = [];
  for (const item of NAV_ITEMS) {
    const last = groups[groups.length - 1];
    if (!last || last.label !== item.group) groups.push({ label: item.group, items: [item] });
    else last.items.push(item);
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#F6F8FB" }}>
      {/* Sidebar */}
      <aside className="flex flex-col shrink-0" style={{ width: "232px", background: "#0F263B", borderRight: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="px-5 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded flex items-center justify-center shrink-0" style={{ background: "rgba(255,255,255,0.1)" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            </div>
            <div>
              <div className="text-white font-bold tracking-widest text-[13px]">I-SPOT</div>
              <div className="text-[10px] tracking-widest" style={{ color: "rgba(255,255,255,0.35)" }}>AI 아동상담 지원</div>
            </div>
          </div>
        </div>

        <div className="px-4 py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0" style={{ background: "#15314A" }}>{initial}</div>
            <div className="min-w-0">
              <div className="text-[13px] font-medium text-white truncate">{auth.name}</div>
              <div className="text-[11px] truncate" style={{ color: "rgba(255,255,255,0.4)" }}>아동·청소년 상담사</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-2 overflow-y-auto">
          {groups.map((group, gi) => (
            <div key={gi} className="mb-1">
              {group.label && (
                <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.25)" }}>
                  {group.label}
                </p>
              )}
              {group.items.map((item, ii) => (
                <NavLink
                  key={`${item.to}-${ii}`}
                  to={item.to}
                  end={item.to === "/cases" && item.label === "통합 사례 목록"}
                  className={({ isActive }) =>
                    `w-full flex items-center gap-2.5 text-left transition-colors`
                  }
                  style={({ isActive }) => ({
                    padding: "7px 16px 7px 14px",
                    borderLeft: isActive ? "2px solid #2563EB" : "2px solid transparent",
                    background: isActive ? "rgba(255,255,255,0.07)" : "transparent",
                    color: isActive ? "#FFFFFF" : "rgba(255,255,255,0.55)",
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                  })}
                >
                  <span className="shrink-0"><NavIcon id={item.icon} /></span>
                  <span className="text-[13px] font-medium flex-1 leading-tight">{item.label}</span>
                  {item.badge != null && item.badge > 0 && (
                    <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-sm min-w-[18px] text-center"
                      style={{ background: item.badge > 1 ? "#DC2626" : "#D97706", color: "white" }}>
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="p-3" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded text-[13px] transition-colors"
            style={{ color: "rgba(255,255,255,0.4)" }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.7)"; (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)"; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.4)"; (e.currentTarget as HTMLElement).style.background = "transparent"; }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            로그아웃
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-[#E2E8F0] px-5 flex items-center justify-between shrink-0" style={{ height: "56px" }}>
          <div className="relative" style={{ width: "300px" }}>
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="빠른 사례 검색..." className="w-full pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-[#F8FAFC] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] transition-all" />
          </div>
          <div className="flex items-center gap-3">
            <NotificationPopover />
            <div className="w-px h-4 bg-[#E2E8F0]" />
            <button
              onClick={() => navigate("/profile")}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              <div className="w-6 h-6 rounded-full bg-[#15314A] flex items-center justify-center text-white text-[10px] font-bold">{initial}</div>
              <span className="text-[13px] font-medium text-[#172033]">{auth.name}</span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-hidden flex flex-col">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
