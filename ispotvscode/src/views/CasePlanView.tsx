import { useState } from "react";
import CaseSelectorPanel from "../components/CaseSelectorPanel";
import { CASES } from "../data/cases";

type Direction = "강화" | "유지" | "완화";

interface InterventionArea {
  id: string;
  label: string;
  priority: number;
  direction: Direction;
  basis: string;
  checked: boolean;
}

const INIT_INTERVENTIONS: InterventionArea[] = [
  { id: "child-psych", label: "아동 심리·정서 지원", priority: 1, direction: "강화", basis: "아동 공포 반응 및 외상 후 증상 확인됨", checked: true },
  { id: "safety",      label: "안전 및 보호 지원",   priority: 2, direction: "강화", basis: "반복적 신체폭력, 피해 은폐 강요 확인", checked: true },
  { id: "guardian",    label: "보호자 상담",          priority: 3, direction: "강화", basis: "주 행위자 부(父) 대상 개입 필요", checked: true },
  { id: "parent-edu",  label: "부모 교육",            priority: 4, direction: "강화", basis: "양육기술 부재 및 충동조절 어려움", checked: true },
  { id: "child-edu",   label: "아동 교육",            priority: 5, direction: "유지", basis: "현재 학교 출석 유지 중", checked: false },
  { id: "family",      label: "가족관계 개선",        priority: 6, direction: "유지", basis: "모 부재로 관계 회복 여건 제한적", checked: false },
];

const PROBLEM_AREAS = {
  child:       [{ label: "외상 후 스트레스 반응", severity: "high" }, { label: "회피 및 위축 행동", severity: "high" }, { label: "수면 장애", severity: "mid" }, { label: "또래 관계 어려움", severity: "low" }],
  guardian:    [{ label: "충동조절 어려움 (분노)", severity: "high" }, { label: "양육 기술 부족", severity: "high" }, { label: "피해 은폐 강요", severity: "high" }, { label: "사회적 지지체계 부재", severity: "mid" }],
  environment: [{ label: "한부모 가정 (모 부재)", severity: "high" }, { label: "사회·경제적 스트레스", severity: "mid" }, { label: "친족 접촉 제한적", severity: "mid" }],
};

const SEVERITY_CFG = {
  high: { label: "심각", cls: "bg-red-50 border-red-200 text-red-700" },
  mid:  { label: "중간", cls: "bg-amber-50 border-amber-200 text-amber-700" },
  low:  { label: "낮음", cls: "bg-green-50 border-green-200 text-green-600" },
};

const DIR_CFG: Record<Direction, string> = {
  강화: "bg-red-100 text-red-700",
  유지: "bg-blue-100 text-blue-700",
  완화: "bg-green-100 text-green-700",
};

export default function CasePlanView() {
  const [selectedId, setSelectedId] = useState(CASES[0].id);
  const [interventions, setInterventions] = useState<InterventionArea[]>(INIT_INTERVENTIONS);
  const [planText, setPlanText] = useState("• 즉각적인 안전 확보 조치 검토 (격리 여부 포함)\n• 경찰 고발 및 의료 진단 연계 추진\n• 8회차부터 외상 중심 인지행동치료(TF-CBT) 적용\n• 부(父) 대상 분노조절 프로그램 연계 의뢰\n• 매주 1회 아동 면담 유지, 가정 방문 월 1회 추가");
  const [saved, setSaved] = useState(false);

  const selectedCase = CASES.find(c => c.id === selectedId)!;

  function handleSelectCase(id: string) { setSelectedId(id); setSaved(false); }
  function toggleIntervention(id: string) { setInterventions(prev => prev.map(i => i.id === id ? { ...i, checked: !i.checked } : i)); }
  function changeDirection(id: string, dir: Direction) { setInterventions(prev => prev.map(i => i.id === id ? { ...i, direction: dir } : i)); }

  const selected = interventions.filter(i => i.checked);

  return (
    <div className="flex h-full overflow-hidden">
      <CaseSelectorPanel selectedId={selectedId} onSelect={handleSelectCase} />

      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-5">
          {/* Header */}
          <div>
            <h1 className="text-xl font-bold text-[#172033]">사례관리 계획</h1>
            <p className="text-[#64748B] text-sm mt-0.5">문제 영역을 분석하고 개입 우선순위 및 방향을 설정합니다</p>
          </div>

          {/* Case bar */}
          <div className="bg-[#15314A] text-white rounded-[8px] px-6 py-4 flex items-center gap-6 flex-wrap border border-[#1E3A54]">
            <div><p className="text-xs text-blue-300 uppercase tracking-wider mb-0.5">대상 아동</p><p className="font-bold text-lg">{selectedCase.childName} · {selectedCase.age}세</p></div>
            <div className="h-8 w-px bg-white/20 hidden sm:block" />
            <div><p className="text-xs text-blue-300 uppercase tracking-wider mb-0.5">사례번호</p><p className="font-mono text-sm">{selectedCase.id}</p></div>
            <div className="h-8 w-px bg-white/20 hidden sm:block" />
            <div><p className="text-xs text-blue-300 uppercase tracking-wider mb-0.5">학대 유형</p>
              <div className="flex gap-1.5">{selectedCase.abuseTypes.map(t => <span key={t} className="px-2 py-0.5 bg-white/15 rounded text-xs font-medium">{t}학대</span>)}</div>
            </div>
            <div className="h-8 w-px bg-white/20 hidden sm:block" />
            <div><p className="text-xs text-blue-300 uppercase tracking-wider mb-0.5">AI 위험도</p><p className="font-bold text-red-300 text-lg">{selectedCase.riskScore}점</p></div>
            <div className="ml-auto text-xs text-blue-300">기준일: 2026-08-21</div>
          </div>

          <div className="grid grid-cols-3 gap-5">
            {/* Problem analysis */}
            <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
              <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC]">
                <h2 className="font-semibold text-[#172033] text-sm">문제 영역 분석</h2>
                <p className="text-xs text-[#64748B] mt-0.5">AI 분석 참고정보 — 상담 내용 기반 문제 영역</p>
              </div>
              <div className="p-5 space-y-5">
                {(["child", "guardian", "environment"] as const).map(domain => {
                  const labels = { child: "아동", guardian: "보호자", environment: "환경" };
                  return (
                    <div key={domain}>
                      <p className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider mb-2">{labels[domain]} 영역</p>
                      <div className="space-y-1.5">
                        {PROBLEM_AREAS[domain].map((item, i) => {
                          const cfg = SEVERITY_CFG[item.severity as keyof typeof SEVERITY_CFG];
                          return (
                            <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-[6px] border text-xs ${cfg.cls}`}>
                              <span>{item.label}</span>
                              <span className="font-semibold shrink-0">{cfg.label}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Intervention priority */}
            <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
              <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC]">
                <h2 className="font-semibold text-[#172033] text-sm">개입 우선순위 추천</h2>
                <p className="text-xs text-[#64748B] mt-0.5">항목 선택 및 방향 조정 후 계획에 반영</p>
              </div>
              <div className="p-5 space-y-2">
                {interventions.map(item => (
                  <div key={item.id} className={`rounded-[6px] border p-3 transition-colors ${item.checked ? "border-blue-200 bg-blue-50" : "border-[#E2E8F0] bg-[#F8FAFC] opacity-60"}`}>
                    <div className="flex items-start gap-2.5">
                      <input type="checkbox" checked={item.checked} onChange={() => toggleIntervention(item.id)} className="mt-0.5 shrink-0 accent-[#2563EB]" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[11px] font-mono text-[#94A3B8]">우선 {item.priority}</span>
                          <span className="text-sm font-semibold text-[#172033]">{item.label}</span>
                        </div>
                        <p className="text-[11px] text-[#64748B] mb-2 leading-relaxed">{item.basis}</p>
                        <div className="flex gap-1">
                          {(["강화", "유지", "완화"] as Direction[]).map(dir => (
                            <button key={dir} onClick={() => changeDirection(item.id, dir)}
                              className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${item.direction === dir ? DIR_CFG[dir] : "bg-white border border-[#E2E8F0] text-[#94A3B8]"}`}
                            >{dir}</button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Final plan */}
            <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden flex flex-col">
              <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC]">
                <h2 className="font-semibold text-[#172033] text-sm">최종 사례관리 계획</h2>
                <p className="text-xs text-[#64748B] mt-0.5">상담사가 직접 확인하고 계획을 수립합니다</p>
              </div>
              <div className="px-5 py-3 border-b border-[#E2E8F0] bg-[#F8FAFC]">
                <p className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-2">선택된 개입 영역 ({selected.length}개)</p>
                <div className="flex flex-wrap gap-1.5">
                  {selected.map(s => (
                    <span key={s.id} className={`px-2 py-0.5 rounded text-[11px] font-medium ${DIR_CFG[s.direction]}`}>{s.label} · {s.direction}</span>
                  ))}
                </div>
              </div>
              <div className="flex-1 flex flex-col p-5 gap-4">
                <div className="flex-1">
                  <label className="block text-[10px] font-semibold text-[#64748B] uppercase tracking-wider mb-2">계획 내용</label>
                  <textarea value={planText} onChange={e => { setPlanText(e.target.value); setSaved(false); }}
                    className="w-full h-full min-h-[180px] px-3 py-3 rounded-[6px] border border-[#E2E8F0] text-sm text-[#172033] leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                  />
                </div>
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-[#F8FAFC] rounded-[6px] border border-[#E2E8F0] p-3"><p className="text-[#64748B] mb-1">담당 상담사</p><p className="font-semibold text-[#172033]">이서연</p></div>
                    <div className="bg-[#F8FAFC] rounded-[6px] border border-[#E2E8F0] p-3"><p className="text-[#64748B] mb-1">계획 수립일</p><p className="font-mono font-semibold text-[#172033]">2026-08-21</p></div>
                  </div>
                  {saved && (
                    <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-[6px] px-3 py-2">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      사례관리 계획이 저장되었습니다
                    </div>
                  )}
                  <button onClick={() => setSaved(true)} className="w-full py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-[6px] transition-colors">
                    계획 확정 및 저장
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
