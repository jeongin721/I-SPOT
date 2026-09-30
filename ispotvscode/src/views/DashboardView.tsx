import { useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { RiskBadge, AbuseBadge } from "../components/ui/Badges";
import { SESSIONS } from "../data/mockData";

const TASKS = [
  { id: 1, type: "음성 검수 대기",      case: "C-2026-0412", urgent: true,  link: "/cases/C-2026-0412/sessions" },
  { id: 2, type: "분석 결과 검토 필요",  case: "C-2026-0351", urgent: true,  link: "/cases/C-2026-0351/analyses" },
  { id: 3, type: "상담일지 승인 대기",   case: "C-2026-0389", urgent: false, link: "/cases/C-2026-0389/plan" },
  { id: 4, type: "종결 검토 예정",       case: "C-2026-0312", urgent: false, link: "/cases/C-2026-0312/closure" },
  { id: 5, type: "분석 결과 검토 필요",  case: "C-2026-0277", urgent: true,  link: "/cases/C-2026-0277/analyses" },
];

const TODAY_SESSIONS = [
  { time: "13:00", childName: "박서준", caseId: "C-2026-0412", type: "정기상담" },
  { time: "14:30", childName: "최유나", caseId: "C-2026-0351", type: "초기면담" },
  { time: "16:00", childName: "이지후", caseId: "C-2026-0277", type: "정기상담" },
];

export default function DashboardView() {
  const navigate = useNavigate();
  const highRisk = CASES.filter(c => c.riskLevel === "high");

  const stats = [
    { label: "전체 담당 사례",   value: CASES.length,                                         note: `활성 ${CASES.filter(c => c.status === "active").length} · 검토 ${CASES.filter(c => c.status === "review").length}` },
    { label: "오늘 예정 상담",   value: TODAY_SESSIONS.length,                               note: TODAY_SESSIONS.map(s => s.time).join(" · ") },
    { label: "작성 대기 문서",   value: 2,                                                    note: "상담일지 1 · 사정기록지 1" },
    { label: "미처리 업무",      value: TASKS.length,                                         note: `긴급 ${TASKS.filter(t => t.urgent).length}건 포함` },
    { label: "수속 상담",        value: 1,                                                    note: "C-2026-0412 긴급" },
  ];

  return (
    <div className="p-6 space-y-5 overflow-y-auto flex-1" style={{ maxWidth: "1100px" }}>
      <div>
        <h1 className="text-[22px] font-semibold text-[#172033]">대시보드</h1>
        <p className="text-[14px] text-[#64748B] mt-0.5">2026년 8월 21일 목요일 · 이서연 상담사</p>
      </div>

      {/* 5-item stat strip */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="grid divide-x divide-[#E2E8F0]" style={{ gridTemplateColumns: "repeat(5,1fr)" }}>
          {stats.map(stat => (
            <div key={stat.label} className="px-5 py-4">
              <p className="text-[12px] font-semibold text-[#64748B] mb-2">{stat.label}</p>
              <p className="text-[28px] font-semibold leading-none mb-1 text-[#172033]">{stat.value}</p>
              <p className="text-[12px] text-[#94A3B8]">{stat.note}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Today's sessions */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
          <span className="text-[14px] font-semibold text-[#172033]">오늘 예정 상담</span>
          <span className="text-[12px] text-[#94A3B8]">{TODAY_SESSIONS.length}건</span>
        </div>
        <div className="flex divide-x divide-[#F1F5F9]">
          {TODAY_SESSIONS.map(s => (
            <button
              key={s.caseId}
              onClick={() => navigate(`/cases/${s.caseId}`)}
              className="flex-1 px-5 py-4 text-left hover:bg-[#F8FAFC] transition-colors"
            >
              <p className="text-[14px] font-mono font-semibold text-[#2563EB] mb-1">{s.time}</p>
              <p className="text-[14px] font-semibold text-[#172033]">{s.childName}</p>
              <p className="text-[12px] text-[#94A3B8] mt-0.5">{s.type}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Main panels */}
      <div className="grid grid-cols-5 gap-5">
        <div className="col-span-3 bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
            <span className="text-[14px] font-semibold text-[#172033]">나의 업무 목록</span>
            <span className="text-[12px] text-[#94A3B8]">{TASKS.length}건 미처리</span>
          </div>
          <div className="divide-y divide-[#F1F5F9]">
            {TASKS.map(task => (
              <div key={task.id} className="flex items-center gap-3 px-5 py-3.5 hover:bg-[#F8FAFC] transition-colors">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${task.urgent ? "bg-[#DC2626]" : "bg-[#CBD5E1]"}`} />
                <span className="text-[14px] text-[#172033] flex-1">{task.type}</span>
                <span className="text-[12px] text-[#94A3B8] font-mono">{task.case}</span>
                <button
                  onClick={() => navigate(task.link)}
                  className="text-[13px] text-[#2563EB] font-medium hover:text-[#1D4ED8] transition-colors shrink-0"
                >
                  처리
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="col-span-2 bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
            <span className="text-[14px] font-semibold text-[#172033]">확인 필요 우선 검토</span>
            <button onClick={() => navigate("/cases")} className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium transition-colors">전체보기</button>
          </div>
          <div className="divide-y divide-[#F1F5F9]">
            {highRisk.slice(0, 5).map(c => (
              <button
                key={c.id}
                onClick={() => navigate(`/cases/${c.id}`)}
                className="w-full text-left px-5 py-3 hover:bg-[#F8FAFC] transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-[14px] font-semibold text-[#172033]">{c.childName}</span>
                    <span className="text-[12px] text-[#94A3B8] ml-2">{c.age}세</span>
                  </div>
                  <RiskBadge level={c.riskLevel} />
                </div>
                <div className="flex items-center gap-1 mt-1.5">
                  {c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}
                  <span className="text-[11px] text-[#94A3B8] font-mono ml-1">{c.id}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
