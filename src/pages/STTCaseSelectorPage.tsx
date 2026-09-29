import { useState, useMemo } from "react";
import { useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { SESSIONS } from "../data/mockData";
import { RiskBadge, StatusLabel } from "../components/ui/Badges";
import Breadcrumb from "../components/ui/Breadcrumb";
import UploadModal from "../components/ui/UploadModal";

export default function STTCaseSelectorPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<"riskScore" | "lastSession">("riskScore");
  const [showUpload, setShowUpload] = useState(false);

  const rows = useMemo(() => CASES.map(c => {
    const cs = SESSIONS.filter(s => s.caseId === c.id);
    const pending = cs.filter(s => s.sttStatus === "검수필요" || s.sttStatus === "처리중").length;
    const latest = cs.sort((a, b) => b.date.localeCompare(a.date))[0];
    return { ...c, pendingCount: pending, latestDate: latest?.date ?? c.lastSession };
  }).filter(c => {
    if (!query) return true;
    return c.childName.includes(query) || c.id.toLowerCase().includes(query.toLowerCase());
  }).sort((a, b) => sortBy === "riskScore" ? b.riskScore - a.riskScore : b.lastSession.localeCompare(a.lastSession)), [query, sortBy]);

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <Breadcrumb items={[{ label: "상담 자료 검수" }, { label: "사례 선택" }]} />

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[22px] font-semibold text-[#172033]">상담 자료 검수</h1>
            <p className="text-[13px] text-[#64748B] mt-0.5">검수가 필요한 상담 자료 목록을 확인하세요</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-0.5 text-[13px] text-[#94A3B8] bg-white border border-[#E2E8F0] rounded-[6px] px-1 py-1">
              <button onClick={() => setSortBy("riskScore")} className={`px-2.5 py-1 rounded transition-all ${sortBy === "riskScore" ? "font-semibold text-[#172033] bg-[#F1F5F9]" : "hover:text-[#172033]"}`}>위험도순</button>
              <button onClick={() => setSortBy("lastSession")} className={`px-2.5 py-1 rounded transition-all ${sortBy === "lastSession" ? "font-semibold text-[#172033] bg-[#F1F5F9]" : "hover:text-[#172033]"}`}>최근상담순</button>
            </div>
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="아동명·사례ID" className="pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-48 transition-all" />
            </div>
            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium text-white bg-[#2563EB] hover:bg-[#1D4ED8] rounded-[6px] transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              상담 자료 업로드
            </button>
          </div>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["아동명", "사례 ID", "위험도", "최근 상담", "STT 대기 건수", "상태", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(c => (
                <tr
                  key={c.id}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                  onClick={() => navigate(`/cases/${c.id}/sessions`)}
                >
                  <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{c.childName}</td>
                  <td className="px-4 py-3 text-[11px] font-mono text-[#94A3B8]">{c.id}</td>
                  <td className="px-4 py-3"><RiskBadge level={c.riskLevel} score={c.riskScore} /></td>
                  <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{c.latestDate}</td>
                  <td className="px-4 py-3">
                    {c.pendingCount > 0 ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-[11px] font-semibold">
                        {c.pendingCount}건 대기
                      </span>
                    ) : (
                      <span className="text-[11px] text-[#94A3B8]">없음</span>
                    )}
                  </td>
                  <td className="px-4 py-3"><StatusLabel status={c.status} /></td>
                  <td className="px-4 py-3">
                    <button className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium">선택</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} />}
    </div>
  );
}
