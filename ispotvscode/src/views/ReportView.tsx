import { useState } from "react";
import CaseSelectorPanel from "../components/CaseSelectorPanel";
import { CASES } from "../data/cases";

type ReportType = "사례회의" | "외부전달" | "종결검토";

interface ContentItem { id: string; label: string; desc: string; }

const CONTENT_ITEMS: Record<ReportType, ContentItem[]> = {
  사례회의: [
    { id: "ai-risk",       label: "AI 위험도 추이 그래프",    desc: "회차별 위험 점수 변화 시각화" },
    { id: "session-sum",   label: "회차별 상담 요약",         desc: "각 회차 핵심 내용 및 아동 상태" },
    { id: "risk-speech",   label: "주요 위험 발화 근거",      desc: "위험 판단에 영향을 준 발화 원문" },
    { id: "abuse-type",    label: "학대유형별 분석 결과",     desc: "신체·정서·성·방임 유형 가능성" },
    { id: "keywords",      label: "핵심 키워드 목록",         desc: "위험 신호 키워드 및 빈도" },
    { id: "intervention",  label: "개입 영역 우선순위",       desc: "AI 추천 사례관리 방향" },
  ],
  외부전달: [
    { id: "case-basic",    label: "사례 기본 정보",           desc: "아동 인적사항 및 의뢰 경로" },
    { id: "abuse-type",    label: "학대유형 및 정황",         desc: "확인된 학대 유형 및 주요 근거" },
    { id: "risk-summary",  label: "위험도 종합 평가",         desc: "최종 위험 등급 및 판단 근거" },
    { id: "risk-speech",   label: "주요 위험 발화 발췌",      desc: "경찰·지자체 전달용 발화 원문" },
    { id: "history",       label: "상담 이력 요약",           desc: "전체 상담 회차 요약" },
    { id: "urgent",        label: "즉각 조치 필요 사항",      desc: "격리, 의료 연계 등 긴급 조치" },
  ],
  종결검토: [
    { id: "goal-achieve",  label: "초기 목표 달성 수준",      desc: "목표별 달성 여부 및 수준" },
    { id: "remaining",     label: "잔존 위험요인 목록",       desc: "해소되지 않은 위험요인" },
    { id: "repeat",        label: "반복 위험요인 분석",       desc: "회차별 반복 확인된 위험요인" },
    { id: "past-match",    label: "과거 중대사건 비교",       desc: "중대사건 위험패턴 일치 결과" },
    { id: "total-risk",    label: "위험도 전체 추이",         desc: "초기~현재 위험도 변화" },
    { id: "checklist",     label: "종결 전 확인 체크리스트", desc: "최종 점검 항목 완료 현황" },
  ],
};

function buildPreview(caseItem: typeof CASES[0], type: ReportType): string {
  const typeLabel = type === "사례회의" ? "내부 사례회의 보고서"
    : type === "외부전달" ? "지자체·경찰 전달용 정황 요약서"
    : "사례 종결 검토서";

  return `■ ${typeLabel}

사례번호: ${caseItem.id}
아  동 명: ${caseItem.childName} (${caseItem.age}세)
작 성 일: 2026년 8월 21일
담 당 자: ${caseItem.counselor} 상담사
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

${type === "사례회의" ? `[학대유형별 분석 결과]
${caseItem.abuseTypes.map(t => `• ${t}학대: 확인됨`).join("\n")}

[AI 위험도]
종합 위험도: ${caseItem.riskScore}점 (${caseItem.riskLevel === "high" ? "고위험" : caseItem.riskLevel === "mid" ? "중위험" : "저위험"})

[주요 위험 키워드]
${caseItem.keywords.map(k => `• ${k}`).join("\n")}

[개입 우선순위 (AI 추천)]
① 아동 심리·정서 지원
② 안전 및 보호 조치
③ 보호자 상담 및 교육`

: type === "외부전달" ? `[학대 정황 요약]
대상 아동: ${caseItem.childName} (${caseItem.age}세)
학대 유형: ${caseItem.abuseTypes.join(", ")}
보호자: ${caseItem.guardian}

[위험도 평가]
종합 위험도: ${caseItem.riskScore}점
등급: ${caseItem.riskLevel === "high" ? "고위험 - 즉각 개입 권고" : caseItem.riskLevel === "mid" ? "중위험 - 지속 모니터링 필요" : "저위험"}

[즉각 조치 필요 사항]
• 현장 출동 및 아동 안전 확인
• 의료기관 연계 (신체 검사)
• 격리 여부 검토`

: `[초기 목표 달성 수준]
• 심리·정서 안정화: 부분 달성
• 가정 내 안전 확보: 부분 달성

[잔존 위험요인]
${caseItem.keywords.slice(0, 2).map(k => `• ${k} (지속 관찰 필요)`).join("\n")}

[과거 중대사건 비교]
위험요인 일치 여부 검토 완료

[최종 권고사항]
담당 상담사 및 사례회의 최종 결정 필요`}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
본 문서는 AI 분석 결과를 기반으로 자동 생성되었습니다.
최종 내용은 담당 상담사의 검토·승인 후 효력이 발생합니다.`;
}

export default function ReportView() {
  const [selectedId, setSelectedId] = useState(CASES[0].id);
  const [reportType, setReportType] = useState<ReportType>("사례회의");
  const [selectedItems, setSelectedItems] = useState<Record<ReportType, Set<string>>>({
    사례회의: new Set(CONTENT_ITEMS["사례회의"].map(i => i.id)),
    외부전달: new Set(CONTENT_ITEMS["외부전달"].map(i => i.id)),
    종결검토: new Set(CONTENT_ITEMS["종결검토"].map(i => i.id)),
  });
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);

  const selectedCase = CASES.find(c => c.id === selectedId)!;

  function handleSelectCase(id: string) { setSelectedId(id); setGenerated(false); }

  function toggleItem(id: string) {
    setSelectedItems(prev => {
      const next = new Set(prev[reportType]);
      if (next.has(id)) next.delete(id); else next.add(id);
      return { ...prev, [reportType]: next };
    });
    setGenerated(false);
  }

  function handleGenerate() {
    setGenerating(true);
    setTimeout(() => { setGenerating(false); setGenerated(true); }, 1200);
  }

  const items = CONTENT_ITEMS[reportType];
  const selected = selectedItems[reportType];

  const TYPE_CFG: Record<ReportType, { color: string; bg: string; border: string; active: string }> = {
    사례회의: { color: "text-blue-700",  bg: "bg-blue-50",  border: "border-blue-200",  active: "border-blue-600 bg-blue-50 text-blue-700" },
    외부전달: { color: "text-red-700",   bg: "bg-red-50",   border: "border-red-200",   active: "border-red-600 bg-red-50 text-red-700" },
    종결검토: { color: "text-green-700", bg: "bg-green-50", border: "border-green-200", active: "border-green-600 bg-green-50 text-green-700" },
  };

  const TYPE_LABELS: Record<ReportType, string> = {
    사례회의: "내부 사례회의 보고서",
    외부전달: "지자체·경찰 전달용 정황 요약서",
    종결검토: "종결 검토서",
  };

  const TYPE_DESCS: Record<ReportType, string> = {
    사례회의: "기관 내 사례회의 제출용 종합 보고서",
    외부전달: "수사기관·지자체 연계를 위한 공식 요약서",
    종결검토: "사례 종결 또는 가정복귀 전 최종 검토서",
  };

  return (
    <div className="flex h-full overflow-hidden">
      <CaseSelectorPanel selectedId={selectedId} onSelect={handleSelectCase} />

      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-5">
          <div>
            <h1 className="text-xl font-bold text-[#172033]">보고서 생성</h1>
            <p className="text-[#64748B] text-sm mt-0.5">
              <span className="font-semibold text-[#172033]">{selectedCase.childName}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              <span className="font-mono text-xs">{selectedCase.id}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              보고서 유형과 포함 항목을 선택하세요
            </p>
          </div>

          <div className="grid grid-cols-5 gap-5">
            {/* Settings */}
            <div className="col-span-2 space-y-5">
              {/* Report type */}
              <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
                <h2 className="font-semibold text-[#172033] text-sm mb-3">보고서 유형</h2>
                <div className="space-y-2.5">
                  {(["사례회의", "외부전달", "종결검토"] as ReportType[]).map(type => {
                    const cfg = TYPE_CFG[type];
                    return (
                      <button key={type} onClick={() => { setReportType(type); setGenerated(false); }}
                        className={`w-full text-left p-3.5 rounded-[6px] border transition-all ${reportType === type ? cfg.active : "border-[#E2E8F0] hover:border-[#CBD5E1] text-[#64748B]"}`}
                      >
                        <div className="font-semibold text-sm mb-0.5">{TYPE_LABELS[type]}</div>
                        <div className="text-xs opacity-70">{TYPE_DESCS[type]}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Items */}
              <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-semibold text-[#172033] text-sm">포함 항목</h2>
                  <span className="text-xs text-[#94A3B8]">{selected.size}/{items.length}</span>
                </div>
                <div className="space-y-2">
                  {items.map(item => (
                    <label key={item.id} className="flex items-start gap-2.5 cursor-pointer group p-2 rounded-[6px] hover:bg-[#F8FAFC] transition-colors">
                      <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleItem(item.id)} className="mt-0.5 shrink-0 accent-blue-600" />
                      <div>
                        <p className="text-sm font-medium text-[#172033]">{item.label}</p>
                        <p className="text-[11px] text-[#94A3B8]">{item.desc}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Generate */}
              <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5 space-y-3">
                <div className="text-xs text-[#64748B] space-y-1.5">
                  {[
                    ["사례번호", selectedCase.id],
                    ["대상 아동", `${selectedCase.childName} (${selectedCase.age}세)`],
                    ["담당 상담사", selectedCase.counselor],
                    ["생성일", "2026-08-21"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span>{k}</span>
                      <span className="font-semibold text-[#172033] font-mono">{v}</span>
                    </div>
                  ))}
                </div>
                <button onClick={handleGenerate} disabled={generating || selected.size === 0}
                  className="w-full py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-[6px] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {generating
                    ? <span className="flex items-center justify-center gap-2"><svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>보고서 생성 중...</span>
                    : "보고서 생성"}
                </button>
                {generated && (
                  <div className="grid grid-cols-2 gap-2">
                    {["PDF 다운로드", "HWP 다운로드"].map(label => (
                      <button key={label} className="flex items-center justify-center gap-1.5 py-2.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Preview */}
            <div className="col-span-3 rounded-[8px] border border-[#E2E8F0] overflow-hidden flex flex-col bg-[#F6F8FB]" style={{ maxHeight: "75vh" }}>
              <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <h2 className="font-semibold text-[#172033] text-sm">미리보기</h2>
                  {generated && (
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${TYPE_CFG[reportType].bg} ${TYPE_CFG[reportType].border} ${TYPE_CFG[reportType].color}`}>
                      생성 완료
                    </span>
                  )}
                </div>
                <span className="text-xs text-[#94A3B8]">{TYPE_LABELS[reportType]}</span>
              </div>
              <div className="flex-1 overflow-y-auto p-6">
                {!generated ? (
                  <div className="flex flex-col items-center justify-center h-full text-[#94A3B8] space-y-3">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                    <p className="text-sm text-center">항목을 선택하고<br/>보고서 생성 버튼을 클릭하세요</p>
                  </div>
                ) : (
                  <div className="bg-white border border-[#E2E8F0] rounded-[8px] shadow-sm mx-auto" style={{ maxWidth: "680px" }}>
                    <div className="px-10 py-8 border-b border-[#E2E8F0]">
                      <p className="text-[10px] text-[#94A3B8] uppercase tracking-widest mb-2">○○아동보호전문기관</p>
                      <h3 className="text-lg font-bold text-[#172033]">{TYPE_LABELS[reportType]}</h3>
                      <div className="flex items-center gap-4 mt-2 text-xs text-[#64748B]">
                        <span>생성일: 2026년 8월 21일</span>
                        <span className="text-[#E2E8F0]">|</span>
                        <span>담당: {selectedCase.counselor} 상담사</span>
                        <span className="text-[#E2E8F0]">|</span>
                        <span className="font-mono">{selectedCase.id}</span>
                      </div>
                    </div>
                    <pre className="font-mono text-xs text-[#172033] leading-relaxed whitespace-pre-wrap px-10 py-8">
                      {buildPreview(selectedCase, reportType)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
