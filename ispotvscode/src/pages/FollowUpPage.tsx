import { useState } from "react";
import { useNavigate } from "react-router";

const STATS = [
  { label: "오늘 상담", value: 3, color: "#2563EB" },
  { label: "기록 작성 대기", value: 2, color: "#D97706" },
  { label: "상담사 확인 필요", value: 1, color: "#7C3AED" },
  { label: "승인 반려", value: 1, color: "#DC2626" },
  { label: "후속상담 예정", value: 2, color: "#0891B2" },
];

const TODAY_SESSIONS = [
  { time: "13:00", childName: "박서준", caseId: "C-2026-0412", type: "정기상담", riskLevel: "high" as const },
  { time: "14:30", childName: "최유나", caseId: "C-2026-0351", type: "초기면담", riskLevel: "mid" as const },
  { time: "16:00", childName: "이지후", caseId: "C-2026-0277", type: "정기상담", riskLevel: "low" as const },
];

const PENDING_SESSIONS = [
  { childName: "김민서", caseId: "C-2026-0389", scheduledDate: "2026-08-25", type: "정기상담", note: "이전 회차 검토 필요" },
  { childName: "정하은", caseId: "C-2026-0312", scheduledDate: "2026-08-28", type: "종결 상담", note: "종결 검토 항목 확인 현황 검토 후 진행" },
];

const APPROVAL_PENDING = [
  { doc: "상담일지 8회차", childName: "박서준", caseId: "C-2026-0412", submittedAt: "2026-08-20", status: "검토중" },
  { doc: "사정기록지", childName: "최유나", caseId: "C-2026-0351", submittedAt: "2026-08-19", status: "검토중" },
];

const APPROVAL_REJECTED = [
  { doc: "상담일지 7회차", childName: "김민서", caseId: "C-2026-0389", reason: "서명 누락", rejectedAt: "2026-08-18" },
];

const INCOMPLETE_TASKS = [
  { label: "C-2026-0412 음성 검수 대기", urgent: true },
  { label: "C-2026-0351 분석 결과 검토", urgent: true },
  { label: "C-2026-0277 상담일지 작성", urgent: false },
];

export default function FollowUpPage() {
  const navigate = useNavigate();
  const [nextDate, setNextDate] = useState("2026-08-25");
  const [checkItems, setCheckItems] = useState("이전 회차 상담 내용 재검토\n위험 신호 변화 여부 확인");
  const [otherMemo, setOtherMemo] = useState("");

  const riskColor = (level: "high" | "mid" | "low") =>
    level === "high" ? "#DC2626" : level === "mid" ? "#D97706" : "#16A34A";

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5" style={{ maxWidth: "1100px" }}>
        <div>
          <h1 className="text-[22px] font-semibold text-[#172033]">후속 관리</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">진행 중인 사례의 후속 상담 및 미처리 업무를 확인하세요</p>
        </div>

        {/* Stat strip */}
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="grid divide-x divide-[#E2E8F0]" style={{ gridTemplateColumns: `repeat(${STATS.length}, 1fr)` }}>
            {STATS.map(s => (
              <div key={s.label} className="px-5 py-4 flex items-center gap-3">
                <div className="w-9 h-9 rounded-[6px] flex items-center justify-center shrink-0" style={{ background: `${s.color}18` }}>
                  <span className="text-[16px] font-bold" style={{ color: s.color }}>{s.value}</span>
                </div>
                <p className="text-[12px] font-semibold text-[#172033]">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-5 gap-5">
          {/* Left column */}
          <div className="col-span-3 space-y-5">
            {/* 오늘 상담 사안 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0]">
                <span className="text-[13px] font-semibold text-[#172033]">오늘 상담 사안</span>
              </div>
              <div className="divide-y divide-[#F1F5F9]">
                {TODAY_SESSIONS.map(s => (
                  <button
                    key={s.caseId}
                    onClick={() => navigate(`/cases/${s.caseId}`)}
                    className="w-full text-left px-5 py-3 hover:bg-[#F8FAFC] transition-colors flex items-center gap-3"
                  >
                    <span className="text-[13px] font-mono text-[#2563EB] shrink-0 w-14">{s.time}</span>
                    <div className="flex items-center gap-1.5 flex-1">
                      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: riskColor(s.riskLevel) }} />
                      <span className="text-[13px] font-semibold text-[#172033]">{s.childName}</span>
                      <span className="text-[11px] text-[#94A3B8]">{s.type}</span>
                    </div>
                    <span className="text-[11px] font-mono text-[#94A3B8]">{s.caseId}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 대기 상담 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0]">
                <span className="text-[13px] font-semibold text-[#172033]">후속상담 예정</span>
              </div>
              <div className="divide-y divide-[#F1F5F9]">
                {PENDING_SESSIONS.map(s => (
                  <div key={s.caseId} className="px-5 py-3 flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[13px] font-semibold text-[#172033]">{s.childName}</span>
                        <span className="text-[11px] text-[#64748B]">{s.type}</span>
                        <span className="text-[11px] font-mono text-[#94A3B8]">{s.caseId}</span>
                      </div>
                      <p className="text-[12px] text-[#64748B]">{s.note}</p>
                    </div>
                    <span className="text-[12px] font-mono text-[#2563EB] shrink-0">{s.scheduledDate}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 승인 대기 / 반려 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0]">
                <span className="text-[13px] font-semibold text-[#172033]">승인 현황</span>
              </div>
              {APPROVAL_PENDING.map(a => (
                <div key={a.doc} className="px-5 py-2.5 flex items-center gap-3 border-b border-[#F1F5F9]">
                  <span className="px-1.5 py-0.5 text-[10px] font-bold text-[#1D4ED8] bg-[#EFF6FF] border border-[#BFDBFE] rounded">검토중</span>
                  <span className="text-[13px] text-[#172033] flex-1">{a.childName} · {a.doc}</span>
                  <span className="text-[11px] font-mono text-[#94A3B8]">{a.submittedAt}</span>
                </div>
              ))}
              {APPROVAL_REJECTED.map(a => (
                <div key={a.doc} className="px-5 py-2.5 flex items-center gap-3">
                  <span className="px-1.5 py-0.5 text-[10px] font-bold text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded">반려</span>
                  <span className="text-[13px] text-[#172033] flex-1">{a.childName} · {a.doc}</span>
                  <span className="text-[12px] text-[#64748B]">{a.reason}</span>
                  <span className="text-[11px] font-mono text-[#94A3B8]">{a.rejectedAt}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right column */}
          <div className="col-span-2 space-y-5">
            {/* 다음 상담일 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0]">
                <span className="text-[13px] font-semibold text-[#172033]">다음 상담일</span>
              </div>
              <div className="px-5 py-4">
                <input
                  type="date"
                  value={nextDate}
                  onChange={e => setNextDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
                />
              </div>
            </div>

            {/* 확인 사항 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0]">
                <span className="text-[13px] font-semibold text-[#172033]">확인사항</span>
              </div>
              <div className="px-5 py-4">
                <textarea
                  value={checkItems}
                  onChange={e => setCheckItems(e.target.value)}
                  rows={4}
                  placeholder="다음 상담 전 확인해야 할 사항을 입력하세요"
                  className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white resize-none focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
                />
              </div>
            </div>

            {/* 미완료 업무 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0]">
                <span className="text-[13px] font-semibold text-[#172033]">미완료 업무</span>
              </div>
              <div className="divide-y divide-[#F1F5F9]">
                {INCOMPLETE_TASKS.map(t => (
                  <div key={t.label} className="flex items-center gap-2.5 px-5 py-2.5">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.urgent ? "bg-[#DC2626]" : "bg-[#CBD5E1]"}`} />
                    <span className="text-[13px] text-[#172033] flex-1">{t.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 기타 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0]">
                <span className="text-[13px] font-semibold text-[#172033]">기타</span>
              </div>
              <div className="px-5 py-4">
                <textarea
                  value={otherMemo}
                  onChange={e => setOtherMemo(e.target.value)}
                  rows={3}
                  placeholder="기타 메모를 입력하세요"
                  className="w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] text-[#172033] bg-white resize-none focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
