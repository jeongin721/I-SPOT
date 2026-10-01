import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import AdminApp from "../admin/AdminApp";
import { auth } from "../api/endpoints";
import { ApiError, SESSION_INFO_KEY, clearLogoutReason, clearSession, readLogoutReason } from "../api/client";

// 로그인은 Backend(POST /auth/login)가 판정한다. 역할도 서버가 준 값을 쓴다.
// 2단계 인증(OTP)은 Backend 에 아직 없어 건너뛴다(팀 결정 대기). 화면 코드는 남겨 둔다.
const PLACEHOLDER = {
  counselor: "counselor@기관.or.kr",
  admin:     "admin@기관.or.kr",
};

export default function LoginPage() {
  const navigate = useNavigate();
  const [id, setId]       = useState("");
  const [pw, setPw]       = useState("");
  const [role, setRole]   = useState<"counselor" | "admin">("counselor");
  const [otpStep, setOtpStep] = useState(false);
  const [otp, setOtp]     = useState("");
  // 토큰이 끊겨 여기로 왔으면(예: 현재 비밀번호를 여러 번 틀림) 서버가 보낸 이유를 먼저 보여 준다(client.ts).
  const [error, setError] = useState(readLogoutReason);
  const [loading, setLoading] = useState(false);
  const [adminMode, setAdminMode] = useState(false);
  const [findPw, setFindPw] = useState(false);

  // 한 번 보여 준 이유는 지운다. 그리는 함수(useState 초기값)에서 지우면 StrictMode 의 두 번째 그리기에서 사라진다.
  useEffect(() => {
    clearLogoutReason();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    if (otpStep) {
      // OTP 단계는 지금 쓰지 않는다. 들어왔다면 처음으로 돌린다.
      setOtpStep(false);
      return;
    }

    if (!id.trim() || !pw) {
      setError("이메일과 비밀번호를 입력해 주세요.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await auth.login({ email: id.trim(), password: pw });
      const user = result.user;
      const uiRole = user.role === "ADMIN" ? "admin" : "counselor";

      // AppLayout 이 이 값으로 로그인 여부와 이름을 본다. 토큰은 auth.login 이 따로 저장한다.
      localStorage.setItem(SESSION_INFO_KEY, JSON.stringify({ role: uiRole, name: user.name }));
      // 이 화면이 뜬 뒤에 늦게 도착한 401 이 남긴 이유가 다음 로그아웃 때 다시 보이지 않게 지운다.
      clearLogoutReason();

      if (uiRole === "admin") {
        // 관리자 화면(AdminApp)은 아직 Backend 에 연결되지 않았다. 임시 비밀번호 안내는 연결할 때 함께 넣는다.
        setAdminMode(true);
      } else if (user.must_change_password) {
        // 임시 비밀번호로 들어왔다. 비밀번호를 바꾸기 전에는 다른 요청이 모두 403 PASSWORD_CHANGE_REQUIRED 라서
        // 대시보드 대신 비밀번호를 바꾸는 내 정보 화면으로 보낸다.
        navigate("/profile", { state: { mustChangePassword: true } });
      } else {
        navigate("/dashboard");
      }
    } catch (caught) {
      // 서버 문구를 그대로 보여 준다. 잠금 · 휴면 · 임시 비밀번호 안내가 여기에 담겨 온다.
      setError(caught instanceof ApiError ? caught.message : "로그인 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  }

  if (adminMode) {
    return <AdminApp onLogout={() => { clearSession(); setAdminMode(false); setOtpStep(false); setId(""); setPw(""); setOtp(""); setLoading(false); }} />;
  }

  const features = [
    { label: "상담 음성 STT 자동 변환 및 검수" },
    { label: "AI 분석 참고정보 및 관련 신호 확인" },
    { label: "상담일지·사정기록지 초안 자동 작성" },
  ];

  return (
    <div className="min-h-screen flex" style={{ background: "#0F263B" }}>
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
                <span className="w-1 h-1 rounded-full bg-white/30 shrink-0" />
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

      <div className="flex-1 flex items-center justify-center p-8" style={{ background: "#F6F8FB" }}>
        <div className="w-full" style={{ maxWidth: "400px" }}>
          <div className="flex lg:hidden items-center gap-2 mb-8">
            <div className="w-7 h-7 rounded flex items-center justify-center bg-[#15314A]">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            </div>
            <span className="font-bold text-[#172033] tracking-widest text-sm">I-SPOT</span>
          </div>

          <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
            <div className="px-6 py-5 border-b border-[#E2E8F0]">
              <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-widest mb-1">아동보호전문기관</p>
              <h2 className="text-base font-semibold text-[#172033]">
                {otpStep ? "2차 인증" : "기관 시스템 로그인"}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="px-6 py-6 space-y-4">
              {!otpStep ? (
                <>
                  <div>
                    <label className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">접속 권한</label>
                    <div className="flex border border-[#E2E8F0] rounded-[6px] overflow-hidden bg-[#F8FAFC]">
                      {(["counselor", "admin"] as const).map(r => (
                        <button
                          key={r}
                          type="button"
                          onClick={() => { setRole(r); setError(""); }}
                          className={`flex-1 py-2 text-sm font-medium transition-all ${
                            role === r ? "bg-[#15314A] text-white" : "text-[#64748B] hover:text-[#172033] hover:bg-[#F1F5F9]"
                          }`}
                        >
                          {r === "counselor" ? "상담사" : "관리자"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label htmlFor="uid" className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">이메일</label>
                    <input
                      id="uid" type="email" value={id} onChange={e => setId(e.target.value)} autoComplete="username"
                      placeholder={PLACEHOLDER[role]}
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

              {!otpStep && (
                <div className="text-center">
                  <button
                    type="button"
                    onClick={() => setFindPw(true)}
                    className="text-[12px] text-[#64748B] hover:text-[#2563EB] transition-colors"
                  >
                    비밀번호 찾기
                  </button>
                </div>
              )}
            </form>

            <div className="px-6 py-4 border-t border-[#E2E8F0] bg-[#F8FAFC]">
              <p className="text-[11px] text-[#94A3B8] leading-relaxed">
                본 시스템은 아동 개인정보를 취급합니다. 무단 접속 시 관계 법령에 따라 처벌받을 수 있으며, 접속 기록은 보관됩니다.
              </p>
            </div>
          </div>
        </div>
      </div>

      {findPw && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(15,38,59,0.5)" }}>
          <div className="bg-white rounded-[8px] border border-[#E2E8F0] w-full max-w-sm mx-4 overflow-hidden">
            <div className="px-6 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
              <h3 className="text-[15px] font-semibold text-[#172033]">비밀번호 찾기</h3>
              <button onClick={() => setFindPw(false)} className="text-[#94A3B8] hover:text-[#64748B]">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            {/* 로그인하지 않은 사람이 재발급을 요청하는 창구는 Backend 에 없다(관리자 재발급만 있다).
                요청이 간 것처럼 보이지 않게, 실제로 할 수 있는 방법만 안내한다. */}
            <div className="px-6 py-5 space-y-4">
              <p className="text-[13px] text-[#64748B] leading-relaxed">
                비밀번호를 잊었거나 여러 번 틀려 잠겼다면 소속 기관 관리자에게 임시 비밀번호 재발급을 요청해 주세요.
              </p>
              <p className="text-[13px] text-[#64748B] leading-relaxed">
                임시 비밀번호로 로그인하면 먼저 새 비밀번호로 바꿔야 합니다. 임시 비밀번호는 사용 기간(기본 72시간)이 지나면 쓸 수 없습니다.
              </p>
              <button
                type="button"
                onClick={() => setFindPw(false)}
                className="w-full py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white font-semibold rounded-[6px] text-sm transition-colors"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
