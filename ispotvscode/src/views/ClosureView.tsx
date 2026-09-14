import { useState } from "react";
import CaseSelectorPanel from "../components/CaseSelectorPanel";
import { CASES } from "../data/cases";

const CASE_DETAIL: Record<string, {
  goals: { label: string; achieved: "완료" | "부분" | "미달" }[];
  riskFactors: { label: string; type: "잔존" | "반복" | "해소" }[];
  pastMatch: { factor: string; match: boolean }[];
  checkItems: { label: string; done: boolean }[];
}> = {
  default: {
    goals: [
      { label: "심리·정서 안정화", achieved: "부분" },
      { label: "가정 내 안전 확보", achieved: "부분" },
      { label: "보호자 양육 능력 향상", achieved: "미달" },
    ],
    riskFactors: [
      { label: "보호자 폭력 위험", type: "반복" },
      { label: "아동 외상 후 증상", type: "잔존" },
      { label: "신체적 위험", type: "잔존" },
    ],
    pastMatch: [
      { factor: "반복적 신체폭력", match: true },
      { factor: "피해 은폐 강요", match: true },
      { factor: "아동 정서 불안정", match: true },
      { factor: "보호자 양육 포기", match: false },
    ],
    checkItems: [
      { label: "초기 사례관리 목표 달성 여부 검토 완료", done: false },
      { label: "잔존 위험요인 확인 및 기록 완료", done: false },
      { label: "과거 중대사건 위험요인 대조 완료", done: false },
      { label: "아동 최종 면담 실시", done: false },
      { label: "보호자 최종 면담 실시", done: false },
      { label: "관련 기관 종결 통보 준비", done: false },
    ],
  },
  "C-2026-0312": {
    goals: [
      { label: "불안 및 과잉경계 감소", achieved: "완료" },
      { label: "아동 자기표현 능력 향상", achieved: "부분" },
      { label: "또래 관계 개선", achieved: "부분" },
      { label: "가정 내 정서적 안전감 확보", achieved: "완료" },
    ],
    riskFactors: [
      { label: "보호자 양육 스트레스", type: "잔존" },
      { label: "아동 위축 행동", type: "반복" },
      { label: "신체적 위험", type: "해소" },
      { label: "학교 적응 어려움", type: "해소" },
    ],
    pastMatch: [
      { factor: "반복적 신체폭력", match: false },
      { factor: "피해 은폐 강요", match: false },
      { factor: "아동 정서 불안정", match: true },
      { factor: "보호자 양육 부재", match: false },
    ],
    checkItems: [
      { label: "초기 사례관리 목표 달성 여부 검토 완료", done: true },
      { label: "잔존 위험요인 확인 및 기록 완료", done: true },
      { label: "과거 중대사건 위험요인 대조 완료", done: true },
      { label: "아동 최종 면담 실시", done: false },
      { label: "보호자 최종 면담 실시", done: false },
      { label: "관련 기관 종결 통보 준비", done: false },
    ],
  },
  "C-2026-0251": {
    goals: [
      { label: "자존감 향상 프로그램 참여", achieved: "완료" },
      { label: "또래 갈등 해결 능력 향상", achieved: "완료" },
      { label: "가정 내 의사소통 개선", achieved: "부분" },
    ],
    riskFactors: [
      { label: "학업 스트레스", type: "잔존" },
      { label: "부모-자녀 의사소통 부재", type: "잔존" },
      { label: "정서적 폭력", type: "해소" },
    ],
    pastMatch: [
      { factor: "반복적 신체폭력", match: false },
      { factor: "아동 정서 불안정", match: true },
      { factor: "부모-자녀 갈등", match: true },
      { factor: "사회적 고립", match: false },
    ],
    checkItems: [
      { label: "초기 사례관리 목표 달성 여부 검토 완료", done: true },
      { label: "잔존 위험요인 확인 및 기록 완료", done: true },
      { label: "아동 최종 면담 실시", done: true },
      { label: "보호자 최종 면담 실시", done: false },
      { label: "관련 기관 종결 통보 준비", done: false },
      { label: "종결 후 추후 관리 계획 수립", done: false },
    ],
  },
};

const ACHIEVED_CFG = {
  완료: { cls: "bg-green-50 border-green-200 text-green-700", bar: "bg-green-500", width: "w-full" },
  부분: { cls: "bg-amber-50 border-amber-200 text-amber-700", bar: "bg-amber-400", width: "w-2/3" },
  미달: { cls: "bg-red-50 border-red-200 text-red-700", bar: "bg-red-400", width: "w-1/4" },
};

const RISK_TYPE_CFG = {
  잔존: { cls: "bg-amber-50 border-amber-200 text-amber-700", dot: "bg-amber-500" },
  반복: { cls: "bg-red-50 border-red-200 text-red-700",   dot: "bg-red-500" },
  해소: { cls: "bg-green-50 border-green-200 text-green-600", dot: "bg-green-400" },
};

type Decision = "" | "종결" | "가정복귀" | "계속관리";

export default function ClosureView() {
  const [selectedId, setSelectedId] = useState(CASES[5].id); // 강○○ (low risk) default
  const [checkStates, setCheckStates] = useState<Record<string, boolean[]>>({});
  const [decision, setDecision] = useState<Decision>("");
  const [decisionNote, setDecisionNote] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const selectedCase = CASES.find(c => c.id === selectedId)!;
  const detail = CASE_DETAIL[selectedId] ?? CASE_DETAIL["default"];

  function getChecks(): boolean[] {
    return checkStates[selectedId] ?? detail.checkItems.map(i => i.done);
  }

  function toggleCheck(i: number) {
    const curr = getChecks();
    setCheckStates(prev => ({ ...prev, [selectedId]: curr.map((v, idx) => idx === i ? !v : v) }));
  }

  function handleSelectCase(id: string) {
    setSelectedId(id);
    setDecision("");
    setDecisionNote("");
    setSubmitted(false);
  }

  const currentChecks = getChecks();
  const doneCount = currentChecks.filter(Boolean).length;
  const allDone = doneCount === currentChecks.length;

  const achievedCount = detail.goals.filter(g => g.achieved === "완료").length;
  const partialCount  = detail.goals.filter(g => g.achieved === "부분").length;
  const remainingRisk = detail.riskFactors.filter(r => r.type !== "해소").length;
  const matchCount    = detail.pastMatch.filter(p => p.match).length;

  return (
    <div className="flex h-full overflow-hidden">
      <CaseSelectorPanel selectedId={selectedId} onSelect={handleSelectCase} />

      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-5">
          <div>
            <h1 className="text-xl font-bold text-[#172033]">종결·가정복귀 검토</h1>
            <p className="text-[#64748B] text-sm mt-0.5">
              <span className="font-semibold text-[#172033]">{selectedCase.childName}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              <span className="font-mono text-xs">{selectedCase.id}</span>
            </p>
          </div>

          {/* Summary stat strip */}
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] grid grid-cols-4 divide-x divide-[#E2E8F0]">
            {[
              { label: "목표 완료", value: `${achievedCount}/${detail.goals.length}건`, color: "text-green-700" },
              { label: "목표 부분 달성", value: `${partialCount}/${detail.goals.length}건`, color: "text-amber-700" },
              { label: "잔존·반복 위험요인", value: `${remainingRisk}개`, color: remainingRisk > 1 ? "text-red-700" : "text-[#172033]" },
              { label: "과거 중대사건 일치", value: `${matchCount}/${detail.pastMatch.length}개`, color: matchCount > 1 ? "text-red-700" : "text-[#172033]" },
            ].map(stat => (
              <div key={stat.label} className="px-5 py-4">
                <p className="text-[11px] text-[#64748B] mb-1">{stat.label}</p>
                <p className={`text-xl font-bold ${stat.color}`}>{stat.value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-3 gap-5">
            {/* Goals */}
            <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
              <div className="px-5 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
                <h2 className="font-semibold text-[#172033] text-sm">초기 목표 달성 수준</h2>
              </div>
              <div className="p-5 space-y-3">
                {detail.goals.map((g, i) => {
                  const cfg = ACHIEVED_CFG[g.achieved];
                  return (
                    <div key={i} className={`rounded-[6px] border p-3 ${cfg.cls}`}>
                      <div className="flex items-center justify-between mb-2"><span className="text-sm font-medium">{g.label}</span><span className="text-xs font-bold">{g.achieved}</span></div>
                      <div className="h-1.5 bg-white/60 rounded-full overflow-hidden"><div className={`h-full rounded-full ${cfg.bar} ${cfg.width}`} /></div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Risk + past */}
            <div className="space-y-4">
              <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
                <div className="px-5 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  <h2 className="font-semibold text-[#172033] text-sm">잔존·반복 위험요인</h2>
                </div>
                <div className="p-5 space-y-2">
                  {detail.riskFactors.map((r, i) => {
                    const cfg = RISK_TYPE_CFG[r.type];
                    return (
                      <div key={i} className={`flex items-center gap-2.5 px-3 py-2.5 rounded-[6px] border ${cfg.cls}`}>
                        <span className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />
                        <span className="text-sm flex-1">{r.label}</span>
                        <span className="text-xs font-bold shrink-0">{r.type}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
                <div className="px-5 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  <h2 className="font-semibold text-[#172033] text-sm">과거 중대사건 위험요인 비교</h2>
                </div>
                <div className="p-5 space-y-2">
                  {detail.pastMatch.map((p, i) => (
                    <div key={i} className={`flex items-center gap-2.5 px-3 py-2 rounded-[6px] border text-sm ${p.match ? "bg-red-50 border-red-200 text-red-800" : "bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]"}`}>
                      <span className={`w-2 h-2 rounded-full shrink-0 ${p.match ? "bg-red-500" : "bg-slate-300"}`} />
                      <span className="flex-1">{p.factor}</span>
                      {p.match && <span className="text-xs font-semibold text-red-600">일치</span>}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Checklist + decision */}
            <div className="space-y-4">
              <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
                <div className="px-5 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between">
                  <h2 className="font-semibold text-[#172033] text-sm">종결 전 확인 체크리스트</h2>
                  <span className="text-xs font-mono text-[#64748B]">{doneCount}/{currentChecks.length}</span>
                </div>
                <div className="p-5 space-y-2.5">
                  {detail.checkItems.map((item, i) => (
                    <label key={i} className="flex items-start gap-2.5 cursor-pointer group">
                      <input type="checkbox" checked={currentChecks[i]} onChange={() => toggleCheck(i)} className="mt-0.5 shrink-0 accent-blue-600" />
                      <span className={`text-sm leading-relaxed transition-colors ${currentChecks[i] ? "text-[#94A3B8] line-through" : "text-[#172033] group-hover:text-[#0F263B]"}`}>{item.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
                <div className="px-5 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  <h2 className="font-semibold text-[#172033] text-sm">최종 결정</h2>
                </div>
                <div className="p-5 space-y-3">
                  {!submitted ? (
                    <>
                      <div className="grid grid-cols-3 gap-2">
                        {(["종결", "가정복귀", "계속관리"] as Decision[]).filter(Boolean).map(opt => (
                          <button key={opt} onClick={() => setDecision(opt)}
                            className={`py-2 rounded-[6px] text-sm font-semibold border transition-all ${decision === opt
                              ? opt === "종결" ? "border-green-500 bg-green-50 text-green-700"
                                : opt === "가정복귀" ? "border-[#2563EB] bg-blue-50 text-blue-700"
                                : "border-amber-400 bg-amber-50 text-amber-700"
                              : "border-[#E2E8F0] text-[#64748B] hover:border-[#CBD5E1]"
                            }`}
                          >{opt}</button>
                        ))}
                      </div>
                      <textarea value={decisionNote} onChange={e => setDecisionNote(e.target.value)} placeholder="결정 사유 및 추가 메모 입력..." rows={3}
                        className="w-full px-3 py-2.5 rounded-[6px] border border-[#E2E8F0] text-sm resize-none focus:outline-none focus:ring-1 focus:ring-[#2563EB]" />
                      <button onClick={() => { if (decision) setSubmitted(true); }} disabled={!decision || !allDone}
                        className="w-full py-2.5 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-[#1D4ED8] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                      >
                        {!allDone ? `체크리스트 ${currentChecks.length - doneCount}건 미완료` : "최종 결정 확정"}
                      </button>
                    </>
                  ) : (
                    <div className="text-center py-4 space-y-2">
                      <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center mx-auto"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg></div>
                      <p className="font-bold text-[#172033]">{decision} 결정 완료</p>
                      <p className="text-xs text-[#64748B] font-mono">2026-08-21 · 이서연 상담사</p>
                      {decisionNote && <p className="text-sm text-[#64748B] bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] p-3 text-left">{decisionNote}</p>}
                      <button onClick={() => setSubmitted(false)} className="text-xs text-[#94A3B8] hover:text-[#64748B] transition-colors">수정하기</button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
