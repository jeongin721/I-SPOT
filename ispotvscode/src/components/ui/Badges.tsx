import type { RiskLevel, AbuseType, CaseRecord } from "../../data/cases";

export function RiskBadge({ level, score }: { level: RiskLevel; score?: number }) {
  const cfg = {
    high: { label: "고위험", cls: "text-[#B91C1C] bg-[#FEF2F2] border-[#FECACA]" },
    mid:  { label: "중위험", cls: "text-[#B45309] bg-[#FFFBEB] border-[#FDE68A]" },
    low:  { label: "저위험", cls: "text-[#15803D] bg-[#F0FDF4] border-[#BBF7D0]" },
  }[level];
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[11px] font-semibold tracking-wide ${cfg.cls}`}>
      {cfg.label}
      {score !== undefined && <span className="opacity-70 font-mono ml-0.5">{score}</span>}
    </span>
  );
}

export function AbuseBadge({ type }: { type: AbuseType }) {
  const cls: Record<AbuseType, string> = {
    "신체": "text-[#991B1B] bg-[#FEF2F2] border-[#FECACA]",
    "정서": "text-[#6B21A8] bg-[#FAF5FF] border-[#E9D5FF]",
    "성":   "text-[#9A3412] bg-[#FFF7ED] border-[#FED7AA]",
    "방임": "text-[#475569] bg-[#F8FAFC] border-[#E2E8F0]",
  };
  return <span className={`px-1.5 py-0.5 rounded border text-[11px] font-medium ${cls[type]}`}>{type}</span>;
}

export function StatusLabel({ status }: { status: CaseRecord["status"] }) {
  const cfg = {
    active:  { label: "진행중",   cls: "text-[#1D4ED8] bg-[#EFF6FF] border-[#BFDBFE]" },
    pending: { label: "대기중",   cls: "text-[#64748B] bg-[#F8FAFC] border-[#E2E8F0]" },
    review:  { label: "검토필요", cls: "text-[#B45309] bg-[#FFFBEB] border-[#FDE68A]" },
  }[status];
  return <span className={`px-1.5 py-0.5 rounded border text-[11px] font-medium ${cfg.cls}`}>{cfg.label}</span>;
}
