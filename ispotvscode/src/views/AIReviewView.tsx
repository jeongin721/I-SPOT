import { useState } from "react";
import CaseSelectorPanel from "../components/CaseSelectorPanel";
import { CASES } from "../data/cases";

const RISK_KEYWORDS = ["때렸어요", "혼난다", "매일이에요", "등이랑 팔", "소리 지르고"];

const TRANSCRIPT_SEGMENTS = [
  { speaker: "상담사", text: "오늘 어떻게 지냈어? 학교에서 재미있는 일 있었니?", time: "00:12" },
  { speaker: "아동", text: "그냥요... 별로 없었어요.", time: "00:18" },
  { speaker: "상담사", text: "그렇구나. 요즘 집에서는 어때?", time: "00:26" },
  { speaker: "아동", text: "아빠가 또 화났어요. 저한테 소리 지르고... 많이 때렸어요.", time: "00:41" },
  { speaker: "상담사", text: "그랬구나, 많이 힘들었겠다. 어디 다친 곳은 없어?", time: "00:55" },
  { speaker: "아동", text: "등이랑 팔이요. 근데 말하면 더 혼난다고 했어요.", time: "01:08" },
  { speaker: "상담사", text: "말해줘서 고마워. 선생님이 꼭 도와줄게. 언제부터 그랬어?", time: "01:22" },
  { speaker: "아동", text: "엄마 없어지고 나서요. 거의 매일이에요.", time: "01:35" },
  { speaker: "상담사", text: "지금 아빠랑 둘이 살고 있어? 다른 어른은 없어?", time: "01:48" },
  { speaker: "아동", text: "할머니가 가끔 오시는데... 아빠 무서워서 저도 숨어요.", time: "02:01" },
];

const PAST_RISK_FACTORS = [
  { factor: "주 양육자에 의한 반복적 신체폭력", match: true },
  { factor: "피해 아동의 외상 후 회피 반응", match: true },
  { factor: "보호자의 음주 후 폭력 패턴", match: false },
  { factor: "한부모 가정 내 방임 동반", match: true },
  { factor: "아동의 자해·자살 표현", match: false },
  { factor: "피해 은폐 강요", match: true },
];

const INIT_DIARY = `[상담일지] 6회차 · 2026-08-19 · 이서연 상담사
※ AI 분석 참고정보 포함 — 상담사 검토 필요

■ 상담 일시: 2026년 8월 19일 (화) 14:00 – 14:50
■ 상담 방법: 개인면담 (놀이치료)
■ 참석자: 아동 (8세)

【상담 내용 요약】
아동은 가정 내 부(父)에 의한 반복적인 신체적 폭력을 보고하였다. 아동 진술에 따르면 모친 부재 이후 매일과 같은 빈도로 폭력이 발생하고 있으며, 등과 팔 부위에 신체적 피해를 호소하였다. 아동은 외부에 사실을 알릴 경우 추가적인 처벌을 받을 것을 염려하여 피해 사실 은폐를 강요받은 것으로 파악된다.

【AI 분석 참고정보】 ← 상담사 검토 및 수정 후 최종 판단
• 신체적 위해 관련 신호 (참고점수 87) – 추가 확인 필요
  근거 발화: "소리 지르고 많이 때렸어요" (00:41), "등이랑 팔이요" (01:08)
• 정서적 위해 관련 신호 (참고점수 65) – 추가 확인 필요
  근거 발화: 반복적 공포 유발, 은폐 강요 행위 확인
• 성적 위해: 관련 신호 없음
• 방임 관련 신호 (참고점수 22) – 상담사 검토 필요

【추가 확인 필요 발화】
1. "소리 지르고 많이 때렸어요" (00:41)
2. "등이랑 팔이요. 말하면 더 혼난다고 했어요" (01:08)
3. "거의 매일이에요" (01:35)

【상담사 소견 및 계획】
(상담사가 직접 작성 또는 수정하세요)
아동의 진술 신뢰도 높음. 즉각적인 안전 확보 필요. 다음 회차 전 보호자 면담 및 경찰 연계 검토 요망.`;

const INIT_REPORT = `[사정기록지] 초안 · 2026-08-19
※ AI 분석 참고정보 포함 — 상담사 검토 및 최종 확인 필요

▶ 사례번호: C-2026-0412
▶ 아동: (남, 8세, 초등학교 2학년)
▶ 의뢰경로: 학교 담임교사 신고
▶ 담당 상담사: 이서연

[학대 실태]
학대 유형: 신체적 위해, 정서적 위해 (상담사 확인 후 확정)
학대 행위자: 부 (친부, 동거)
학대 발생 시기: 모친 가출 이후 (약 6개월 전)
학대 빈도: 거의 매일 (아동 진술)
피해 부위: 등, 팔 (아동 진술 — 의료 확인 필요)

[관련 신호 및 위험요인] ← AI 분석 참고정보, 상담사 검토 필요
• 보호자 요인: 한부모 환경, 충동조절 어려움, 피해 은폐 강요 가능성
• 아동 요인: 회피적 성향, 공포 반응, 외부 도움 요청 어려움
• 환경 요인: 사회적 지지 체계 취약 (모친 부재, 친족 접촉 제한적)

[사례관리 방향] ← AI 분석 참고정보, 상담사 검토 필요
우선순위 1: 아동 안전 확보 및 격리 여부 검토
우선순위 2: 경찰 고발 및 의료 진단 연계
우선순위 3: 아동 심리치료 (외상 중심 인지행동치료)
우선순위 4: 부 대상 교육 및 상담 프로그램 연계`;

function highlightRisk(text: string) {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let idx = 0;
  for (const kw of RISK_KEYWORDS) {
    const pos = remaining.indexOf(kw);
    if (pos !== -1) {
      parts.push(<span key={`pre-${idx}`}>{remaining.slice(0, pos)}</span>);
      parts.push(<mark key={`kw-${idx}`} className="bg-[#FEF3C7] text-[#92400E] rounded px-0.5 font-medium">{kw}</mark>);
      remaining = remaining.slice(pos + kw.length);
      idx++;
    }
  }
  parts.push(<span key="tail">{remaining}</span>);
  return parts;
}

export default function AIReviewView() {
  const [selectedId, setSelectedId] = useState(CASES[0].id);
  const [activeDoc, setActiveDoc] = useState<"diary" | "report">("diary");
  const [diaryText, setDiaryText] = useState(INIT_DIARY);
  const [reportText, setReportText] = useState(INIT_REPORT);
  const [showModal, setShowModal] = useState(false);
  const [approved, setApproved] = useState(false);
  const [approvalLog, setApprovalLog] = useState<{ time: string; note: string }[]>([]);
  const [editNote, setEditNote] = useState("");

  const selectedCase = CASES.find(c => c.id === selectedId)!;

  function handleSelectCase(id: string) {
    setSelectedId(id);
    setApproved(false);
    setApprovalLog([]);
  }

  function handleApprove() {
    const now = new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
    setApprovalLog(prev => [...prev, { time: now, note: editNote || "검토 완료" }]);
    setApproved(true);
    setEditNote("");
  }

  return (
    <div className="flex h-full overflow-hidden">
      <CaseSelectorPanel selectedId={selectedId} onSelect={handleSelectCase} />

      <div className="flex-1 flex flex-col overflow-hidden bg-[#F6F8FB]">
        {/* Page header */}
        <div className="px-6 py-4 border-b border-[#E2E8F0] bg-white shrink-0 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#172033]">분석 결과 검토</h1>
            <p className="text-[#64748B] text-sm mt-0.5">
              <span className="font-semibold text-[#172033]">{selectedCase.childName}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              <span className="font-mono text-xs">{selectedCase.id}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              {selectedCase.sessionCount}회차
            </p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 text-sm font-medium rounded-[6px] transition-colors"
          >
            중대사건 위험요인 대조
          </button>
        </div>

        {/* 2-pane body */}
        <div className="flex-1 overflow-hidden grid grid-cols-2 gap-0">
          {/* Left: transcript */}
          <div className="border-r border-[#E2E8F0] flex flex-col overflow-hidden bg-white">
            <div className="px-5 py-3 border-b border-[#F1F5F9] bg-[#F8FAFC] flex items-center justify-between shrink-0">
              <h2 className="font-semibold text-[#172033] text-sm">음성 원문</h2>
              <span className="flex items-center gap-1 text-xs text-[#64748B]"><mark className="bg-[#FEF3C7] rounded px-1 text-[#92400E]">관련 신호</mark></span>
            </div>
            <div className="flex-1 overflow-y-auto">
              {TRANSCRIPT_SEGMENTS.map((seg, i) => (
                <div key={i} className="flex gap-3 px-5 py-3 border-b border-[#F1F5F9]">
                  <span className="text-[11px] font-mono text-[#94A3B8] shrink-0 pt-0.5 w-10">{seg.time}</span>
                  <div>
                    <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded mr-2 ${seg.speaker === "상담사" ? "bg-blue-50 text-blue-700 border border-blue-100" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>{seg.speaker}</span>
                    <span className="text-sm text-[#172033] leading-relaxed">{highlightRisk(seg.text)}</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="px-5 py-3 border-t border-[#F1F5F9] bg-amber-50 shrink-0">
              <p className="text-xs font-semibold text-amber-800 mb-1.5">추가 확인 필요 발화 ({RISK_KEYWORDS.length}건) — 상담사 검토 필요</p>
              <div className="flex flex-wrap gap-1.5">
                {RISK_KEYWORDS.map(k => <span key={k} className="px-2 py-0.5 bg-[#FEF3C7] border border-amber-200 text-[#92400E] rounded text-[11px] font-medium">"{k}"</span>)}
              </div>
            </div>
          </div>

          {/* Right: document editor */}
          <div className="flex flex-col overflow-hidden bg-white">
            <div className="px-5 py-3 border-b border-[#F1F5F9] bg-[#F8FAFC] shrink-0 flex items-center justify-between">
              <div className="flex gap-1.5">
                {(["diary", "report"] as const).map(tab => (
                  <button key={tab} onClick={() => setActiveDoc(tab)}
                    className={`px-3 py-1.5 rounded-[6px] text-xs font-medium transition-colors ${activeDoc === tab ? "bg-[#2563EB] text-white" : "bg-white border border-[#E2E8F0] text-[#64748B] hover:bg-[#F8FAFC]"}`}
                  >
                    {tab === "diary" ? "상담일지" : "사정기록지"}
                  </button>
                ))}
              </div>
              {approved && <span className="text-xs text-green-700 bg-green-50 border border-green-200 px-2.5 py-1 rounded font-medium">승인 완료</span>}
            </div>
            <textarea
              value={activeDoc === "diary" ? diaryText : reportText}
              onChange={e => activeDoc === "diary" ? setDiaryText(e.target.value) : setReportText(e.target.value)}
              disabled={approved}
              className="flex-1 w-full p-5 text-sm font-mono text-[#172033] leading-relaxed resize-none focus:outline-none disabled:bg-[#F8FAFC] disabled:text-[#64748B]"
            />
            <div className="px-5 py-4 border-t border-[#F1F5F9] bg-[#F8FAFC] shrink-0 space-y-3">
              {approvalLog.length > 0 && (
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider">변경 이력</p>
                  {approvalLog.map((log, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-[#64748B]">
                      <span className="font-mono">{log.time}</span><span>이서연 상담사 ·</span>
                      <span className="text-green-700 font-medium">{log.note}</span>
                    </div>
                  ))}
                </div>
              )}
              {!approved ? (
                <div className="flex gap-2">
                  <input type="text" value={editNote} onChange={e => setEditNote(e.target.value)} placeholder="승인 메모 (선택)" className="flex-1 px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-sm focus:outline-none focus:ring-1 focus:ring-[#2563EB]" />
                  <button onClick={handleApprove} className="px-5 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-blue-700 transition-colors">검토 완료</button>
                </div>
              ) : (
                <button onClick={() => setApproved(false)} className="text-xs text-[#94A3B8] hover:text-[#64748B] transition-colors">승인 취소 후 수정</button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Risk modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-[8px] shadow-lg w-full max-w-lg mx-4 overflow-hidden">
            <div className="bg-[#15314A] px-6 py-5 text-white flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold">과거 중대사건 위험요인 대조</h3>
                <p className="text-slate-300 text-sm mt-0.5">아동학대 사망·중대 사건 공통 위험요인 비교</p>
              </div>
              <button onClick={() => setShowModal(false)} className="text-white/60 hover:text-white transition-colors">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div className="p-6 space-y-2">
              {PAST_RISK_FACTORS.map((f, i) => (
                <div key={i} className={`flex items-center gap-3 px-3.5 py-2.5 rounded-[6px] border ${f.match ? "bg-red-50 border-red-200" : "bg-[#F8FAFC] border-[#E2E8F0]"}`}>
                  <span className={`w-2 h-2 rounded-full shrink-0 ${f.match ? "bg-red-500" : "bg-slate-300"}`} />
                  <span className={`text-sm flex-1 ${f.match ? "text-red-800 font-medium" : "text-[#64748B]"}`}>{f.factor}</span>
                  {f.match && <span className="text-xs font-semibold text-red-600 bg-red-100 px-2 py-0.5 rounded shrink-0">일치</span>}
                </div>
              ))}
              <div className="pt-3 border-t border-[#F1F5F9]">
                <div className="bg-amber-50 border border-amber-200 rounded-[6px] p-4">
                  <p className="text-sm font-semibold text-amber-800 mb-1">중대사건 위험요인 {PAST_RISK_FACTORS.filter(f => f.match).length}/{PAST_RISK_FACTORS.length}개 일치</p>
                  <p className="text-xs text-amber-700">과거 사망 사건과 유사한 위험 패턴이 감지되었습니다. 즉각적인 안전 확보 조치를 검토하십시오.</p>
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-[#F1F5F9] flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 border border-[#E2E8F0] text-[#64748B] text-sm rounded-[6px] hover:bg-[#F8FAFC] transition-colors">닫기</button>
              <button className="px-4 py-2 bg-red-600 text-white text-sm font-semibold rounded-[6px] hover:bg-red-700 transition-colors">보고서에 포함</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
