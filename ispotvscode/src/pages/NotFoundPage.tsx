import { useNavigate } from "react-router";

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F6F8FB]">
      <div className="text-center space-y-4">
        <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-widest">404</p>
        <h1 className="text-[28px] font-semibold text-[#172033]">페이지를 찾을 수 없습니다</h1>
        <p className="text-[13px] text-[#64748B]">요청하신 페이지가 존재하지 않거나 이동되었습니다.</p>
        <button
          onClick={() => navigate("/dashboard")}
          className="mt-4 px-5 py-2.5 bg-[#2563EB] text-white text-[13px] font-semibold rounded-[6px] hover:bg-[#1D4ED8] transition-colors"
        >
          대시보드로 이동
        </button>
      </div>
    </div>
  );
}
