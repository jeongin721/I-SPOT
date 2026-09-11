import { useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router";
import CaseSelectorPanel from "../components/CaseSelectorPanel";
import { CASES } from "../data/cases";
import { SESSIONS } from "../data/mockData";
import Breadcrumb from "../components/ui/Breadcrumb";
import ConfirmModal from "../components/ui/ConfirmModal";
import { useToast } from "../components/ui/Toast";

interface Segment {
  id: number;
  speaker: "상담사" | "아동";
  timestamp: string;
  text: string;
  confidence: number;
  confirmed: boolean;
  editing: boolean;
  draft: string;
}

const LOW_CONF = 0.75;

const INIT_SEGMENTS: Segment[] = [
  { id: 1,  speaker: "상담사", timestamp: "00:12", confidence: 0.97, text: "오늘 어떻게 지냈어? 학교에서 재미있는 일 있었니?",         confirmed: false, editing: false, draft: "" },
  { id: 2,  speaker: "아동",   timestamp: "00:18", confidence: 0.91, text: "그냥요... 별로 없었어요.",                                    confirmed: false, editing: false, draft: "" },
  { id: 3,  speaker: "상담사", timestamp: "00:26", confidence: 0.95, text: "그렇구나. 요즘 집에서는 어때?",                              confirmed: false, editing: false, draft: "" },
  { id: 4,  speaker: "아동",   timestamp: "00:41", confidence: 0.62, text: "아빠가 또 화났어요. 저한테 소리 지르고... 많이 때렸어요.",   confirmed: false, editing: false, draft: "" },
  { id: 5,  speaker: "상담사", timestamp: "00:55", confidence: 0.98, text: "그랬구나, 많이 힘들었겠다. 어디 다친 곳은 없어?",           confirmed: false, editing: false, draft: "" },
  { id: 6,  speaker: "아동",   timestamp: "01:08", confidence: 0.58, text: "등이랑 팔이요. 근데 말하면 더 혼난다고 했어요.",             confirmed: false, editing: false, draft: "" },
  { id: 7,  speaker: "상담사", timestamp: "01:22", confidence: 0.99, text: "말해줘서 고마워. 선생님이 꼭 도와줄게. 언제부터 그랬어?",   confirmed: false, editing: false, draft: "" },
  { id: 8,  speaker: "아동",   timestamp: "01:35", confidence: 0.71, text: "엄마 없어지고 나서요. 거의 매일이에요.",                     confirmed: false, editing: false, draft: "" },
  { id: 9,  speaker: "상담사", timestamp: "01:48", confidence: 0.96, text: "지금 아빠랑 둘이 살고 있어? 다른 어른은 없어?",             confirmed: false, editing: false, draft: "" },
  { id: 10, speaker: "아동",   timestamp: "02:01", confidence: 0.83, text: "할머니가 가끔 오시는데... 아빠 무서워서 저도 숨어요.",       confirmed: false, editing: false, draft: "" },
  { id: 11, speaker: "상담사", timestamp: "02:15", confidence: 0.97, text: "할머니한테 말씀드린 적은 있어?",                             confirmed: false, editing: false, draft: "" },
  { id: 12, speaker: "아동",   timestamp: "02:22", confidence: 0.55, text: "아니요. 할머니도 무서울 것 같아서요.",                       confirmed: false, editing: false, draft: "" },
];

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= LOW_CONF ? "bg-green-400" : value >= 0.55 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="w-16 h-1.5 bg-[#F1F5F9] rounded overflow-hidden shrink-0">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-[11px] font-mono font-semibold shrink-0 ${value < LOW_CONF ? "text-amber-600" : "text-[#94A3B8]"}`}>
        {pct}%
      </span>
    </div>
  );
}

export default function TranscriptReviewView() {
  const { caseId, sessionId } = useParams<{ caseId: string; sessionId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  // Determine selected case: from URL params or fallback to selector
  const [selectedId, setSelectedId] = useState(caseId ?? CASES[0].id);
  const [segments, setSegments] = useState<Segment[]>(INIT_SEGMENTS);
  const [filterLow, setFilterLow] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const selectedCase = CASES.find(c => c.id === selectedId)!;
  const session = sessionId ? SESSIONS.find(s => s.id === sessionId) : null;

  const displayed = useMemo(() =>
    filterLow ? segments.filter(s => s.confidence < LOW_CONF) : segments,
    [segments, filterLow]
  );

  const confirmedCount  = segments.filter(s => s.confirmed).length;
  const lowConfCount    = segments.filter(s => s.confidence < LOW_CONF).length;
  const pendingLowCount = segments.filter(s => s.confidence < LOW_CONF && !s.confirmed).length;
  const allDone         = segments.every(s => s.confirmed);

  function startEdit(id: number) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, editing: true, draft: s.text } : s));
  }
  function saveDraft(id: number) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, editing: false, text: s.draft, confirmed: true } : s));
  }
  function cancelEdit(id: number) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, editing: false, draft: "" } : s));
  }
  function confirm(id: number) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, confirmed: true } : s));
  }
  function unconfirm(id: number) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, confirmed: false } : s));
  }
  function confirmAll() {
    setSegments(prev => prev.map(s => ({ ...s, confirmed: true })));
  }

  function handleComplete() {
    setShowConfirm(true);
  }

  function handleConfirmComplete() {
    setShowConfirm(false);
    showToast("STT 검수가 완료되었습니다.", "success");
    if (caseId) navigate(`/cases/${caseId}/analyses`);
  }

  const isRouted = !!caseId;

  return (
    <div className="flex h-full overflow-hidden">
      {!isRouted && (
        <CaseSelectorPanel selectedId={selectedId} onSelect={id => { setSelectedId(id); setSegments(INIT_SEGMENTS); }} />
      )}

      <div className="flex-1 flex flex-col overflow-hidden bg-[#F6F8FB]">
        {/* Breadcrumb header */}
        {isRouted && (
          <div className="px-6 pt-4 pb-2 shrink-0">
            <Breadcrumb items={[
              { label: "STT 검수", to: "/stt-cases" },
              { label: selectedCase.childName, to: `/cases/${selectedId}/sessions` },
              { label: session ? `${session.date} 상담` : "STT 검수" },
              { label: "STT 검수" },
            ]} />
          </div>
        )}

        {/* Header */}
        <div className="px-6 py-4 border-b border-[#E2E8F0] bg-white shrink-0 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#172033]">STT 검수</h1>
            <p className="text-[#64748B] text-sm mt-0.5">
              <span className="font-semibold text-[#172033]">{selectedCase.childName}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              <span className="font-mono text-xs">{selectedCase.id}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              저신뢰 구간을 확인하고 수정·확정하세요
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isRouted && (
              <button
                onClick={() => navigate(-1)}
                className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-sm font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
              >
                뒤로
              </button>
            )}
            {allDone && (
              <button
                onClick={handleComplete}
                className="flex items-center gap-2 px-4 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-blue-700 transition-colors"
              >
                STT 검수 완료
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
              </button>
            )}
          </div>
        </div>

        {/* Stats bar */}
        <div className="px-6 py-2.5 bg-white border-b border-[#E2E8F0] shrink-0 flex items-center gap-6 flex-wrap text-sm">
          <div className="flex items-center gap-2">
            <span className="text-[#64748B] text-xs">전체</span>
            <span className="font-semibold text-[#172033]">{segments.length}개</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span className="text-[#64748B] text-xs">저신뢰 구간</span>
            <span className={`font-semibold ${lowConfCount > 0 ? "text-amber-600" : "text-[#172033]"}`}>{lowConfCount}개</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
            <span className="text-[#64748B] text-xs">확정 완료</span>
            <span className="font-semibold text-green-700">{confirmedCount}/{segments.length}</span>
          </div>
          {pendingLowCount > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 border border-amber-200 rounded text-xs font-medium text-amber-700">
              저신뢰 {pendingLowCount}개 미검수
            </div>
          )}
          <div className="ml-auto flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-[#64748B] cursor-pointer select-none">
              <input type="checkbox" checked={filterLow} onChange={e => setFilterLow(e.target.checked)} className="accent-amber-500" />
              저신뢰만 보기
            </label>
            <button onClick={confirmAll} disabled={allDone}
              className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              전체 확정
            </button>
          </div>
        </div>

        {/* Segment list */}
        <div className="flex-1 overflow-y-auto bg-white">
          {displayed.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-[#94A3B8] space-y-3">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><polyline points="20 6 9 17 4 12"/></svg>
              <p className="text-sm">모든 저신뢰 구간이 검수되었습니다</p>
            </div>
          )}

          {displayed.map(seg => {
            const isLow = seg.confidence < LOW_CONF;
            return (
              <div
                key={seg.id}
                className={`px-6 py-3.5 border-b border-[#F1F5F9] transition-colors ${
                  seg.confirmed ? "bg-[#F0FDF4]/40" : isLow ? "bg-[#FFFBEB]" : "bg-white hover:bg-[#F8FAFC]"
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className="flex flex-col items-start gap-1.5 shrink-0 w-24 pt-0.5">
                    <span className="text-[11px] font-mono text-[#94A3B8]">{seg.timestamp}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold ${seg.speaker === "상담사" ? "bg-blue-50 text-blue-700 border border-blue-100" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>
                      {seg.speaker}
                    </span>
                    <ConfidenceBar value={seg.confidence} />
                    {isLow && !seg.confirmed && (
                      <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">검수 필요</span>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    {seg.editing ? (
                      <div className="space-y-2">
                        <textarea
                          value={seg.draft}
                          onChange={e => setSegments(prev => prev.map(s => s.id === seg.id ? { ...s, draft: e.target.value } : s))}
                          rows={2}
                          autoFocus
                          className="w-full px-3 py-2 rounded-[6px] border border-[#2563EB] text-sm text-[#172033] resize-none focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                        />
                        <div className="flex items-center gap-2">
                          <button onClick={() => saveDraft(seg.id)} className="px-3 py-1.5 bg-[#2563EB] text-white text-xs font-semibold rounded-[6px] hover:bg-blue-700 transition-colors">
                            저장 및 확정
                          </button>
                          <button onClick={() => cancelEdit(seg.id)} className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors">
                            취소
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className={`text-sm leading-relaxed ${isLow && !seg.confirmed ? "text-amber-900" : seg.confirmed ? "text-[#64748B]" : "text-[#172033]"}`}>
                        {seg.text}
                      </p>
                    )}
                  </div>

                  {!seg.editing && (
                    <div className="flex items-center gap-2 shrink-0">
                      {seg.confirmed ? (
                        <>
                          <span className="flex items-center gap-1 text-xs text-green-700 font-medium">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>확정
                          </span>
                          <button onClick={() => unconfirm(seg.id)} className="text-xs text-[#94A3B8] hover:text-[#64748B] underline transition-colors">취소</button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => startEdit(seg.id)} className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors">
                            수정
                          </button>
                          <button onClick={() => confirm(seg.id)} className="px-3 py-1.5 bg-[#2563EB] hover:bg-blue-700 text-white text-xs font-semibold rounded-[6px] transition-colors">
                            확정
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer CTA */}
        {allDone && (
          <div className="px-6 py-4 border-t border-[#E2E8F0] bg-white shrink-0 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-green-700">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span className="font-medium">모든 구간 검수 완료</span>
              <span className="text-[#94A3B8] text-xs">· {segments.length}개 확정</span>
            </div>
            <div className="flex gap-2">
              <button className="px-4 py-2 border border-[#E2E8F0] text-[#64748B] text-sm font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors">
                검수 결과 저장
              </button>
              <button
                onClick={handleComplete}
                className="flex items-center gap-2 px-5 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-blue-700 transition-colors"
              >
                STT 검수 완료
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
              </button>
            </div>
          </div>
        )}
      </div>

      <ConfirmModal
        open={showConfirm}
        title="STT 검수 완료"
        message="STT 검수를 완료하시겠습니까? 완료 후 AI 분석 결과 검토 단계로 이동합니다."
        confirmLabel="완료"
        onConfirm={handleConfirmComplete}
        onCancel={() => setShowConfirm(false)}
      />
    </div>
  );
}
