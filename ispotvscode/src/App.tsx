import { useState, useMemo } from "react";
import RecordingView from "./views/RecordingView";
import TranscriptReviewView from "./views/TranscriptReviewView";
import AIReviewView from "./views/AIReviewView";
import CasePlanView from "./views/CasePlanView";
import ClosureView from "./views/ClosureView";
import ReportView from "./views/ReportView";
import AdminApp from "./admin/AdminApp";
import { CASES, type RiskLevel, type AbuseType, type CaseRecord as Case } from "./data/cases";

// ── Types ──────────────────────────────────────────────────────────────────
type View = "login" | "dashboard" | "cases" | "recording" | "stt-review" | "ai-review" | "case-plan" | "closure" | "report";

const TASKS = [
  { id: 1, type: "음성 검수 대기",    case: "C-2026-0412", urgent: true },
  { id: 2, type: "분석 결과 검토 필요", case: "C-2026-0351", urgent: true },
  { id: 3, type: "상담일지 승인 대기", case: "C-2026-0389", urgent: false },
  { id: 4, type: "종결 검토 예정",    case: "C-2026-0312", urgent: false },
  { id: 5, type: "분석 결과 검토 필요", case: "C-2026-0277", urgent: true },
];

// ── Shared compact components ───────────────────────────────────────────────
function RiskBadge({ level, score }: { level: RiskLevel; score?: number }) {
  const cfg = {
    high: { label: "고위험", cls: "text-[#B91C1C] bg-[#FEF2F2] border-[#FECACA]" },
    mid:  { label: "중위험", cls: "text-[#B45309] bg-[#FFFBEB] border-[#FDE68A]" },
    low:  { label: "저위험", cls: "text-[#15803D] bg-[#F0FDF4] border-[#BBF7D0]" },
  }[level];
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[11px] font-semibold tracking-wide ${cfg.cls}`}>
      {cfg.label}{score !== undefined && <span className="opacity-70 font-mono ml-0.5">{score}</span>}
    </span>
  );
}

function AbuseBadge({ type }: { type: AbuseType }) {
  const cls: Record<AbuseType, string> = {
    "신체": "text-[#991B1B] bg-[#FEF2F2] border-[#FECACA]",
    "정서": "text-[#6B21A8] bg-[#FAF5FF] border-[#E9D5FF]",
    "성":   "text-[#9A3412] bg-[#FFF7ED] border-[#FED7AA]",
    "방임": "text-[#475569] bg-[#F8FAFC] border-[#E2E8F0]",
  };
  return <span className={`px-1.5 py-0.5 rounded border text-[11px] font-medium ${cls[type]}`}>{type}</span>;
}

function StatusLabel({ status }: { status: Case["status"] }) {
  const cfg = {
    active:  { label: "진행중",  cls: "text-[#1D4ED8] bg-[#EFF6FF] border-[#BFDBFE]" },
    pending: { label: "대기중",  cls: "text-[#64748B] bg-[#F8FAFC] border-[#E2E8F0]" },
    review:  { label: "검토필요", cls: "text-[#B45309] bg-[#FFFBEB] border-[#FDE68A]" },
  }[status];
  return <span className={`px-1.5 py-0.5 rounded border text-[11px] font-medium ${cfg.cls}`}>{cfg.label}</span>;
}

// ── Login ──────────────────────────────────────────────────────────────────
const CREDENTIALS = {
  counselor: { id: "이서연", pw: "1234",      hint: "이서연 / 1234" },
  admin:     { id: "김민준", pw: "admin1234", hint: "김민준 / admin1234" },
};

function LoginScreen({ onLogin }: { onLogin: (role: "counselor" | "admin") => void }) {
  const [id, setId]       = useState("");
  const [pw, setPw]       = useState("");
  const [role, setRole]   = useState<"counselor" | "admin">("counselor");
  const [otpStep, setOtpStep] = useState(false);
  const [otp, setOtp]     = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!otpStep) {
      const cred = CREDENTIALS[role];
      if (id === cred.id && pw === cred.pw) { setOtpStep(true); setError(""); }
      else setError("기관 ID 또는 비밀번호가 올바르지 않습니다.");
    } else {
      if (otp === "123456") { setLoading(true); setTimeout(() => onLogin(role), 600); }
      else setError("인증번호가 일치하지 않습니다.");
    }
  }

  const features = [
    { label: "상담 음성 STT 자동 변환 및 검수", icon: (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>) },
    { label: "AI 분석 참고정보 및 관련 신호 확인", icon: (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="11" width="18" height="10" rx="2"/><path d="M12 11V7"/><circle cx="12" cy="5" r="2"/></svg>) },
    { label: "상담일지·사정기록지 초안 자동 작성", icon: (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>) },
  ];

  return (
    <div className="min-h-screen flex" style={{ background: "#0F263B" }}>
      {/* Left brand panel */}
      <div className="hidden lg:flex flex-col justify-between w-[420px] p-12 shrink-0" style={{ borderRight: "1px solid rgba(255,255,255,0.08)" }}>
        <div>
          <div className="flex items-center gap-2.5 mb-14">
            <div className="w-8 h-8 rounded flex items-center justify-center" style={{ background: "rgba(255,255,255,0.1)" }}>
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
              </svg>
            </div>
            <div>
              <span className="text-white font-bold tracking-widest text-sm">I-SPOT</span>
              <span className="text-[11px] text-white/40 ml-2 tracking-widest uppercase">아동상담 지원</span>
            </div>
          </div>

          <h1 className="text-white font-semibold leading-snug mb-3" style={{ fontSize: "26px" }}>
            말과 그림 속 작은<br/>위험 신호를 찾아,<br/>상담사의 판단을 돕는
          </h1>
          <p className="text-sm font-medium" style={{ color: "rgba(255,255,255,0.5)" }}>AI 아동상담 지원 서비스</p>

          <div className="mt-10 space-y-3" style={{ borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "32px" }}>
            {features.map(f => (
              <div key={f.label} className="flex items-center gap-3" style={{ color: "rgba(255,255,255,0.6)" }}>
                <span className="shrink-0" style={{ color: "rgba(255,255,255,0.4)" }}>{f.icon}</span>
                <span className="text-[13px]">{f.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="text-[11px]" style={{ color: "rgba(255,255,255,0.3)" }}>
          i-child Safety Prediction &amp; Outreach Text-system<br/>
          개발기간 2026.08 – 2026.12
        </div>
      </div>

      {/* Right login panel */}
      <div className="flex-1 flex items-center justify-center p-8" style={{ background: "#F6F8FB" }}>
        <div className="w-full" style={{ maxWidth: "400px" }}>
          {/* Mobile logo */}
          <div className="flex lg:hidden items-center gap-2 mb-8">
            <div className="w-7 h-7 rounded flex items-center justify-center bg-[#15314A]">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            </div>
            <span className="font-bold text-[#172033] tracking-widest text-sm">I-SPOT</span>
          </div>

          <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
            {/* Panel header */}
            <div className="px-6 py-5 border-b border-[#E2E8F0]">
              <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-widest mb-1">아동보호전문기관</p>
              <h2 className="text-base font-semibold text-[#172033]">
                {otpStep ? "2차 인증" : "기관 시스템 로그인"}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="px-6 py-6 space-y-4">
              {!otpStep ? (
                <>
                  {/* Segmented control for role */}
                  <div>
                    <label className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">접속 권한</label>
                    <div className="flex border border-[#E2E8F0] rounded-[6px] overflow-hidden bg-[#F8FAFC]">
                      {(["counselor", "admin"] as const).map(r => (
                        <button
                          key={r}
                          type="button"
                          onClick={() => { setRole(r); setError(""); }}
                          className={`flex-1 py-2 text-sm font-medium transition-all ${
                            role === r
                              ? "bg-[#15314A] text-white"
                              : "text-[#64748B] hover:text-[#172033] hover:bg-[#F1F5F9]"
                          }`}
                        >
                          {r === "counselor" ? "상담사" : "관리자"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label htmlFor="uid" className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">기관 ID</label>
                    <input
                      id="uid" type="text" value={id} onChange={e => setId(e.target.value)} autoComplete="username"
                      placeholder={CREDENTIALS[role].id}
                      className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-sm text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] transition-all"
                    />
                  </div>

                  <div>
                    <label htmlFor="pw" className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">비밀번호</label>
                    <input
                      id="pw" type="password" value={pw} onChange={e => setPw(e.target.value)} autoComplete="current-password"
                      placeholder="••••••••"
                      className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-sm text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] transition-all"
                    />
                    <p className="mt-1 text-[11px] text-[#94A3B8]">테스트: {CREDENTIALS[role].hint} / OTP: 123456</p>
                  </div>
                </>
              ) : (
                <div>
                  <label htmlFor="otp" className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">OTP 인증번호 (6자리)</label>
                  <input
                    id="otp" type="text" value={otp} onChange={e => setOtp(e.target.value)} maxLength={6} autoFocus
                    placeholder="123456"
                    className="w-full px-3 py-2.5 rounded-[6px] border border-[#E2E8F0] text-sm text-[#172033] bg-white font-mono text-center tracking-[0.5em] text-base focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] transition-all"
                  />
                </div>
              )}

              {error && (
                <div className="flex items-center gap-2 text-[#B91C1C] text-[13px] bg-[#FEF2F2] border border-[#FECACA] px-3 py-2 rounded-[6px]">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white font-semibold rounded-[6px] text-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? "인증 중..." : otpStep ? "인증 완료" : "로그인"}
              </button>

              {otpStep && (
                <button type="button" onClick={() => { setOtpStep(false); setError(""); }}
                  className="w-full text-center text-[13px] text-[#94A3B8] hover:text-[#64748B] transition-colors"
                >
                  이전으로
                </button>
              )}
            </form>

            <div className="px-6 py-4 border-t border-[#E2E8F0] bg-[#F8FAFC]">
              <p className="text-[11px] text-[#94A3B8] leading-relaxed">
                본 시스템은 아동 개인정보를 취급합니다. 무단 접속 시 관계 법령에 따라 처벌받을 수 있으며, 접속 기록은 보관됩니다.
              </p>
            </div>
          </div>

          <p className="text-center text-[11px] text-[#94A3B8] mt-4">
            최근 로그인: 2026-08-20 09:14 · 서울 관악구
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: "dashboard",  label: "대시보드",          icon: "grid",       group: null },
  { id: "cases",      label: "통합 사례 목록",     icon: "folder",     group: "사례 관리" },
  { id: "recording",  label: "상담 녹음",          icon: "mic",        group: "상담 업무" },
  { id: "stt-review", label: "STT 검수",           icon: "transcript", group: "상담 업무", badge: 1 },
  { id: "ai-review",  label: "분석 결과 검토",     icon: "robot",      group: "상담 업무", badge: 2 },
  { id: "case-plan",  label: "사례관리 계획",      icon: "clipboard",  group: "상담 업무" },
  { id: "closure",    label: "종결·가정복귀 검토", icon: "home",       group: "상담 업무" },
  { id: "report",     label: "보고서 생성",        icon: "document",   group: "문서" },
];

function NavIcon({ id }: { id: string }) {
  const s = { width: 15, height: 15, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.7" };
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

function Sidebar({ current, onChange, onLogout }: { current: View; onChange: (v: View) => void; onLogout: () => void }) {
  const groups: { label: string | null; items: typeof NAV_ITEMS }[] = [];
  for (const item of NAV_ITEMS) {
    const last = groups[groups.length - 1];
    if (!last || last.label !== item.group) groups.push({ label: item.group, items: [item] });
    else last.items.push(item);
  }

  return (
    <aside className="flex flex-col shrink-0" style={{ width: "232px", background: "#0F263B", borderRight: "1px solid rgba(255,255,255,0.06)" }}>
      {/* Logo */}
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

      {/* User info */}
      <div className="px-4 py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0" style={{ background: "#15314A" }}>이</div>
          <div className="min-w-0">
            <div className="text-[13px] font-medium text-white truncate">이서연</div>
            <div className="text-[11px] truncate" style={{ color: "rgba(255,255,255,0.4)" }}>아동·청소년 상담사</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {groups.map((group, gi) => (
          <div key={gi} className="mb-1">
            {group.label && (
              <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.25)" }}>
                {group.label}
              </p>
            )}
            {group.items.map(item => {
              const active = current === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onChange(item.id as View)}
                  className="w-full flex items-center gap-2.5 text-left transition-colors"
                  style={{
                    padding: "7px 16px 7px 14px",
                    borderLeft: active ? "2px solid #2563EB" : "2px solid transparent",
                    background: active ? "rgba(255,255,255,0.07)" : "transparent",
                    color: active ? "#FFFFFF" : "rgba(255,255,255,0.55)",
                  }}
                  onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)"; }}
                  onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                >
                  <span className="shrink-0"><NavIcon id={item.icon} /></span>
                  <span className="text-[13px] font-medium flex-1 leading-tight">{item.label}</span>
                  {item.badge && (
                    <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-sm min-w-[18px] text-center"
                      style={{ background: item.badge > 1 ? "#DC2626" : "#D97706", color: "white" }}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Logout */}
      <div className="p-3" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <button
          onClick={onLogout}
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
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────
function DashboardView({ onNavigate }: { onNavigate: (v: View) => void }) {
  const highRisk = CASES.filter(c => c.riskLevel === "high");

  return (
    <div className="p-6 space-y-5" style={{ maxWidth: "1100px" }}>
      <div>
        <h1 className="text-[22px] font-semibold text-[#172033]">대시보드</h1>
        <p className="text-[13px] text-[#64748B] mt-0.5">2026년 8월 21일 목요일 · 이서연 상담사</p>
      </div>

      {/* Compact stat strip — no big emoji, no identical KPI cards */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="grid grid-cols-4 divide-x divide-[#E2E8F0]">
          {[
            { label: "전체 담당 사례", value: CASES.length,    note: `활성 ${CASES.filter(c => c.status === "active").length} · 검토 ${CASES.filter(c => c.status === "review").length}` },
            { label: "오늘 예정 상담", value: 3,               note: "13:00, 14:30, 16:00" },
            { label: "고위험 우선 검토", value: highRisk.length, note: "즉시 검토 필요", accent: true },
            { label: "미처리 업무",    value: TASKS.length,    note: `긴급 ${TASKS.filter(t => t.urgent).length}건 포함` },
          ].map(stat => (
            <div key={stat.label} className="px-5 py-4">
              <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">{stat.label}</p>
              <p className={`text-[28px] font-semibold leading-none mb-1 ${stat.accent ? "text-[#B91C1C]" : "text-[#172033]"}`}>{stat.value}</p>
              <p className="text-[12px] text-[#94A3B8]">{stat.note}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-5 gap-5">
        {/* Task list — compact, not card collection */}
        <div className="col-span-3 bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
            <span className="text-[13px] font-semibold text-[#172033]">나의 업무 목록</span>
            <span className="text-[11px] text-[#94A3B8]">{TASKS.length}건 미처리</span>
          </div>
          <div className="divide-y divide-[#F1F5F9]">
            {TASKS.map(task => (
              <div key={task.id} className="flex items-center gap-3 px-5 py-3 hover:bg-[#F8FAFC] transition-colors">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${task.urgent ? "bg-[#DC2626]" : "bg-[#CBD5E1]"}`} />
                <span className="text-[13px] text-[#172033] flex-1">{task.type}</span>
                <span className="text-[11px] text-[#94A3B8] font-mono">{task.case}</span>
                <button className="text-[12px] text-[#2563EB] font-medium hover:text-[#1D4ED8] transition-colors shrink-0">처리</button>
              </div>
            ))}
          </div>
        </div>

        {/* High-risk compact table */}
        <div className="col-span-2 bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
            <span className="text-[13px] font-semibold text-[#172033]">고위험 우선 검토</span>
            <button onClick={() => onNavigate("cases")} className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium transition-colors">전체보기</button>
          </div>
          <div className="divide-y divide-[#F1F5F9]">
            {highRisk.slice(0, 5).map(c => (
              <div key={c.id} className="px-5 py-2.5 hover:bg-[#F8FAFC] transition-colors">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-[13px] font-semibold text-[#172033]">{c.childName}</span>
                    <span className="text-[11px] text-[#94A3B8] ml-1.5">{c.age}세</span>
                  </div>
                  <RiskBadge level={c.riskLevel} score={c.riskScore} />
                </div>
                <div className="flex items-center gap-1 mt-1">
                  {c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}
                  <span className="text-[10px] text-[#94A3B8] font-mono ml-1">{c.id}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Cases View ─────────────────────────────────────────────────────────────
const ABUSE_OPTIONS: (AbuseType | "전체")[] = ["전체", "신체", "정서", "성", "방임"];
const RISK_OPTIONS:  (RiskLevel | "전체")[] = ["전체", "high", "mid", "low"];
const RISK_LABELS = { "전체": "전체", high: "고위험", mid: "중위험", low: "저위험" };

function CasesView() {
  const [query,        setQuery]        = useState("");
  const [abuseFilter,  setAbuseFilter]  = useState<AbuseType | "전체">("전체");
  const [riskFilter,   setRiskFilter]   = useState<RiskLevel | "전체">("전체");
  const [kwQuery,      setKwQuery]      = useState("");
  const [sortBy,       setSortBy]       = useState<"riskScore" | "lastSession">("riskScore");
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);

  const filtered = useMemo(() => CASES.filter(c => {
    if (query && !c.childName.includes(query) && !c.id.toLowerCase().includes(query.toLowerCase()) && !c.guardian.includes(query)) return false;
    if (abuseFilter !== "전체" && !c.abuseTypes.includes(abuseFilter)) return false;
    if (riskFilter !== "전체" && c.riskLevel !== riskFilter) return false;
    if (kwQuery && !c.keywords.some(k => k.includes(kwQuery))) return false;
    return true;
  }).sort((a, b) => sortBy === "riskScore" ? b.riskScore - a.riskScore : b.lastSession.localeCompare(a.lastSession)), [query, abuseFilter, riskFilter, kwQuery, sortBy]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Page header + filter toolbar */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-[22px] font-semibold text-[#172033]">통합 사례 목록</h1>
            <p className="text-[13px] text-[#64748B] mt-0.5">담당 사례 전체 · 이름, 학대유형, 키워드로 검색</p>
          </div>
          <button className="flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium text-white bg-[#15314A] hover:bg-[#0F263B] rounded-[6px] transition-colors">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            새 사례 등록
          </button>
        </div>

        {/* Single filter toolbar — no separate cards */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="아동명·보호자·사례ID" className="pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-48 transition-all" />
          </div>
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
            <input value={kwQuery} onChange={e => setKwQuery(e.target.value)} placeholder="키워드 검색" className="pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-36 transition-all" />
          </div>

          <div className="h-4 w-px bg-[#E2E8F0]" />

          {/* Abuse type filter */}
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mr-1">유형</span>
            {ABUSE_OPTIONS.map(o => (
              <button key={o} onClick={() => setAbuseFilter(o)}
                className={`px-2 py-1 text-[12px] font-medium rounded transition-all border ${abuseFilter === o ? "bg-[#172033] text-white border-[#172033]" : "border-[#E2E8F0] text-[#64748B] hover:border-[#CBD5E1]"}`}
              >
                {o === "전체" ? "전체" : `${o}학대`}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-[#E2E8F0]" />

          {/* Risk filter */}
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mr-1">위험도</span>
            {RISK_OPTIONS.map(r => (
              <button key={r} onClick={() => setRiskFilter(r)}
                className={`px-2 py-1 text-[12px] font-medium rounded transition-all border ${riskFilter === r ? "bg-[#172033] text-white border-[#172033]" : "border-[#E2E8F0] text-[#64748B] hover:border-[#CBD5E1]"}`}
              >
                {RISK_LABELS[r]}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-1 text-[12px] text-[#64748B]">
            <span>정렬:</span>
            <button onClick={() => setSortBy("riskScore")} className={`px-2 py-1 rounded transition-all ${sortBy === "riskScore" ? "font-semibold text-[#172033]" : "hover:text-[#172033]"}`}>위험도순</button>
            <button onClick={() => setSortBy("lastSession")} className={`px-2 py-1 rounded transition-all ${sortBy === "lastSession" ? "font-semibold text-[#172033]" : "hover:text-[#172033]"}`}>최근상담순</button>
            <span className="ml-2 text-[#94A3B8]">{filtered.length}건</span>
          </div>
        </div>
      </div>

      {/* Enterprise data table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-[#F8FAFC] border-b border-[#E2E8F0] z-10">
            <tr>
              {["사례 ID", "아동명", "연령", "학대유형", "위험도", "주요 키워드", "최근 상담", "상태", "담당", ""].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(c => (
              <>
                <tr
                  key={c.id}
                  onClick={() => setSelectedCase(selectedCase?.id === c.id ? null : c)}
                  className="cursor-pointer border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors"
                  style={{ borderLeft: c.riskLevel === "high" ? "2px solid #DC2626" : "2px solid transparent" }}
                >
                  <td className="px-4 py-3 font-mono text-[11px] text-[#94A3B8]">{c.id}</td>
                  <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{c.childName}</td>
                  <td className="px-4 py-3 text-[13px] text-[#64748B]">{c.age}세</td>
                  <td className="px-4 py-3"><div className="flex gap-1">{c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}</div></td>
                  <td className="px-4 py-3"><RiskBadge level={c.riskLevel} score={c.riskScore} /></td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      {c.keywords.slice(0, 2).map(k => <span key={k} className="text-[11px] text-[#64748B]">#{k}</span>)}
                      {c.keywords.length > 2 && <span className="text-[11px] text-[#94A3B8]">+{c.keywords.length - 2}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-[12px] text-[#64748B] font-mono">{c.lastSession}</td>
                  <td className="px-4 py-3"><StatusLabel status={c.status} /></td>
                  <td className="px-4 py-3 text-[13px] text-[#64748B]">{c.counselor}</td>
                  <td className="px-4 py-3">
                    <button className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium transition-colors">상세</button>
                  </td>
                </tr>
                {selectedCase?.id === c.id && (
                  <tr key={`${c.id}-detail`} className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                    <td colSpan={10} className="px-6 py-4">
                      <div className="flex items-start justify-between gap-6">
                        <div className="grid grid-cols-3 gap-6 flex-1">
                          <div>
                            <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">기본 정보</p>
                            <div className="space-y-1 text-[13px]">
                              <div className="flex gap-2"><span className="text-[#94A3B8] w-16">연령</span><span className="text-[#172033] font-medium">{c.age}세</span></div>
                              <div className="flex gap-2"><span className="text-[#94A3B8] w-16">보호자</span><span className="text-[#172033] font-medium">{c.guardian}</span></div>
                              <div className="flex gap-2"><span className="text-[#94A3B8] w-16">상담 회차</span><span className="text-[#172033] font-medium">{c.sessionCount}회차</span></div>
                            </div>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">학대 유형</p>
                            <div className="flex gap-1 flex-wrap">{c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}</div>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">주요 키워드</p>
                            <div className="flex gap-1 flex-wrap">
                              {c.keywords.map(k => <span key={k} className="text-[11px] text-[#64748B] bg-[#F1F5F9] border border-[#E2E8F0] px-1.5 py-0.5 rounded">#{k}</span>)}
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2 shrink-0">
                          <button className="px-3 py-1.5 bg-[#15314A] text-white text-[12px] font-medium rounded-[6px] hover:bg-[#0F263B] transition-colors">상세 화면</button>
                          <button className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-[12px] font-medium rounded-[6px] hover:bg-[#F1F5F9] transition-colors">새 상담 시작</button>
                          <button onClick={() => setSelectedCase(null)} className="p-1.5 text-[#94A3B8] hover:text-[#64748B] transition-colors">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">검색 결과가 없습니다.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────
export default function App() {
  const [auth,     setAuth]     = useState(false);
  const [userRole, setUserRole] = useState<"counselor" | "admin">("counselor");
  const [view,     setView]     = useState<View>("dashboard");

  function handleLogin(role: "counselor" | "admin") {
    setUserRole(role);
    setAuth(true);
  }

  function handleLogout() {
    setAuth(false);
    setUserRole("counselor");
    setView("dashboard");
  }

  if (!auth)               return <LoginScreen onLogin={handleLogin} />;
  if (userRole === "admin") return <AdminApp onLogout={handleLogout} />;

  const renderMain = () => {
    switch (view) {
      case "dashboard":  return <DashboardView onNavigate={setView} />;
      case "cases":      return <CasesView />;
      case "recording":  return <RecordingView />;
      case "stt-review": return <TranscriptReviewView />;
      case "ai-review":  return <AIReviewView />;
      case "case-plan":  return <CasePlanView />;
      case "closure":    return <ClosureView />;
      case "report":     return <ReportView />;
      default:           return <DashboardView onNavigate={setView} />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#F6F8FB" }}>
      <Sidebar current={view} onChange={setView} onLogout={handleLogout} />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Compact enterprise header — 56px */}
        <header className="bg-white border-b border-[#E2E8F0] px-5 flex items-center justify-between shrink-0" style={{ height: "56px" }}>
          <div className="relative" style={{ width: "300px" }}>
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="빠른 사례 검색..." className="w-full pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-[#F8FAFC] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] transition-all" />
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-1.5 text-[#94A3B8] hover:text-[#64748B] transition-colors">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>
              <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-[#DC2626] rounded-full" />
            </button>
            <div className="w-px h-4 bg-[#E2E8F0]" />
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-[#15314A] flex items-center justify-center text-white text-[10px] font-bold">이</div>
              <span className="text-[13px] font-medium text-[#172033]">이서연</span>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-hidden flex flex-col">
          {renderMain()}
        </main>
      </div>
    </div>
  );
}
