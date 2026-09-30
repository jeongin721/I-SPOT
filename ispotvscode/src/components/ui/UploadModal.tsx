import { useState, useMemo, useRef } from "react";
import { CASES } from "../../data/cases";
import { SESSIONS } from "../../data/mockData";

type UploadType = "audio" | "document";

interface UploadModalProps {
  onClose: () => void;
  preSelectedCaseId?: string;
  preSelectedType?: UploadType;
  onUploaded?: (info: { caseId: string; sessionNumber: number; type: UploadType; fileName: string }) => void;
}

const AUDIO_ACCEPT = ".mp3,.m4a,.wav";
const DOC_ACCEPT   = ".pdf,.hwp,.hwpx,.txt,.docx";

export default function UploadModal({ onClose, preSelectedCaseId, preSelectedType, onUploaded }: UploadModalProps) {
  const skipCaseStep = !!preSelectedCaseId;
  const skipTypeStep = !!preSelectedType;

  // derive initial step
  const initialStep = skipCaseStep ? 1 : 0;

  const [step, setStep]               = useState(initialStep);
  const [selectedCaseId, setSelectedCaseId] = useState(preSelectedCaseId ?? "");
  const [query, setQuery]             = useState("");
  const [sessionChoice, setSessionChoice] = useState<number | "new">("new");
  const [uploadType, setUploadType]   = useState<UploadType | "">(preSelectedType ?? "");
  const [fileName, setFileName]       = useState("");
  const [uploading, setUploading]     = useState(false);
  const [done, setDone]               = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const selectedCase = CASES.find(c => c.id === selectedCaseId);
  const caseSessions = selectedCase
    ? SESSIONS.filter(s => s.caseId === selectedCase.id).sort((a, b) => b.sessionNumber - a.sessionNumber)
    : [];
  const nextSessionNumber = selectedCase ? selectedCase.sessionCount + 1 : 1;

  const filteredCases = useMemo(() =>
    CASES.filter(c => !query || c.childName.includes(query) || c.id.toLowerCase().includes(query.toLowerCase()))
      .sort((a, b) => b.riskScore - a.riskScore),
    [query]
  );

  function goNext() {
    if (step === 0) { setStep(1); return; }
    if (step === 1) { setStep(skipTypeStep ? 3 : 2); return; }
    if (step === 2) { setStep(3); return; }
  }

  function goBack() {
    if (step === 3 && skipTypeStep) { setStep(1); return; }
    if (step === 3) { setStep(2); return; }
    if (step === 2) { setStep(1); return; }
    if (step === 1 && !skipCaseStep) { setStep(0); return; }
    onClose();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) setFileName(file.name);
  }

  function handleUpload() {
    if (!fileName) return;
    setUploading(true);
    setTimeout(() => {
      setUploading(false);
      setDone(true);
      const sessionNum = sessionChoice === "new" ? nextSessionNumber : sessionChoice;
      onUploaded?.({ caseId: selectedCaseId, sessionNumber: sessionNum, type: (uploadType || preSelectedType) as UploadType, fileName });
    }, 1000);
  }

  const stepLabels = skipCaseStep
    ? ["상담 회차", "업로드 유형", "파일 선택"]
    : ["사례 선택", "상담 회차", "업로드 유형", "파일 선택"];

  const displayStep = skipCaseStep ? step : step;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white border border-[#E2E8F0] rounded-[10px] w-[520px] max-h-[90vh] overflow-hidden flex flex-col shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0]">
          <div>
            <h2 className="text-[16px] font-semibold text-[#172033]">상담 자료 업로드</h2>
            {!done && (
              <div className="flex items-center gap-2 mt-2">
                {stepLabels.map((label, i) => {
                  const idx = skipCaseStep ? i + 1 : i;
                  const active = idx === step;
                  const past = idx < step;
                  return (
                    <div key={label} className="flex items-center gap-1.5">
                      <div className="flex items-center gap-1">
                        <span className="w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center shrink-0"
                          style={{ background: past ? "#16A34A" : active ? "#2563EB" : "#E2E8F0", color: past || active ? "white" : "#94A3B8" }}>
                          {past ? "✓" : i + 1}
                        </span>
                        <span className="text-[11px] font-medium" style={{ color: active ? "#2563EB" : past ? "#16A34A" : "#94A3B8" }}>{label}</span>
                      </div>
                      {i < stepLabels.length - 1 && <span className="text-[#E2E8F0] text-[10px]">›</span>}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <button onClick={onClose} className="text-[#94A3B8] hover:text-[#64748B] transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">

          {/* Done state */}
          {done && (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <div className="w-12 h-12 rounded-full bg-green-50 border border-green-200 flex items-center justify-center">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              </div>
              <p className="text-[15px] font-semibold text-[#172033]">업로드 완료</p>
              <p className="text-[13px] text-[#64748B] text-center">
                <span className="font-medium">{selectedCase?.childName}</span>의 자료가 사례에 연결되었습니다.
              </p>
              <button onClick={onClose} className="mt-2 px-5 py-2 bg-[#2563EB] text-white text-[13px] font-medium rounded-[6px] hover:bg-[#1D4ED8] transition-colors">
                닫기
              </button>
            </div>
          )}

          {/* Step 0: 사례 선택 */}
          {!done && step === 0 && (
            <div className="space-y-4">
              <p className="text-[13px] font-semibold text-[#172033]">연결할 사례 선택</p>
              <div className="relative">
                <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input value={query} onChange={e => setQuery(e.target.value)} placeholder="이름 또는 사례번호 검색"
                  className="w-full pl-8 pr-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] bg-[#F8FAFC]" />
              </div>
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {filteredCases.map(c => (
                  <label key={c.id} className="flex items-start gap-3 p-3 border rounded-[6px] cursor-pointer transition-all"
                    style={{ borderColor: selectedCaseId === c.id ? "#2563EB" : "#E2E8F0", background: selectedCaseId === c.id ? "#EFF6FF" : "white" }}>
                    <input type="radio" name="case-select" value={c.id} checked={selectedCaseId === c.id}
                      onChange={() => setSelectedCaseId(c.id)} className="mt-0.5 accent-[#2563EB]" />
                    <div>
                      <p className="text-[13px] font-semibold text-[#172033]">{c.childName}</p>
                      <p className="text-[11px] font-mono text-[#94A3B8]">{c.id}</p>
                      <p className="text-[11px] text-[#64748B]">담당 상담사 {c.counselor} · {c.sessionCount}회차</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Step 1: 상담 회차 */}
          {!done && step === 1 && selectedCase && (
            <div className="space-y-4">
              <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] px-4 py-3">
                <p className="text-[13px] font-semibold text-[#172033]">{selectedCase.childName}</p>
                <p className="text-[11px] font-mono text-[#94A3B8]">{selectedCase.id}</p>
              </div>
              <p className="text-[13px] font-semibold text-[#172033]">연결할 상담 회차</p>
              <div className="space-y-2">
                <label className="flex items-center gap-3 p-3 border rounded-[6px] cursor-pointer transition-all"
                  style={{ borderColor: sessionChoice === "new" ? "#2563EB" : "#E2E8F0", background: sessionChoice === "new" ? "#EFF6FF" : "white" }}>
                  <input type="radio" name="session-choice" checked={sessionChoice === "new"} onChange={() => setSessionChoice("new")} className="accent-[#2563EB]" />
                  <div>
                    <p className="text-[13px] font-semibold text-[#172033]">새 상담 회차 ({nextSessionNumber}회차)</p>
                    <p className="text-[11px] text-[#64748B]">신규 회차로 등록합니다</p>
                  </div>
                </label>
                {caseSessions.slice(0, 5).map(s => (
                  <label key={s.id} className="flex items-center gap-3 p-3 border rounded-[6px] cursor-pointer transition-all"
                    style={{ borderColor: sessionChoice === s.sessionNumber ? "#2563EB" : "#E2E8F0", background: sessionChoice === s.sessionNumber ? "#EFF6FF" : "white" }}>
                    <input type="radio" name="session-choice" checked={sessionChoice === s.sessionNumber} onChange={() => setSessionChoice(s.sessionNumber)} className="accent-[#2563EB]" />
                    <div>
                      <p className="text-[13px] font-medium text-[#172033]">{s.sessionNumber}회차</p>
                      <p className="text-[11px] text-[#94A3B8]">{s.date} · {s.type}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: 업로드 유형 */}
          {!done && step === 2 && (
            <div className="space-y-4">
              <p className="text-[13px] font-semibold text-[#172033]">업로드 유형 선택</p>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col items-center justify-center gap-2 p-6 border-2 rounded-[8px] cursor-pointer transition-all"
                  style={{ borderColor: uploadType === "audio" ? "#2563EB" : "#E2E8F0", background: uploadType === "audio" ? "#EFF6FF" : "white" }}>
                  <input type="radio" name="upload-type" checked={uploadType === "audio"} onChange={() => setUploadType("audio")} className="sr-only" />
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={uploadType === "audio" ? "#2563EB" : "#94A3B8"} strokeWidth="1.8"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                  <span className="text-[13px] font-semibold" style={{ color: uploadType === "audio" ? "#2563EB" : "#172033" }}>음성 파일</span>
                  <span className="text-[11px] text-[#94A3B8]">MP3 / M4A / WAV</span>
                </label>
                <label className="flex flex-col items-center justify-center gap-2 p-6 border-2 rounded-[8px] cursor-pointer transition-all"
                  style={{ borderColor: uploadType === "document" ? "#2563EB" : "#E2E8F0", background: uploadType === "document" ? "#EFF6FF" : "white" }}>
                  <input type="radio" name="upload-type" checked={uploadType === "document"} onChange={() => setUploadType("document")} className="sr-only" />
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={uploadType === "document" ? "#2563EB" : "#94A3B8"} strokeWidth="1.8"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  <span className="text-[13px] font-semibold" style={{ color: uploadType === "document" ? "#2563EB" : "#172033" }}>문서 파일</span>
                  <span className="text-[11px] text-[#94A3B8]">PDF / HWP / HWPX / TXT / DOCX</span>
                </label>
              </div>
            </div>
          )}

          {/* Step 3: 파일 선택 */}
          {!done && step === 3 && selectedCase && (
            <div className="space-y-4">
              {/* 연결 정보 요약 */}
              <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] p-4 space-y-2 text-[13px]">
                <div className="flex gap-3"><span className="text-[#94A3B8] w-20">연결 사례</span><span className="font-medium text-[#172033]">{selectedCase.childName} · {selectedCase.id}</span></div>
                <div className="flex gap-3"><span className="text-[#94A3B8] w-20">상담 회차</span><span className="font-medium text-[#172033]">{sessionChoice === "new" ? `${nextSessionNumber}회차 (신규)` : `${sessionChoice}회차`}</span></div>
                <div className="flex gap-3"><span className="text-[#94A3B8] w-20">자료 유형</span><span className="font-medium text-[#172033]">{(uploadType || preSelectedType) === "audio" ? "음성 파일" : "문서 파일"}</span></div>
              </div>

              {/* 파일 선택 */}
              <div>
                <p className="text-[13px] font-semibold text-[#172033] mb-2">파일 선택</p>
                <input
                  ref={fileRef}
                  type="file"
                  className="hidden"
                  accept={(uploadType || preSelectedType) === "audio" ? AUDIO_ACCEPT : DOC_ACCEPT}
                  onChange={handleFileChange}
                />
                <button
                  onClick={() => fileRef.current?.click()}
                  className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-[#E2E8F0] rounded-[8px] text-[13px] text-[#64748B] hover:border-[#2563EB] hover:text-[#2563EB] hover:bg-[#F8FAFC] transition-all"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                  파일 선택
                </button>
                {fileName && (
                  <div className="mt-2 flex items-center gap-2 px-3 py-2 bg-[#F0FDF4] border border-green-200 rounded-[6px]">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <span className="text-[12px] text-[#172033] font-medium flex-1 truncate">{fileName}</span>
                    <button onClick={() => setFileName("")} className="text-[#94A3B8] hover:text-[#64748B]">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!done && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-[#E2E8F0] bg-[#F8FAFC]">
            <button onClick={goBack} className="px-4 py-2 text-[13px] text-[#64748B] border border-[#E2E8F0] rounded-[6px] hover:bg-white transition-colors">
              {step === initialStep ? "취소" : "이전"}
            </button>
            {step < 3 ? (
              <button
                onClick={goNext}
                disabled={
                  (step === 0 && !selectedCaseId) ||
                  (step === 2 && !uploadType)
                }
                className="px-4 py-2 text-[13px] font-medium text-white bg-[#2563EB] hover:bg-[#1D4ED8] rounded-[6px] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                다음
              </button>
            ) : (
              <button
                onClick={handleUpload}
                disabled={!fileName || uploading}
                className="px-4 py-2 text-[13px] font-medium text-white bg-[#2563EB] hover:bg-[#1D4ED8] rounded-[6px] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {uploading ? "업로드 중..." : "업로드"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
