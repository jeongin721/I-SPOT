import { Fragment, useState, useMemo } from "react";
import { useNavigate } from "react-router";
import { CASES, type RiskLevel, type AbuseType, type CaseRecord as Case } from "../data/cases";
import { RiskBadge, AbuseBadge, StatusLabel } from "../components/ui/Badges";

const ABUSE_OPTIONS: (AbuseType | "전체")[] = ["전체", "신체", "정서", "성", "방임"];
const RISK_OPTIONS: (RiskLevel | "전체")[] = ["전체", "high", "mid", "low"];
const RISK_LABELS = { "전체": "전체", high: "고위험", mid: "중위험", low: "저위험" };

export default function CasesView() {
  const navigate = useNavigate();
  const [query,       setQuery]       = useState("");
  const [abuseFilter, setAbuseFilter] = useState<AbuseType | "전체">("전체");
  const [riskFilter,  setRiskFilter]  = useState<RiskLevel | "전체">("전체");
  const [kwQuery,     setKwQuery]     = useState("");
  const [sortBy,      setSortBy]      = useState<"riskScore" | "lastSession">("riskScore");
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);

  const filtered = useMemo(() => CASES.filter(c => {
    if (query && !c.childName.includes(query) && !c.id.toLowerCase().includes(query.toLowerCase()) && !c.guardian.includes(query)) return false;
    if (abuseFilter !== "전체" && !c.abuseTypes.includes(abuseFilter)) return false;
    if (riskFilter !== "전체" && c.riskLevel !== riskFilter) return false;
    if (kwQuery && !c.keywords.some(k => k.includes(kwQuery))) return false;
    return true;
  }).sort((a, b) => sortBy === "riskScore" ? b.riskScore - a.riskScore : b.lastSession.localeCompare(a.lastSession)), [query, abuseFilter, riskFilter, kwQuery, sortBy]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-[22px] font-semibold text-[#172033]">통합 사례 목록</h1>
            <p className="text-[13px] text-[#64748B] mt-0.5">담당 사례 전체 · 이름, 학대유형, 키워드로 검색</p>
          </div>
          <button className="flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium text-white bg-[#15314A] hover:bg-[#0F263B] rounded-[6px] transition-colors">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            새 사례 등록
          </button>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="아동명·보호자·사례ID" className="pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-48 transition-all" />
          </div>
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
            <input value={kwQuery} onChange={e => setKwQuery(e.target.value)} placeholder="키워드 검색" className="pl-8 pr-3 py-1.5 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-36 transition-all" />
          </div>
          <div className="h-4 w-px bg-[#E2E8F0]" />
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mr-1">유형</span>
            {ABUSE_OPTIONS.map(o => (
              <button key={o} onClick={() => setAbuseFilter(o)}
                className={`px-2 py-1 text-[12px] font-medium rounded transition-all border ${abuseFilter === o ? "bg-[#172033] text-white border-[#172033]" : "border-[#E2E8F0] text-[#64748B] hover:border-[#CBD5E1]"}`}
              >
                {o === "전체" ? "전체" : `${o}학대`}
              </button>
            ))}
          </div>
          <div className="h-4 w-px bg-[#E2E8F0]" />
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mr-1">위험도</span>
            {RISK_OPTIONS.map(r => (
              <button key={r} onClick={() => setRiskFilter(r)}
                className={`px-2 py-1 text-[12px] font-medium rounded transition-all border ${riskFilter === r ? "bg-[#172033] text-white border-[#172033]" : "border-[#E2E8F0] text-[#64748B] hover:border-[#CBD5E1]"}`}
              >
                {RISK_LABELS[r]}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-1 text-[12px] text-[#64748B]">
            <span>정렬:</span>
            <button onClick={() => setSortBy("riskScore")} className={`px-2 py-1 rounded transition-all ${sortBy === "riskScore" ? "font-semibold text-[#172033]" : "hover:text-[#172033]"}`}>위험도순</button>
            <button onClick={() => setSortBy("lastSession")} className={`px-2 py-1 rounded transition-all ${sortBy === "lastSession" ? "font-semibold text-[#172033]" : "hover:text-[#172033]"}`}>최근상담순</button>
            <span className="ml-2 text-[#94A3B8]">{filtered.length}건</span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-[#F8FAFC] border-b border-[#E2E8F0] z-10">
            <tr>
              {["사례 ID", "아동명", "연령", "학대유형", "위험도", "주요 키워드", "최근 상담", "상태", "담당", ""].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(c => (
              <Fragment key={c.id}>
                <tr
                  onClick={() => setSelectedCase(selectedCase?.id === c.id ? null : c)}
                  className="cursor-pointer border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors"
                  style={{ borderLeft: c.riskLevel === "high" ? "2px solid #DC2626" : "2px solid transparent" }}
                >
                  <td className="px-4 py-3 font-mono text-[11px] text-[#94A3B8]">{c.id}</td>
                  <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{c.childName}</td>
                  <td className="px-4 py-3 text-[13px] text-[#64748B]">{c.age}세</td>
                  <td className="px-4 py-3"><div className="flex gap-1">{c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}</div></td>
                  <td className="px-4 py-3"><RiskBadge level={c.riskLevel} score={c.riskScore} /></td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      {c.keywords.slice(0, 2).map(k => <span key={k} className="text-[11px] text-[#64748B]">#{k}</span>)}
                      {c.keywords.length > 2 && <span className="text-[11px] text-[#94A3B8]">+{c.keywords.length - 2}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-[12px] text-[#64748B] font-mono">{c.lastSession}</td>
                  <td className="px-4 py-3"><StatusLabel status={c.status} /></td>
                  <td className="px-4 py-3 text-[13px] text-[#64748B]">{c.counselor}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={e => { e.stopPropagation(); navigate(`/cases/${c.id}`); }}
                      className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium transition-colors"
                    >
                      상세
                    </button>
                  </td>
                </tr>
                {selectedCase?.id === c.id && (
                  <tr key={`${c.id}-detail`} className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                    <td colSpan={10} className="px-6 py-4">
                      <div className="flex items-start justify-between gap-6">
                        <div className="grid grid-cols-3 gap-6 flex-1">
                          <div>
                            <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">기본 정보</p>
                            <div className="space-y-1 text-[13px]">
                              <div className="flex gap-2"><span className="text-[#94A3B8] w-16">연령</span><span className="text-[#172033] font-medium">{c.age}세</span></div>
                              <div className="flex gap-2"><span className="text-[#94A3B8] w-16">보호자</span><span className="text-[#172033] font-medium">{c.guardian}</span></div>
                              <div className="flex gap-2"><span className="text-[#94A3B8] w-16">상담 회차</span><span className="text-[#172033] font-medium">{c.sessionCount}회차</span></div>
                            </div>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">학대 유형</p>
                            <div className="flex gap-1 flex-wrap">{c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}</div>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">주요 키워드</p>
                            <div className="flex gap-1 flex-wrap">
                              {c.keywords.map(k => <span key={k} className="text-[11px] text-[#64748B] bg-[#F1F5F9] border border-[#E2E8F0] px-1.5 py-0.5 rounded">#{k}</span>)}
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2 shrink-0">
                          <button
                            onClick={() => navigate(`/cases/${c.id}`)}
                            className="px-3 py-1.5 bg-[#15314A] text-white text-[12px] font-medium rounded-[6px] hover:bg-[#0F263B] transition-colors"
                          >
                            상세 화면
                          </button>
                          <button
                            onClick={() => navigate(`/cases/${c.id}/counseling/new`)}
                            className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-[12px] font-medium rounded-[6px] hover:bg-[#F1F5F9] transition-colors"
                          >
                            새 상담 시작
                          </button>
                          <button onClick={() => setSelectedCase(null)} className="p-1.5 text-[#94A3B8] hover:text-[#64748B] transition-colors">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">검색 결과가 없습니다.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
