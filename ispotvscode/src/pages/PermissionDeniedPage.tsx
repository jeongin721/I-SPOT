import { useNavigate } from "react-router";

export default function PermissionDeniedPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F6F8FB]">
      <div className="text-center space-y-4">
        <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-widest">403</p>
        <h1 className="text-[28px] font-semibold text-[#172033]">접근 권한이 없습니다</h1>
        <p className="text-[13px] text-[#64748B]">해당 페이지에 접근할 권한이 없습니다. 관리자에게 문의하세요.</p>
        <button
          onClick={() => navigate(-1)}
          className="mt-4 px-5 py-2.5 bg-[#2563EB] text-white text-[13px] font-semibold rounded-[6px] hover:bg-[#1D4ED8] transition-colors"
        >
          이전 페이지로
        </button>
      </div>
    </div>
  );
}
