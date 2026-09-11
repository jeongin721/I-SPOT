import { useState, useEffect, useRef } from "react";
import CaseSelectorPanel from "../components/CaseSelectorPanel";
import { CASES } from "../data/cases";

type RecordState = "idle" | "recording" | "paused" | "done" | "uploading" | "processing" | "ready" | "mic-error";

interface Segment {
  id: number;
  speaker: "상담사" | "아동";
  text: string;
  time: string;
}

const DEMO_SEGMENTS: Segment[] = [
  { id: 1, speaker: "상담사", text: "오늘 어떻게 지냈어? 학교에서 재미있는 일 있었니?", time: "00:12" },
  { id: 2, speaker: "아동",   text: "그냥요... 별로 없었어요.", time: "00:18" },
  { id: 3, speaker: "상담사", text: "그렇구나. 요즘 집에서는 어때?", time: "00:26" },
  { id: 4, speaker: "아동",   text: "아빠가 또 화났어요. 저한테 소리 지르고... 많이 때렸어요.", time: "00:41" },
  { id: 5, speaker: "상담사", text: "그랬구나, 많이 힘들었겠다. 어디 다친 곳은 없어?", time: "00:55" },
  { id: 6, speaker: "아동",   text: "등이랑 팔이요. 근데 말하면 더 혼난다고 했어요.", time: "01:08" },
  { id: 7, speaker: "상담사", text: "말해줘서 고마워. 선생님이 꼭 도와줄게. 언제부터 그랬어?", time: "01:22" },
  { id: 8, speaker: "아동",   text: "엄마 없어지고 나서요. 거의 매일이에요.", time: "01:35" },
];

const STATE_LABEL: Record<RecordState, string> = {
  idle:       "녹음 대기 중",
  recording:  "녹음 중",
  paused:     "일시 정지",
  done:       "녹음 완료",
  uploading:  "파일 업로드 중...",
  processing: "STT 변환 처리 중...",
  ready:      "STT 검수 준비 완료",
  "mic-error": "마이크 오류",
};

function useUploadProgress(active: boolean) {
  const [pct, setPct] = useState(0);
  useEffect(() => {
    if (!active) { setPct(0); return; }
    setPct(0);
    const iv = setInterval(() => {
      setPct(p => {
        if (p >= 100) { clearInterval(iv); return 100; }
        return p + Math.random() * 12;
      });
    }, 200);
    return () => clearInterval(iv);
  }, [active]);
  return Math.min(Math.round(pct), 100);
}

export default function RecordingView() {
  const [selectedId, setSelectedId] = useState(CASES[0].id);
  const [state, setState] = useState<RecordState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [visibleCount, setVisibleCount] = useState(0);
  const [bars, setBars] = useState<number[]>(Array(22).fill(4));
  const [sessionNum, setSessionNum] = useState(7);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const segRef      = useRef<ReturnType<typeof setInterval> | null>(null);
  const bottomRef   = useRef<HTMLDivElement>(null);

  const uploadPct = useUploadProgress(state === "uploading");

  const selectedCase = CASES.find(c => c.id === selectedId)!;

  function reset() {
    setState("idle"); setElapsed(0); setSegments([]); setVisibleCount(0);
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (segRef.current) clearInterval(segRef.current);
  }

  function handleSelectCase(id: string) { reset(); setSelectedId(id); }

  function startRecording() {
    if (Math.random() < 0.01) { setState("mic-error"); return; }
    setState("recording");
  }

  function stopRecording() {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (segRef.current) clearInterval(segRef.current);
    setSegments(DEMO_SEGMENTS);
    setState("done");
  }

  function submitForProcessing() {
    setState("uploading");
    setTimeout(() => {
      setState("processing");
      setTimeout(() => setState("ready"), 3000);
    }, 2500);
  }

  useEffect(() => {
    if (state === "recording") {
      intervalRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
      const barsIv = setInterval(() => setBars(Array(22).fill(0).map(() => Math.floor(Math.random() * 30) + 4)), 120);
      if (visibleCount < DEMO_SEGMENTS.length) {
        segRef.current = setInterval(() => {
          setVisibleCount(v => {
            if (v < DEMO_SEGMENTS.length) { setSegments(DEMO_SEGMENTS.slice(0, v + 1)); return v + 1; }
            return v;
          });
        }, 3200);
      }
      return () => { clearInterval(intervalRef.current!); clearInterval(barsIv); clearInterval(segRef.current!); };
    }
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (segRef.current) clearInterval(segRef.current);
  }, [state]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [segments]);

  const fmtTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="flex h-full overflow-hidden">
      <CaseSelectorPanel selectedId={selectedId} onSelect={handleSelectCase} />

      <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
        <div className="p-6 space-y-5 max-w-5xl">

          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-bold text-[#172033]">상담 녹음</h1>
              <p className="text-[#64748B] text-sm mt-0.5">
                <span className="font-semibold text-[#172033]">{selectedCase.childName}</span>
                <span className="mx-1.5 text-[#94A3B8]">·</span>
                <span className="font-mono text-xs">{selectedCase.id}</span>
                <span className="mx-1.5 text-[#94A3B8]">·</span>
                {sessionNum}회차
              </p>
            </div>
            {state === "ready" && (
              <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-[6px] text-green-700 text-sm font-medium">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                STT 변환 완료 · 검수 화면으로 이동하세요
              </div>
            )}
          </div>

          {/* 마이크 오류 배너 */}
          {state === "mic-error" && (
            <div className="flex items-start gap-3 px-5 py-4 bg-[#FEF2F2] border border-[#FECACA] rounded-[6px]">
              <svg className="text-[#B91C1C] shrink-0 mt-0.5" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <div>
                <p className="font-semibold text-[#B91C1C] text-sm">마이크 접근 권한이 없습니다</p>
                <p className="text-xs text-[#B91C1C]/80 mt-0.5">브라우저 설정에서 마이크 권한을 허용한 뒤 다시 시도해 주세요.</p>
              </div>
              <button onClick={reset} className="ml-auto text-xs text-[#B91C1C] hover:text-red-900 underline shrink-0">닫기</button>
            </div>
          )}

          {/* Session info bar */}
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-3.5 flex items-center gap-6 flex-wrap text-sm">
            <div><span className="text-[#94A3B8] text-xs">대상 아동</span><p className="font-bold mt-0.5 text-[#172033]">{selectedCase.childName} · {selectedCase.age}세</p></div>
            <div className="w-px h-8 bg-[#E2E8F0]" />
            <div><span className="text-[#94A3B8] text-xs">보호자</span><p className="font-medium mt-0.5 text-[#172033]">{selectedCase.guardian}</p></div>
            <div className="w-px h-8 bg-[#E2E8F0]" />
            <div>
              <span className="text-[#94A3B8] text-xs">상담 회차</span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <input type="number" value={sessionNum} onChange={e => setSessionNum(Number(e.target.value))}
                  disabled={state !== "idle"}
                  className="w-12 px-2 py-0.5 rounded-[6px] text-[#172033] font-mono text-sm border border-[#E2E8F0] bg-[#F8FAFC] focus:outline-none disabled:opacity-60"
                />
                <span className="text-[#94A3B8] text-xs">회차</span>
              </div>
            </div>
            <div className="ml-auto text-xs text-[#94A3B8] font-mono">2026-08-21</div>
          </div>

          <div className="grid grid-cols-5 gap-5">
            {/* Controls */}
            <div className="col-span-2 space-y-4">
              <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
                <h2 className="font-semibold text-[#172033] text-sm mb-4">녹음 컨트롤</h2>

                {/* Timer */}
                <div className="text-center mb-5">
                  <div className={`text-5xl font-mono font-bold tracking-widest ${state === "recording" ? "text-red-600" : "text-[#172033]"}`}>
                    {fmtTime(elapsed)}
                  </div>
                  <div className="mt-1.5 text-xs flex items-center justify-center gap-1.5">
                    {state === "recording"
                      ? <><span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" /><span className="text-red-500">녹음 중</span></>
                      : <span className="text-[#94A3B8]">{STATE_LABEL[state]}</span>}
                  </div>
                </div>

                {/* Waveform */}
                <div className="flex items-center justify-center gap-0.5 h-10 mb-5">
                  {state === "recording"
                    ? bars.map((h, i) => <div key={i} className="w-1 bg-red-400 transition-all duration-100" style={{ height: `${h}px` }} />)
                    : Array(22).fill(0).map((_, i) => <div key={i} className="w-1 bg-[#E2E8F0]" style={{ height: "4px" }} />)
                  }
                </div>

                {/* Controls */}
                <div className="flex justify-center gap-3">
                  {state === "idle" && (
                    <button onClick={startRecording} className="flex items-center gap-2 px-6 py-2.5 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-[6px] text-sm transition-all shadow-sm">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8"/></svg>녹음 시작
                    </button>
                  )}
                  {state === "mic-error" && (
                    <button onClick={reset} className="px-5 py-2.5 border border-[#E2E8F0] text-[#64748B] font-medium rounded-[6px] text-sm hover:bg-[#F8FAFC] transition-all">다시 시도</button>
                  )}
                  {state === "recording" && (
                    <>
                      <button onClick={() => setState("paused")} className="flex items-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-semibold rounded-[6px] text-sm transition-all">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>일시정지
                      </button>
                      <button onClick={stopRecording} className="flex items-center gap-2 px-4 py-2.5 bg-slate-700 hover:bg-slate-800 text-white font-semibold rounded-[6px] text-sm transition-all">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16"/></svg>종료
                      </button>
                    </>
                  )}
                  {state === "paused" && (
                    <>
                      <button onClick={() => setState("recording")} className="flex items-center gap-2 px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-[6px] text-sm transition-all">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8"/></svg>재개
                      </button>
                      <button onClick={stopRecording} className="flex items-center gap-2 px-4 py-2.5 bg-slate-700 hover:bg-slate-800 text-white font-semibold rounded-[6px] text-sm transition-all">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16"/></svg>종료
                      </button>
                    </>
                  )}
                  {state === "done" && (
                    <button onClick={reset} className="px-5 py-2.5 border border-[#E2E8F0] text-[#64748B] font-medium rounded-[6px] text-sm hover:bg-[#F8FAFC] transition-all">초기화</button>
                  )}
                  {(state === "uploading" || state === "processing" || state === "ready") && (
                    <button onClick={reset} className="px-5 py-2.5 border border-[#E2E8F0] text-[#64748B] font-medium rounded-[6px] text-sm hover:bg-[#F8FAFC] transition-all">새 녹음</button>
                  )}
                </div>

                {/* Upload / Processing state */}
                {(state === "uploading" || state === "processing" || state === "ready") && (
                  <div className="mt-5 space-y-3">
                    <div>
                      <div className="flex justify-between text-xs text-[#64748B] mb-1.5">
                        <span>{state === "uploading" ? "파일 업로드 중" : "업로드 완료"}</span>
                        <span className="font-mono">{state === "uploading" ? `${uploadPct}%` : "100%"}</span>
                      </div>
                      <div className="h-1.5 bg-[#F1F5F9] rounded overflow-hidden">
                        <div className="h-full bg-[#2563EB] transition-all duration-200" style={{ width: state === "uploading" ? `${uploadPct}%` : "100%" }} />
                      </div>
                    </div>
                    {(state === "processing" || state === "ready") && (
                      <div>
                        <div className="flex justify-between text-xs text-[#64748B] mb-1.5">
                          <span>STT 변환 처리</span>
                          <span>{state === "ready" ? "완료" : "처리 중..."}</span>
                        </div>
                        <div className="h-1.5 bg-[#F1F5F9] rounded overflow-hidden">
                          <div className={`h-full transition-all duration-700 ${state === "ready" ? "bg-green-500 w-full" : "bg-amber-400 animate-pulse w-3/4"}`} />
                        </div>
                      </div>
                    )}
                    {state === "ready" && (
                      <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded-[6px] px-3 py-2.5">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                        변환 완료. 좌측 메뉴에서 <strong>STT 검수</strong> 화면으로 이동하세요.
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Submit button */}
              {state === "done" && (
                <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
                  <h2 className="font-semibold text-[#172033] text-sm mb-2">상담 종료 후</h2>
                  <p className="text-xs text-[#64748B] mb-4 leading-relaxed">녹음 파일을 서버에 전송하면 자동으로 텍스트로 변환됩니다. 변환 완료 후 STT 검수 화면에서 내용을 확인할 수 있습니다.</p>
                  <button onClick={submitForProcessing} className="w-full py-2.5 bg-[#2563EB] hover:bg-blue-700 text-white text-sm font-semibold rounded-[6px] transition-colors">
                    녹음 제출 및 변환 요청
                  </button>
                </div>
              )}

              {/* Stats */}
              {segments.length > 0 && state !== "uploading" && state !== "processing" && state !== "ready" && (
                <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
                  <h2 className="font-semibold text-[#172033] text-sm mb-3">녹음 현황</h2>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-[#64748B]">녹음 시간</span><span className="font-mono font-semibold text-[#172033]">{fmtTime(elapsed)}</span></div>
                    <div className="flex justify-between"><span className="text-[#64748B]">감지된 발화</span><span className="font-semibold text-[#172033]">{segments.length}개</span></div>
                    <div className="flex justify-between">
                      <span className="text-[#64748B]">화자</span>
                      <div className="flex gap-1">
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium border border-blue-100">상담사</span>
                        <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs font-medium border border-slate-200">아동</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Transcript */}
            <div className="col-span-3 bg-white rounded-[8px] border border-[#E2E8F0] flex flex-col overflow-hidden" style={{ maxHeight: "62vh" }}>
              <div className="px-5 py-3 border-b border-[#F1F5F9] shrink-0 flex items-center justify-between">
                <h2 className="font-semibold text-[#172033] text-sm">실시간 발화 기록</h2>
                <div className="flex items-center gap-2 text-xs">
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded font-medium border border-blue-100">상담사</span>
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded font-medium border border-slate-200">아동</span>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                {segments.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-[#94A3B8] space-y-3 p-5">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                      <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/>
                      <path d="M19 10v2a7 7 0 01-14 0v-2"/>
                      <line x1="12" y1="19" x2="12" y2="23"/>
                    </svg>
                    <p className="text-sm text-center">녹음을 시작하면<br/>발화 내용이 여기에 표시됩니다</p>
                  </div>
                ) : segments.map(seg => (
                  <div key={seg.id} className="flex gap-3 px-5 py-3 border-b border-[#F1F5F9]">
                    <span className="text-[11px] font-mono text-[#94A3B8] shrink-0 pt-0.5 w-10">{seg.time}</span>
                    <div className="flex-1">
                      <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded mr-2 ${seg.speaker === "상담사" ? "bg-blue-50 text-blue-700 border border-blue-100" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>
                        {seg.speaker}
                      </span>
                      <span className="text-sm text-[#172033] leading-relaxed">{seg.text}</span>
                    </div>
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
