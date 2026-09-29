import { useState, useMemo, Fragment } from "react";
import { useNavigate } from "react-router";
import { CASES, type CaseRecord } from "../data/cases";
import { SESSIONS, AI_ANALYSES } from "../data/mockData";
import { RiskBadge, AbuseBadge } from "../components/ui/Badges";
import { useToast } from "../components/ui/Toast";

// ─── Types ───────────────────────────────────────────────────────────────────

type Tab = "ai-review" | "plan" | "closure" | "history";

// ─── Compact Case Selector ────────────────────────────────────────────────────

function CaseSelector({ selected, onSelect }: { selected: CaseRecord | null; onSelect: (c: CaseRecord) => void }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() =>
    CASES.filter(c => !query || c.childName.includes(query) || c.id.toLowerCase().includes(query.toLowerCase()))
      .sort((a, b) => (a.riskLevel === "high" ? 0 : a.riskLevel === "mid" ? 1 : 2) - (b.riskLevel === "high" ? 0 : b.riskLevel === "mid" ? 1 : 2)),
    [query]
  );

  return (
    <div className="bg-white border-b border-[#E2E8F0]">
      <div className="px-6 py-3 flex items-center justify-between border-b border-[#F1F5F9]">
        <span className="text-[13px] font-semibold text-[#172033]">사례 선택</span>
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="아동명·사례ID"
            className="pl-7 pr-3 py-1 rounded-[6px] border border-[#E2E8F0] text-[12px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-[#F8FAFC] w-40 transition-all"
          />
        </div>
      </div>
      <div className="overflow-y-auto" style={{ maxHeight: "200px" }}>
        <table className="w-full">
          <thead className="bg-[#F8FAFC] sticky top-0">
            <tr>
              {["아동명", "사례 ID", "위험도", "상태", "최근 상담", ""].map(h => (
                <th key={h} className="px-4 py-2 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(c => (
              <tr
                key={c.id}
                onClick={() => onSelect(c)}
                className="border-b border-[#F1F5F9] cursor-pointer transition-colors"
                style={{ background: selected?.id === c.id ? "#EFF6FF" : undefined }}
                onMouseEnter={e => { if (selected?.id !== c.id) (e.currentTarget as HTMLElement).style.background = "#F8FAFC"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = selected?.id === c.id ? "#EFF6FF" : ""; }}
              >
                <td className="px-4 py-2 text-[13px] font-semibold text-[#172033]">
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: c.riskLevel === "high" ? "#DC2626" : c.riskLevel === "mid" ? "#D97706" : "#16A34A" }} />
                    {c.childName}
                  </div>
                </td>
                <td className="px-4 py-2 text-[11px] font-mono text-[#94A3B8]">{c.id}</td>
                <td className="px-4 py-2">
                  <span className={`px-1.5 py-0.5 rounded border text-[11px] font-semibold ${c.riskLevel === "high" ? "text-[#B91C1C] bg-[#FEF2F2] border-[#FECACA]" : c.riskLevel === "mid" ? "text-[#B45309] bg-[#FFFBEB] border-[#FDE68A]" : "text-[#15803D] bg-[#F0FDF4] border-[#BBF7D0]"}`}>
                    {c.riskLevel === "high" ? "확인 필요" : c.riskLevel === "mid" ? "확인 중" : "확인 완료"}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <span className={`px-1.5 py-0.5 rounded border text-[11px] font-medium ${c.status === "active" ? "text-[#1D4ED8] bg-[#EFF6FF] border-[#BFDBFE]" : c.status === "review" ? "text-[#B45309] bg-[#FFFBEB] border-[#FDE68A]" : "text-[#64748B] bg-[#F8FAFC] border-[#E2E8F0]"}`}>
                    {c.status === "active" ? "진행중" : c.status === "review" ? "검토필요" : "대기중"}
                  </span>
                </td>
                <td className="px-4 py-2 text-[12px] font-mono text-[#64748B]">{c.lastSession}</td>
                <td className="px-4 py-2">
                  <span className={`text-[12px] font-medium ${selected?.id === c.id ? "text-[#2563EB]" : "text-[#94A3B8]"}`}>
                    {selected?.id === c.id ? "선택됨" : "선택"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Sub-nav Tabs ─────────────────────────────────────────────────────────────

function SubNav({ active, onChange, caseObj }: { active: Tab; onChange: (t: Tab) => void; caseObj: CaseRecord }) {
  const analyses = AI_ANALYSES.filter(a => a.caseId === caseObj.id);
  const hasPending = analyses.some(a => a.status === "검토필요");

  const tabs: { id: Tab; label: string; badge?: number }[] = [
    { id: "ai-review", label: "분석 결과 검토", badge: hasPending ? analyses.filter(a => a.status === "검토필요").length : undefined },
    { id: "plan",      label: "사례관리 계획" },
    { id: "closure",   label: "종결·가정복귀 검토" },
    { id: "history",   label: "이전 상담" },
  ];

  return (
    <div className="bg-white border-b border-[#E2E8F0] px-6 flex items-center gap-0">
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className="relative flex items-center gap-1.5 px-4 py-3 text-[13px] font-medium transition-colors border-b-2"
          style={{
            borderBottomColor: active === t.id ? "#2563EB" : "transparent",
            color: active === t.id ? "#2563EB" : "#64748B",
          }}
        >
          {t.label}
          {t.badge != null && t.badge > 0 && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-sm bg-amber-500 text-white min-w-[18px] text-center">
              {t.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

// ─── AI Review Tab ────────────────────────────────────────────────────────────

const INDICATOR_DETAILS: Record<string, {
  sessionSummary: string;
  evidences: { text: string; keyPhrase: string; speaker: string; timestamp: string }[];
  ragSources: { title: string; content: string; connection: string }[];
}> = {
  "신체적 학대 발화": {
    sessionSummary: "8회차 상담에서 아동이 신체적 불편함을 반복적으로 언급하였음. 보호자로부터의 신체적 접촉에 대한 두려움이 표현되었으며, 등과 팔 부위의 통증을 호소함. 상담 내내 위축된 자세와 회피적 시선이 관찰됨.",
    evidences: [
      { text: "보호자가 화가 나면 아이를 밀치거나 때리는 경우가 있다고 진술함.", keyPhrase: "밀치거나 때리는 경우", speaker: "아동", timestamp: "00:41" },
      { text: "소리 지르고 많이 때렸어요. 등이랑 팔이요.", keyPhrase: "때렸어요", speaker: "아동", timestamp: "01:08" },
    ],
    ragSources: [
      { title: "아동학대 신체학대 판단 기준 (보건복지부 2023)", content: "신체학대는 보호자가 아동에게 신체적 손상을 입히거나 신체적 손상을 입힐 위험이 있는 폭력 행위를 포함함.", connection: "아동 발화의 '때리다', '밀치다' 표현이 신체적 손상 유발 행위와 일치" },
    ],
  },
  "두려움·회피 반응": {
    sessionSummary: "아동이 보호자에 대한 두려움을 직접적으로 표현하지 않으면서도, 간접적 회피 표현과 함께 위축 행동을 보임. 상담 중 주제 전환 시도와 눈맞춤 회피가 반복적으로 관찰됨.",
    evidences: [
      { text: "말하면 더 혼난다고 했어요. 그래서 말 안 하려고요.", keyPhrase: "말하면 더 혼난다", speaker: "아동", timestamp: "01:08" },
      { text: "집에 가기 싫어요. 거기 있으면 무서워요.", keyPhrase: "무서워요", speaker: "아동", timestamp: "02:30" },
    ],
    ragSources: [
      { title: "외상 후 스트레스 반응 체크리스트 (아동심리연구원)", content: "학대 피해 아동에서 나타나는 회피 반응: 관련 자극 회피, 정보 은폐 시도, 위축 행동", connection: "아동의 '말 안 하려고'라는 표현이 정보 은폐 시도 패턴과 일치" },
    ],
  },
  "방임 가능성 발화": {
    sessionSummary: "아동이 기본적 생활 필요의 미충족 상황을 구체적으로 언급함. 식사 제공 여부, 위생 관리, 수면 환경에 대한 진술이 방임 가능성을 시사함.",
    evidences: [
      { text: "밥도 안 줄 때가 있어요. 라면 끓여 먹어요.", keyPhrase: "밥도 안 줄 때가", speaker: "아동", timestamp: "02:15" },
    ],
    ragSources: [
      { title: "방임 판단 매뉴얼 (아동권리보장원 2022)", content: "정서적·신체적 방임: 기본 생활 필요(식사, 의복, 위생) 미충족, 적절한 보호 결여", connection: "식사 미제공 진술이 신체적 방임 판단 지표와 직접 부합" },
    ],
  },
};

function AiReviewTab({ caseObj, onNavigate }: { caseObj: CaseRecord; onNavigate: (t: Tab) => void }) {
  const analyses = AI_ANALYSES.filter(a => a.caseId === caseObj.id).sort((a, b) => b.sessionNumber - a.sessionNumber);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [showEvidence, setShowEvidence] = useState<string | null>(null);
  const [selectedIndicator, setSelectedIndicator] = useState<string | null>(null);
  const analysis = analyses[selectedIdx];

  if (!analysis) {
    return (
      <div className="flex-1 flex items-center justify-center text-[14px] text-[#94A3B8]">
        이 사례에 대한 AI 분석 결과가 없습니다.
      </div>
    );
  }

  const statusLabel: Record<string, string> = {
    검토필요: "검토 필요",
    검토중: "검토 중",
    수정됨: "수정됨",
    상담사검토완료: "상담사 검토 완료",
    분석중: "분석 중",
  };

  const signalItems = [
    { signal: "신체적 학대 관련 신호", evidence: "소리 지르고 많이 때렸어요", timestamp: "00:41", speaker: "아동", keyword: "신체" },
    { signal: "두려움·회피 반응 신호", evidence: "등이랑 팔이요. 말하면 더 혼난다고 했어요", timestamp: "01:08", speaker: "아동", keyword: "두려움" },
    { signal: "방임 가능성 신호", evidence: "밥도 안 줄 때가 있어요", timestamp: "02:15", speaker: "아동", keyword: "방임" },
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      {/* Analysis selector + meta */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-[18px] font-semibold text-[#172033]">{caseObj.childName} · 분석 결과 검토</h2>
          <span className="text-[12px] font-semibold px-2 py-1 rounded-[4px] border border-[#CBD5E1] text-[#475569] bg-white">
            {statusLabel[analysis.status] ?? analysis.status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[#94A3B8]">회차:</span>
          {analyses.map((a, i) => (
            <button key={a.id} onClick={() => setSelectedIdx(i)}
              className="px-2.5 py-1 text-[12px] font-medium rounded-[6px] border transition-all"
              style={{
                borderColor: selectedIdx === i ? "#2563EB" : "#E2E8F0",
                background: selectedIdx === i ? "#EFF6FF" : "white",
                color: selectedIdx === i ? "#2563EB" : "#64748B",
              }}>
              {a.sessionNumber}회차
            </button>
          ))}
        </div>
      </div>

      {/* Summary strip */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-4 flex gap-6">
        <div className="flex-1">
          <p className="text-[12px] font-semibold text-[#64748B] mb-1">AI 분석 참고정보</p>
          <p className="text-[14px] text-[#172033]">{analysis.summary}</p>
        </div>
        <div className="flex gap-5 shrink-0 border-l border-[#F1F5F9] pl-5">
          <div className="text-center">
            <div className="text-[22px] font-bold text-[#172033]">{signalItems.length}</div>
            <div className="text-[12px] text-[#94A3B8]">감지 신호</div>
          </div>
          <div className="text-center">
            <div className="text-[22px] font-bold text-[#172033]">{analysis.sessionNumber}</div>
            <div className="text-[12px] text-[#94A3B8]">회차</div>
          </div>
          <div className="text-center">
            <div className="text-[22px] font-bold text-[#172033]">{analysis.date.slice(5)}</div>
            <div className="text-[12px] text-[#94A3B8]">분석일</div>
          </div>
        </div>
      </div>

      {/* 추가 확인 필요 발화 */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span className="text-[14px] font-semibold text-[#172033]">추가 확인 필요 발화</span>
          <span className="text-[12px] text-[#64748B]">AI가 주의 표시한 발화입니다. 상담사의 최종 판단이 필요합니다.</span>
        </div>
        <div className="divide-y divide-[#F1F5F9]">
          {signalItems.map((item, i) => (
            <div key={i} className="px-5 py-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[11px] font-mono text-[#94A3B8] bg-[#F1F5F9] px-1.5 py-0.5 rounded">{item.timestamp}</span>
                    <span className="text-[12px] text-[#64748B]">{item.speaker}</span>
                    <span className="text-[12px] text-[#475569] border border-[#CBD5E1] px-1.5 py-0.5 rounded bg-white font-medium">#{item.keyword}</span>
                  </div>
                  <p className="text-[14px] text-[#172033] font-medium">"{item.evidence}"</p>
                  <p className="text-[12px] text-[#64748B] mt-1">관련 신호: {item.signal}</p>
                </div>
                <button
                  onClick={() => setShowEvidence(showEvidence === `${i}` ? null : `${i}`)}
                  className="shrink-0 px-2.5 py-1.5 text-[12px] font-medium rounded-[6px] border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC] transition-colors"
                >
                  원문 위치 보기
                </button>
              </div>
              {showEvidence === `${i}` && (
                <div className="mt-3 border-t border-[#F1F5F9] pt-3">
                  <p className="text-[12px] font-semibold text-[#94A3B8] mb-2">STT 원문 컨텍스트</p>
                  <div className="bg-[#F8FAFC] rounded-[6px] px-4 py-3 font-mono text-[13px] text-[#64748B]">
                    <span className="text-[#94A3B8]">{item.timestamp.replace(":", "분 ")}초</span>{" "}
                    <span className="text-[#172033] font-bold underline underline-offset-2">{item.evidence}</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Risk indicators - clickable */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
          <p className="text-[14px] font-semibold text-[#172033]">위험 관련 신호·근거 발화</p>
          <span className="text-[12px] text-[#94A3B8]">항목을 클릭하면 근거를 확인할 수 있습니다</span>
        </div>
        <div className="divide-y divide-[#F1F5F9]">
          {analysis.riskIndicators.map((ind, i) => {
            const key = Object.keys(INDICATOR_DETAILS)[i % Object.keys(INDICATOR_DETAILS).length];
            const detail = INDICATOR_DETAILS[key];
            const isOpen = selectedIndicator === `${i}`;
            return (
              <div key={i}>
                <button
                  onClick={() => setSelectedIndicator(isOpen ? null : `${i}`)}
                  className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-[#F8FAFC] transition-colors"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#475569] shrink-0" />
                  <span className="text-[14px] text-[#172033] flex-1 font-medium">{ind}</span>
                  <span className="text-[12px] text-[#94A3B8]">참고 신호</span>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 transition-transform" style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0)" }}><polyline points="6 9 12 15 18 9"/></svg>
                </button>
                {isOpen && detail && (
                  <div className="border-t border-[#F1F5F9] bg-[#FAFAFA] px-5 py-5 space-y-5">
                    {/* 전체 상담 요약본 */}
                    <div>
                      <p className="text-[12px] font-semibold text-[#64748B] mb-2">전체 상담 요약본</p>
                      <p className="text-[14px] text-[#172033] leading-relaxed">{detail.sessionSummary}</p>
                    </div>

                    {/* 학대 근거 요인 */}
                    <div>
                      <p className="text-[12px] font-semibold text-[#64748B] mb-2">학대 근거 요인</p>
                      <div className="space-y-3">
                        {detail.evidences.map((ev, ei) => (
                          <div key={ei} className="border border-[#E2E8F0] rounded-[6px] bg-white p-4">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-[11px] font-mono text-[#94A3B8] bg-[#F1F5F9] px-1.5 py-0.5 rounded">{ev.timestamp}</span>
                              <span className="text-[12px] text-[#64748B]">{ev.speaker}</span>
                            </div>
                            <p className="text-[14px] text-[#172033] leading-relaxed mb-2">
                              {ev.text.split(ev.keyPhrase).map((part, pi, arr) => (
                                <Fragment key={pi}>
                                  {part}
                                  {pi < arr.length - 1 && (
                                    <span className="font-bold underline underline-offset-2">{ev.keyPhrase}</span>
                                  )}
                                </Fragment>
                              ))}
                            </p>
                            <div className="flex items-start gap-2 pt-2 border-t border-[#F1F5F9]">
                              <span className="text-[11px] text-[#94A3B8] shrink-0 mt-0.5">근거 요소</span>
                              <span className="text-[12px] font-semibold text-[#172033]">"{ev.keyPhrase}"</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* RAG 근거 자료 */}
                    {detail.ragSources.length > 0 && (
                      <div>
                        <p className="text-[12px] font-semibold text-[#64748B] mb-2">관련 근거 자료</p>
                        <div className="space-y-2">
                          {detail.ragSources.map((rag, ri) => (
                            <div key={ri} className="border border-[#E2E8F0] rounded-[6px] bg-white p-4">
                              <p className="text-[13px] font-semibold text-[#172033] mb-1">{rag.title}</p>
                              <p className="text-[13px] text-[#475569] mb-2">{rag.content}</p>
                              <div className="flex items-start gap-2 pt-2 border-t border-[#F1F5F9]">
                                <span className="text-[11px] text-[#94A3B8] shrink-0 mt-0.5">연결 근거</span>
                                <p className="text-[12px] text-[#475569]">{rag.connection}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Navigation to plan */}
      <div className="flex justify-end">
        <button
          onClick={() => onNavigate("plan")}
          className="flex items-center gap-2 px-4 py-2 text-[13px] font-medium text-white rounded-[6px] bg-[#2563EB] hover:bg-[#1D4ED8] transition-colors"
        >
          사례관리 계획으로 이동
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
      </div>
    </div>
  );
}

// ─── Case Plan Tab ────────────────────────────────────────────────────────────

function CasePlanTab({ caseObj, onNavigate }: { caseObj: CaseRecord; onNavigate: (t: Tab) => void }) {
  const [planTab, setPlanTab] = useState<"domains" | "priority" | "records">("domains");
  const [expandedEvidence, setExpandedEvidence] = useState<number | null>(null);
  const { showToast } = useToast();

  const problemDomains = [
    { domain: "신체 안전", level: "높음", basis: "신체 학대 관련 발화 3건", source: "6회차 00:41, 01:08, 03:22", color: "#DC2626" },
    { domain: "정서 발달", level: "중간", basis: "두려움·위축 반응 반복 관찰", source: "5회차, 6회차 전반", color: "#D97706" },
    { domain: "학교생활", level: "낮음", basis: "결석 이력 확인 필요", source: "초기 면담 기록", color: "#16A34A" },
    { domain: "가족 관계", level: "높음", basis: "보호자와 갈등 패턴 지속", source: "4회차, 5회차, 6회차", color: "#DC2626" },
  ];

  const priorities = [
    { rank: 1, goal: "즉각적인 신체 안전 확보", basis: "신체적 학대 징후 지속 확인됨", action: "보호조치 검토 요청", status: "진행중" },
    { rank: 2, goal: "아동 정서 안정 지원", basis: "위축 행동 및 두려움 반응", action: "전문 심리치료 연계", status: "대기중" },
    { rank: 3, goal: "보호자 교육 및 상담 연계", basis: "가족 관계 갈등 지속", action: "부모 교육 프로그램 소개", status: "대기중" },
  ];

  const records = [
    { date: "2026-08-15", content: "6회차 상담 후 아동 신체 학대 관련 진술 강화 확인. 보호조치 논의 시작.", counselor: caseObj.counselor },
    { date: "2026-08-10", content: "5회차 상담. 아동 일상 개선 없음. 담임 교사와 연계 확인.", counselor: caseObj.counselor },
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-[18px] font-semibold text-[#172033]">{caseObj.childName} · 사례관리 계획</h2>
        <div className="flex items-center gap-1 bg-white border border-[#E2E8F0] rounded-[8px] p-0.5">
          {(["domains", "priority", "records"] as const).map((t, i) => {
            const labels = ["문제 영역", "상담사 확인 필요 항목", "사례관리 기록"];
            return (
              <button key={t} onClick={() => setPlanTab(t)}
                className="px-3 py-1.5 text-[12px] font-medium rounded-[6px] transition-all"
                style={{
                  background: planTab === t ? "#172033" : "transparent",
                  color: planTab === t ? "white" : "#64748B",
                }}>
                {labels[i]}
              </button>
            );
          })}
        </div>
      </div>

      {planTab === "domains" && (
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["문제 영역", "위험 수준", "주요 근거", "발화 출처", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {problemDomains.map((d, i) => (
                <Fragment key={i}>
                  <tr className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                    <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{d.domain}</td>
                    <td className="px-4 py-3">
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-[4px]"
                        style={{ background: `${d.color}15`, color: d.color }}>{d.level}</span>
                    </td>
                    <td className="px-4 py-3 text-[13px] text-[#64748B]">{d.basis}</td>
                    <td className="px-4 py-3 text-[12px] font-mono text-[#94A3B8]">{d.source}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setExpandedEvidence(expandedEvidence === i ? null : i)}
                        className="text-[11px] font-medium text-[#2563EB] hover:text-[#1D4ED8] border border-[#DBEAFE] px-2 py-1 rounded-[4px] hover:bg-[#EFF6FF] transition-colors"
                      >
                        근거 보기
                      </button>
                    </td>
                  </tr>
                  {expandedEvidence === i && (
                    <tr className="bg-[#EFF6FF] border-b border-[#DBEAFE]">
                      <td colSpan={5} className="px-6 py-3">
                        <p className="text-[12px] font-semibold text-[#2563EB] mb-1.5">관련 발화 근거</p>
                        <p className="text-[12px] text-[#172033]">{d.basis}</p>
                        <p className="text-[11px] text-[#64748B] mt-1">출처: {d.source}</p>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {planTab === "priority" && (
        <div className="space-y-3">
          {priorities.map(p => (
            <div key={p.rank} className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-4 flex gap-4 items-start">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-bold text-white shrink-0"
                style={{ background: p.rank === 1 ? "#DC2626" : p.rank === 2 ? "#D97706" : "#64748B" }}>
                {p.rank}
              </div>
              <div className="flex-1">
                <p className="text-[14px] font-semibold text-[#172033]">{p.goal}</p>
                <p className="text-[12px] text-[#64748B] mt-0.5">근거: {p.basis}</p>
                <p className="text-[12px] text-[#2563EB] mt-1">조치: {p.action}</p>
              </div>
              <span className="text-[11px] px-2 py-0.5 rounded-[4px] font-medium shrink-0"
                style={{
                  background: p.status === "진행중" ? "#EFF6FF" : "#F8FAFC",
                  color: p.status === "진행중" ? "#2563EB" : "#94A3B8",
                }}>
                {p.status}
              </span>
            </div>
          ))}
        </div>
      )}

      {planTab === "records" && (
        <div className="space-y-4">
          {records.map((r, i) => (
            <div key={i} className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-[12px] font-mono text-[#94A3B8]">{r.date}</span>
                <span className="text-[12px] text-[#64748B]">{r.counselor}</span>
              </div>
              <p className="text-[13px] text-[#172033]">{r.content}</p>
            </div>
          ))}
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-4">
            <p className="text-[12px] font-semibold text-[#94A3B8] mb-2">새 기록 추가</p>
            <textarea
              className="w-full h-24 text-[13px] border border-[#E2E8F0] rounded-[6px] p-3 text-[#172033] placeholder:text-[#CBD5E1] focus:outline-none focus:border-[#2563EB] resize-none"
              placeholder="상담 내용, 조치 사항, 소견 등을 기록하세요..."
            />
            <div className="flex justify-end mt-2">
              <button
                onClick={() => showToast("사례관리 기록이 저장되었습니다.", "success")}
                className="px-3 py-1.5 text-[12px] font-medium text-white bg-[#2563EB] hover:bg-[#1D4ED8] rounded-[6px] transition-colors"
              >
                기록 저장
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={() => onNavigate("closure")}
          className="flex items-center gap-2 px-4 py-2 text-[13px] font-medium text-white rounded-[6px] bg-[#15314A] hover:bg-[#0F263B] transition-colors"
        >
          종결·가정복귀 검토로 이동
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
      </div>
    </div>
  );
}

// ─── Previous Sessions Tab ────────────────────────────────────────────────────

function HistoryTab({ caseObj }: { caseObj: CaseRecord }) {
  const sessions = SESSIONS.filter(s => s.caseId === caseObj.id).sort((a, b) => b.sessionNumber - a.sessionNumber);
  const [viewSession, setViewSession] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);

  const currentSession = sessions[0];
  const selected = sessions.find(s => s.id === viewSession);

  const compareRows = [
    { category: "주요 호소 내용", prev: "부모의 체벌이 무서워 집에 가기 싫다고 함", curr: "체벌 빈도 줄었다고 함, 그래도 두렵다 표현", change: "유지" as const },
    { category: "정서 상태", prev: "극도의 불안·위축", curr: "다소 불안하나 대화 가능", change: "감소" as const },
    { category: "학교 출석", prev: "주 2회 결석", curr: "주 1회 결석", change: "감소" as const },
    { category: "보호자 태도", prev: "협조 거부", curr: "1회 면담 응함", change: "증가" as const },
  ];

  const changeColor = { 증가: "#16A34A", 감소: "#DC2626", 유지: "#D97706" };
  const changeArrow = { 증가: "↑", 감소: "↓", 유지: "→" };

  if (compareMode && selected) {
    return (
      <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
        <div className="flex items-center gap-3">
          <button onClick={() => setCompareMode(false)} className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium flex items-center gap-1">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
            목록으로
          </button>
          <h2 className="text-[18px] font-semibold text-[#172033]">상담 비교: {selected.sessionNumber}회차 ↔ {currentSession.sessionNumber}회차</h2>
        </div>
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="grid grid-cols-[1fr_1fr_1fr_80px] bg-[#F8FAFC] border-b border-[#E2E8F0]">
            <div className="px-4 py-2.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">항목</div>
            <div className="px-4 py-2.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider border-l border-[#E2E8F0]">이전 ({selected.sessionNumber}회차)</div>
            <div className="px-4 py-2.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider border-l border-[#E2E8F0]">현재 ({currentSession.sessionNumber}회차)</div>
            <div className="px-4 py-2.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider border-l border-[#E2E8F0] text-center">변화</div>
          </div>
          {compareRows.map((r, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_80px] border-b border-[#F1F5F9]">
              <div className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{r.category}</div>
              <div className="px-4 py-3 text-[13px] text-[#64748B] border-l border-[#F1F5F9]">{r.prev}</div>
              <div className="px-4 py-3 text-[13px] text-[#172033] border-l border-[#F1F5F9]">{r.curr}</div>
              <div className="px-4 py-3 border-l border-[#F1F5F9] flex items-center justify-center">
                <span className="text-[12px] font-bold" style={{ color: changeColor[r.change] }}>
                  {changeArrow[r.change]} {r.change}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (viewSession && selected) {
    return (
      <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => setViewSession(null)} className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium flex items-center gap-1">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
              목록으로
            </button>
            <h2 className="text-[18px] font-semibold text-[#172033]">{selected.sessionNumber}회차 상담 내역</h2>
          </div>
          {selected.sessionNumber !== currentSession.sessionNumber && (
            <button
              onClick={() => setCompareMode(true)}
              className="flex items-center gap-2 px-3 py-1.5 text-[12px] font-medium text-[#2563EB] border border-[#DBEAFE] rounded-[6px] bg-[#EFF6FF] hover:bg-[#DBEAFE] transition-colors"
            >
              현재 상담과 비교
            </button>
          )}
        </div>
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5 space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "상담 일시", value: `${selected.date} ${selected.time}` },
              { label: "상담 유형", value: selected.type },
              { label: "장소", value: selected.location },
              { label: "소요 시간", value: selected.duration },
            ].map(f => (
              <div key={f.label}>
                <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-1">{f.label}</p>
                <p className="text-[13px] text-[#172033] font-medium">{f.value}</p>
              </div>
            ))}
          </div>
          <div className="border-t border-[#F1F5F9] pt-4">
            <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">상담 내용 요약</p>
            <p className="text-[13px] text-[#64748B]">{caseObj.childName} {selected.sessionNumber}회차 상담 기록입니다. 아동의 현재 상태를 점검하고 개입 방향을 협의하였습니다.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      <h2 className="text-[18px] font-semibold text-[#172033]">{caseObj.childName} · 이전 상담 내역</h2>
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <table className="w-full">
          <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
            <tr>
              {["회차", "일시", "유형", "장소", "소요시간", "STT", "AI 분석", ""].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sessions.map((s, i) => (
              <tr key={s.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer" onClick={() => setViewSession(s.id)}>
                <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">
                  {s.sessionNumber}회차
                  {i === 0 && <span className="ml-1.5 text-[10px] px-1.5 py-0.5 bg-[#EFF6FF] text-[#2563EB] rounded font-medium">최근</span>}
                </td>
                <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{s.date}</td>
                <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.type}</td>
                <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.location}</td>
                <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.duration}</td>
                <td className="px-4 py-3">
                  <span className="text-[11px] px-1.5 py-0.5 rounded font-medium"
                    style={{ background: s.sttStatus === "분석완료" ? "#F0FDF4" : s.sttStatus === "검수완료" ? "#EFF6FF" : "#FFFBEB", color: s.sttStatus === "분석완료" ? "#16A34A" : s.sttStatus === "검수완료" ? "#2563EB" : "#D97706" }}>
                    {s.sttStatus}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-[11px] px-1.5 py-0.5 rounded font-medium"
                    style={{ background: s.aiStatus === "상담사검토완료" ? "#F0FDF4" : s.aiStatus === "검토완료" ? "#EFF6FF" : s.aiStatus === "검토필요" ? "#FFF7ED" : "#F8FAFC", color: s.aiStatus === "상담사검토완료" ? "#16A34A" : s.aiStatus === "검토완료" ? "#2563EB" : s.aiStatus === "검토필요" ? "#D97706" : "#94A3B8" }}>
                    {s.aiStatus}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium" onClick={e => { e.stopPropagation(); setViewSession(s.id); }}>
                    상세
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Closure Tab ─────────────────────────────────────────────────────────────

type ClosureItemStatus = "근거확인" | "정보부족" | "해당없음" | "추가상담필요" | null;

interface ClosureCheckItem {
  id: string;
  label: string;
  evidence: string;
  source: string;
  session: number;
  quote: string;
  required: boolean;
}

const CLOSURE_CHECK_ITEMS: ClosureCheckItem[] = [
  { id: "c1", label: "신체적 위험 신호 해소 여부", evidence: "6회차 발화에서 체벌 관련 진술 확인", source: "6회차 상담 기록", session: 6, quote: "소리 지르고 많이 때렸어요", required: true },
  { id: "c2", label: "보호자 협조 충분성 확인", evidence: "면담 1회만 참여, 추가 협조 필요", source: "사례관리 기록", session: 5, quote: "보호자 면담 1회 참여 기록", required: true },
  { id: "c3", label: "아동 정서 안정화 여부", evidence: "5회차, 6회차 모두 위축 반응 관찰", source: "상담 기록", session: 6, quote: "집에 가기 싫어요", required: true },
  { id: "c4", label: "아동 안전 환경 확인", evidence: "가정 내 안전 환경 점검 필요", source: "현장 방문 기록", session: 4, quote: "엄마가 화나면 무서워요", required: true },
  { id: "c5", label: "지역사회 연계 자원 확인", evidence: "연계 기관 확인 필요", source: "자원 연계 기록", session: 3, quote: "지역 자원 연계 현황", required: true },
  { id: "c6", label: "후속 모니터링 계획 수립", evidence: "종결 후 모니터링 방안 필요", source: "사례관리 계획", session: 7, quote: "후속 계획 미수립", required: true },
  { id: "c7", label: "아동 의견 청취 여부", evidence: "아동 의사 확인 필요", source: "상담 기록", session: 6, quote: "아동이 원하는 상황 파악 필요", required: false },
  { id: "c8", label: "보호자 양육 역량 향상 여부", evidence: "부모 교육 참여 기록 확인", source: "교육 참여 기록", session: 5, quote: "부모 교육 1회 참여", required: false },
];

const STATUS_BTN_LABELS: Record<NonNullable<ClosureItemStatus>, string> = {
  "근거확인": "근거 확인",
  "정보부족": "정보 부족",
  "해당없음": "해당 없음",
  "추가상담필요": "추가 상담 필요",
};

function ClosureTab({ caseObj }: { caseObj: CaseRecord }) {
  const [itemStatuses, setItemStatuses] = useState<Record<string, ClosureItemStatus>>({});
  const [itemMemos, setItemMemos] = useState<Record<string, string>>({});
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [opinion, setOpinion] = useState("");
  const { showToast } = useToast();
  const navigate = useNavigate();

  const requiredItems = CLOSURE_CHECK_ITEMS.filter(i => i.required);
  const allRequiredDone = requiredItems.every(i => itemStatuses[i.id] != null);

  const counts = {
    total: requiredItems.length,
    confirmed: requiredItems.filter(i => itemStatuses[i.id] === "근거확인").length,
    insufficient: requiredItems.filter(i => itemStatuses[i.id] === "정보부족").length,
    additional: requiredItems.filter(i => itemStatuses[i.id] === "추가상담필요").length,
  };

  function setItemStatus(id: string, status: ClosureItemStatus) {
    setItemStatuses(prev => ({ ...prev, [id]: status }));
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      <h2 className="text-[18px] font-semibold text-[#172033]">{caseObj.childName} · 종결 검토 항목 확인 현황</h2>

      {/* 전체 현황 통계 */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#E2E8F0]">
          <span className="text-[14px] font-semibold text-[#172033]">필수 검토 항목 현황</span>
        </div>
        <div className="grid grid-cols-4 divide-x divide-[#E2E8F0]">
          {[
            { label: "전체 필수 항목", value: counts.total },
            { label: "근거 확인 완료", value: counts.confirmed },
            { label: "정보 부족", value: counts.insufficient },
            { label: "추가 상담 필요", value: counts.additional },
          ].map(s => (
            <div key={s.label} className="px-5 py-3">
              <p className="text-[12px] text-[#64748B] mb-1">{s.label}</p>
              <p className="text-[22px] font-semibold text-[#172033]">{s.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 검토 항목 목록 */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
          <span className="text-[14px] font-semibold text-[#172033]">종결 검토 항목</span>
          <span className="text-[12px] text-[#94A3B8]">항목을 클릭하면 근거를 확인할 수 있습니다</span>
        </div>
        <div className="divide-y divide-[#F1F5F9]">
          {CLOSURE_CHECK_ITEMS.map(item => {
            const status = itemStatuses[item.id];
            const isOpen = expandedItem === item.id;
            return (
              <div key={item.id}>
                <div className="px-5 py-4">
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => setExpandedItem(isOpen ? null : item.id)}
                      className="flex-1 flex items-center gap-2 text-left"
                    >
                      <span className={`text-[11px] border rounded px-1.5 py-0.5 shrink-0 ${item.required ? "border-[#64748B] text-[#172033] font-semibold" : "border-[#CBD5E1] text-[#94A3B8]"}`}>
                        {item.required ? "필수" : "선택"}
                      </span>
                      <span className="text-[14px] font-medium text-[#172033] flex-1">{item.label}</span>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 transition-transform" style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0)" }}><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="flex gap-1 shrink-0">
                      {(["근거확인", "정보부족", "해당없음", "추가상담필요"] as NonNullable<ClosureItemStatus>[]).map(s => (
                        <button
                          key={s}
                          onClick={() => setItemStatus(item.id, status === s ? null : s)}
                          className="px-2.5 py-1.5 text-[12px] rounded-[6px] border transition-all"
                          style={{
                            borderColor: status === s ? "#2563EB" : "#E2E8F0",
                            background: status === s ? "#EFF6FF" : "white",
                            color: status === s ? "#2563EB" : "#64748B",
                            fontWeight: status === s ? 600 : 400,
                          }}
                        >
                          {STATUS_BTN_LABELS[s]}
                        </button>
                      ))}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="mt-3 pl-12 space-y-3">
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] p-4">
                        <div className="grid grid-cols-2 gap-3 text-[13px] mb-3">
                          <div><span className="text-[#94A3B8] mr-2">관련 근거</span><span className="text-[#172033]">{item.evidence}</span></div>
                          <div><span className="text-[#94A3B8] mr-2">출처</span><span className="text-[#172033]">{item.source}</span></div>
                          <div><span className="text-[#94A3B8] mr-2">확인 회차</span><span className="text-[#172033]">{item.session}회차</span></div>
                        </div>
                        <div className="border-t border-[#E2E8F0] pt-3">
                          <p className="text-[12px] text-[#94A3B8] mb-1">원문 발화 또는 기록</p>
                          <p className="text-[13px] text-[#172033] font-medium">"{item.quote}"</p>
                        </div>
                      </div>
                      {status === "정보부족" && (
                        <div>
                          <p className="text-[12px] text-[#64748B] mb-1.5">정보 부족 메모</p>
                          <textarea
                            value={itemMemos[item.id] ?? ""}
                            onChange={e => setItemMemos(prev => ({ ...prev, [item.id]: e.target.value }))}
                            rows={2}
                            placeholder="어떤 정보가 필요한지 기록하세요..."
                            className="w-full px-3 py-2 text-[13px] border border-[#E2E8F0] rounded-[6px] text-[#172033] resize-none focus:outline-none focus:border-[#2563EB]"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 상담사 최종 의견 */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5 space-y-4">
        <p className="text-[14px] font-semibold text-[#172033]">상담사 최종 의견</p>
        <textarea
          value={opinion}
          onChange={e => setOpinion(e.target.value)}
          className="w-full h-24 text-[13px] border border-[#E2E8F0] rounded-[6px] p-3 text-[#172033] placeholder:text-[#CBD5E1] focus:outline-none focus:border-[#2563EB] resize-none"
          placeholder="종결 또는 가정복귀에 대한 상담사 의견을 입력하세요..."
        />
        {!allRequiredDone && (
          <p className="text-[13px] text-[#64748B] border border-[#E2E8F0] rounded-[6px] px-3 py-2 bg-[#F8FAFC]">
            필수 검토 항목을 모두 확인해야 제출할 수 있습니다.
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            onClick={() => navigate(`/cases/${caseObj.id}/reports`)}
            className="px-3 py-2 text-[13px] font-medium text-[#64748B] border border-[#E2E8F0] rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
          >
            보고서 생성
          </button>
          <button
            disabled={!allRequiredDone}
            onClick={() => showToast("종결 검토 자료가 제출되었습니다.", "success")}
            className="px-4 py-2 text-[13px] font-medium text-white rounded-[6px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ background: allRequiredDone ? "#2563EB" : "#94A3B8" }}
          >
            종결 검토 자료 제출
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Case List (entry view) ───────────────────────────────────────────────────

function CaseListView({ onSelect }: { onSelect: (c: CaseRecord) => void }) {
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<"riskScore" | "lastSession">("riskScore");
  const rows = useMemo(() =>
    CASES.filter(c => !query || c.childName.includes(query) || c.id.toLowerCase().includes(query.toLowerCase()))
      .sort((a, b) => sortBy === "riskScore" ? b.riskScore - a.riskScore : b.lastSession.localeCompare(a.lastSession)),
    [query, sortBy]
  );

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[22px] font-semibold text-[#172033]">사례 관리</h1>
            <p className="text-[14px] text-[#64748B] mt-0.5">관리할 사례를 선택하세요</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-0.5 text-[13px] text-[#94A3B8] bg-white border border-[#E2E8F0] rounded-[6px] px-1 py-1">
              <button onClick={() => setSortBy("riskScore")} className={`px-2.5 py-1 rounded transition-all ${sortBy === "riskScore" ? "font-semibold text-[#172033] bg-[#F1F5F9]" : "hover:text-[#172033]"}`}>위험도순</button>
              <button onClick={() => setSortBy("lastSession")} className={`px-2.5 py-1 rounded transition-all ${sortBy === "lastSession" ? "font-semibold text-[#172033] bg-[#F1F5F9]" : "hover:text-[#172033]"}`}>최근상담순</button>
            </div>
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="아동명·사례ID" className="pl-8 pr-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-48 transition-all" />
            </div>
          </div>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["아동명", "사례 ID", "위험도", "상담 회차", "최근 상담", "상태", "담당 상담사", ""].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[12px] font-semibold text-[#64748B] whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(c => (
                <tr
                  key={c.id}
                  onClick={() => onSelect(c)}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                >
                  <td className="px-4 py-3.5 text-[14px] font-semibold text-[#172033]">{c.childName}</td>
                  <td className="px-4 py-3.5 text-[12px] font-mono text-[#64748B]">{c.id}</td>
                  <td className="px-4 py-3.5"><RiskBadge level={c.riskLevel} /></td>
                  <td className="px-4 py-3.5 text-[13px] text-[#475569]">{c.sessionCount}회</td>
                  <td className="px-4 py-3.5 text-[13px] font-mono text-[#475569]">{c.lastSession}</td>
                  <td className="px-4 py-3.5">
                    <span className={`px-2 py-0.5 rounded border text-[12px] bg-white ${c.status === "review" ? "border-[#64748B] text-[#172033] font-bold" : c.status === "active" ? "border-[#94A3B8] text-[#172033] font-semibold" : "border-[#CBD5E1] text-[#64748B]"}`}>
                      {c.status === "active" ? "진행중" : c.status === "review" ? "검토필요" : "대기중"}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-[13px] text-[#475569]">{c.counselor}</td>
                  <td className="px-4 py-3.5">
                    <button className="text-[13px] text-[#2563EB] hover:text-[#1D4ED8] font-medium">선택</button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-[14px] text-[#94A3B8]">검색 조건에 맞는 사례가 없습니다.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function CaseManagementPage() {
  const [selectedCase, setSelectedCase] = useState<CaseRecord | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("ai-review");

  if (!selectedCase) {
    return <CaseListView onSelect={c => { setSelectedCase(c); setActiveTab("ai-review"); }} />;
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header with case info + back button */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-3 shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSelectedCase(null)}
            className="flex items-center gap-1.5 text-[13px] text-[#64748B] hover:text-[#172033] transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            사례 목록
          </button>
          <span className="text-[#E2E8F0]">/</span>
          <div>
            <span className="text-[16px] font-semibold text-[#172033]">{selectedCase.childName}</span>
            <span className="text-[13px] text-[#94A3B8] font-mono ml-2">{selectedCase.id}</span>
          </div>
          <RiskBadge level={selectedCase.riskLevel} />
        </div>
      </div>

      {/* Sub-nav */}
      <SubNav active={activeTab} onChange={setActiveTab} caseObj={selectedCase} />

      {/* Content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {activeTab === "ai-review" && <AiReviewTab caseObj={selectedCase} onNavigate={setActiveTab} />}
        {activeTab === "plan"      && <CasePlanTab caseObj={selectedCase} onNavigate={setActiveTab} />}
        {activeTab === "history"   && <HistoryTab caseObj={selectedCase} />}
        {activeTab === "closure"   && <ClosureTab caseObj={selectedCase} />}
      </div>
    </div>
  );
}
