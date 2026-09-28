import { useParams, useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { AI_ANALYSES } from "../data/mockData";
import Breadcrumb from "../components/ui/Breadcrumb";

const STATUS_CFG: Record<string, string> = {
  "분석중":   "bg-blue-50 text-blue-700",
  "검토필요": "bg-amber-50 text-amber-700",
  "검토중":   "bg-amber-50 text-amber-700",
  "수정됨":   "bg-blue-50 text-blue-700",
  "승인완료": "bg-green-50 text-green-700",
};

export default function AIAnalysisListPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const c = CASES.find(x => x.id === caseId);
  if (!c) return <div className="flex items-center justify-center h-full text-[#94A3B8]">사례를 찾을 수 없습니다.</div>;

  const analyses = AI_ANALYSES.filter(a => a.caseId === caseId).sort((a, b) => b.date.localeCompare(a.date));

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <Breadcrumb items={[
          { label: "AI 분석 검토", to: "/ai-cases" },
          { label: c.childName },
          { label: "분석 목록" },
        ]} />

        <div>
          <h1 className="text-[22px] font-semibold text-[#172033]">{c.childName} — AI 분석 목록</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">{c.id} · 전체 {analyses.length}건</p>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["분석 날짜", "상담 회차", "분석 상태", "관련 신호 수", "검토자", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {analyses.map(a => (
                <tr key={a.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                  <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{a.date}</td>
                  <td className="px-4 py-3 text-[13px] text-[#172033]">{a.sessionNumber}회차</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${STATUS_CFG[a.status] ?? "bg-slate-50 text-slate-600"}`}>
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[13px] text-[#64748B]">{a.signals}건</td>
                  <td className="px-4 py-3 text-[12px] text-[#64748B]">{a.reviewedBy ?? "-"}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => navigate(`/cases/${caseId}/analyses/${a.id}`)}
                      className="px-2.5 py-1 bg-[#2563EB] text-white text-[11px] font-semibold rounded-[6px] hover:bg-[#1D4ED8] transition-colors"
                    >
                      검토하기
                    </button>
                  </td>
                </tr>
              ))}
              {analyses.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">분석 결과가 없습니다.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
