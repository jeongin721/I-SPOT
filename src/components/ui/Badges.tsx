import type { RiskLevel, AbuseType, CaseRecord } from "../../data/cases";

export function RiskBadge({ level, score: _score }: { level: RiskLevel; score?: number }) {
  const cfg = {
    high: { label: "확인 필요", cls: "font-bold border-[#64748B] text-[#172033]" },
    mid:  { label: "확인 중",   cls: "font-semibold border-[#94A3B8] text-[#172033]" },
    low:  { label: "확인 완료", cls: "font-medium border-[#CBD5E1] text-[#475569]" },
  }[level];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[12px] bg-white ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

export function AbuseBadge({ type }: { type: AbuseType }) {
  return (
    <span className="px-2 py-0.5 rounded border border-[#CBD5E1] text-[12px] text-[#475569] bg-white font-medium">
      {type}
    </span>
  );
}

export function StatusLabel({ status }: { status: CaseRecord["status"] }) {
  const cfg = {
    active:  { label: "진행중",   cls: "border-[#94A3B8] text-[#172033] font-semibold" },
    pending: { label: "대기중",   cls: "border-[#CBD5E1] text-[#64748B] font-medium" },
    review:  { label: "검토필요", cls: "border-[#64748B] text-[#172033] font-bold" },
  }[status];
  return (
    <span className={`px-2 py-0.5 rounded border text-[12px] bg-white ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}
