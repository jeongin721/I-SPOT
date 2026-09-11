import { useState } from "react";
import { useParams, useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { SESSIONS } from "../data/mockData";
import Breadcrumb from "../components/ui/Breadcrumb";

export default function PreSessionPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const c = CASES.find(x => x.id === caseId);
  const nextSession = c ? c.sessionCount + 1 : 1;

  const [type, setType]   = useState<string>("정기상담");
  const [method, setMethod] = useState<string>("개인면담");
  const [place, setPlace] = useState("");
  const [memo, setMemo]   = useState("");

  if (!c) {
    return <div className="flex items-center justify-center h-full text-[#94A3B8]">사례를 찾을 수 없습니다.</div>;
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5 max-w-2xl">
        <Breadcrumb items={[
          { label: "통합 사례", to: "/cases" },
          { label: c.childName, to: `/cases/${caseId}` },
          { label: "새 상담 시작" },
        ]} />

        <div>
          <h1 className="text-[22px] font-semibold text-[#172033]">새 상담 시작</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">상담 정보를 입력하고 녹음을 시작하세요</p>
        </div>

        {/* Read-only info */}
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
          <h2 className="text-[13px] font-semibold text-[#172033] mb-4">기본 정보</h2>
          <div className="grid grid-cols-2 gap-4 text-[13px]">
            {[
              ["아동명", c.childName],
              ["사례 ID", c.id],
              ["예정 회차", `${nextSession}회차`],
              ["날짜", "2026-08-21"],
              ["담당 상담사", c.counselor],
              ["위험도", c.riskLevel === "high" ? "고위험" : c.riskLevel === "mid" ? "중위험" : "저위험"],
            ].map(([k, v]) => (
              <div key={k} className="flex gap-3">
                <span className="text-[#94A3B8] w-24 shrink-0">{k}</span>
                <span className="text-[#172033] font-medium">{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Input section */}
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5 space-y-4">
          <h2 className="text-[13px] font-semibold text-[#172033]">상담 설정</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">상담 유형</label>
              <select
                value={type}
                onChange={e => setType(e.target.value)}
                className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
              >
                <option>초기면담</option>
                <option>정기상담</option>
                <option>전화상담</option>
                <option>방문상담</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">상담 방식</label>
              <select
                value={method}
                onChange={e => setMethod(e.target.value)}
                className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
              >
                <option>개인면담</option>
                <option>놀이치료</option>
                <option>집단상담</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">장소</label>
            <input
              value={place}
              onChange={e => setPlace(e.target.value)}
              placeholder="예: 면담실 A"
              className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5">목적 / 메모</label>
            <textarea
              value={memo}
              onChange={e => setMemo(e.target.value)}
              rows={3}
              placeholder="이번 회차 상담 목적 및 주의사항을 입력하세요"
              className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white resize-none focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button
            onClick={() => navigate(-1)}
            className="px-5 py-2.5 border border-[#E2E8F0] text-[#64748B] text-[13px] font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
          >
            취소
          </button>
          <button
            onClick={() => navigate(`/cases/${caseId}/recording`)}
            className="px-5 py-2.5 bg-[#2563EB] text-white text-[13px] font-semibold rounded-[6px] hover:bg-[#1D4ED8] transition-colors"
          >
            상담 시작
          </button>
        </div>
      </div>
    </div>
  );
}
