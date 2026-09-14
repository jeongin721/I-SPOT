import { useState, useMemo } from "react";
import { useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { SESSIONS, AI_ANALYSES } from "../data/mockData";
import { RiskBadge, StatusLabel } from "../components/ui/Badges";
import Breadcrumb from "../components/ui/Breadcrumb";

type Mode = "plan" | "closure" | "report";

const MODE_CFG: Record<Mode, {
  title: string;
  subtitle: string;
  breadcrumb: string;
  dest: (caseId: string) => string;
  col: string;
  colValue: (caseId: string) => React.ReactNode;
}> = {
  plan: {
    title: "사례관리 계획 — 사례 선택",
    subtitle: "사례관리 계획을 작성하거나 확인할 사례를 선택하세요",
    breadcrumb: "사례관리 계획",
    dest: (id) => `/cases/${id}/plan`,
    col: "계획 상태",
    colValue: (caseId) => {
      const c = CASES.find(x => x.id === caseId)!;
      if (c.status === "review") return <span className="text-[11px] px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded">검토 필요</span>;
      if (c.status === "active") return <span className="text-[11px] px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded">진행중</span>;
      return <span className="text-[11px] text-[#94A3B8]">대기중</span>;
    },
  },
  closure: {
    title: "종결·가정복귀 검토 — 사례 선택",
    subtitle: "종결 또는 가정복귀 검토가 필요한 사례를 선택하세요",
    breadcrumb: "종결·가정복귀 검토",
    dest: (id) => `/cases/${id}/closure`,
    col: "상담 회차",
    colValue: (caseId) => {
      const c = CASES.find(x => x.id === caseId)!;
      return <span className="text-[12px] text-[#64748B]">{c.sessionCount}회차</span>;
    },
  },
  report: {
    title: "보고서 생성 — 사례 선택",
    subtitle: "보고서를 생성할 사례를 선택하세요",
    breadcrumb: "보고서 생성",
    dest: (id) => `/cases/${id}/reports`,
    col: "분석 완료",
    colValue: (caseId) => {
      const count = AI_ANALYSES.filter(a => a.caseId === caseId && a.status === "승인완료").length;
      return count > 0
        ? <span className="text-[11px] px-2 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded">{count}건 완료</span>
        : <span className="text-[11px] text-[#94A3B8]">없음</span>;
    },
  },
};

export default function CaseSelectorListPage({ mode }: { mode: Mode }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const cfg = MODE_CFG[mode];

  const rows = useMemo(() =>
    CASES.filter(c => {
      if (!query) return true;
      return c.childName.includes(query) || c.id.toLowerCase().includes(query.toLowerCase());
    }).sort((a, b) => b.riskScore - a.riskScore),
    [query]
  );

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <Breadcrumb items={[{ label: cfg.breadcrumb }, { label: "사례 선택" }]} />

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[22px] font-semibold text-[#172033]">{cfg.title}</h1>
            <p className="text-[13px] text-[#64748B] mt-0.5">{cfg.subtitle}</p>
          </div>
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="아동명·사례ID"
              className="pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-48 transition-all"
            />
          </div>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["아동명", "사례 ID", "위험도", "최근 상담", cfg.col, "상태", "담당 상담사", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(c => (
                <tr
                  key={c.id}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                  style={{ borderLeft: c.riskLevel === "high" ? "2px solid #DC2626" : "2px solid transparent" }}
                  onClick={() => navigate(cfg.dest(c.id))}
                >
                  <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{c.childName}</td>
                  <td className="px-4 py-3 text-[11px] font-mono text-[#94A3B8]">{c.id}</td>
                  <td className="px-4 py-3"><RiskBadge level={c.riskLevel} score={c.riskScore} /></td>
                  <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{c.lastSession}</td>
                  <td className="px-4 py-3">{cfg.colValue(c.id)}</td>
                  <td className="px-4 py-3"><StatusLabel status={c.status} /></td>
                  <td className="px-4 py-3 text-[12px] text-[#64748B]">{c.counselor}</td>
                  <td className="px-4 py-3">
                    <button className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium">선택</button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">
                    검색 조건에 맞는 사례가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
