import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { tasks as tasksApi } from "../api/endpoints";
import { describeApiError } from "../api/adapters";
import { toDashboardTaskRow, toFollowUpStats, type DashboardTaskRow } from "../api/dashboardAdapters";
import type { TaskSummary } from "../api/types";

// 미완료 업무 · 승인 대기는 처리 대기 업무 API(GET /tasks, GET /tasks/summary)에서 온다.
// 승인 대기 = AI 결과 검토(REVIEW_ANALYSIS) 업무, 즉 상담사 승인을 기다리는 상담 요약이다.
// 오늘 상담 · 후속상담 예정 · 승인 반려 · 기록 작성 대기는 Backend 에 조회가 없어 "—" 로 둔다.
// 다음 상담일 · 확인사항 · 기타 메모는 저장할 곳이 없어 이 화면에만 남는다.

const INCOMPLETE_PAGE_SIZE = 10;
const APPROVAL_PAGE_SIZE = 10;

function OverdueTag() {
  return (
    <span className="shrink-0 px-1.5 py-0.5 text-[10px] font-bold text-[#B91C1C] bg-[#FEF2F2] border border-[#FECACA] rounded">지연</span>
  );
}

export default function FollowUpPage() {
  const navigate = useNavigate();
  const [nextDate, setNextDate] = useState("");
  const [checkItems, setCheckItems] = useState("");
  const [otherMemo, setOtherMemo] = useState("");

  const [summary, setSummary]             = useState<TaskSummary | null>(null);
  const [incomplete, setIncomplete]       = useState<DashboardTaskRow[]>([]);
  const [incompleteTotal, setIncompleteTotal] = useState(0);
  const [approvals, setApprovals]         = useState<DashboardTaskRow[]>([]);
  const [approvalTotal, setApprovalTotal] = useState(0);
  const [loading, setLoading]             = useState(true);
  const [loadError, setLoadError]         = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      tasksApi.summary(),
      tasksApi.list({ page: 1, page_size: INCOMPLETE_PAGE_SIZE }),
      tasksApi.list({ task_type: "REVIEW_ANALYSIS", page: 1, page_size: APPROVAL_PAGE_SIZE }),
    ])
      .then(([counts, all, review]) => {
        if (cancelled) return;
        setSummary(counts);
        setIncomplete(all.items.map(toDashboardTaskRow));
        setIncompleteTotal(all.meta.total);
        setApprovals(review.items.map(toDashboardTaskRow));
        setApprovalTotal(review.meta.total);
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "업무 목록을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const stats = toFollowUpStats(summary);

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5" style={{ maxWidth: "1100px" }}>
        <div>
          <h1 className="text-[22px] font-semibold text-[#172033]">후속 관리</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">진행 중인 사례의 후속 상담 및 미처리 업무를 확인하세요</p>
        </div>

        {loadError && (
          <div className="bg-[#FEF2F2] border border-[#FECACA] rounded-[8px] px-4 py-3 text-[13px] text-red-600">{loadError}</div>
        )}

        {/* Stat strip */}
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="grid divide-x divide-[#E2E8F0]" style={{ gridTemplateColumns: `repeat(${stats.length}, 1fr)` }}>
            {stats.map(s => (
              <div key={s.label} className="px-5 py-4 flex items-center gap-3">
                <div className="w-9 h-9 rounded-[6px] flex items-center justify-center shrink-0" style={{ background: `${s.color}18` }}>
                  <span className="text-[16px] font-bold" style={{ color: s.color }}>{loading && s.fromServer ? "…" : s.value}</span>
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
              <div className="px-5 py-4 text-[12px] text-[#94A3B8]">
                여러 사례에 걸친 상담 일정 조회가 아직 서버에 없습니다.
              </div>
            </div>

            {/* 대기 상담 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0]">
                <span className="text-[13px] font-semibold text-[#172033]">후속상담 예정</span>
              </div>
              <div className="px-5 py-4 text-[12px] text-[#94A3B8]">
                후속상담 일정은 아직 서버에 없습니다.
              </div>
            </div>

            {/* 승인 대기 / 반려 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
                <span className="text-[13px] font-semibold text-[#172033]">승인 현황</span>
                {!loading && !loadError && approvalTotal > approvals.length && (
                  <span className="text-[11px] text-[#94A3B8]">최근 {approvals.length}건 / 전체 {approvalTotal}건</span>
                )}
              </div>
              {approvals.map(a => (
                <button
                  key={a.sessionId}
                  onClick={() => navigate(a.link)}
                  className="w-full text-left px-5 py-2.5 flex items-center gap-3 border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors"
                >
                  <span className="px-1.5 py-0.5 text-[10px] font-bold text-[#1D4ED8] bg-[#EFF6FF] border border-[#BFDBFE] rounded">승인 대기</span>
                  <span className="text-[13px] text-[#172033] flex-1">{a.childName} · {a.sessionNumber}회기 상담 요약</span>
                  {a.isOverdue && <OverdueTag />}
                  <span className="text-[11px] font-mono text-[#94A3B8]">{a.waitingSince}</span>
                </button>
              ))}
              {loading && (
                <div className="px-5 py-2.5 text-[12px] text-[#94A3B8] border-b border-[#F1F5F9]">불러오는 중...</div>
              )}
              {!loading && !loadError && approvals.length === 0 && (
                <div className="px-5 py-2.5 text-[12px] text-[#94A3B8] border-b border-[#F1F5F9]">승인을 기다리는 상담 요약이 없습니다.</div>
              )}
              <div className="px-5 py-2.5 flex items-center gap-3">
                <span className="px-1.5 py-0.5 text-[10px] font-bold text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded">반려</span>
                <span className="text-[12px] text-[#94A3B8] flex-1">반려 기록은 아직 서버에 없습니다.</span>
              </div>
            </div>
          </div>

          {/* Right column */}
          <div className="col-span-2 space-y-5">
            <p className="text-[12px] text-[#94A3B8]">다음 상담일 · 확인사항 · 기타 메모는 아직 서버에 저장되지 않습니다.</p>

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
              <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
                <span className="text-[13px] font-semibold text-[#172033]">미완료 업무</span>
                {!loading && !loadError && incompleteTotal > incomplete.length && (
                  <span className="text-[11px] text-[#94A3B8]">오래된 {incomplete.length}건 / 전체 {incompleteTotal}건</span>
                )}
              </div>
              <div className="divide-y divide-[#F1F5F9]">
                {incomplete.map(t => (
                  <button
                    key={t.sessionId}
                    onClick={() => navigate(t.link)}
                    className="w-full text-left flex items-center gap-2.5 px-5 py-2.5 hover:bg-[#F8FAFC] transition-colors"
                  >
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.isOverdue ? "bg-[#DC2626]" : "bg-[#CBD5E1]"}`} />
                    <span className="text-[13px] text-[#172033] flex-1">{t.caseNumber} {t.sessionNumber}회기 {t.taskLabel}</span>
                    {t.isOverdue && <OverdueTag />}
                  </button>
                ))}
                {loading && (
                  <div className="px-5 py-2.5 text-[12px] text-[#94A3B8]">불러오는 중...</div>
                )}
                {!loading && !loadError && incomplete.length === 0 && (
                  <div className="px-5 py-2.5 text-[12px] text-[#94A3B8]">미완료 업무가 없습니다.</div>
                )}
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
