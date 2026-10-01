import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import Breadcrumb from "../components/ui/Breadcrumb";
import { useToast } from "../components/ui/Toast";
import { auth as authApi } from "../api/endpoints";
import { ApiError, SESSION_INFO_KEY, clearSession } from "../api/client";
import { PASSWORD_RULE_TEXT, type User } from "../api/types";
import { toLocalDate } from "../api/dashboardAdapters";

/** WEAK_PASSWORD 는 details.reasons 에 사유 문장 배열이 온다. */
function passwordReasons(caught: ApiError): string[] {
  const details = caught.details as { reasons?: unknown } | undefined;

  return Array.isArray(details?.reasons) ? details.reasons.filter((r): r is string => typeof r === "string") : [];
}

export default function AccountPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast } = useToast();
  const [auth, setAuth] = useState<{ role: string; name: string } | null>(null);
  const [editing, setEditing] = useState(false);
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const [pwErrors, setPwErrors] = useState<string[]>([]);

  const [me, setMe] = useState<User | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem(SESSION_INFO_KEY);
    if (raw) {
      try { setAuth(JSON.parse(raw)); } catch { /* ignore */ }
    }

    let cancelled = false;

    authApi
      .me()
      .then((user) => {
        if (!cancelled) setMe(user);
      })
      .catch(() => {
        // 401 이면 client 가 로그인 화면으로 보낸다. 그 밖의 실패는 저장된 이름으로 보여 준다.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // 비밀번호 변경은 Backend(POST /auth/me/password)가 규칙을 검사한다.
  // 바꾸고 나면 다른 기기의 로그인이 끊기므로(토큰 무효화) 이 기기도 다시 로그인하게 한다.
  async function handleSavePassword() {
    if (!pwCurrent || !pwNew) {
      showToast("현재 비밀번호와 새 비밀번호를 모두 입력해주세요.", "error");
      return;
    }
    if (pwSaving) return;

    setPwSaving(true);
    setPwErrors([]);
    try {
      await authApi.changePassword({ current_password: pwCurrent, new_password: pwNew });
      showToast("비밀번호가 변경되었습니다. 새 비밀번호로 다시 로그인해 주세요.", "success");
      clearSession();
      navigate("/login");
    } catch (caught) {
      if (caught instanceof ApiError) {
        const reasons = passwordReasons(caught);
        setPwErrors(reasons.length > 0 ? reasons : [caught.message]);
      } else {
        setPwErrors(["비밀번호 변경에 실패했습니다. 잠시 후 다시 시도해 주세요."]);
      }
    } finally {
      setPwSaving(false);
    }
  }

  function handleLogout() {
    clearSession();
    navigate("/login");
  }

  const name = auth?.name ?? "이서연";
  const role = auth?.role === "admin" ? "관리자" : "상담사";

  // 임시 비밀번호로 로그인했다. 로그인 화면 · AppLayout 이 이 화면으로 보낼 때 state 로 알리고,
  // 새로고침했을 때는 GET /auth/me 의 must_change_password 로 안다.
  const mustChangePassword =
    me?.must_change_password ?? Boolean((location.state as { mustChangePassword?: boolean } | null)?.mustChangePassword);
  const accountStatus = !me ? "—" : !me.is_active ? "비활성" : me.must_change_password ? "임시 비밀번호(변경 필요)" : "활성";

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5 max-w-2xl">
        <Breadcrumb items={[{ label: "계정 정보" }]} />

        {mustChangePassword && (
          <div className="flex items-start gap-2 px-4 py-3 bg-amber-50 border border-amber-200 rounded-[8px] text-[13px] text-amber-800">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 mt-0.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <p>
              임시 비밀번호로 로그인했습니다. 아래 보안 설정에서 새 비밀번호로 바꿔야 다른 화면을 쓸 수 있습니다.
              현재 비밀번호 칸에는 받은 임시 비밀번호를 넣어 주세요.
            </p>
          </div>
        )}

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
            {/* 이름 · 역할 · 이메일 · 계정 상태는 GET /auth/me 에서 온다.
                소속 기관 · 연락처 · 접속 위치는 Backend 에 없어 "—" 로 둔다. */}
            {[
              ["이름", me?.name ?? name],
              ["소속 기관", "—"],
              ["역할", role],
              ["이메일", me?.email ?? "—"],
              ["연락처", "—"],
              ["계정 상태", accountStatus],
              // 시간대 표시가 없으면 UTC 로 읽어 사용자 시간대 날짜로 바꾼다(API_CONTRACT 1.5). 앞 10글자를 자르면
              // 한국 시각 0~9시에 만든 계정이 하루 전 날짜로 보인다.
              ["계정 생성일", me ? toLocalDate(me.created_at) : "—"],
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
              <p className="mt-1 text-[11px] text-[#94A3B8]">{PASSWORD_RULE_TEXT}</p>
            </div>
            {pwErrors.length > 0 && (
              <ul className="text-[12px] text-red-600 space-y-0.5">
                {pwErrors.map(reason => <li key={reason}>{reason}</li>)}
              </ul>
            )}
            <button
              onClick={handleSavePassword}
              disabled={pwSaving}
              className="px-4 py-2 bg-[#2563EB] text-white text-[13px] font-semibold rounded-[6px] hover:bg-[#1D4ED8] transition-colors disabled:opacity-60"
            >
              {pwSaving ? "변경 중..." : "비밀번호 변경"}
            </button>
          </div>

          <div className="pt-4 border-t border-[#E2E8F0]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[13px] font-medium text-[#172033]">2단계 인증</p>
                <p className="text-[11px] text-[#94A3B8] mt-0.5">2단계 인증 방식은 팀에서 정하는 중입니다. 아직 서버에 없습니다.</p>
              </div>
              <span className="px-2 py-0.5 bg-[#F8FAFC] text-[#94A3B8] border border-[#E2E8F0] rounded text-[11px] font-medium">준비 중</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
