import { Outlet, NavLink, useNavigate, Navigate, useLocation } from "react-router";
import { useEffect, useState } from "react";
import NotificationPopover from "../components/ui/NotificationPopover";
import {
  PASSWORD_CHANGE_REQUIRED_EVENT,
  SESSION_INFO_KEY,
  TOKEN_KEY,
  UNAUTHORIZED_EVENT,
  clearSession,
  getToken,
} from "../api/client";
import { tasks as tasksApi } from "../api/endpoints";
import { toMenuBadges } from "../api/dashboardAdapters";

// 메뉴 배지 숫자는 처리 대기 업무 요약(GET /tasks/summary)에서 온다. 어느 메뉴가 어떤 업무를 세는지는
// dashboardAdapters.MENU_BADGE_TASKS 에 있다(보고서 생성은 대응하는 업무가 Backend 에 없어 배지가 없다).
const NAV_ITEMS = [
  { to: "/dashboard",       label: "대시보드",       icon: "grid",       group: null },
  { to: "/cases",           label: "통합 사례 목록", icon: "folder",     group: "사례 관리" },
  { to: "/follow-up",       label: "후속 관리",      icon: "home",       group: "사례 관리" },
  { to: "/stt-cases",       label: "상담 자료 검수", icon: "transcript", group: "상담 업무" },
  { to: "/case-management", label: "사례 관리",      icon: "clipboard",  group: "상담 업무" },
  { to: "/report-cases",    label: "보고서 생성",    icon: "document",   group: "문서" },
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

/** 메뉴 옆 숫자. 0 이거나 아직 모르면(불러오는 중 · 실패) 그리지 않는다. */
function MenuBadge({ count }: { count: number | undefined }) {
  if (count == null || count <= 0) return null;

  return (
    <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-sm min-w-[18px] text-center"
      style={{ background: count > 1 ? "#DC2626" : "#D97706", color: "white" }}>
      {count}
    </span>
  );
}

export default function AppLayout() {
  const navigate = useNavigate();
  const [auth, setAuth] = useState<{ role: string; name: string } | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // 이름 · 역할만 남고 토큰이 없으면 서버를 부를 수 없으므로 로그인하지 않은 것으로 본다.
    function readStoredAuth(): { role: string; name: string } | null {
      const raw = localStorage.getItem(SESSION_INFO_KEY);
      if (!raw || !getToken()) return null;
      try { return JSON.parse(raw); } catch { return null; }
    }

    setAuth(readStoredAuth());
    setChecked(true);

    // 어느 화면에서든 토큰이 만료 · 폐기되면(401) 로그인 화면으로 보낸다.
    function onUnauthorized() {
      setAuth(null);
    }

    // 임시 비밀번호 상태(403 PASSWORD_CHANGE_REQUIRED)면 비밀번호를 바꾸는 내 정보 화면으로 보낸다.
    // 새로고침 · 주소 직접 입력으로 다른 화면에 들어와도 그 화면이나 메뉴 배지의 첫 요청에서 여기로 온다.
    function onPasswordChangeRequired() {
      if (window.location.pathname !== "/profile") {
        navigate("/profile", { replace: true, state: { mustChangePassword: true } });
      }
    }

    // 다른 탭에서 로그아웃 · 다른 계정 로그인 · 토큰 폐기가 일어나면 localStorage 가 바뀐다(이 탭에는 storage 이벤트로 온다).
    // 토큰이 없어졌으면 로그인 화면으로, 다른 계정이 들어왔으면 그 이름 · 역할로 바꾼다.
    function onStorage(event: StorageEvent) {
      if (event.key !== null && event.key !== TOKEN_KEY && event.key !== SESSION_INFO_KEY) return;
      setAuth(readStoredAuth());
    }

    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    window.addEventListener(PASSWORD_CHANGE_REQUIRED_EVENT, onPasswordChangeRequired);
    window.addEventListener("storage", onStorage);

    return () => {
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
      window.removeEventListener(PASSWORD_CHANGE_REQUIRED_EVENT, onPasswordChangeRequired);
      window.removeEventListener("storage", onStorage);
    };
  }, [navigate]);

  // 메뉴 배지. 화면을 옮길 때마다 다시 세어 검수 · 승인 뒤 숫자가 따라오게 한다.
  // 처음 불러오는 중이거나 실패하면 배지를 숨긴다(null). 다시 세는 동안에는 직전 숫자를 둔다.
  const location = useLocation();
  const [badges, setBadges] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    if (!auth) return;

    let cancelled = false;

    tasksApi
      .summary()
      .then((summary) => {
        if (!cancelled) setBadges(toMenuBadges(summary));
      })
      .catch(() => {
        if (!cancelled) setBadges(null);
      });

    return () => {
      cancelled = true;
    };
  }, [auth, location.pathname]);

  if (!checked) return null;
  if (!auth) return <Navigate to="/login" replace />;

  function handleLogout() {
    clearSession();
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
          <button onClick={() => navigate("/profile")} className="flex items-center gap-2.5 w-full text-left hover:opacity-80 transition-opacity">
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0" style={{ background: "#15314A" }}>{initial}</div>
            <div className="min-w-0">
              <div className="text-[13px] font-medium text-white truncate">{auth.name}</div>
              <div className="text-[11px] truncate" style={{ color: "rgba(255,255,255,0.4)" }}>아동·청소년 상담사</div>
            </div>
          </button>
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
                  <MenuBadge count={badges?.[item.to]} />
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
        <header className="bg-white border-b border-[#E2E8F0] px-5 flex items-center justify-end shrink-0" style={{ height: "52px" }}>
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
