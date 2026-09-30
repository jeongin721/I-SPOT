import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router";
import type { Session as UiSession } from "../data/mockData";
import Breadcrumb from "../components/ui/Breadcrumb";
import { cases as casesApi } from "../api/endpoints";
import { describeApiError, toUiCaseDetail, toUiSession, type CaseWithId, type SessionWithStatus } from "../api/adapters";

// 사례와 회기 목록은 Backend(GET /cases/{id}, GET /cases/{id}/sessions)에서 온다.
// 주소의 caseId 는 Backend UUID 다. 녹음 길이 · 상담사(회기 단위)는 아직 Backend 에 없어 "—" 로 보인다.
const SESSION_PAGE_SIZE = 100;


// 칸 문구(sttLabel · aiLabel)로 색을 고른다. 대기 상태(음성 업로드 대기 · 원문 변환 대기)는 기본 색으로 보인다.
const STT_CFG: Record<string, string> = {
  "처리중":   "bg-blue-50 text-blue-700",
  "검수필요": "bg-amber-50 text-amber-700",
  "검수완료": "bg-green-50 text-green-700",
  "분석완료": "bg-green-50 text-green-700",
  "원문 변환 실패": "bg-red-50 text-red-700",
};

const AI_CFG: Record<string, string> = {
  "대기중":   "text-[#94A3B8]",
  "분석중":   "text-blue-600",
  "검토필요": "text-amber-600 font-semibold",
  "검토완료": "text-green-600",
  "상담사검토완료": "text-green-700 font-semibold",
  "AI 분석 실패": "text-red-600 font-semibold",
};

export default function SessionListPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [c, setCase]              = useState<CaseWithId | null>(null);
  const [sessions, setSessions]   = useState<SessionWithStatus[]>([]);
  const [loading, setLoading]     = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;

    let cancelled = false;

    setLoading(true);
    setLoadError(null);

    Promise.all([
      casesApi.get(caseId),
      casesApi.listSessions(caseId, { page: 1, page_size: SESSION_PAGE_SIZE }),
    ])
      .then(([detail, page]) => {
        if (cancelled) return;
        setCase(toUiCaseDetail(detail));
        // Backend 가 최신 회기(session_number 내림차순)부터 주므로 다시 정렬하지 않는다.
        setSessions(page.items.map((s) =>
          toUiSession(s, detail.case_number, { counselorName: detail.counselor_name ?? undefined }),
        ));
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

  if (loading) return <div className="flex items-center justify-center h-full text-[#94A3B8]">사례를 불러오는 중...</div>;
  if (loadError || !c) return <div className="flex items-center justify-center h-full text-[#94A3B8]">{loadError ?? "사례를 찾을 수 없습니다."}</div>;

  // AI 분석은 회기당 하나(GET /sessions/{id}/analysis)라 분석 화면 주소에도 회기 UUID 를 쓴다.
  // 검수가 끝난 회기는 모두 AI 분석 화면으로 갈 수 있다. 요청 전 · 실패면 "AI 분석"(요청 · 다시 요청),
  // 요청 뒤면 "AI 검토". 승인된 회기는 결과 보기와 상담일지 작성으로 간다.
  function hasAnalysis(s: UiSession) {
    return s.aiStatus === "분석중" || s.aiStatus === "검토필요";
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <Breadcrumb items={[
          { label: "STT 검수", to: "/stt-cases" },
          { label: c.childName },
          { label: "녹음 목록" },
        ]} />

        <div>
          <h1 className="text-[22px] font-semibold text-[#172033]">{c.childName} — 상담 녹음 목록</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">{c.id} · 전체 {sessions.length}회차</p>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["날짜", "시간", "회차", "상담사", "녹음 길이", "STT 상태", "상태", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => {
                return (
                  <tr key={s.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                    <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{s.date}</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.time}</td>
                    <td className="px-4 py-3 text-[13px] text-[#172033]">{s.sessionNumber}회차</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.counselor}</td>
                    <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.duration}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${STT_CFG[s.sttLabel] ?? "bg-slate-50 text-slate-600"}`}>
                        {s.sttLabel}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-[12px] ${AI_CFG[s.aiLabel] ?? "text-[#64748B]"}`}>{s.aiLabel}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {s.sttStatus === "검수필요" && (
                          <button
                            onClick={() => navigate(`/cases/${caseId}/sessions/${s.id}/transcript`)}
                            className="px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-200 text-[11px] font-medium rounded-[6px] hover:bg-amber-100 transition-colors"
                          >
                            STT 검수
                          </button>
                        )}
                        {s.sttStatus === "검수완료" && (
                          <button
                            onClick={() => navigate(`/cases/${caseId}/analyses/${s.id}`)}
                            className="px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 text-[11px] font-medium rounded-[6px] hover:bg-blue-100 transition-colors"
                          >
                            {hasAnalysis(s) ? "AI 검토" : "AI 분석"}
                          </button>
                        )}
                        {(s.sttStatus === "분석완료") && (
                          <>
                            <button
                              onClick={() => navigate(`/cases/${caseId}/analyses/${s.id}`)}
                              className="px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 text-[11px] font-medium rounded-[6px] hover:bg-blue-100 transition-colors"
                            >
                              AI 결과
                            </button>
                            <button
                              onClick={() => navigate(`/cases/${caseId}/sessions/${s.id}/document`)}
                              className="px-2.5 py-1 bg-white text-[#172033] border border-[#E2E8F0] text-[11px] font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
                            >
                              상담일지
                            </button>
                            <button
                              onClick={() => navigate(`/cases/${caseId}/sessions/${s.id}/transcript`)}
                              className="text-[11px] text-[#94A3B8] hover:text-[#64748B]"
                            >
                              원문
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {sessions.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-[13px] text-[#94A3B8]">상담 기록이 없습니다.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
