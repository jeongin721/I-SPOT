import type { RiskLevel, AbuseType, CaseRecord } from "../../data/cases";

export function RiskBadge({ level, score: _score }: { level?: RiskLevel; score?: number }) {
  // 위험도가 아직 없는 사례(Backend 에 사례 위험도가 없다). "확인 완료" 로 그리면 아무도 보지 않은 사례가
  // 검토가 끝난 것처럼 보인다.
  if (!level) {
    return (
      <span title="위험도는 아직 서버에 없습니다" className="inline-flex items-center px-2 py-0.5 rounded border text-[12px] bg-white font-medium border-[#E2E8F0] text-[#94A3B8]">
        —
      </span>
    );
  }

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
