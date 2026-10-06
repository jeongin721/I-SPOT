import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router";
import Breadcrumb from "../components/ui/Breadcrumb";
import { cases as casesApi } from "../api/endpoints";
import { describeApiError, toUiCaseDetail, type CaseWithId } from "../api/adapters";

// 사례는 Backend(GET /cases/{id})에서 오고, 회기 등록은 POST /cases/{id}/sessions 로 저장한다.
// 주소의 caseId 는 Backend UUID 다. 상담 유형 · 상담 방식은 Backend 에 아직 없어 화면에만 있고 보내지 않는다.


/** 오늘 날짜(YYYY-MM-DD). 화면 표시용이라 사용자의 시간대 기준이다. */
function todayLabel(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export default function PreSessionPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [c, setCase]              = useState<CaseWithId | null>(null);
  const [loading, setLoading]     = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving]       = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const nextSession = c ? c.sessionCount + 1 : 1;

  const [type, setType]   = useState<string>("정기상담");
  const [method, setMethod] = useState<string>("개인면담");
  const [place, setPlace] = useState("");
  const [memo, setMemo]   = useState("");

  useEffect(() => {
    if (!caseId) return;

    let cancelled = false;

    setLoading(true);
    setLoadError(null);

    casesApi
      .get(caseId)
      .then((detail) => {
        if (!cancelled) setCase(toUiCaseDetail(detail));
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "사례를 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId]);

  async function handleRegister() {
    if (!caseId || saving) return;

    setSaving(true);
    setSaveError(null);
    try {
      // 회차 번호(session_number)는 Backend 가 매긴다. 상담 유형 · 방식은 Backend 에 없어 보내지 않는다.
      await casesApi.createSession(caseId, {
        consulted_at: new Date().toISOString(),
        location: place.trim() || null,
        memo: memo.trim() || null,
      });
      navigate(`/cases/${caseId}`);
    } catch (caught) {
      setSaveError(describeApiError(caught, "상담 등록에 실패했습니다. 잠시 후 다시 시도해 주세요."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-full text-[#94A3B8]">사례를 불러오는 중...</div>;
  }

  if (loadError || !c) {
    return <div className="flex items-center justify-center h-full text-[#94A3B8]">{loadError ?? "사례를 찾을 수 없습니다."}</div>;
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
          <p className="text-[13px] text-[#64748B] mt-0.5">상담 정보를 입력하고 자료를 업로드하세요</p>
        </div>

        {/* Read-only info */}
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
          <h2 className="text-[13px] font-semibold text-[#172033] mb-4">기본 정보</h2>
          <div className="grid grid-cols-2 gap-4 text-[13px]">
            {[
              ["아동명", c.childName],
              ["사례 ID", c.id],
              ["예정 회차", `${nextSession}회차`],
              ["날짜", todayLabel()],
              ["담당 상담사", c.counselor],
              ["위험도", !c.riskLevel ? "—" : c.riskLevel === "high" ? "확인 필요" : c.riskLevel === "mid" ? "확인 중" : "확인 완료"],
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

        {saveError && (
          <p className="text-[12px] text-red-600">{saveError}</p>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={() => navigate(-1)}
            className="px-5 py-2.5 border border-[#E2E8F0] text-[#64748B] text-[13px] font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleRegister}
            disabled={saving}
            className="px-5 py-2.5 bg-[#2563EB] text-white text-[13px] font-semibold rounded-[6px] hover:bg-[#1D4ED8] transition-colors disabled:opacity-60"
          >
            {saving ? "등록 중..." : "상담 등록 완료"}
          </button>
        </div>
      </div>
    </div>
  );
}
