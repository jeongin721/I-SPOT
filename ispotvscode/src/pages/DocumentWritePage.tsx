import { useState } from "react";
import { useParams, useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { useToast } from "../components/ui/Toast";

const DRAFT_TEXT = `[상담 일지 - AI 생성 초안]

상담일시: 2026-07-14 (화) 14:00 ~ 15:00
상담형태: 개인 면담
상담 장소: 상담실 A

■ 아동 상태 및 태도
아동은 상담 초반 다소 위축된 모습을 보였으나, 상담이 진행될수록 점차 이야기를 이어갔습니다. 눈을 자주 피하고 손을 만지작거리는 불안 행동이 관찰되었습니다.

■ 주요 상담 내용
아동은 가정 내 신체적 위협 상황에 대해 발화하였습니다. "배가 너무 아파요, 때렸어요"라는 직접적 진술이 확인되었으며, 보호자(부)의 행위에 대한 두려움을 표현하였습니다. 또한 "집에 가기 싫어요"라는 표현을 반복하며 귀가에 대한 거부감을 드러냈습니다.

■ 아동 안전 여부
신체 증상 호소(복통)가 있었으며, 의료기관 연계 여부를 검토할 필요가 있습니다. 보호자와의 관계에서 두려움이 지속되고 있어 안전 환경 확인이 요구됩니다.

■ 다음 회차 계획
- 의료기관 연계 여부 확인 (신체 검사)
- 보호자 면담 일정 조율
- 정서 안정화를 위한 놀이치료 검토
- 다음 면담: 2026-07-28 예정`;

interface EvidenceItem {
  id: string;
  timestamp: string;
  speaker: string;
  quote: string;
  signal: string;
  checklist: string;
  aiRef: string;
  status: "확인필요" | "확인완료" | "보류" | null;
}

const EVIDENCE_ITEMS: EvidenceItem[] = [
  {
    id: "e1",
    timestamp: "14:12",
    speaker: "아동",
    quote: "배가 너무 아파요, 때렸어요",
    signal: "신체적 학대 발화",
    checklist: "신체 증상 호소 → 의료기관 연계 검토",
    aiRef: "신체학대 관련 아동 발화 패턴 (자료명: 아동학대 조기 발견 지침서, 보건복지부 2024, p.32)",
    status: null,
  },
  {
    id: "e2",
    timestamp: "14:28",
    speaker: "아동",
    quote: "집에 가기 싫어요",
    signal: "두려움·회피 반응",
    checklist: "귀가 거부 → 안전 환경 확인 필요",
    aiRef: "가정 내 위협 지각 시 귀가 거부 패턴 (자료명: 피해아동 상담 지침, 2023, p.17)",
    status: null,
  },
  {
    id: "e3",
    timestamp: "14:41",
    speaker: "아동",
    quote: "엄마가 화나면 무서워요",
    signal: "두려움·회피 반응",
    checklist: "보호자 태도 파악 → 보호자 면담 필요",
    aiRef: "보호자 폭력 노출 아동의 정서 반응 (자료명: 외상 중심 상담 가이드, 2022, p.45)",
    status: null,
  },
];

export default function DocumentWritePage() {
  const { caseId, sessionId } = useParams<{ caseId: string; sessionId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const caseObj = CASES.find(c => c.id === caseId) ?? CASES[0];

  const [docText, setDocText] = useState(DRAFT_TEXT);
  const [evidences, setEvidences] = useState<EvidenceItem[]>(EVIDENCE_ITEMS);
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>("e1");

  const unconfirmed = evidences.filter(e => e.status === null || e.status === "확인필요").length;
  const activeEvidence = evidences.find(e => e.id === selectedEvidence);

  function setEvidenceStatus(id: string, status: EvidenceItem["status"]) {
    setEvidences(prev => prev.map(e => e.id === id ? { ...e, status } : e));
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#F6F8FB]">
      {/* Header */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 flex items-center gap-4 shrink-0">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-[13px] text-[#64748B] hover:text-[#172033] transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          돌아가기
        </button>
        <div className="h-5 w-px bg-[#E2E8F0]" />
        <div className="flex-1 flex items-center gap-3">
          <span className="text-[16px] font-semibold text-[#172033]">{caseObj.childName}</span>
          <span className="text-[#94A3B8]">·</span>
          <span className="text-[13px] font-mono text-[#64748B]">{caseObj.id}</span>
          <span className="text-[#94A3B8]">·</span>
          <span className="text-[13px] text-[#64748B]">8회차</span>
          <span className="text-[#94A3B8]">·</span>
          <span className="text-[13px] text-[#64748B]">2026-07-14</span>
          <span className="text-[#94A3B8]">·</span>
          <span className="text-[13px] text-[#64748B]">담당: {caseObj.counselor}</span>
        </div>
        <div className="flex items-center gap-2">
          {unconfirmed > 0 && (
            <span className="text-[12px] font-medium px-3 py-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] text-[#64748B]">
              미확인 근거 {unconfirmed}건
            </span>
          )}
          <button
            onClick={() => showToast("임시저장되었습니다.", "success")}
            className="px-3 py-2 text-[13px] font-medium text-[#64748B] border border-[#E2E8F0] rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
          >
            임시저장
          </button>
          <button
            onClick={() => {
              if (unconfirmed > 0) {
                showToast(`미확인 근거 ${unconfirmed}건을 먼저 처리해주세요.`, "error");
                return;
              }
              showToast("상담일지가 저장되었습니다.", "success");
              navigate(-1);
            }}
            className="px-4 py-2 text-[13px] font-medium text-white bg-[#2563EB] hover:bg-[#1D4ED8] rounded-[6px] transition-colors"
          >
            상담일지 저장
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main edit area */}
        <div className="flex-1 flex flex-col overflow-hidden p-5 gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-[16px] font-semibold text-[#172033]">상담일지 작성</h2>
            <span className="text-[11px] font-medium px-2 py-0.5 border border-[#94A3B8] rounded text-[#64748B] bg-white">
              AI 생성 초안 — 상담사 검토 후 확정
            </span>
          </div>
          <textarea
            value={docText}
            onChange={e => setDocText(e.target.value)}
            className="flex-1 w-full px-5 py-4 text-[14px] leading-relaxed text-[#172033] bg-white border border-[#E2E8F0] rounded-[8px] resize-none focus:outline-none focus:border-[#2563EB] font-mono"
          />
        </div>

        {/* Right panel: evidence */}
        <div className="w-[360px] shrink-0 border-l border-[#E2E8F0] bg-white flex flex-col overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E2E8F0]">
            <h3 className="text-[14px] font-semibold text-[#172033]">작성 근거</h3>
            <p className="text-[12px] text-[#94A3B8] mt-0.5">AI 참고정보 — 상담사가 직접 확인·판단</p>
          </div>

          {/* Evidence list */}
          <div className="flex flex-col overflow-hidden flex-1">
            <div className="flex border-b border-[#F1F5F9]">
              {evidences.map(e => (
                <button
                  key={e.id}
                  onClick={() => setSelectedEvidence(e.id)}
                  className="flex-1 py-2.5 text-[12px] font-medium transition-colors border-b-2"
                  style={{
                    borderBottomColor: selectedEvidence === e.id ? "#2563EB" : "transparent",
                    color: selectedEvidence === e.id ? "#2563EB" : "#64748B",
                  }}
                >
                  {e.timestamp}
                </button>
              ))}
            </div>

            {activeEvidence && (
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {/* Quote */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">원문 발화</p>
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] px-4 py-3">
                    <p className="text-[12px] text-[#94A3B8] mb-1">{activeEvidence.timestamp} · {activeEvidence.speaker}</p>
                    <p className="text-[14px] font-medium text-[#172033]">"{activeEvidence.quote}"</p>
                  </div>
                </div>

                {/* Signal */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">관련 신호</p>
                  <span className="text-[13px] border border-[#64748B] px-2 py-1 rounded text-[#172033] font-semibold">
                    {activeEvidence.signal}
                  </span>
                </div>

                {/* Checklist */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">연결 체크리스트</p>
                  <p className="text-[13px] text-[#172033] bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] px-3 py-2">{activeEvidence.checklist}</p>
                </div>

                {/* AI Reference */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">AI 참고정보</p>
                  <p className="text-[12px] text-[#64748B] bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] px-3 py-2 leading-relaxed">{activeEvidence.aiRef}</p>
                </div>

                {/* Status buttons */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">상담사 확인 상태</p>
                  <div className="flex flex-col gap-2">
                    {(["확인필요", "확인완료", "보류"] as NonNullable<EvidenceItem["status"]>[]).map(s => (
                      <button
                        key={s}
                        onClick={() => setEvidenceStatus(activeEvidence.id, activeEvidence.status === s ? null : s)}
                        className="w-full py-2 text-[13px] rounded-[6px] border transition-all text-left px-3"
                        style={{
                          borderColor: activeEvidence.status === s ? "#2563EB" : "#E2E8F0",
                          background: activeEvidence.status === s ? "#EFF6FF" : "white",
                          color: activeEvidence.status === s ? "#2563EB" : "#64748B",
                          fontWeight: activeEvidence.status === s ? 600 : 400,
                        }}
                      >
                        {s === "확인필요" ? "확인 필요" : s === "확인완료" ? "확인 완료 (상담사 확인)" : "보류"}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
