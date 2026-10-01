import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router";
import Breadcrumb from "../components/ui/Breadcrumb";
import { cases as casesApi } from "../api/endpoints";
import { NOT_PROVIDED, describeApiError, toUiCaseDetail, type CaseWithId } from "../api/adapters";
import { toUiAnalysisRow, type UiAnalysisRow } from "../api/aiAdapters";

// 사례와 회기 목록은 Backend(GET /cases/{id}, GET /cases/{id}/sessions)에서 온다.
// AI 분석은 회기당 하나라 회기마다 한 줄이고, 분석 상태는 회기 상태에서 유도한다(adapters.deriveStatus).
// 관련 신호 수 · 검토자 이름은 회기 목록 응답에 없어 "—" 로 보인다.
const SESSION_PAGE_SIZE = 100;

const STATUS_CFG: Record<string, string> = {
  "분석중":   "border-[#CBD5E1] text-[#64748B]",
  "검토필요": "border-[#64748B] text-[#172033] font-semibold",
  "검토중":   "border-[#64748B] text-[#172033] font-semibold",
  "수정됨":   "border-[#CBD5E1] text-[#64748B]",
  "상담사검토완료": "border-[#CBD5E1] text-[#475569]",
  "분석 실패": "border-red-200 text-red-700 font-semibold",
};

export default function AIAnalysisListPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [c, setCase]              = useState<CaseWithId | null>(null);
  const [analyses, setAnalyses]   = useState<UiAnalysisRow[]>([]);
  const [total, setTotal]         = useState(0);
  const [loading, setLoading]     = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;

    let cancelled = false;

    setLoading(true);
    setLoadError(null);

    Promise.all([
      casesApi.get(caseId),
      casesApi.listSessions(caseId, { page: 1, page_size: SESSION_PAGE_SIZE }),
    ])
      .then(([detail, page]) => {
        if (cancelled) return;
        setCase(toUiCaseDetail(detail));
        // Backend 가 최신 회기(session_number 내림차순)부터 주므로 다시 정렬하지 않는다.
        setAnalyses(page.items.map(toUiAnalysisRow));
        setTotal(page.meta.total);
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "사례를 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (loading) return <div className="flex items-center justify-center h-full text-[#94A3B8]">사례를 불러오는 중...</div>;
  if (loadError || !c) return <div className="flex items-center justify-center h-full text-[#94A3B8]">{loadError ?? "사례를 찾을 수 없습니다."}</div>;

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
          <p className="text-[13px] text-[#64748B] mt-0.5">{c.id} · 전체 {total}건</p>
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
                <tr key={a.sessionId} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                  <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{a.analysisDate}</td>
                  <td className="px-4 py-3 text-[13px] text-[#172033]">
                    {a.sessionNumber}회차
                    {a.sessionTitle && <span className="ml-1.5 text-[11px] text-[#94A3B8]">{a.sessionTitle}</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded border text-[12px] bg-white ${STATUS_CFG[a.aiLabel] ?? "border-[#CBD5E1] text-[#64748B]"}`}>
                      {a.aiLabel}
                    </span>
                    <span className={`ml-2 text-[11px] ${a.failed ? "text-red-600" : "text-[#94A3B8]"}`}>{a.statusLabel}</span>
                  </td>
                  <td className="px-4 py-3 text-[13px] text-[#94A3B8]">{NOT_PROVIDED}</td>
                  <td className="px-4 py-3 text-[12px] text-[#94A3B8]">{NOT_PROVIDED}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => navigate(`/cases/${caseId}/analyses/${a.sessionId}`)}
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
