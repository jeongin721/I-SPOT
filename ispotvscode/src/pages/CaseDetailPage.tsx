import { useParams, useNavigate } from "react-router";
import type { Session as UiSession } from "../data/mockData";
import { RiskBadge, AbuseBadge, StatusLabel } from "../components/ui/Badges";
import Breadcrumb from "../components/ui/Breadcrumb";
import { useState, useMemo, useEffect } from "react";
import UploadModal from "../components/ui/UploadModal";
import { cases as casesApi, summary as summaryApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import { toUiCaseDetail, toUiSession, type CaseWithId } from "../api/adapters";
import type { Summary } from "../api/types";

// 사례와 회기 목록은 Backend(GET /cases/{id}, GET /cases/{id}/sessions)에서 온다.
// 주소의 caseId 는 Backend UUID 이고, 화면에 보이는 사례번호(C-2026-0001)는 응답의 case_number 다.
// 학대 유형 · 키워드 · 위험도 · 상담 유형 · 소요 시간은 아직 Backend 에 없어 adapters 의 기본값으로 보인다.
const SESSION_PAGE_SIZE = 100;

function loadErrorMessage(caught: unknown, fallback: string): string {
  if (!(caught instanceof ApiError)) return fallback;
  if (caught.isForbidden) return "권한이 없거나 없는 사례입니다.";
  return caught.message;
}

const STT_STATUS_CFG: Record<string, string> = {
  "처리중":   "border-[#94A3B8] text-[#475569]",
  "검수필요": "border-[#64748B] text-[#172033] font-semibold",
  "검수완료": "border-[#CBD5E1] text-[#475569]",
  "분석완료": "border-[#CBD5E1] text-[#475569]",
};

interface MockFile {
  id: string;
  name: string;
  type: "음성" | "문서";
  session: number;
  uploadDate: string;
  uploader: string;
  status: string;
}

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"overview" | "sessions" | "documents">("overview");
  const [showUpload, setShowUpload] = useState(false);
  const [extraFiles, setExtraFiles] = useState<MockFile[]>([]);
  const [c, setCase]                = useState<CaseWithId | null>(null);
  const [sessions, setSessions]     = useState<UiSession[]>([]);
  const [loading, setLoading]       = useState(true);
  const [loadError, setLoadError]   = useState<string | null>(null);
  // 최근 회기의 요약(GET /sessions/{id}/summary). 아직 분석 · 승인 전이면 null.
  const [latestSummary, setLatestSummary] = useState<Summary | null>(null);

  useEffect(() => {
    if (!caseId) return;

    let cancelled = false;

    setLoading(true);
    setLoadError(null);
    setLatestSummary(null);

    Promise.all([
      casesApi.get(caseId),
      casesApi.listSessions(caseId, { page: 1, page_size: SESSION_PAGE_SIZE }),
    ])
      .then(([detail, page]) => {
        if (cancelled) return;
        // Backend 가 최신 회기(session_number 내림차순)부터 주므로 다시 정렬하지 않는다.
        const uiSessions = page.items.map((s) =>
          toUiSession(s, detail.case_number, { counselorName: detail.counselor_name ?? undefined }),
        );
        setCase(toUiCaseDetail(detail));
        setSessions(uiSessions);

        const latest = uiSessions[0];
        if (!latest) return;

        // 요약은 없을 수 있으므로(회기 등록 직후 등) 실패해도 화면은 그대로 둔다.
        summaryApi
          .get(latest.id)
          .then((envelope) => {
            if (!cancelled) setLatestSummary(envelope.summary);
          })
          .catch(() => {
            if (!cancelled) setLatestSummary(null);
          });
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(loadErrorMessage(caught, "사례를 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const mockFiles = useMemo<MockFile[]>(() => {
    if (!c) return [];
    const files: MockFile[] = [];
    const completedSessions = sessions.filter(s => s.sttStatus === "분석완료" || s.sttStatus === "검수완료");
    completedSessions.slice(0, 3).forEach(s => {
      files.push({ id: `f-audio-${s.id}`, name: `상담_${s.sessionNumber}회차.m4a`, type: "음성", session: s.sessionNumber, uploadDate: s.date, uploader: s.counselor, status: s.sttStatus === "분석완료" ? "분석 완료" : "검수 완료" });
      files.push({ id: `f-doc-${s.id}`, name: `상담일지_${s.sessionNumber}회차.pdf`, type: "문서", session: s.sessionNumber, uploadDate: s.date, uploader: s.counselor, status: "등록 완료" });
    });
    return files;
  }, [c, sessions]);

  const allFiles = useMemo(() => [...extraFiles, ...mockFiles], [extraFiles, mockFiles]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[#94A3B8]">
        사례를 불러오는 중...
      </div>
    );
  }

  if (loadError || !c) {
    return (
      <div className="flex items-center justify-center h-full text-[#94A3B8]">
        {loadError ?? "사례를 찾을 수 없습니다."}
      </div>
    );
  }

  return (
    <>
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
        {tab === "overview" && (() => {
          const latestSession = sessions[0];
          const progressSteps = [
            { label: "자료 등록",   done: c.sessionCount > 0 },
            { label: "자료 검수",   done: sessions.some(s => s.sttStatus === "검수완료" || s.sttStatus === "분석완료") },
            { label: "AI 분석",     done: sessions.some(s => s.sttStatus === "분석완료") },
            // Backend 상태로는 "검토완료" 가 나오지 않고 승인되면 "상담사검토완료" 가 된다.
            { label: "문서 작성",   done: sessions.some(s => s.aiStatus === "검토완료" || s.aiStatus === "상담사검토완료") },
            { label: "후속 업무",   done: false },
          ];
          const currentStep = progressSteps.filter(s => s.done).length;

          return (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-5">
              <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
                <h2 className="text-[14px] font-semibold text-[#172033] mb-4">아동 기본정보</h2>
                <div className="space-y-2.5 text-[14px]">
                  <div className="flex gap-3"><span className="text-[#94A3B8] w-28 shrink-0">이름</span><span className="text-[#172033] font-medium">{c.childName}</span></div>
                  <div className="flex gap-3"><span className="text-[#94A3B8] w-28 shrink-0">연령</span><span className="text-[#172033] font-medium">{c.age}세</span></div>
                  <div className="flex gap-3"><span className="text-[#94A3B8] w-28 shrink-0">보호자</span><span className="text-[#172033] font-medium">{c.guardian}</span></div>
                  <div className="flex gap-3"><span className="text-[#94A3B8] w-28 shrink-0">담당 상담사</span><span className="text-[#172033] font-medium">{c.counselor}</span></div>
                  <div className="flex gap-3"><span className="text-[#94A3B8] w-28 shrink-0">상담 회차</span><span className="text-[#172033] font-medium">{c.sessionCount}회</span></div>
                  <div className="flex gap-3"><span className="text-[#94A3B8] w-28 shrink-0">최근 상담</span><span className="text-[#172033] font-mono">{c.lastSession}</span></div>
                </div>
              </div>
              <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
                <h2 className="text-[14px] font-semibold text-[#172033] mb-4">주요 위험요인</h2>
                <div className="mb-4">
                  <p className="text-[12px] text-[#94A3B8] mb-2">학대 유형</p>
                  <div className="flex gap-1.5 flex-wrap">{c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}</div>
                </div>
                <div>
                  <p className="text-[12px] text-[#94A3B8] mb-2">주요 키워드</p>
                  <div className="flex gap-1.5 flex-wrap">
                    {c.keywords.map(k => (
                      <span key={k} className="text-[12px] text-[#475569] bg-[#F1F5F9] border border-[#E2E8F0] px-2 py-0.5 rounded">#{k}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 상담 진행 상황 */}
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
              <h2 className="text-[14px] font-semibold text-[#172033] mb-4">현재 상담 진행 상황</h2>
              <div className="flex items-center gap-0">
                {progressSteps.map((step, i) => (
                  <div key={step.label} className="flex items-center flex-1">
                    <div className="flex flex-col items-center flex-1">
                      <div className="flex items-center gap-2 mb-1.5">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 border"
                          style={{
                            background: step.done ? "#172033" : i === currentStep ? "#F8FAFC" : "#F8FAFC",
                            borderColor: step.done ? "#172033" : i === currentStep ? "#64748B" : "#E2E8F0",
                          }}>
                          {step.done
                            ? <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                            : <span className="text-[10px] font-bold" style={{ color: i === currentStep ? "#172033" : "#CBD5E1" }}>{i + 1}</span>
                          }
                        </div>
                      </div>
                      <span className="text-[12px] text-center" style={{ color: step.done ? "#172033" : i === currentStep ? "#475569" : "#94A3B8", fontWeight: i === currentStep ? 600 : step.done ? 500 : 400 }}>
                        {step.label}
                      </span>
                      {i === currentStep && (
                        <span className="text-[11px] text-[#64748B] mt-0.5 border border-[#CBD5E1] rounded px-1.5 py-0.5">진행 중</span>
                      )}
                    </div>
                    {i < progressSteps.length - 1 && (
                      <div className="h-px flex-none mx-1 shrink-0" style={{ width: "16px", background: step.done ? "#172033" : "#E2E8F0" }} />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 최근 상담 요약본 */}
            {latestSession && (
              <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-[14px] font-semibold text-[#172033]">최근 상담 요약본</h2>
                  <span className="text-[12px] text-[#94A3B8] font-mono">{latestSession.date} · {latestSession.sessionNumber}회차</span>
                </div>
                <div className="space-y-3 text-[14px] text-[#172033] leading-relaxed">
                  <div>
                    <p className="text-[12px] font-semibold text-[#64748B] mb-1">상담 개요</p>
                    <p>{latestSession.type} 진행. {latestSession.duration} 소요. 담당: {latestSession.counselor}</p>
                  </div>
                  <div>
                    <p className="text-[12px] font-semibold text-[#64748B] mb-1">주요 내용</p>
                    {/* 요약은 AI 분석 뒤 상담사가 검수한 것(GET /sessions/{id}/summary). 아직 없으면 그렇다고 보여 준다. */}
                    {latestSummary ? (
                      <>
                        <p>{latestSummary.overview}</p>
                        {latestSummary.key_points.length > 0 && (
                          <ul className="list-disc pl-5 mt-1 space-y-0.5">
                            {latestSummary.key_points.map((point, i) => <li key={i}>{point}</li>)}
                          </ul>
                        )}
                      </>
                    ) : (
                      <p className="text-[#94A3B8]">아직 작성된 요약이 없습니다. AI 분석과 상담사 검수가 끝나면 여기에 보입니다.</p>
                    )}
                  </div>
                  <div>
                    <p className="text-[12px] font-semibold text-[#64748B] mb-1">다음 회차 계획</p>
                    {/* 다음 회차 계획은 Backend 에 아직 없다. */}
                    <p className="text-[#94A3B8]">—</p>
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-[#F1F5F9]">
                  <button
                    onClick={() => navigate(`/cases/${caseId}/sessions/${latestSession.id}/transcript`)}
                    className="text-[13px] text-[#2563EB] hover:text-[#1D4ED8] font-medium transition-colors"
                  >
                    원문 보기 →
                  </button>
                </div>
              </div>
            )}
          </div>
          );
        })()}

        {tab === "sessions" && (
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
            <table className="w-full">
              <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                <tr>
                  {["날짜", "회차", "유형", "상담사", "시간", "STT 상태", "상태", ""].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-[12px] font-semibold text-[#64748B] whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                    <td className="px-4 py-3 text-[13px] font-mono text-[#475569]">{s.date}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[#172033]">{s.sessionNumber}회차</td>
                    <td className="px-4 py-3 text-[13px] text-[#475569]">{s.type}</td>
                    <td className="px-4 py-3 text-[13px] text-[#475569]">{s.counselor}</td>
                    <td className="px-4 py-3 text-[13px] text-[#475569]">{s.duration}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded border text-[12px] bg-white ${STT_STATUS_CFG[s.sttStatus] ?? "border-[#E2E8F0] text-[#64748B]"}`}>
                        {s.sttStatus}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[13px] text-[#64748B]">{s.aiStatus}</td>
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
                {sessions.length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-[13px] text-[#94A3B8]">상담 기록이 없습니다.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {tab === "documents" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-[15px] font-semibold text-[#172033]">사례 자료</h2>
                <p className="text-[12px] text-[#64748B] mt-0.5">이 사례에 연결된 음성 및 문서 파일</p>
              </div>
              <button
                onClick={() => setShowUpload(true)}
                className="flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium text-white bg-[#2563EB] hover:bg-[#1D4ED8] rounded-[6px] transition-colors"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                새 문서 업로드
              </button>
            </div>
            <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
              <table className="w-full">
                <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                  <tr>
                    {["파일명", "자료 유형", "연결 상담", "업로드일", "등록자", "상태", "작업"].map(h => (
                      <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {allFiles.map(f => (
                    <tr key={f.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                      <td className="px-4 py-3 text-[13px] text-[#172033] font-medium">{f.name}</td>
                      <td className="px-4 py-3">
                        <span className="text-[12px] px-2 py-0.5 rounded border border-[#CBD5E1] text-[#475569] bg-white font-medium">
                          {f.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[12px] text-[#64748B]">{f.session}회차</td>
                      <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{f.uploadDate}</td>
                      <td className="px-4 py-3 text-[12px] text-[#64748B]">{f.uploader}</td>
                      <td className="px-4 py-3 text-[11px] text-[#64748B]">{f.status}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => alert("실제 파일이 연결되지 않은 목업입니다.")}
                          className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium"
                        >
                          다운로드
                        </button>
                      </td>
                    </tr>
                  ))}
                  {allFiles.length === 0 && (
                    <tr><td colSpan={7} className="px-4 py-10 text-center text-[13px] text-[#94A3B8]">등록된 자료가 없습니다.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>

    {showUpload && (
      <UploadModal
        onClose={() => setShowUpload(false)}
        preSelectedCaseId={caseId}
        preSelectedType="document"
        onUploaded={info => {
          const newFile: MockFile = {
            id: `f-new-${Date.now()}`,
            name: info.fileName,
            type: info.type === "audio" ? "음성" : "문서",
            session: info.sessionNumber,
            uploadDate: new Date().toISOString().slice(0, 10),
            uploader: c?.counselor ?? "",
            status: "등록 완료",
          };
          setExtraFiles(prev => [newFile, ...prev]);
        }}
      />
    )}
    </>
  );
}
