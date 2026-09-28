import { useParams, useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { SESSIONS, AI_ANALYSES } from "../data/mockData";
import Breadcrumb from "../components/ui/Breadcrumb";

const STT_CFG: Record<string, string> = {
  "처리중":   "bg-blue-50 text-blue-700",
  "검수필요": "bg-amber-50 text-amber-700",
  "검수완료": "bg-green-50 text-green-700",
  "분석완료": "bg-green-50 text-green-700",
};

const AI_CFG: Record<string, string> = {
  "대기중":   "text-[#94A3B8]",
  "분석중":   "text-blue-600",
  "검토필요": "text-amber-600 font-semibold",
  "검토완료": "text-green-600",
  "승인완료": "text-green-700 font-semibold",
};

export default function SessionListPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const c = CASES.find(x => x.id === caseId);
  if (!c) return <div className="flex items-center justify-center h-full text-[#94A3B8]">사례를 찾을 수 없습니다.</div>;

  const sessions = SESSIONS.filter(s => s.caseId === caseId).sort((a, b) => b.date.localeCompare(a.date));

  function getAnalysisId(sessionId: string) {
    return AI_ANALYSES.find(a => a.sessionId === sessionId)?.id;
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <Breadcrumb items={[
          { label: "STT 검수", to: "/stt-cases" },
          { label: c.childName },
          { label: "녹음 목록" },
        ]} />

        <div>
          <h1 className="text-[22px] font-semibold text-[#172033]">{c.childName} — 상담 녹음 목록</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">{c.id} · 전체 {sessions.length}회차</p>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["날짜", "시간", "회차", "상담사", "녹음 길이", "STT 상태", "AI 상태", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => {
                const analysisId = getAnalysisId(s.id);
                return (
                  <tr key={s.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                    <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{s.date}</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.time}</td>
                    <td className="px-4 py-3 text-[13px] text-[#172033]">{s.sessionNumber}회차</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.counselor}</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.duration}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${STT_CFG[s.sttStatus] ?? "bg-slate-50 text-slate-600"}`}>
                        {s.sttStatus}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-[12px] ${AI_CFG[s.aiStatus] ?? "text-[#64748B]"}`}>{s.aiStatus}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {s.sttStatus === "검수필요" && (
                          <button
                            onClick={() => navigate(`/cases/${caseId}/sessions/${s.id}/transcript`)}
                            className="px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-200 text-[11px] font-medium rounded-[6px] hover:bg-amber-100 transition-colors"
                          >
                            STT 검수
                          </button>
                        )}
                        {s.sttStatus === "검수완료" && analysisId && (
                          <button
                            onClick={() => navigate(`/cases/${caseId}/analyses/${analysisId}`)}
                            className="px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 text-[11px] font-medium rounded-[6px] hover:bg-blue-100 transition-colors"
                          >
                            AI 검토
                          </button>
                        )}
                        {(s.sttStatus === "분석완료") && (
                          <button
                            onClick={() => navigate(`/cases/${caseId}/sessions/${s.id}/transcript`)}
                            className="text-[11px] text-[#94A3B8] hover:text-[#64748B]"
                          >
                            보기
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {sessions.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">상담 기록이 없습니다.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
