import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import Breadcrumb from "../components/ui/Breadcrumb";
import { useToast } from "../components/ui/Toast";

export default function AccountPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [auth, setAuth] = useState<{ role: string; name: string } | null>(null);
  const [editing, setEditing] = useState(false);
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew, setPwNew] = useState("");

  useEffect(() => {
    const raw = localStorage.getItem("ispot_auth");
    if (raw) {
      try { setAuth(JSON.parse(raw)); } catch { /* ignore */ }
    }
  }, []);

  function handleSavePassword() {
    if (!pwCurrent || !pwNew) {
      showToast("현재 비밀번호와 새 비밀번호를 모두 입력해주세요.", "error");
      return;
    }
    showToast("비밀번호가 변경되었습니다.", "success");
    setPwCurrent("");
    setPwNew("");
  }

  function handleLogout() {
    localStorage.removeItem("ispot_auth");
    navigate("/login");
  }

  const name = auth?.name ?? "이서연";
  const role = auth?.role === "admin" ? "관리자" : "상담사";

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5 max-w-2xl">
        <Breadcrumb items={[{ label: "계정 정보" }]} />

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[22px] font-semibold text-[#172033]">프로필 / 계정 설정</h1>
            <p className="text-[13px] text-[#64748B] mt-0.5">계정 정보 확인 및 보안 설정</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setEditing(v => !v)}
              className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-[12px] font-medium rounded-[6px] hover:bg-[#F1F5F9] transition-colors"
            >
              {editing ? "취소" : "계정 정보 수정"}
            </button>
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 border border-[#FECACA] text-[#B91C1C] text-[12px] font-medium rounded-[6px] hover:bg-[#FEF2F2] transition-colors"
            >
              로그아웃
            </button>
          </div>
        </div>

        {/* Info section */}
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
          <h2 className="text-[13px] font-semibold text-[#172033] mb-4">계정 정보</h2>
          <div className="grid grid-cols-2 gap-4 text-[13px]">
            {[
              ["이름", name],
              ["소속 기관", "서울 관악구 아동보호전문기관"],
              ["역할", role],
              ["기관 ID", auth?.role === "admin" ? "김민준" : "이서연"],
              ["이메일", `${name}@cpsc.or.kr`],
              ["연락처", "02-123-4567"],
              ["계정 상태", "활성"],
              ["마지막 로그인", "2026-08-20 09:14"],
              ["최근 접속 위치", "서울 관악구"],
            ].map(([k, v]) => (
              <div key={k} className="flex gap-3">
                <span className="text-[#94A3B8] w-28 shrink-0">{k}</span>
                <span className="text-[#172033] font-medium">{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Security section */}
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5 space-y-4">
          <h2 className="text-[13px] font-semibold text-[#172033]">보안 설정</h2>

          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">현재 비밀번호</label>
              <input
                type="password"
                value={pwCurrent}
                onChange={e => setPwCurrent(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">새 비밀번호</label>
              <input
                type="password"
                value={pwNew}
                onChange={e => setPwNew(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
              />
            </div>
            <button
              onClick={handleSavePassword}
              className="px-4 py-2 bg-[#2563EB] text-white text-[13px] font-semibold rounded-[6px] hover:bg-[#1D4ED8] transition-colors"
            >
              비밀번호 변경
            </button>
          </div>

          <div className="pt-4 border-t border-[#E2E8F0]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[13px] font-medium text-[#172033]">2단계 인증</p>
                <p className="text-[11px] text-[#94A3B8] mt-0.5">OTP 앱을 통한 2단계 인증이 활성화되어 있습니다.</p>
              </div>
              <span className="px-2 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded text-[11px] font-medium">활성</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
