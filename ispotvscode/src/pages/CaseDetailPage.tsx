import { useParams, useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { SESSIONS } from "../data/mockData";
import { RiskBadge, AbuseBadge, StatusLabel } from "../components/ui/Badges";
import Breadcrumb from "../components/ui/Breadcrumb";
import { useState } from "react";

const STT_STATUS_CFG: Record<string, string> = {
  "처리중":   "bg-blue-50 text-blue-700",
  "검수필요": "bg-amber-50 text-amber-700",
  "검수완료": "bg-green-50 text-green-700",
  "분석완료": "bg-green-50 text-green-700",
};

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"overview" | "sessions" | "documents">("overview");

  const c = CASES.find(x => x.id === caseId);
  if (!c) {
    return (
      <div className="flex items-center justify-center h-full text-[#94A3B8]">
        사례를 찾을 수 없습니다.
      </div>
    );
  }

  const sessions = SESSIONS.filter(s => s.caseId === caseId).sort((a, b) => b.date.localeCompare(a.date));

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5 max-w-5xl">
        {/* Breadcrumb */}
        <Breadcrumb items={[
          { label: "통합 사례", to: "/cases" },
          { label: c.childName },
          { label: "상세 정보" },
        ]} />

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap mb-1">
              <h1 className="text-[22px] font-semibold text-[#172033]">{c.childName}</h1>
              <span className="text-[13px] text-[#94A3B8]">{c.age}세</span>
              <RiskBadge level={c.riskLevel} score={c.riskScore} />
              <StatusLabel status={c.status} />
            </div>
            <p className="text-[12px] text-[#94A3B8] font-mono">{c.id} · 담당: {c.counselor}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => navigate(-1)}
              className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-[12px] font-medium rounded-[6px] hover:bg-[#F1F5F9] transition-colors"
            >
              뒤로
            </button>
            <button
              onClick={() => navigate(`/cases/${caseId}/counseling/new`)}
              className="px-3 py-1.5 bg-[#2563EB] text-white text-[12px] font-semibold rounded-[6px] hover:bg-[#1D4ED8] transition-colors"
            >
              새 상담 시작
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-[#E2E8F0]">
          {(["overview", "sessions", "documents"] as const).map(t => {
            const labels = { overview: "개요", sessions: "상담 이력", documents: "문서" };
            return (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2.5 text-[13px] font-medium border-b-2 transition-colors ${
                  tab === t ? "border-[#2563EB] text-[#2563EB]" : "border-transparent text-[#64748B] hover:text-[#172033]"
                }`}
              >
                {labels[t]}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {tab === "overview" && (
          <div className="grid grid-cols-2 gap-5">
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
              <h2 className="text-[13px] font-semibold text-[#172033] mb-4">아동 기본정보</h2>
              <div className="space-y-2 text-[13px]">
                <div className="flex gap-3"><span className="text-[#94A3B8] w-24">이름</span><span className="text-[#172033] font-medium">{c.childName}</span></div>
                <div className="flex gap-3"><span className="text-[#94A3B8] w-24">연령</span><span className="text-[#172033] font-medium">{c.age}세</span></div>
                <div className="flex gap-3"><span className="text-[#94A3B8] w-24">보호자</span><span className="text-[#172033] font-medium">{c.guardian}</span></div>
                <div className="flex gap-3"><span className="text-[#94A3B8] w-24">담당 상담사</span><span className="text-[#172033] font-medium">{c.counselor}</span></div>
                <div className="flex gap-3"><span className="text-[#94A3B8] w-24">상담 회차</span><span className="text-[#172033] font-medium">{c.sessionCount}회</span></div>
                <div className="flex gap-3"><span className="text-[#94A3B8] w-24">최근 상담</span><span className="text-[#172033] font-mono">{c.lastSession}</span></div>
              </div>
            </div>
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
              <h2 className="text-[13px] font-semibold text-[#172033] mb-4">주요 위험요인</h2>
              <div className="mb-3">
                <p className="text-[11px] text-[#94A3B8] uppercase tracking-wider mb-2">학대 유형</p>
                <div className="flex gap-1 flex-wrap">{c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}</div>
              </div>
              <div>
                <p className="text-[11px] text-[#94A3B8] uppercase tracking-wider mb-2">주요 키워드</p>
                <div className="flex gap-1 flex-wrap">
                  {c.keywords.map(k => (
                    <span key={k} className="text-[11px] text-[#64748B] bg-[#F1F5F9] border border-[#E2E8F0] px-1.5 py-0.5 rounded">#{k}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "sessions" && (
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
            <table className="w-full">
              <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                <tr>
                  {["날짜", "회차", "유형", "상담사", "시간", "STT 상태", "AI 상태", ""].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                    <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{s.date}</td>
                    <td className="px-4 py-3 text-[13px] text-[#172033]">{s.sessionNumber}회차</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.type}</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.counselor}</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.duration}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${STT_STATUS_CFG[s.sttStatus] ?? "bg-slate-50 text-slate-600"}`}>
                        {s.sttStatus}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.aiStatus}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => navigate(`/cases/${caseId}/sessions/${s.id}/transcript`)}
                        className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium"
                      >
                        보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "documents" && (
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "사례관리 계획", to: `/cases/${caseId}/plan`, desc: "개입 우선순위 및 계획" },
              { label: "종결·가정복귀 검토", to: `/cases/${caseId}/closure`, desc: "목표 달성 및 종결 검토" },
              { label: "보고서 생성", to: `/cases/${caseId}/reports`, desc: "사례회의·외부전달·종결검토" },
            ].map(doc => (
              <button
                key={doc.label}
                onClick={() => navigate(doc.to)}
                className="bg-white border border-[#E2E8F0] rounded-[8px] p-5 text-left hover:border-[#2563EB] hover:bg-blue-50/30 transition-all"
              >
                <p className="text-[13px] font-semibold text-[#172033] mb-1">{doc.label}</p>
                <p className="text-[12px] text-[#94A3B8]">{doc.desc}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
