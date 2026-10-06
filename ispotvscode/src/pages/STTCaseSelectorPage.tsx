import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router";
import { StatusLabel } from "../components/ui/Badges";
import Breadcrumb from "../components/ui/Breadcrumb";
import UploadModal from "../components/ui/UploadModal";
import { tasks as tasksApi } from "../api/endpoints";
import { describeApiError, toUiTaskRow, type UiTaskRow } from "../api/adapters";

// 목록은 처리 대기 업무 API(GET /tasks, task_type=REVIEW_TRANSCRIPT)에서 온다.
// 사례가 아니라 검수가 필요한 회기 하나가 한 줄이고, 누르면 그 회기의 전사 검수 화면으로 간다.
// 위험도는 Backend 에 없어 정렬 기준에서 뺐다(오래 기다린 순 · 최근 순).
const PAGE_SIZE = 100;

export default function STTCaseSelectorPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<"waiting" | "recent">("waiting");
  const [showUpload, setShowUpload] = useState(false);
  const [tasks, setTasks] = useState<UiTaskRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    tasksApi
      .list({ task_type: "REVIEW_TRANSCRIPT", page: 1, page_size: PAGE_SIZE })
      .then((page) => {
        if (!cancelled) setTasks(page.items.map(toUiTaskRow));
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "검수 목록을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const rows = useMemo(() => tasks.filter(t => {
    if (!query) return true;
    return t.childName.includes(query) || t.caseNumber.toLowerCase().includes(query.toLowerCase());
  }).sort((a, b) => sortBy === "waiting" ? a.waitingSince.localeCompare(b.waitingSince) : b.waitingSince.localeCompare(a.waitingSince)), [tasks, query, sortBy]);

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
              <button onClick={() => setSortBy("waiting")} className={`px-2.5 py-1 rounded transition-all ${sortBy === "waiting" ? "font-semibold text-[#172033] bg-[#F1F5F9]" : "hover:text-[#172033]"}`}>오래 기다린순</button>
              <button onClick={() => setSortBy("recent")} className={`px-2.5 py-1 rounded transition-all ${sortBy === "recent" ? "font-semibold text-[#172033] bg-[#F1F5F9]" : "hover:text-[#172033]"}`}>최근순</button>
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
                {["아동명", "사례 ID", "회차", "대기 시작", "STT 대기", "상태", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(t => (
                <tr
                  key={t.sessionId}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                  onClick={() => navigate(`/cases/${t.caseId}/sessions/${t.sessionId}/transcript`)}
                >
                  <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{t.childName}</td>
                  <td className="px-4 py-3 text-[11px] font-mono text-[#94A3B8]">{t.caseNumber}</td>
                  <td className="px-4 py-3 text-[13px] text-[#64748B]">
                    {t.sessionNumber}회차
                    {t.sessionTitle && <span className="ml-1.5 text-[11px] text-[#94A3B8]">{t.sessionTitle}</span>}
                  </td>
                  <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{t.waitingSince}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-[11px] font-semibold">
                      {t.taskLabel} 대기
                    </span>
                    {t.isOverdue && (
                      <span className="ml-1.5 inline-flex items-center px-2 py-0.5 bg-red-50 text-red-700 border border-red-200 rounded text-[11px] font-semibold">
                        지연
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3"><StatusLabel status="review" /></td>
                  <td className="px-4 py-3">
                    <button className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium">선택</button>
                  </td>
                </tr>
              ))}
              {loading && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">검수 목록을 불러오는 중...</td></tr>
              )}
              {!loading && loadError && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-[13px] text-red-600">{loadError}</td></tr>
              )}
              {!loading && !loadError && rows.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">{query ? "검색 결과가 없습니다." : "검수할 상담 자료가 없습니다."}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} />}
    </div>
  );
}
