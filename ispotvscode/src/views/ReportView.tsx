import { useEffect, useState } from "react";
import { useParams } from "react-router";
import Breadcrumb from "../components/ui/Breadcrumb";
import { cases as casesApi } from "../api/endpoints";
import { describeApiError, toUiCaseDetail, type CaseWithId } from "../api/adapters";

// 보고서 생성은 아직 Backend 에 없다. 예전에는 주소의 사례와 상관없이 가짜 사례(data/cases)의 보고서를
// 만들어 보여 줬다(다른 아동의 문서, 학대 여부를 단정하는 문구). 연결 전까지는 사례 정보만
// 실제 값으로 보여 주고, 유형 · 항목은 고를 수 있지만 문서는 만들지 않는다(사례 관리의 계획 · 종결 탭과 같은 방식).

type ReportType = "사례회의" | "외부전달" | "종결검토" | "요약본";

interface ContentItem { id: string; label: string; desc: string; }

const CONTENT_ITEMS: Record<ReportType, ContentItem[]> = {
  요약본: [
    { id: "summary-risk",    label: "위험도 요약",              desc: "현재 위험 등급 및 핵심 근거" },
    { id: "summary-speech",  label: "주요 발화 요약",           desc: "가장 위험도 높은 발화 3~5건" },
    { id: "summary-session", label: "최근 상담 요약",           desc: "최근 2회차 핵심 내용" },
    { id: "summary-action",  label: "필요 조치 요약",           desc: "즉각 개입이 필요한 사항" },
  ],
  사례회의: [
    { id: "ai-risk",       label: "회차별 근거 신호 변화",    desc: "회차별 위험 점수 변화 시각화" },
    { id: "session-sum",   label: "회차별 상담 요약",         desc: "각 회차 핵심 내용 및 아동 상태" },
    { id: "risk-speech",   label: "주요 위험 발화 근거",      desc: "위험 판단에 영향을 준 발화 원문" },
    { id: "abuse-type",    label: "학대유형별 분석 결과",     desc: "신체·정서·성·방임 유형 가능성" },
    { id: "keywords",      label: "핵심 키워드 목록",         desc: "위험 신호 키워드 및 빈도" },
    { id: "intervention",  label: "상담사 지정 개입 계획",       desc: "AI 추천 사례관리 방향" },
  ],
  외부전달: [
    { id: "case-basic",    label: "사례 기본 정보",           desc: "아동 인적사항 및 의뢰 경로" },
    { id: "abuse-type",    label: "학대유형 및 정황",         desc: "관련 신호가 있는 학대유형과 근거 발화(상담사 검토 필요)" },
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

export default function ReportView() {
  const { caseId } = useParams<{ caseId: string }>();
  const [selectedCase, setSelectedCase] = useState<CaseWithId | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [reportType, setReportType] = useState<ReportType>("사례회의");
  const [selectedItems, setSelectedItems] = useState<Record<ReportType, Set<string>>>({
    요약본:  new Set(CONTENT_ITEMS["요약본"].map(i => i.id)),
    사례회의: new Set(CONTENT_ITEMS["사례회의"].map(i => i.id)),
    외부전달: new Set(CONTENT_ITEMS["외부전달"].map(i => i.id)),
    종결검토: new Set(CONTENT_ITEMS["종결검토"].map(i => i.id)),
  });
  const [draftMode, setDraftMode] = useState(false);

  useEffect(() => {
    if (!caseId) return;

    let cancelled = false;

    setSelectedCase(null);
    setLoadError(null);

    casesApi
      .get(caseId)
      .then((detail) => {
        if (!cancelled) setSelectedCase(toUiCaseDetail(detail));
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "사례를 불러오지 못했습니다."));
      });

    return () => {
      cancelled = true;
    };
  }, [caseId]);

  function toggleItem(id: string) {
    setSelectedItems(prev => {
      const next = new Set(prev[reportType]);
      if (next.has(id)) next.delete(id); else next.add(id);
      return { ...prev, [reportType]: next };
    });
  }

  const items = CONTENT_ITEMS[reportType];
  const selected = selectedItems[reportType];
  const childName = selectedCase?.childName ?? "—";

  const TYPE_CFG: Record<ReportType, { color: string; bg: string; border: string; active: string }> = {
    요약본:   { color: "text-violet-700", bg: "bg-violet-50", border: "border-violet-200", active: "border-violet-600 bg-violet-50 text-violet-700" },
    사례회의: { color: "text-blue-700",  bg: "bg-blue-50",  border: "border-blue-200",  active: "border-blue-600 bg-blue-50 text-blue-700" },
    외부전달: { color: "text-red-700",   bg: "bg-red-50",   border: "border-red-200",   active: "border-red-600 bg-red-50 text-red-700" },
    종결검토: { color: "text-green-700", bg: "bg-green-50", border: "border-green-200", active: "border-green-600 bg-green-50 text-green-700" },
  };

  const TYPE_LABELS: Record<ReportType, string> = {
    요약본:   "AI 분석 요약본",
    사례회의: "내부 사례회의 보고서",
    외부전달: "지자체·경찰 전달용 정황 요약서",
    종결검토: "종결 검토서",
  };

  const TYPE_DESCS: Record<ReportType, string> = {
    요약본:   "AI가 생성하는 핵심 위험 신호 요약 문서",
    사례회의: "기관 내 사례회의 제출용 종합 보고서",
    외부전달: "수사기관·지자체 연계를 위한 공식 요약서",
    종결검토: "사례 종결 또는 가정복귀 전 최종 검토서",
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <Breadcrumb items={[{ label: "보고서 생성", to: "/report-cases" }, { label: childName }]} />
        <div>
          <h1 className="text-[22px] font-semibold text-[#172033]">보고서 생성</h1>
          <p className="text-[#64748B] text-[13px] mt-0.5">
            <span className="font-semibold text-[#172033]">{childName}</span>
            <span className="mx-1.5 text-[#94A3B8]">·</span>
            <span className="font-mono text-xs">{selectedCase?.id ?? "—"}</span>
            <span className="mx-1.5 text-[#94A3B8]">·</span>
            보고서 유형과 포함 항목을 선택하세요
          </p>
        </div>

        {loadError && (
          <div className="bg-white border border-red-200 rounded-[8px] px-4 py-3 text-[13px] text-red-600">{loadError}</div>
        )}

        <div className="bg-white border border-[#CBD5E1] rounded-[8px] px-4 py-3 text-[13px] text-[#475569]">
          보고서 생성은 아직 서버에 없습니다. 유형과 포함 항목은 고를 수 있지만 문서는 만들어지지 않고 저장 · 내려받기도 되지 않습니다.
        </div>

          <div className="grid grid-cols-5 gap-5">
            {/* Settings */}
            <div className="col-span-2 space-y-5">
              {/* Report type */}
              <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
                <h2 className="font-semibold text-[#172033] text-sm mb-3">보고서 유형</h2>
                <div className="space-y-2.5">
                  {(["요약본", "사례회의", "외부전달", "종결검토"] as ReportType[]).map(type => {
                    const cfg = TYPE_CFG[type];
                    return (
                      <button key={type} onClick={() => setReportType(type)}
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
                    ["사례번호", selectedCase?.id ?? "—"],
                    ["대상 아동", selectedCase ? `${selectedCase.childName} (${selectedCase.age}세)` : "—"],
                    ["담당 상담사", selectedCase?.counselor ?? "—"],
                    ["생성일", "—"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span>{k}</span>
                      <span className="font-semibold text-[#172033] font-mono">{v}</span>
                    </div>
                  ))}
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <div
                    onClick={() => setDraftMode(d => !d)}
                    className="relative w-8 h-4.5 rounded-full transition-colors shrink-0"
                    style={{ background: draftMode ? "#2563EB" : "#CBD5E1", width: "32px", height: "18px" }}
                  >
                    <div className="absolute top-0.5 transition-all rounded-full bg-white" style={{ width: "14px", height: "14px", left: draftMode ? "15px" : "2px" }} />
                  </div>
                  <span className="text-[12px] text-[#64748B]">초안 모드 (생성 후 직접 편집)</span>
                </label>
                <button disabled title="보고서 생성은 아직 서버에 없습니다"
                  className="w-full py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-[6px] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {draftMode ? "초안 생성" : "보고서 생성"}
                </button>
              </div>
            </div>

            {/* Preview */}
            <div className="col-span-3 rounded-[8px] border border-[#E2E8F0] overflow-hidden flex flex-col bg-[#F6F8FB]" style={{ maxHeight: "75vh" }}>
              <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <h2 className="font-semibold text-[#172033] text-sm">미리보기</h2>
                </div>
                <span className="text-xs text-[#94A3B8]">{TYPE_LABELS[reportType]}</span>
              </div>
              <div className="flex-1 overflow-y-auto p-6">
                <div className="flex flex-col items-center justify-center h-full text-[#94A3B8] space-y-3">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                  <p className="text-sm text-center">보고서 생성은 아직 서버에 없어<br/>미리보기를 만들 수 없습니다</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
  );
}
