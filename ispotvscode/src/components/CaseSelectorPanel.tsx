import { useState, useMemo } from "react";
import { CASES, CaseRecord, RiskLevel, AbuseType } from "../data/cases";

interface Props {
  selectedId: string;
  onSelect: (id: string) => void;
  filterLevel?: RiskLevel[];
}

const RISK_CFG: Record<RiskLevel, { label: string; dot: string; text: string }> = {
  high: { label: "고위험", dot: "bg-red-400",   text: "text-red-300" },
  mid:  { label: "중위험", dot: "bg-amber-400", text: "text-amber-300" },
  low:  { label: "저위험", dot: "bg-green-400", text: "text-green-300" },
};

const ABUSE_COLOR: Record<AbuseType, string> = {
  신체: "bg-red-900/40 text-red-300",
  정서: "bg-purple-900/40 text-purple-300",
  성:   "bg-orange-900/40 text-orange-300",
  방임: "bg-slate-700 text-slate-300",
};

const STATUS_CFG = {
  active:  { label: "진행중",  cls: "text-blue-400" },
  pending: { label: "대기중",  cls: "text-slate-400" },
  review:  { label: "검토필요", cls: "text-amber-400" },
};

export default function CaseSelectorPanel({ selectedId, onSelect, filterLevel }: Props) {
  const [query, setQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskLevel | "전체">("전체");

  const filtered = useMemo(() => {
    let list = filterLevel ? CASES.filter(c => filterLevel.includes(c.riskLevel)) : CASES;
    if (riskFilter !== "전체") list = list.filter(c => c.riskLevel === riskFilter);
    if (query) {
      const q = query.toLowerCase();
      list = list.filter(c =>
        c.childName.includes(q) ||
        c.id.toLowerCase().includes(q) ||
        c.keywords.some(k => k.includes(q)) ||
        c.counselor.includes(q)
      );
    }
    return [...list].sort((a, b) => b.riskScore - a.riskScore);
  }, [query, riskFilter, filterLevel]);

  return (
    <aside className="w-64 shrink-0 flex flex-col overflow-hidden" style={{ background: "#0F263B" }}>
      {/* Panel header */}
      <div className="px-4 py-3.5 border-b shrink-0" style={{ borderColor: "#1E3A54" }}>
        <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2">담당 사례 목록</p>

        {/* Search */}
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="이름, ID, 키워드 검색"
            className="w-full pl-8 pr-3 py-1.5 rounded-[6px] text-xs focus:outline-none focus:ring-1 focus:ring-[#2563EB] transition-all"
            style={{ background: "#15314A", border: "1px solid #1E3A54", color: "#CBD5E1" }}
          />
        </div>

        {/* Risk filter chips */}
        <div className="flex gap-1 mt-2 flex-wrap">
          {(["전체", "high", "mid", "low"] as const).map(r => {
            const labels = { 전체: "전체", high: "고위험", mid: "중위험", low: "저위험" };
            const isActive = riskFilter === r;
            return (
              <button
                key={r}
                onClick={() => setRiskFilter(r)}
                className={`px-2 py-0.5 rounded text-[10px] font-semibold border transition-all ${
                  isActive
                    ? r === "high" ? "bg-red-600 text-white border-red-600"
                      : r === "mid" ? "bg-amber-500 text-white border-amber-500"
                      : r === "low" ? "bg-green-600 text-white border-green-600"
                      : "text-white border-slate-500"
                    : "text-slate-400 hover:text-slate-200"
                }`}
                style={isActive && r === "전체" ? { background: "#2563EB", borderColor: "#2563EB" } : !isActive ? { background: "transparent", borderColor: "#1E3A54" } : {}}
              >
                {labels[r]}
              </button>
            );
          })}
        </div>
      </div>

      {/* Count */}
      <div className="px-4 py-2 shrink-0" style={{ borderBottom: "1px solid #1E3A54" }}>
        <span className="text-[10px] text-slate-500">{filtered.length}개 사례</span>
      </div>

      {/* Case list */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 && (
          <div className="px-4 py-8 text-center text-slate-500 text-xs">검색 결과 없음</div>
        )}
        {filtered.map(c => {
          const risk = RISK_CFG[c.riskLevel];
          const status = STATUS_CFG[c.status];
          const isSelected = c.id === selectedId;

          return (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={`w-full text-left px-4 py-3 transition-all border-b ${
                isSelected ? "border-l-2 border-l-[#2563EB]" : "border-l-2 border-l-transparent"
              }`}
              style={{
                borderBottomColor: "#1E3A54",
                background: isSelected ? "#15314A" : "transparent",
              }}
              onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLButtonElement).style.background = "#15314A80"; }}
              onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
            >
              {/* Name + risk */}
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold text-sm text-white">
                  {c.childName}
                  <span className="ml-1.5 text-xs font-normal text-slate-400">{c.age}세</span>
                </span>
                <span className="flex items-center gap-1 text-[10px] font-semibold text-slate-400">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${risk.dot}`} />
                  {c.riskScore}점
                </span>
              </div>

              {/* Case ID */}
              <p className="font-mono text-[10px] mb-1.5 text-slate-500">{c.id}</p>

              {/* Abuse types */}
              <div className="flex gap-1 flex-wrap mb-1.5">
                {c.abuseTypes.map(t => (
                  <span
                    key={t}
                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${ABUSE_COLOR[t]}`}
                  >
                    {t}
                  </span>
                ))}
              </div>

              {/* Status + last session */}
              <div className="flex items-center justify-between">
                <span className={`text-[10px] font-medium ${status.cls}`}>{status.label}</span>
                <span className="text-[10px] font-mono text-slate-500">{c.lastSession.slice(5)}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-2.5 shrink-0" style={{ borderTop: "1px solid #1E3A54" }}>
        <p className="text-[10px] text-slate-500 text-center">
          고위험 {CASES.filter(c => c.riskLevel === "high").length}건 · 중위험 {CASES.filter(c => c.riskLevel === "mid").length}건 · 저위험 {CASES.filter(c => c.riskLevel === "low").length}건
        </p>
      </div>
    </aside>
  );
}
