import { useParams, useNavigate } from "react-router";
import { CASES } from "../data/cases";
import { SESSIONS } from "../data/mockData";
import { RiskBadge, AbuseBadge, StatusLabel } from "../components/ui/Badges";
import Breadcrumb from "../components/ui/Breadcrumb";
import { useState, useMemo } from "react";
import UploadModal from "../components/ui/UploadModal";

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

  const c = CASES.find(x => x.id === caseId);
  const sessions = SESSIONS.filter(s => s.caseId === caseId).sort((a, b) => b.date.localeCompare(a.date));

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

  if (!c) {
    return (
      <div className="flex items-center justify-center h-full text-[#94A3B8]">
        사례를 찾을 수 없습니다.
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
            { label: "문서 작성",   done: sessions.some(s => s.aiStatus === "검토완료") },
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
                    <p>아동이 가정 내 상황에 대한 불안감을 표현하였으며, 신체적 증상에 대한 호소가 있었음. 보호자와의 관계에서 지속적인 긴장이 관찰됨. 아동의 위축 행동이 이전 회차 대비 증가하였음.</p>
                  </div>
                  <div>
                    <p className="text-[12px] font-semibold text-[#64748B] mb-1">다음 회차 계획</p>
                    <p>보호자 면담 예약 및 추가 심리 검사 검토 필요.</p>
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
