import { useState, useMemo, useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router";
import {
  analysis as analysisApi,
  cases as casesApi,
  summary as summaryApi,
  transcript as transcriptApi,
} from "../api/endpoints";
import { NOT_PROVIDED, describeApiError, toUiTranscriptSegments } from "../api/adapters";
import {
  ANALYSED_SESSION_STATUSES,
  indexSegments,
  segmentContext,
  sortByRecentSession,
  sortSessionsLatestFirst,
  toAnalysisStatusLabel,
  toHistoryRow,
  toLocalDate,
  toManagedCase,
  toUiReferenceSignals,
  toUiRiskUtterances,
  type HistoryRow,
  type ManagedCase,
} from "../api/dashboardAdapters";
import type { AnalysisEnvelope, Session, SessionStatus, Summary, SummaryEnvelope, TranscriptEnvelope } from "../api/types";

// 사례 목록은 GET /cases, 이전 상담은 GET /cases/{id}/sessions(+ 회기별 요약 · 전사본),
// 분석 결과 검토 탭은 회기별 GET /sessions/{id}/analysis · summary 를 읽기 전용으로 보여 준다.
// 검토 · 승인은 AI 분석 화면(/cases/{caseId}/analyses/{sessionId})에서 한다.
// 이 화면은 주소에 사례가 없어 고른 사례를 화면 상태로만 들고 있다.
//
// 위험도 · 상담 회차 수 · 상담 유형 · 소요 시간은 Backend 에 없어 "—" 로 둔다.
// 사례관리 계획 · 종결 검토는 Backend 에 기능이 없어 화면 구성만 두고 저장 · 제출을 막았다.

/** 사례는 한 번에 받는다(Backend 최대 100). 검색 · 최근 상담순 정렬은 화면에서 한다. */
const CASE_PAGE_SIZE = 100;
const SESSION_PAGE_SIZE = 100;

// ─── Types ───────────────────────────────────────────────────────────────────

type Tab = "ai-review" | "plan" | "closure" | "history";

function matchesQuery(c: ManagedCase, query: string): boolean {
  return !query || c.childName.includes(query) || c.caseNumber.toLowerCase().includes(query.toLowerCase());
}

function CaseStatusChip({ c }: { c: ManagedCase }) {
  return (
    <span className={`px-2 py-0.5 rounded border text-[12px] bg-white ${c.status === "ACTIVE" ? "border-[#94A3B8] text-[#172033] font-semibold" : "border-[#CBD5E1] text-[#64748B]"}`}>
      {c.statusLabel}
    </span>
  );
}

/** Backend 에 아직 없는 기능 안내. */
function NotServedNotice({ children }: { children: ReactNode }) {
  return (
    <div className="bg-white border border-[#CBD5E1] rounded-[8px] px-4 py-3 text-[13px] text-[#475569]">
      {children}
    </div>
  );
}

function CenteredMessage({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return (
    <div className={`flex-1 flex items-center justify-center text-[14px] ${error ? "text-red-600" : "text-[#94A3B8]"}`}>
      {children}
    </div>
  );
}

// ─── Compact Case Selector ────────────────────────────────────────────────────
//
// 지금 이 화면의 첫 단계는 아래 CaseListView 라 이 표는 쓰이지 않는다(원래부터). 다시 쓸 때를 위해
// 가짜 데이터 대신 사례 목록을 받도록만 바꿔 두었다.

/** 분석 단계에서 상담사가 할 일이 있는 회기(분석 요청 대기 · 결과 검토 · 실패 뒤 다시 요청). */
const NEEDS_ACTION_STATUSES: SessionStatus[] = ["STT_CONFIRMED", "AI_REVIEW_REQUIRED", "AI_FAILED"];

function CaseSelector({ cases, selected, onSelect }: { cases: ManagedCase[]; selected: ManagedCase | null; onSelect: (c: ManagedCase) => void }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => cases.filter(c => matchesQuery(c, query)), [cases, query]);

  return (
    <div className="bg-white border-b border-[#E2E8F0]">
      <div className="px-6 py-3 flex items-center justify-between border-b border-[#F1F5F9]">
        <span className="text-[13px] font-semibold text-[#172033]">사례 선택</span>
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="아동명·사례ID"
            className="pl-7 pr-3 py-1 rounded-[6px] border border-[#E2E8F0] text-[12px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-[#F8FAFC] w-40 transition-all"
          />
        </div>
      </div>
      <div className="overflow-y-auto" style={{ maxHeight: "200px" }}>
        <table className="w-full">
          <thead className="bg-[#F8FAFC] sticky top-0">
            <tr>
              {["아동명", "사례 ID", "위험도", "상태", "최근 상담", ""].map(h => (
                <th key={h} className="px-4 py-2 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(c => {
              const isSelected = selected?.backendId === c.backendId;
              return (
                <tr
                  key={c.backendId}
                  onClick={() => onSelect(c)}
                  className="border-b border-[#F1F5F9] cursor-pointer transition-colors"
                  style={{ background: isSelected ? "#EFF6FF" : undefined }}
                  onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = "#F8FAFC"; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = isSelected ? "#EFF6FF" : ""; }}
                >
                  <td className="px-4 py-2 text-[13px] font-semibold text-[#172033]">{c.childName}</td>
                  <td className="px-4 py-2 text-[11px] font-mono text-[#94A3B8]">{c.caseNumber}</td>
                  <td className="px-4 py-2 text-[12px] text-[#94A3B8]">{NOT_PROVIDED}</td>
                  <td className="px-4 py-2"><CaseStatusChip c={c} /></td>
                  <td className="px-4 py-2 text-[12px] font-mono text-[#64748B]">{c.lastSession || NOT_PROVIDED}</td>
                  <td className="px-4 py-2">
                    <span className={`text-[12px] font-medium ${isSelected ? "text-[#2563EB]" : "text-[#94A3B8]"}`}>
                      {isSelected ? "선택됨" : "선택"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Sub-nav Tabs ─────────────────────────────────────────────────────────────

function SubNav({ active, onChange, reviewCount }: { active: Tab; onChange: (t: Tab) => void; reviewCount: number }) {
  const tabs: { id: Tab; label: string; badge?: number }[] = [
    { id: "ai-review", label: "분석 결과 검토", badge: reviewCount > 0 ? reviewCount : undefined },
    { id: "plan",      label: "사례관리 계획" },
    { id: "closure",   label: "종결·가정복귀 검토" },
    { id: "history",   label: "이전 상담" },
  ];

  return (
    <div className="bg-white border-b border-[#E2E8F0] px-6 flex items-center gap-0">
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className="relative flex items-center gap-1.5 px-4 py-3 text-[13px] font-medium transition-colors border-b-2"
          style={{
            borderBottomColor: active === t.id ? "#2563EB" : "transparent",
            color: active === t.id ? "#2563EB" : "#64748B",
          }}
        >
          {t.label}
          {t.badge != null && t.badge > 0 && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-sm bg-amber-500 text-white min-w-[18px] text-center">
              {t.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

// ─── AI Review Tab ────────────────────────────────────────────────────────────

interface AnalysisDetail {
  analysis: AnalysisEnvelope;
  /** 요약 · 전사본은 없어도 분석 결과는 보여 준다. 불러오지 못하면 null. */
  summary: SummaryEnvelope | null;
  transcript: TranscriptEnvelope | null;
}

interface SessionListProps {
  caseObj: ManagedCase;
  sessions: Session[];
  sessionsLoading: boolean;
  sessionsError: string | null;
}

function AiReviewTab({ caseObj, sessions, sessionsLoading, sessionsError, onNavigate }: SessionListProps & { onNavigate: (t: Tab) => void }) {
  const navigate = useNavigate();
  // 분석을 요청한 적이 있는 회기만, 최근 회기부터.
  const analyses = useMemo(
    () => sortSessionsLatestFirst(sessions.filter(s => ANALYSED_SESSION_STATUSES.includes(s.status))),
    [sessions],
  );
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [showEvidence, setShowEvidence] = useState<string | null>(null);
  const [selectedIndicator, setSelectedIndicator] = useState<string | null>(null);
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const session = analyses[selectedIdx];
  const sessionId = session?.id;

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;

    setDetail(null);
    setDetailLoading(true);
    setDetailError(null);
    setShowEvidence(null);
    setSelectedIndicator(null);

    Promise.all([
      analysisApi.get(sessionId),
      summaryApi.get(sessionId).catch(() => null),
      transcriptApi.get(sessionId).catch(() => null),
    ])
      .then(([analysis, summary, transcript]) => {
        if (!cancelled) setDetail({ analysis, summary, transcript });
      })
      .catch((caught) => {
        if (!cancelled) setDetailError(describeApiError(caught, "분석 결과를 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (sessionsLoading) return <CenteredMessage>회기 목록을 불러오는 중...</CenteredMessage>;
  if (sessionsError) return <CenteredMessage error>{sessionsError}</CenteredMessage>;

  if (!session) {
    return (
      <div className="flex-1 flex items-center justify-center text-[14px] text-[#94A3B8]">
        이 사례에 대한 AI 분석 결과가 없습니다.
      </div>
    );
  }

  const analysis = detail?.analysis.analysis ?? null;
  const result = analysis?.status === "COMPLETED" ? analysis.result : null;
  const summaryData: Summary | null = detail?.summary?.summary ?? null;
  const transcript = detail?.transcript?.transcript ?? null;
  const segments = indexSegments(transcript);
  const utterances = toUiRiskUtterances(result);
  const signals = toUiReferenceSignals(result);
  const overview = result?.summary.overview || summaryData?.overview || "";
  const warnings = result?.warnings ?? [];
  const failure = detail?.analysis.error ?? analysis?.error ?? null;
  const analysedOn = analysis ? toLocalDate(analysis.completed_at ?? analysis.created_at).slice(5) : NOT_PROVIDED;

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      {/* Analysis selector + meta */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-[18px] font-semibold text-[#172033]">{caseObj.childName} · 분석 결과 검토</h2>
          <span className="text-[12px] font-semibold px-2 py-1 rounded-[4px] border border-[#CBD5E1] text-[#475569] bg-white">
            {toAnalysisStatusLabel(session.status, summaryData)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[#94A3B8]">회차:</span>
          {analyses.map((a, i) => (
            <button key={a.id} onClick={() => setSelectedIdx(i)}
              className="px-2.5 py-1 text-[12px] font-medium rounded-[6px] border transition-all"
              style={{
                borderColor: selectedIdx === i ? "#2563EB" : "#E2E8F0",
                background: selectedIdx === i ? "#EFF6FF" : "white",
                color: selectedIdx === i ? "#2563EB" : "#64748B",
              }}>
              {a.session_number}회차
            </button>
          ))}
        </div>
      </div>

      {/* 읽기 전용 안내 */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-3 flex items-center justify-between gap-3">
        <p className="text-[13px] text-[#64748B]">이 탭은 읽기 전용입니다. 검토 · 승인은 AI 분석 화면에서 합니다.</p>
        <button
          onClick={() => navigate(`/cases/${caseObj.backendId}/analyses/${session.id}`)}
          className="shrink-0 px-3 py-1.5 text-[12px] font-medium text-[#2563EB] border border-[#DBEAFE] rounded-[6px] bg-[#EFF6FF] hover:bg-[#DBEAFE] transition-colors"
        >
          AI 분석 화면에서 검토하기
        </button>
      </div>

      {detailLoading && (
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-8 text-center text-[13px] text-[#94A3B8]">분석 결과를 불러오는 중...</div>
      )}
      {!detailLoading && detailError && (
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-8 text-center text-[13px] text-red-600">{detailError}</div>
      )}
      {!detailLoading && detail && !result && (
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-8 text-center text-[13px] text-[#64748B]">
          {session.status === "AI_PROCESSING" || analysis?.status === "PROCESSING"
            ? "AI 분석이 진행 중입니다. 끝나면 결과가 여기에 보입니다."
            : failure
              ? `AI 분석에 실패했습니다: ${failure.message}`
              : session.status === "STT_CONFIRMED"
                ? "아직 AI 분석을 요청하지 않았습니다. 위의 'AI 분석 화면에서 검토하기' 에서 요청할 수 있습니다."
                : "이 회기의 분석 결과가 아직 없습니다."}
        </div>
      )}

      {!detailLoading && result && (
        <>
          {/* Summary strip */}
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-4 flex gap-6">
            <div className="flex-1">
              <p className="text-[12px] font-semibold text-[#64748B] mb-1">AI 분석 참고정보</p>
              <p className="text-[14px] text-[#172033]">{overview || NOT_PROVIDED}</p>
              {warnings.length > 0 && (
                <ul className="mt-2 space-y-0.5">
                  {warnings.map((w, i) => (
                    <li key={i} className="text-[12px] text-[#64748B]">· {w}</li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex gap-5 shrink-0 border-l border-[#F1F5F9] pl-5">
              <div className="text-center">
                <div className="text-[22px] font-bold text-[#172033]">{utterances.length}</div>
                <div className="text-[12px] text-[#94A3B8]">감지 신호</div>
              </div>
              <div className="text-center">
                <div className="text-[22px] font-bold text-[#172033]">{session.session_number}</div>
                <div className="text-[12px] text-[#94A3B8]">회차</div>
              </div>
              <div className="text-center">
                <div className="text-[22px] font-bold text-[#172033]">{analysedOn}</div>
                <div className="text-[12px] text-[#94A3B8]">분석일</div>
              </div>
            </div>
          </div>

          {/* 추가 확인 필요 발화 */}
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
            <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <span className="text-[14px] font-semibold text-[#172033]">추가 확인 필요 발화</span>
              <span className="text-[12px] text-[#64748B]">AI가 주의 표시한 발화입니다. 상담사의 최종 판단이 필요합니다.</span>
            </div>
            <div className="divide-y divide-[#F1F5F9]">
              {utterances.map((item, i) => {
                const seg = item.segmentId ? segments.get(item.segmentId) : undefined;
                const context = item.segmentId ? segmentContext(transcript, item.segmentId) : [];
                return (
                  <div key={i} className="px-5 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[11px] font-mono text-[#94A3B8] bg-[#F1F5F9] px-1.5 py-0.5 rounded">{seg?.timestamp ?? NOT_PROVIDED}</span>
                          <span className="text-[12px] text-[#64748B]">{seg?.speakerLabel ?? NOT_PROVIDED}</span>
                          {item.typeLabel && (
                            <span className="text-[12px] text-[#475569] border border-[#CBD5E1] px-1.5 py-0.5 rounded bg-white font-medium">#{item.typeLabel}</span>
                          )}
                        </div>
                        <p className="text-[14px] text-[#172033] font-medium">"{item.text || seg?.text || NOT_PROVIDED}"</p>
                        <p className="text-[12px] text-[#64748B] mt-1">관련 신호: {item.reason || NOT_PROVIDED}</p>
                      </div>
                      <button
                        onClick={() => setShowEvidence(showEvidence === `${i}` ? null : `${i}`)}
                        className="shrink-0 px-2.5 py-1.5 text-[12px] font-medium rounded-[6px] border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC] transition-colors"
                      >
                        원문 위치 보기
                      </button>
                    </div>
                    {showEvidence === `${i}` && (
                      <div className="mt-3 border-t border-[#F1F5F9] pt-3">
                        <p className="text-[12px] font-semibold text-[#94A3B8] mb-2">STT 원문 컨텍스트</p>
                        <div className="bg-[#F8FAFC] rounded-[6px] px-4 py-3 font-mono text-[13px] text-[#64748B] space-y-1">
                          {context.length === 0 && <p>전사본에서 이 발화를 찾지 못했습니다.</p>}
                          {context.map(line => (
                            <p key={line.id}>
                              <span className="text-[#94A3B8]">{line.timestamp}</span>{" "}
                              <span className="text-[#94A3B8]">{line.speakerLabel}</span>{" "}
                              <span className={line.id === item.segmentId ? "text-[#172033] font-bold underline underline-offset-2" : ""}>{line.text}</span>
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              {utterances.length === 0 && (
                <div className="px-5 py-6 text-[13px] text-[#94A3B8]">AI가 주의 표시한 발화가 없습니다.</div>
              )}
            </div>
          </div>

          {/* Risk indicators - clickable */}
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
            <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
              <p className="text-[14px] font-semibold text-[#172033]">위험 관련 신호·근거 발화</p>
              <span className="text-[12px] text-[#94A3B8]">항목을 클릭하면 근거를 확인할 수 있습니다</span>
            </div>
            <div className="divide-y divide-[#F1F5F9]">
              {signals.map((ind, i) => {
                const isOpen = selectedIndicator === `${i}`;
                return (
                  <div key={i}>
                    <button
                      onClick={() => setSelectedIndicator(isOpen ? null : `${i}`)}
                      className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-[#F8FAFC] transition-colors"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-[#475569] shrink-0" />
                      <span className="text-[14px] text-[#172033] flex-1 font-medium">{ind.label}</span>
                      <span className="text-[12px] text-[#94A3B8]">{ind.kind}</span>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 transition-transform" style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0)" }}><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    {isOpen && (
                      <div className="border-t border-[#F1F5F9] bg-[#FAFAFA] px-5 py-5 space-y-5">
                        {/* 전체 상담 요약본 */}
                        <div>
                          <p className="text-[12px] font-semibold text-[#64748B] mb-2">전체 상담 요약본</p>
                          <p className="text-[14px] text-[#172033] leading-relaxed">{summaryData?.overview || overview || NOT_PROVIDED}</p>
                        </div>

                        {/* 근거 발화 */}
                        <div>
                          <p className="text-[12px] font-semibold text-[#64748B] mb-2">근거 발화</p>
                          <div className="space-y-3">
                            {ind.segmentIds.map(id => {
                              const ev = segments.get(id);
                              return (
                                <div key={id} className="border border-[#E2E8F0] rounded-[6px] bg-white p-4">
                                  <div className="flex items-center gap-2 mb-2">
                                    <span className="text-[11px] font-mono text-[#94A3B8] bg-[#F1F5F9] px-1.5 py-0.5 rounded">{ev?.timestamp ?? NOT_PROVIDED}</span>
                                    <span className="text-[12px] text-[#64748B]">{ev?.speakerLabel ?? NOT_PROVIDED}</span>
                                  </div>
                                  <p className="text-[14px] text-[#172033] leading-relaxed">
                                    {ev?.text ?? "전사본에서 이 발화를 찾지 못했습니다."}
                                  </p>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              {signals.length === 0 && (
                <div className="px-5 py-6 text-[13px] text-[#94A3B8]">AI가 표시한 관련 신호가 없습니다.</div>
              )}
            </div>
          </div>
        </>
      )}

      {/* 요약 검토 현황 (읽기 전용) */}
      {!detailLoading && detail && (
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
            <p className="text-[14px] font-semibold text-[#172033]">상담 요약 검토 현황</p>
            {summaryData && (
              <span className="text-[12px] text-[#64748B]">
                {summaryData.status === "APPROVED" ? "승인됨" : "초안"}{summaryData.is_edited ? " · 상담사 수정" : ""}
              </span>
            )}
          </div>
          {summaryData ? (
            <div className="px-5 py-4 space-y-3">
              <p className="text-[14px] text-[#172033]">{summaryData.overview || NOT_PROVIDED}</p>
              {summaryData.key_points.length > 0 && (
                <ul className="space-y-1">
                  {summaryData.key_points.map((point, i) => (
                    <li key={i} className="text-[13px] text-[#475569]">· {point}</li>
                  ))}
                </ul>
              )}
              {summaryData.counselor_note && (
                <p className="text-[12px] text-[#64748B] border-t border-[#F1F5F9] pt-2">상담사 메모: {summaryData.counselor_note}</p>
              )}
            </div>
          ) : (
            <div className="px-5 py-6 text-[13px] text-[#94A3B8]">요약이 아직 없습니다.</div>
          )}
        </div>
      )}

      {/* Navigation to plan */}
      <div className="flex justify-end">
        <button
          onClick={() => onNavigate("plan")}
          className="flex items-center gap-2 px-4 py-2 text-[13px] font-medium text-white rounded-[6px] bg-[#2563EB] hover:bg-[#1D4ED8] transition-colors"
        >
          사례관리 계획으로 이동
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
      </div>
    </div>
  );
}

// ─── Case Plan Tab ────────────────────────────────────────────────────────────
//
// 사례관리 계획은 Backend 에 없다. 화면 구성만 두고 내용은 비워 둔다(예시 문장을 사실처럼 보이지 않게).

function CasePlanTab({ caseObj, onNavigate }: { caseObj: ManagedCase; onNavigate: (t: Tab) => void }) {
  const [planTab, setPlanTab] = useState<"domains" | "priority" | "records">("domains");
  const [draft, setDraft] = useState("");

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-[18px] font-semibold text-[#172033]">{caseObj.childName} · 사례관리 계획</h2>
        <div className="flex items-center gap-1 bg-white border border-[#E2E8F0] rounded-[8px] p-0.5">
          {(["domains", "priority", "records"] as const).map((t, i) => {
            const labels = ["문제 영역", "상담사 확인 필요 항목", "사례관리 기록"];
            return (
              <button key={t} onClick={() => setPlanTab(t)}
                className="px-3 py-1.5 text-[12px] font-medium rounded-[6px] transition-all"
                style={{
                  background: planTab === t ? "#172033" : "transparent",
                  color: planTab === t ? "white" : "#64748B",
                }}>
                {labels[i]}
              </button>
            );
          })}
        </div>
      </div>

      <NotServedNotice>
        사례관리 계획은 아직 서버에 없습니다. 화면 구성만 보여 주며, 입력한 내용은 저장되지 않습니다.
      </NotServedNotice>

      {planTab === "domains" && (
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["문제 영역", "위험 수준", "주요 근거", "발화 출처", ""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-[13px] text-[#94A3B8]">정리된 문제 영역이 아직 없습니다.</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {planTab === "priority" && (
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-10 text-center text-[13px] text-[#94A3B8]">
          상담사 확인 필요 항목이 아직 없습니다.
        </div>
      )}

      {planTab === "records" && (
        <div className="space-y-4">
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-5 py-8 text-center text-[13px] text-[#94A3B8]">
            사례관리 기록이 아직 없습니다.
          </div>
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-4">
            <p className="text-[12px] font-semibold text-[#94A3B8] mb-2">새 기록 추가</p>
            <textarea
              value={draft}
              onChange={e => setDraft(e.target.value)}
              className="w-full h-24 text-[13px] border border-[#E2E8F0] rounded-[6px] p-3 text-[#172033] placeholder:text-[#CBD5E1] focus:outline-none focus:border-[#2563EB] resize-none"
              placeholder="상담 내용, 조치 사항, 소견 등을 기록하세요..."
            />
            <div className="flex items-center justify-end gap-3 mt-2">
              <span className="text-[12px] text-[#94A3B8]">서버에 저장 기능이 아직 없습니다.</span>
              <button
                disabled
                className="px-3 py-1.5 text-[12px] font-medium text-white bg-[#2563EB] rounded-[6px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                기록 저장
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={() => onNavigate("closure")}
          className="flex items-center gap-2 px-4 py-2 text-[13px] font-medium text-white rounded-[6px] bg-[#15314A] hover:bg-[#0F263B] transition-colors"
        >
          종결·가정복귀 검토로 이동
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
      </div>
    </div>
  );
}

// ─── Previous Sessions Tab ────────────────────────────────────────────────────

const STT_CHIP: Record<string, { bg: string; color: string }> = {
  "분석완료": { bg: "#F0FDF4", color: "#16A34A" },
  "검수완료": { bg: "#EFF6FF", color: "#2563EB" },
  "원문 변환 실패": { bg: "#FEF2F2", color: "#B91C1C" },
};

const AI_CHIP: Record<string, { bg: string; color: string }> = {
  "상담사검토완료": { bg: "#F0FDF4", color: "#16A34A" },
  "검토완료":       { bg: "#EFF6FF", color: "#2563EB" },
  "검토필요":       { bg: "#FFF7ED", color: "#D97706" },
  "AI 분석 실패":   { bg: "#FEF2F2", color: "#B91C1C" },
};

/** 요약 상태를 사람에게 보여줄 문구. */
function summaryStatusText(summary: Summary | null): string {
  if (!summary) return NOT_PROVIDED;

  return `${summary.status === "APPROVED" ? "승인됨" : "초안"}${summary.is_edited ? " · 상담사 수정" : ""}`;
}

function SessionDetailView({ session, canCompare, onBack, onCompare }: {
  session: HistoryRow;
  canCompare: boolean;
  onBack: () => void;
  onCompare: () => void;
}) {
  const [summaryEnv, setSummaryEnv]       = useState<SummaryEnvelope | null>(null);
  const [transcriptEnv, setTranscriptEnv] = useState<TranscriptEnvelope | null>(null);
  const [loading, setLoading]             = useState(true);
  const [loadError, setLoadError]         = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setLoadError(null);

    Promise.all([summaryApi.get(session.id), transcriptApi.get(session.id)])
      .then(([s, t]) => {
        if (cancelled) return;
        setSummaryEnv(s);
        setTranscriptEnv(t);
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "회기 기록을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [session.id]);

  const summaryData = summaryEnv?.summary ?? null;
  const transcriptData = transcriptEnv?.transcript ?? null;
  const lines = transcriptData ? toUiTranscriptSegments(transcriptData) : [];

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium flex items-center gap-1">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
            목록으로
          </button>
          <h2 className="text-[18px] font-semibold text-[#172033]">{session.sessionNumber}회차 상담 내역</h2>
        </div>
        {canCompare && (
          <button
            onClick={onCompare}
            className="flex items-center gap-2 px-3 py-1.5 text-[12px] font-medium text-[#2563EB] border border-[#DBEAFE] rounded-[6px] bg-[#EFF6FF] hover:bg-[#DBEAFE] transition-colors"
          >
            현재 상담과 비교
          </button>
        )}
      </div>
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5 space-y-4">
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "상담 일시", value: `${session.date} ${session.time}`.trim() || NOT_PROVIDED },
            { label: "상담 유형", value: session.type },
            { label: "장소", value: session.location },
            { label: "소요 시간", value: session.duration },
          ].map(f => (
            <div key={f.label}>
              <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-1">{f.label}</p>
              <p className="text-[13px] text-[#172033] font-medium">{f.value}</p>
            </div>
          ))}
        </div>
        <div className="border-t border-[#F1F5F9] pt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">상담 내용 요약</p>
            {summaryData && <span className="text-[11px] text-[#64748B]">{summaryStatusText(summaryData)}</span>}
          </div>
          {loading && <p className="text-[13px] text-[#94A3B8]">불러오는 중...</p>}
          {!loading && loadError && <p className="text-[13px] text-red-600">{loadError}</p>}
          {!loading && !loadError && !summaryData && (
            <p className="text-[13px] text-[#94A3B8]">요약이 아직 없습니다. AI 분석이 끝나면 여기에 보입니다.</p>
          )}
          {!loading && summaryData && (
            <div className="space-y-2">
              <p className="text-[13px] text-[#172033]">{summaryData.overview || NOT_PROVIDED}</p>
              {summaryData.key_points.length > 0 && (
                <ul className="space-y-0.5">
                  {summaryData.key_points.map((point, i) => (
                    <li key={i} className="text-[13px] text-[#64748B]">· {point}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
        <div className="border-t border-[#F1F5F9] pt-4">
          <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">전사 원문</p>
          {!loading && !loadError && lines.length === 0 && (
            <p className="text-[13px] text-[#94A3B8]">전사본이 아직 없습니다.</p>
          )}
          {lines.length > 0 && (
            <div className="bg-[#F8FAFC] rounded-[6px] px-4 py-3 space-y-1.5 overflow-y-auto" style={{ maxHeight: "320px" }}>
              {lines.map(line => (
                <p key={line.id} className="text-[13px] text-[#172033]">
                  <span className="font-mono text-[11px] text-[#94A3B8] mr-2">{line.timestamp}</span>
                  <span className="text-[12px] text-[#64748B] mr-2">{line.speakerLabel}</span>
                  {line.text}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * 두 회기의 요약을 나란히 보여 준다. 회기 사이 변화를 판단하는 기능은 Backend 에 없어 "변화" 칸은 "—".
 */
function SessionCompareView({ prev, curr, onBack }: { prev: HistoryRow; curr: HistoryRow; onBack: () => void }) {
  const [prevSummary, setPrevSummary] = useState<Summary | null>(null);
  const [currSummary, setCurrSummary] = useState<Summary | null>(null);
  const [loading, setLoading]         = useState(true);
  const [loadError, setLoadError]     = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setLoadError(null);

    Promise.all([summaryApi.get(prev.id), summaryApi.get(curr.id)])
      .then(([p, c]) => {
        if (cancelled) return;
        setPrevSummary(p.summary);
        setCurrSummary(c.summary);
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "요약을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [prev.id, curr.id]);

  const compareRows = [
    { category: "상담 요약", prev: prevSummary?.overview, curr: currSummary?.overview },
    { category: "주요 내용", prev: prevSummary?.key_points.join(" / "), curr: currSummary?.key_points.join(" / ") },
    { category: "상담사 메모", prev: prevSummary?.counselor_note ?? undefined, curr: currSummary?.counselor_note ?? undefined },
    { category: "검토 상태", prev: summaryStatusText(prevSummary), curr: summaryStatusText(currSummary) },
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium flex items-center gap-1">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          목록으로
        </button>
        <h2 className="text-[18px] font-semibold text-[#172033]">상담 비교: {prev.sessionNumber}회차 ↔ {curr.sessionNumber}회차</h2>
      </div>
      {loading && <p className="text-[13px] text-[#94A3B8]">요약을 불러오는 중...</p>}
      {!loading && loadError && <p className="text-[13px] text-red-600">{loadError}</p>}
      {!loading && !loadError && (
        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <div className="grid grid-cols-[1fr_1fr_1fr_80px] bg-[#F8FAFC] border-b border-[#E2E8F0]">
            <div className="px-4 py-2.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">항목</div>
            <div className="px-4 py-2.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider border-l border-[#E2E8F0]">이전 ({prev.sessionNumber}회차)</div>
            <div className="px-4 py-2.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider border-l border-[#E2E8F0]">현재 ({curr.sessionNumber}회차)</div>
            <div className="px-4 py-2.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider border-l border-[#E2E8F0] text-center">변화</div>
          </div>
          {compareRows.map((r, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_80px] border-b border-[#F1F5F9]">
              <div className="px-4 py-3 text-[13px] font-semibold text-[#172033]">{r.category}</div>
              <div className="px-4 py-3 text-[13px] text-[#64748B] border-l border-[#F1F5F9]">{r.prev || NOT_PROVIDED}</div>
              <div className="px-4 py-3 text-[13px] text-[#172033] border-l border-[#F1F5F9]">{r.curr || NOT_PROVIDED}</div>
              <div className="px-4 py-3 border-l border-[#F1F5F9] flex items-center justify-center">
                <span className="text-[12px] text-[#94A3B8]">{NOT_PROVIDED}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function HistoryTab({ caseObj, sessions, sessionsLoading, sessionsError }: SessionListProps) {
  const rows = useMemo(() => sortSessionsLatestFirst(sessions).map(toHistoryRow), [sessions]);
  const [viewSession, setViewSession] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);

  const currentSession = rows[0];
  const selected = rows.find(s => s.id === viewSession);

  if (compareMode && selected && currentSession) {
    return <SessionCompareView prev={selected} curr={currentSession} onBack={() => setCompareMode(false)} />;
  }

  if (viewSession && selected && currentSession) {
    return (
      <SessionDetailView
        session={selected}
        canCompare={selected.sessionNumber !== currentSession.sessionNumber}
        onBack={() => setViewSession(null)}
        onCompare={() => setCompareMode(true)}
      />
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      <h2 className="text-[18px] font-semibold text-[#172033]">{caseObj.childName} · 이전 상담 내역</h2>
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <table className="w-full">
          <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
            <tr>
              {["회차", "일시", "유형", "장소", "소요시간", "STT", "AI 분석", ""].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((s, i) => {
              const stt = STT_CHIP[s.sttLabel] ?? { bg: "#FFFBEB", color: "#D97706" };
              const ai = AI_CHIP[s.aiLabel] ?? { bg: "#F8FAFC", color: "#94A3B8" };
              return (
                <tr key={s.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer" onClick={() => setViewSession(s.id)}>
                  <td className="px-4 py-3 text-[13px] font-semibold text-[#172033]">
                    {s.sessionNumber}회차
                    {i === 0 && <span className="ml-1.5 text-[10px] px-1.5 py-0.5 bg-[#EFF6FF] text-[#2563EB] rounded font-medium">최근</span>}
                  </td>
                  <td className="px-4 py-3 text-[12px] font-mono text-[#64748B]">{s.date || NOT_PROVIDED}</td>
                  <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.type}</td>
                  <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.location}</td>
                  <td className="px-4 py-3 text-[12px] text-[#64748B]">{s.duration}</td>
                  <td className="px-4 py-3">
                    <span className="text-[11px] px-1.5 py-0.5 rounded font-medium" style={{ background: stt.bg, color: stt.color }}>
                      {s.sttLabel}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-[11px] px-1.5 py-0.5 rounded font-medium" style={{ background: ai.bg, color: ai.color }}>
                      {s.aiLabel}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button className="text-[12px] text-[#2563EB] hover:text-[#1D4ED8] font-medium" onClick={e => { e.stopPropagation(); setViewSession(s.id); }}>
                      상세
                    </button>
                  </td>
                </tr>
              );
            })}
            {sessionsLoading && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-[13px] text-[#94A3B8]">회기 목록을 불러오는 중...</td></tr>
            )}
            {!sessionsLoading && sessionsError && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-[13px] text-red-600">{sessionsError}</td></tr>
            )}
            {!sessionsLoading && !sessionsError && rows.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-[13px] text-[#94A3B8]">등록된 회기가 없습니다.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Closure Tab ─────────────────────────────────────────────────────────────
//
// 종결 · 가정복귀 검토는 Backend 에 없다. 점검 항목 이름만 두고 근거 · 출처는 비워 둔다
// (예시 발화를 사실처럼 보이지 않게). 제출은 막아 둔다.

type ClosureItemStatus = "근거확인" | "정보부족" | "해당없음" | "추가상담필요" | null;

interface ClosureCheckItem {
  id: string;
  label: string;
  required: boolean;
}

const CLOSURE_CHECK_ITEMS: ClosureCheckItem[] = [
  { id: "c1", label: "신체적 위험 신호 해소 여부", required: true },
  { id: "c2", label: "보호자 협조 충분성 확인", required: true },
  { id: "c3", label: "아동 정서 안정화 여부", required: true },
  { id: "c4", label: "아동 안전 환경 확인", required: true },
  { id: "c5", label: "지역사회 연계 자원 확인", required: true },
  { id: "c6", label: "후속 모니터링 계획 수립", required: true },
  { id: "c7", label: "아동 의견 청취 여부", required: false },
  { id: "c8", label: "보호자 양육 역량 향상 여부", required: false },
];

const STATUS_BTN_LABELS: Record<NonNullable<ClosureItemStatus>, string> = {
  "근거확인": "근거 확인",
  "정보부족": "정보 부족",
  "해당없음": "해당 없음",
  "추가상담필요": "추가 상담 필요",
};

function ClosureTab({ caseObj }: { caseObj: ManagedCase }) {
  const [itemStatuses, setItemStatuses] = useState<Record<string, ClosureItemStatus>>({});
  const [itemMemos, setItemMemos] = useState<Record<string, string>>({});
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [opinion, setOpinion] = useState("");
  const navigate = useNavigate();

  const requiredItems = CLOSURE_CHECK_ITEMS.filter(i => i.required);
  const allRequiredDone = requiredItems.every(i => itemStatuses[i.id] != null);

  const counts = {
    total: requiredItems.length,
    confirmed: requiredItems.filter(i => itemStatuses[i.id] === "근거확인").length,
    insufficient: requiredItems.filter(i => itemStatuses[i.id] === "정보부족").length,
    additional: requiredItems.filter(i => itemStatuses[i.id] === "추가상담필요").length,
  };

  function setItemStatus(id: string, status: ClosureItemStatus) {
    setItemStatuses(prev => ({ ...prev, [id]: status }));
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB] p-6 space-y-5">
      <h2 className="text-[18px] font-semibold text-[#172033]">{caseObj.childName} · 종결 검토 항목 확인 현황</h2>

      <NotServedNotice>
        종결 · 가정복귀 검토는 아직 서버에 없습니다. 항목 확인과 의견은 이 화면에만 남고 저장 · 제출되지 않습니다.
      </NotServedNotice>

      {/* 전체 현황 통계 */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#E2E8F0]">
          <span className="text-[14px] font-semibold text-[#172033]">필수 검토 항목 현황</span>
        </div>
        <div className="grid grid-cols-4 divide-x divide-[#E2E8F0]">
          {[
            { label: "전체 필수 항목", value: counts.total },
            { label: "근거 확인 완료", value: counts.confirmed },
            { label: "정보 부족", value: counts.insufficient },
            { label: "추가 상담 필요", value: counts.additional },
          ].map(s => (
            <div key={s.label} className="px-5 py-3">
              <p className="text-[12px] text-[#64748B] mb-1">{s.label}</p>
              <p className="text-[22px] font-semibold text-[#172033]">{s.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 검토 항목 목록 */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
          <span className="text-[14px] font-semibold text-[#172033]">종결 검토 항목</span>
          <span className="text-[12px] text-[#94A3B8]">항목을 클릭하면 근거를 확인할 수 있습니다</span>
        </div>
        <div className="divide-y divide-[#F1F5F9]">
          {CLOSURE_CHECK_ITEMS.map(item => {
            const status = itemStatuses[item.id];
            const isOpen = expandedItem === item.id;
            return (
              <div key={item.id}>
                <div className="px-5 py-4">
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => setExpandedItem(isOpen ? null : item.id)}
                      className="flex-1 flex items-center gap-2 text-left"
                    >
                      <span className={`text-[11px] border rounded px-1.5 py-0.5 shrink-0 ${item.required ? "border-[#64748B] text-[#172033] font-semibold" : "border-[#CBD5E1] text-[#94A3B8]"}`}>
                        {item.required ? "필수" : "선택"}
                      </span>
                      <span className="text-[14px] font-medium text-[#172033] flex-1">{item.label}</span>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 transition-transform" style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0)" }}><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="flex gap-1 shrink-0">
                      {(["근거확인", "정보부족", "해당없음", "추가상담필요"] as NonNullable<ClosureItemStatus>[]).map(s => (
                        <button
                          key={s}
                          onClick={() => setItemStatus(item.id, status === s ? null : s)}
                          className="px-2.5 py-1.5 text-[12px] rounded-[6px] border transition-all"
                          style={{
                            borderColor: status === s ? "#2563EB" : "#E2E8F0",
                            background: status === s ? "#EFF6FF" : "white",
                            color: status === s ? "#2563EB" : "#64748B",
                            fontWeight: status === s ? 600 : 400,
                          }}
                        >
                          {STATUS_BTN_LABELS[s]}
                        </button>
                      ))}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="mt-3 pl-12 space-y-3">
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] p-4">
                        <div className="grid grid-cols-2 gap-3 text-[13px] mb-3">
                          <div><span className="text-[#94A3B8] mr-2">관련 근거</span><span className="text-[#172033]">{NOT_PROVIDED}</span></div>
                          <div><span className="text-[#94A3B8] mr-2">출처</span><span className="text-[#172033]">{NOT_PROVIDED}</span></div>
                          <div><span className="text-[#94A3B8] mr-2">확인 회차</span><span className="text-[#172033]">{NOT_PROVIDED}</span></div>
                        </div>
                        <div className="border-t border-[#E2E8F0] pt-3">
                          <p className="text-[12px] text-[#94A3B8] mb-1">원문 발화 또는 기록</p>
                          <p className="text-[13px] text-[#94A3B8]">연결된 근거가 아직 없습니다.</p>
                        </div>
                      </div>
                      {status === "정보부족" && (
                        <div>
                          <p className="text-[12px] text-[#64748B] mb-1.5">정보 부족 메모</p>
                          <textarea
                            value={itemMemos[item.id] ?? ""}
                            onChange={e => setItemMemos(prev => ({ ...prev, [item.id]: e.target.value }))}
                            rows={2}
                            placeholder="어떤 정보가 필요한지 기록하세요..."
                            className="w-full px-3 py-2 text-[13px] border border-[#E2E8F0] rounded-[6px] text-[#172033] resize-none focus:outline-none focus:border-[#2563EB]"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 상담사 최종 의견 */}
      <div className="bg-white border border-[#E2E8F0] rounded-[8px] p-5 space-y-4">
        <p className="text-[14px] font-semibold text-[#172033]">상담사 최종 의견</p>
        <textarea
          value={opinion}
          onChange={e => setOpinion(e.target.value)}
          className="w-full h-24 text-[13px] border border-[#E2E8F0] rounded-[6px] p-3 text-[#172033] placeholder:text-[#CBD5E1] focus:outline-none focus:border-[#2563EB] resize-none"
          placeholder="종결 또는 가정복귀에 대한 상담사 의견을 입력하세요..."
        />
        {!allRequiredDone && (
          <p className="text-[13px] text-[#64748B] border border-[#E2E8F0] rounded-[6px] px-3 py-2 bg-[#F8FAFC]">
            필수 검토 항목을 모두 확인해야 제출할 수 있습니다.
          </p>
        )}
        <div className="flex items-center justify-end gap-2">
          <span className="text-[12px] text-[#94A3B8] mr-1">서버에 제출 기능이 아직 없습니다.</span>
          <button
            onClick={() => navigate(`/cases/${caseObj.backendId}/reports`)}
            className="px-3 py-2 text-[13px] font-medium text-[#64748B] border border-[#E2E8F0] rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
          >
            보고서 생성
          </button>
          <button
            disabled
            className="px-4 py-2 text-[13px] font-medium text-white rounded-[6px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ background: "#94A3B8" }}
          >
            종결 검토 자료 제출
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Case List (entry view) ───────────────────────────────────────────────────

function CaseListView({ cases, loading, error, onSelect }: {
  cases: ManagedCase[];
  loading: boolean;
  error: string | null;
  onSelect: (c: ManagedCase) => void;
}) {
  const [query, setQuery] = useState("");
  // 위험도는 사례 단위로 Backend 에 없어 최근 상담순만 쓴다(위험도순 단추는 막아 둔다).
  const rows = useMemo(
    () => sortByRecentSession(cases.filter(c => matchesQuery(c, query))),
    [cases, query],
  );

  return (
    <div className="flex-1 overflow-y-auto bg-[#F6F8FB]">
      <div className="p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[22px] font-semibold text-[#172033]">사례 관리</h1>
            <p className="text-[14px] text-[#64748B] mt-0.5">관리할 사례를 선택하세요</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-0.5 text-[13px] text-[#94A3B8] bg-white border border-[#E2E8F0] rounded-[6px] px-1 py-1">
              <button disabled title="위험도는 아직 서버에 없습니다" className="px-2.5 py-1 rounded transition-all opacity-50 cursor-not-allowed">위험도순</button>
              <button className="px-2.5 py-1 rounded transition-all font-semibold text-[#172033] bg-[#F1F5F9]">최근상담순</button>
            </div>
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="아동명·사례ID" className="pl-8 pr-3 py-2 rounded-[6px] border border-[#E2E8F0] text-[13px] focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] bg-white w-48 transition-all" />
            </div>
          </div>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {["아동명", "사례 ID", "위험도", "상담 회차", "최근 상담", "상태", "담당 상담사", ""].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[12px] font-semibold text-[#64748B] whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(c => (
                <tr
                  key={c.backendId}
                  onClick={() => onSelect(c)}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                >
                  <td className="px-4 py-3.5 text-[14px] font-semibold text-[#172033]">{c.childName}</td>
                  <td className="px-4 py-3.5 text-[12px] font-mono text-[#64748B]">{c.caseNumber}</td>
                  <td className="px-4 py-3.5 text-[13px] text-[#94A3B8]">{NOT_PROVIDED}</td>
                  <td className="px-4 py-3.5 text-[13px] text-[#94A3B8]">{NOT_PROVIDED}</td>
                  <td className="px-4 py-3.5 text-[13px] font-mono text-[#475569]">{c.lastSession || NOT_PROVIDED}</td>
                  <td className="px-4 py-3.5"><CaseStatusChip c={c} /></td>
                  <td className="px-4 py-3.5 text-[13px] text-[#475569]">{c.counselor}</td>
                  <td className="px-4 py-3.5">
                    <button className="text-[13px] text-[#2563EB] hover:text-[#1D4ED8] font-medium">선택</button>
                  </td>
                </tr>
              ))}
              {loading && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-[14px] text-[#94A3B8]">사례 목록을 불러오는 중...</td></tr>
              )}
              {!loading && error && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-[14px] text-red-600">{error}</td></tr>
              )}
              {!loading && !error && rows.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-[14px] text-[#94A3B8]">
                  {cases.length === 0 ? "담당 사례가 없습니다." : "검색 조건에 맞는 사례가 없습니다."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function CaseManagementPage() {
  const [cases, setCases]                     = useState<ManagedCase[]>([]);
  const [casesLoading, setCasesLoading]       = useState(true);
  const [casesError, setCasesError]           = useState<string | null>(null);
  const [selectedCase, setSelectedCase]       = useState<ManagedCase | null>(null);
  const [activeTab, setActiveTab]             = useState<Tab>("ai-review");
  const [sessions, setSessions]               = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError]     = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    casesApi
      .list({ page: 1, page_size: CASE_PAGE_SIZE })
      .then((page) => {
        if (!cancelled) setCases(page.items.map(toManagedCase));
      })
      .catch((caught) => {
        if (!cancelled) setCasesError(describeApiError(caught, "사례 목록을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setCasesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // 고른 사례의 회기 목록. 분석 결과 검토 · 이전 상담 탭과 탭 배지가 함께 쓴다.
  const selectedId = selectedCase?.backendId;

  useEffect(() => {
    if (!selectedId) return;

    let cancelled = false;

    setSessions([]);
    setSessionsLoading(true);
    setSessionsError(null);

    casesApi
      .listSessions(selectedId, { page: 1, page_size: SESSION_PAGE_SIZE })
      .then((page) => {
        if (!cancelled) setSessions(page.items);
      })
      .catch((caught) => {
        if (!cancelled) setSessionsError(describeApiError(caught, "회기 목록을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setSessionsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  if (!selectedCase) {
    return (
      <CaseListView
        cases={cases}
        loading={casesLoading}
        error={casesError}
        onSelect={c => { setSelectedCase(c); setActiveTab("ai-review"); }}
      />
    );
  }

  // 상담사가 할 일이 있는 회기 수. 메뉴 배지(분석 요청 · 결과 검토 · 다시 요청)와 같은 기준이다.
  const reviewCount = sessions.filter(s => NEEDS_ACTION_STATUSES.includes(s.status)).length;
  const sessionProps = { caseObj: selectedCase, sessions, sessionsLoading, sessionsError };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header with case info + back button */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-3 shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSelectedCase(null)}
            className="flex items-center gap-1.5 text-[13px] text-[#64748B] hover:text-[#172033] transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            사례 목록
          </button>
          <span className="text-[#E2E8F0]">/</span>
          <div>
            <span className="text-[16px] font-semibold text-[#172033]">{selectedCase.childName}</span>
            <span className="text-[13px] text-[#94A3B8] font-mono ml-2">{selectedCase.caseNumber}</span>
          </div>
          <CaseStatusChip c={selectedCase} />
        </div>
      </div>

      {/* Sub-nav */}
      <SubNav active={activeTab} onChange={setActiveTab} reviewCount={reviewCount} />

      {/* Content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {activeTab === "ai-review" && <AiReviewTab key={selectedCase.backendId} {...sessionProps} onNavigate={setActiveTab} />}
        {activeTab === "plan"      && <CasePlanTab caseObj={selectedCase} onNavigate={setActiveTab} />}
        {activeTab === "history"   && <HistoryTab key={selectedCase.backendId} {...sessionProps} />}
        {activeTab === "closure"   && <ClosureTab caseObj={selectedCase} />}
      </div>
    </div>
  );
}
