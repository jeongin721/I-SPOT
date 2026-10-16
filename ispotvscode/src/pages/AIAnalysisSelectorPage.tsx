import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router";
import { StatusLabel } from "../components/ui/Badges";
import Breadcrumb from "../components/ui/Breadcrumb";
import { cases as casesApi, tasks as tasksApi } from "../api/endpoints";
import { NOT_PROVIDED, describeApiError } from "../api/adapters";
import { AI_TASK_TYPES, describePending, toUiAiCaseRows, type UiAiCaseRow } from "../api/aiAdapters";

// 사례 목록(GET /cases)에 처리 대기 업무(GET /tasks)의 AI 분석 업무 수를 붙여 보여 준다.
// 이 화면은 "사례를 고르는" 목록이라 한 줄이 사례 하나다. 업무 목록만 쓰면 대기 업무가 없는
// 사례를 고를 수 없어서, 사례 목록을 바탕으로 하고 업무 수는 "검토 대기" 칸에만 쓴다.
// 위험도 · 사례별 분석 수는 아직 Backend 에 없어 "—" 로 보인다.
const CASE_PAGE_SIZE = 100;
const TASK_PAGE_SIZE = 100;

export default function AIAnalysisSelectorPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [allRows, setAllRows] = useState<UiAiCaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setLoadError(null);

    // 업무는 종류별로 따로 받는다. 한 번에 받으면 AI 와 상관없는 업무(녹음 업로드 등)가
    // 한 쪽을 채워 AI 업무가 잘릴 수 있다.
    Promise.all([
      casesApi.list({ page: 1, page_size: CASE_PAGE_SIZE }),
      ...AI_TASK_TYPES.map(taskType =>
        tasksApi.list({ page: 1, page_size: TASK_PAGE_SIZE, task_type: taskType }),
      ),
    ])
      .then(([casePage, ...taskPages]) => {
        if (cancelled) return;
        setAllRows(toUiAiCaseRows(casePage.items, taskPages.flatMap(page => page.items)));
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "사례 목록을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const rows = useMemo(() => allRows.filter(c => {
    if (!query) return true;
    return c.childName.includes(query) || c.id.toLowerCase().includes(query.toLowerCase());
  }), [allRows, query]);

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <Breadcrumb items={[{ label: "AI 분석 검토" }, { label: "사례 선택" }]} />

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[22px] font-semibold text-[#172033]">AI 분석 결과 검토 — 사례 선택</h1>
            <p className="text-[13px] text-[#64748B] mt-0.5">AI 분석 결과 검토가 필요한 사례를 선택하세요</p>
          </div>
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="아동명·사례ID" className="pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-48 transition-all" />
          </div>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["아동명", "사례 ID", "위험도", "전체 분석", "검토 대기", "상태", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">사례 목록을 불러오는 중...</td></tr>
              )}
              {!loading && loadError && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-[13px] text-red-600">{loadError}</td></tr>
              )}
              {!loading && !loadError && rows.map(c => (
                <tr
                  key={c.backendId}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                  onClick={() => navigate(`/cases/${c.backendId}/analyses`)}
                >
                  <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{c.childName}</td>
                  <td className="px-4 py-3 text-[11px] font-mono text-[#94A3B8]">{c.id}</td>
                  {/* 사례 단위 위험도 · 분석 수는 Backend 에 아직 없다. */}
                  <td className="px-4 py-3 text-[13px] text-[#94A3B8]">{NOT_PROVIDED}</td>
                  <td className="px-4 py-3 text-[13px] text-[#94A3B8]">{NOT_PROVIDED}</td>
                  <td className="px-4 py-3">
                    {c.pending.total > 0 ? (
                      <span
                        title={describePending(c.pending)}
                        className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-[11px] font-semibold"
                      >
                        {c.pending.total}건 대기
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
              {!loading && !loadError && rows.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">{query ? "검색 결과가 없습니다." : "담당 사례가 없습니다."}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
