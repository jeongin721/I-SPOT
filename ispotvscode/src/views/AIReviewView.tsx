import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router";
import CaseSelectorPanel from "../components/CaseSelectorPanel";
import Breadcrumb from "../components/ui/Breadcrumb";
import ConfirmModal from "../components/ui/ConfirmModal";
import { useToast } from "../components/ui/Toast";
import { ApiError } from "../api/client";
import {
  analysis as analysisApi,
  cases as casesApi,
  sessions as sessionsApi,
  summary as summaryApi,
  transcript as transcriptApi,
} from "../api/endpoints";
import type {
  AIAnalysis,
  AnalysisEnvelope,
  SessionErrorInfo,
  SessionStatus,
  Summary,
  SummaryEnvelope,
  SummaryEvidenceItem,
} from "../api/types";
import type { CaseRecord } from "../data/cases";
import type { Session as UiSession } from "../data/mockData";
import {
  NOT_PROVIDED,
  describeApiError,
  deriveStatus,
  toUiCase,
  toUiSession,
  toUiTranscriptSegments,
  type UiTranscriptSegment,
} from "../api/adapters";
import {
  riskSegmentIdSet,
  toLocalDateTime,
  toReviewStage,
  toSummaryDraft,
  toSummaryUpdate,
  toUiEvidence,
  toUiReferenceSignals,
  toUiRiskUtterances,
  type SummaryDraft,
} from "../api/aiAdapters";

// 주소의 caseId 는 사례 UUID, analysisId 는 회기 UUID 다(AI 분석은 회기당 하나라 회기로 찾는다).
//
// - 왼쪽 음성 원문: GET /sessions/{id}/transcript
// - 위험 관련 발화 강조: AI 결과(GET /sessions/{id}/analysis)의 risk_utterances 근거 발화(segment_id)
// - 오른쪽 상담일지: 상담사 검수용 요약(GET · PATCH /sessions/{id}/summary), "검토 완료" 는 승인(POST .../approve)
// - 사정기록지 초안 · 과거 중대사건 대조는 아직 Backend 에 없어 안내만 보여 준다.
//
// AI 결과는 판정이 아니라 참고정보다. 승인은 상담사가 직접 한다.

/** AI 분석이 끝나기를 기다릴 때 다시 확인하는 간격과 횟수(약 2분). 전사 검수 화면과 같다. */
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_TRIES = 60;

const EMPTY_DRAFT: SummaryDraft = { overview: "", keyPointsText: "", counselorNote: "" };

export default function AIReviewView() {
  const { caseId, analysisId: sessionId } = useParams<{ caseId: string; analysisId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  // 주소 없이 열리면(현재 경로 설정에는 없다) 왼쪽 선택 패널만 보인다.
  const [selectedId, setSelectedId] = useState(caseId ?? "");
  const [activeDoc, setActiveDoc] = useState<"diary" | "report">("diary");
  const [showModal, setShowModal] = useState(false);
  const [showApprove, setShowApprove] = useState(false);

  const [caseInfo, setCaseInfo] = useState<CaseRecord | null>(null);
  const [sessionInfo, setSessionInfo] = useState<UiSession | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [segments, setSegments] = useState<UiTranscriptSegment[]>([]);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [aiError, setAiError] = useState<SessionErrorInfo | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [evidence, setEvidence] = useState<SummaryEvidenceItem[]>([]);
  const [draft, setDraft] = useState<SummaryDraft>(EMPTY_DRAFT);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  /** 근거 발화 보기로 강조 중인 발화 번호. */
  const [focusIds, setFocusIds] = useState<string[]>([]);

  function applyAnalysis(envelope: AnalysisEnvelope) {
    setStatus(envelope.session_status);
    setAnalysis(envelope.analysis);
    setAiError(envelope.error ?? envelope.analysis?.error ?? null);
  }

  function applySummary(envelope: SummaryEnvelope) {
    setSummary(envelope.summary);
    setEvidence(envelope.summary_evidence);
    setDraft(toSummaryDraft(envelope.summary));
  }

  useEffect(() => {
    if (!caseId || !sessionId) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setLoadError(null);

    Promise.all([
      casesApi.get(caseId),
      sessionsApi.get(sessionId),
      transcriptApi.get(sessionId),
      analysisApi.get(sessionId),
      summaryApi.get(sessionId),
    ])
      .then(([c, s, transcriptEnvelope, analysisEnvelope, summaryEnvelope]) => {
        if (cancelled) return;
        if (s.case_id !== c.id) {
          setLoadError("주소의 사례와 회기가 맞지 않습니다.");
          return;
        }
        setCaseInfo(toUiCase(c, { sessionCount: c.session_count }));
        setSessionInfo(toUiSession(s, c.case_number, { counselorName: c.counselor_name ?? undefined }));
        setSegments(transcriptEnvelope.transcript ? toUiTranscriptSegments(transcriptEnvelope.transcript) : []);
        applyAnalysis(analysisEnvelope);
        applySummary(summaryEnvelope);
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "AI 분석 결과를 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId, sessionId]);

  // AI 분석이 도는 중이면 끝날 때까지 결과를 다시 확인한다. 끝나면 요약도 함께 받는다.
  const [pollTries, setPollTries] = useState(0);

  useEffect(() => {
    if (status !== "AI_PROCESSING" || !sessionId || pollTries >= POLL_MAX_TRIES) return;

    const timer = window.setTimeout(() => {
      analysisApi
        .get(sessionId)
        .then(async (envelope) => {
          if (envelope.session_status !== "AI_PROCESSING") {
            applySummary(await summaryApi.get(sessionId));
          }
          applyAnalysis(envelope);
        })
        .catch(() => {
          // 한 번 실패해도 다음 확인에서 다시 시도한다.
        })
        .finally(() => setPollTries(n => n + 1));
    }, POLL_INTERVAL_MS);

    return () => window.clearTimeout(timer);
  }, [status, sessionId, pollTries]);

  /**
   * 다른 사람이 먼저 처리했을 수 있을 때 서버 상태로 다시 맞춘다.
   * 요약 편집 칸도 서버 값으로 바뀌므로, 저장 · 승인 실패에서는 상태 충돌(409)일 때만 부른다.
   * 연결 오류 같은 다른 실패에서 부르면 상담사가 쓰던 내용이 사라진다.
   */
  function resync() {
    if (!sessionId) return;

    Promise.all([analysisApi.get(sessionId), summaryApi.get(sessionId)])
      .then(([analysisEnvelope, summaryEnvelope]) => {
        applyAnalysis(analysisEnvelope);
        applySummary(summaryEnvelope);
      })
      .catch(() => {
        // 다시 맞추지 못해도 화면은 그대로 둔다. 새로고침하면 된다.
      });
  }

  const stage = status ? toReviewStage(status) : null;
  const result = analysis?.result ?? null;
  const riskUtterances = useMemo(() => toUiRiskUtterances(result, segments), [result, segments]);
  const riskIds = useMemo(() => riskSegmentIdSet(riskUtterances), [riskUtterances]);
  const referenceSignals = useMemo(() => toUiReferenceSignals(result), [result]);
  const evidenceRows = useMemo(() => toUiEvidence(evidence, segments), [evidence, segments]);
  const warnings = result?.warnings ?? [];
  const editable = stage === "review" && summary?.status === "DRAFT";
  const approved = summary?.status === "APPROVED";
  const pendingUpdate = summary ? toSummaryUpdate(summary, draft) : null;

  /** 근거 발화를 왼쪽 원문에서 강조하고 첫 발화로 옮겨 간다. 같은 것을 다시 누르면 끈다. */
  function focusSegments(ids: string[]) {
    const same = ids.length === focusIds.length && ids.every(id => focusIds.includes(id));
    setFocusIds(same ? [] : ids);
    if (!same && ids[0]) {
      document.getElementById(`ai-seg-${ids[0]}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  /** AI 분석 요청(POST .../analysis). 202 로 돌아오고, 결과는 위의 재확인이 받아 온다. */
  async function handleRequestAnalysis() {
    if (!sessionId || requesting) return;

    setRequesting(true);
    try {
      const response = await analysisApi.run(sessionId);
      setStatus(response.session_status);
      setAiError(null);
      setPollTries(0);
      showToast("AI 분석을 요청했습니다.", "success");
    } catch (caught) {
      showToast(describeApiError(caught, "AI 분석 요청에 실패했습니다.", "권한이 없거나 없는 회기입니다."), "error");
      resync();
    } finally {
      setRequesting(false);
    }
  }

  /** 바뀐 필드만 저장한다(PATCH .../summary). 바뀐 것이 없으면 보내지 않는다. */
  async function handleSave() {
    if (!sessionId || !summary || !pendingUpdate || saving) return;

    setSaving(true);
    try {
      const updated = await summaryApi.update(sessionId, pendingUpdate);
      setSummary(updated);
      setDraft(toSummaryDraft(updated));
      showToast("수정한 내용을 저장했습니다.", "success");
    } catch (caught) {
      showToast(describeApiError(caught, "저장에 실패했습니다.", "권한이 없거나 없는 회기입니다."), "error");
      if (caught instanceof ApiError && caught.status === 409) resync();
    } finally {
      setSaving(false);
    }
  }

  /** 검토 완료 = 승인(POST .../summary/approve). 저장하지 않은 수정이 있으면 먼저 저장한다. */
  async function handleApprove() {
    if (!sessionId || !summary || approving) return;

    setApproving(true);
    try {
      if (pendingUpdate) await summaryApi.update(sessionId, pendingUpdate);
      const approvedSummary = await summaryApi.approve(sessionId);
      setSummary(approvedSummary);
      setDraft(toSummaryDraft(approvedSummary));
      setStatus("APPROVED");
      setShowApprove(false);
      showToast("검토를 완료했습니다.", "success");
    } catch (caught) {
      setShowApprove(false);
      showToast(describeApiError(caught, "검토 완료 처리에 실패했습니다.", "권한이 없거나 없는 회기입니다."), "error");
      if (caught instanceof ApiError && caught.status === 409) resync();
    } finally {
      setApproving(false);
    }
  }

  const isRouted = !!caseId && !!sessionId;
  const childName = caseInfo?.childName ?? "—";
  const caseNumber = caseInfo?.id ?? "—";
  const docReady = stage === "review" || stage === "approved";

  const textareaCls = "w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-sm font-mono text-[#172033] leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-[#2563EB] disabled:bg-[#F8FAFC] disabled:text-[#64748B]";

  function renderDiaryBody() {
    if (stage === null) return null;

    if (stage === "beforeStt") {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-[#94A3B8] space-y-3 p-6 text-center">
          <p className="text-sm text-[#172033] font-medium">먼저 STT 검수를 마쳐 주세요</p>
          <p className="text-xs">
            현재 상태: {status ? deriveStatus(status).label : "—"} · 전사본을 검수 확정하면 AI 분석을 요청할 수 있습니다.
          </p>
          <button
            onClick={() => navigate(`/cases/${caseId}/sessions/${sessionId}/transcript`)}
            className="px-4 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-blue-700 transition-colors"
          >
            전사 검수로 이동
          </button>
        </div>
      );
    }

    if (stage === "ready") {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-[#94A3B8] space-y-3 p-6 text-center">
          <p className="text-sm text-[#172033] font-medium">아직 AI 분석을 요청하지 않았습니다</p>
          <p className="text-xs">검수 확정된 전사본으로 AI 분석을 요청하면 상담 내용 요약 초안이 만들어집니다.</p>
          <button
            onClick={handleRequestAnalysis}
            disabled={requesting}
            className="px-4 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {requesting ? "요청 중..." : "AI 분석 요청"}
          </button>
        </div>
      );
    }

    if (stage === "processing") {
      const gaveUp = pollTries >= POLL_MAX_TRIES;
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-[#94A3B8] space-y-3 p-6 text-center">
          <p className="text-sm text-[#172033] font-medium">AI 분석 중입니다</p>
          <p className="text-xs">
            {gaveUp ? "분석이 오래 걸리고 있습니다. 잠시 뒤 다시 확인해 주세요." : "끝나면 이 화면에 요약 초안이 나타납니다."}
          </p>
          {gaveUp && (
            <button
              onClick={() => setPollTries(0)}
              className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
            >
              다시 확인
            </button>
          )}
        </div>
      );
    }

    if (stage === "failed") {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-[#94A3B8] space-y-3 p-6 text-center">
          <p className="text-sm text-red-700 font-medium">AI 분석에 실패했습니다</p>
          <p className="text-xs text-red-600">{aiError?.message ?? "잠시 뒤 다시 요청해 주세요."}</p>
          <button
            onClick={handleRequestAnalysis}
            disabled={requesting}
            className="px-4 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {requesting ? "요청 중..." : "다시 요청"}
          </button>
        </div>
      );
    }

    if (!summary) {
      return (
        <div className="flex-1 flex items-center justify-center text-[#94A3B8] text-sm p-6 text-center">
          아직 서버에 상담 요약이 없습니다.
        </div>
      );
    }

    return (
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        <div className="text-xs font-mono text-[#64748B] space-y-0.5">
          <p>
            [상담일지] {sessionInfo ? `${sessionInfo.sessionNumber}회차 · ${sessionInfo.date}` : "—"}
            {caseInfo && caseInfo.counselor !== NOT_PROVIDED ? ` · ${caseInfo.counselor} 상담사` : ""}
          </p>
          <p className="text-amber-800 font-semibold">※ AI 분석 참고정보 — 상담사 검토 필요</p>
        </div>

        {warnings.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-[6px] px-3.5 py-2.5">
            <p className="text-xs font-semibold text-amber-800 mb-1">AI 분석 참고 안내</p>
            <ul className="space-y-0.5">
              {warnings.map((w, i) => <li key={i} className="text-xs text-amber-700">• {w}</li>)}
            </ul>
          </div>
        )}

        {referenceSignals.length > 0 && (
          <div className="border border-[#E2E8F0] rounded-[6px] px-3.5 py-2.5">
            <p className="text-xs font-semibold text-[#172033] mb-1.5">【AI 분석 참고정보】 ← 상담사 검토 및 최종 판단</p>
            <div className="space-y-1">
              {referenceSignals.map(signal => (
                <button
                  key={signal.key}
                  onClick={() => focusSegments(signal.segmentIds)}
                  className="block text-left text-xs text-[#475569] hover:text-[#2563EB] transition-colors"
                >
                  • {signal.label} — 추가 확인 필요 · 근거 발화 {signal.segmentIds.length}건
                </button>
              ))}
            </div>
          </div>
        )}

        <section className="space-y-1.5">
          <label className="block text-xs font-semibold text-[#172033]">【상담 내용 요약】</label>
          <textarea
            value={draft.overview}
            onChange={e => setDraft(d => ({ ...d, overview: e.target.value }))}
            disabled={!editable}
            rows={5}
            className={textareaCls}
          />
        </section>

        <section className="space-y-1.5">
          <label className="block text-xs font-semibold text-[#172033]">
            【주요 내용】 <span className="font-normal text-[#94A3B8]">한 줄에 하나씩</span>
          </label>
          <textarea
            value={draft.keyPointsText}
            onChange={e => setDraft(d => ({ ...d, keyPointsText: e.target.value }))}
            disabled={!editable}
            rows={5}
            className={textareaCls}
          />
          {evidenceRows.length > 0 && (
            <div className="pt-1 space-y-1">
              <p className="text-[11px] font-semibold text-[#64748B]">AI 근거 발화 (누르면 왼쪽 원문에서 강조)</p>
              {evidenceRows.map(ev => (
                <button
                  key={ev.key}
                  onClick={() => focusSegments(ev.segmentIds)}
                  className="block w-full text-left text-[11px] text-[#475569] hover:text-[#2563EB] transition-colors"
                >
                  <span className="mr-1">"{ev.keyPoint}"</span>
                  <span className="font-mono text-[#94A3B8]">({ev.refs.join(", ")})</span>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="space-y-1.5">
          <label className="block text-xs font-semibold text-[#172033]">【상담사 소견 및 계획】</label>
          <textarea
            value={draft.counselorNote}
            onChange={e => setDraft(d => ({ ...d, counselorNote: e.target.value }))}
            disabled={!editable}
            rows={4}
            placeholder="(상담사가 직접 작성 또는 수정하세요)"
            className={textareaCls}
          />
        </section>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {!isRouted && (
        <CaseSelectorPanel selectedId={selectedId} onSelect={id => setSelectedId(id)} />
      )}

      <div className="flex-1 flex flex-col overflow-hidden bg-[#F6F8FB]">
        {isRouted && (
          <div className="px-6 pt-4 pb-2 shrink-0">
            <Breadcrumb items={[
              { label: "AI 분석 검토", to: "/ai-cases" },
              { label: childName, to: `/cases/${caseId}/analyses` },
              { label: sessionInfo ? `${sessionInfo.sessionNumber}회차 분석 결과` : "분석 결과" },
            ]} />
          </div>
        )}

        {/* Page header */}
        <div className="px-6 py-4 border-b border-[#E2E8F0] bg-white shrink-0 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#172033]">분석 결과 검토</h1>
            <p className="text-[#64748B] text-sm mt-0.5">
              <span className="font-semibold text-[#172033]">{childName}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              <span className="font-mono text-xs">{caseNumber}</span>
              {sessionInfo && (
                <>
                  <span className="mx-1.5 text-[#94A3B8]">·</span>
                  {sessionInfo.sessionNumber}회차
                </>
              )}
              {status && (
                <>
                  <span className="mx-1.5 text-[#94A3B8]">·</span>
                  <span className="text-xs">{deriveStatus(status).label}</span>
                </>
              )}
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
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 text-sm font-medium rounded-[6px] transition-colors"
            >
              중대사건 위험요인 대조
            </button>
          </div>
        </div>

        {!isRouted && (
          <div className="flex-1 flex items-center justify-center text-[#94A3B8] text-sm">
            AI 분석 목록에서 검토할 회기를 선택해 주세요.
          </div>
        )}

        {isRouted && loading && (
          <div className="flex-1 flex items-center justify-center text-[#94A3B8] text-sm">AI 분석 결과를 불러오는 중...</div>
        )}

        {isRouted && !loading && loadError && (
          <div className="flex-1 flex items-center justify-center text-red-600 text-sm">{loadError}</div>
        )}

        {/* 2-pane body */}
        {isRouted && !loading && !loadError && (
          <div className="flex-1 overflow-hidden grid grid-cols-2 gap-0">
            {/* Left: transcript */}
            <div className="border-r border-[#E2E8F0] flex flex-col overflow-hidden bg-white">
              <div className="px-5 py-3 border-b border-[#F1F5F9] bg-[#F8FAFC] flex items-center justify-between shrink-0">
                <h2 className="font-semibold text-[#172033] text-sm">음성 원문</h2>
                <span className="flex items-center gap-2 text-xs text-[#64748B]">
                  <mark className="bg-[#FEF3C7] rounded px-1 text-[#92400E]">관련 신호</mark>
                  {focusIds.length > 0 && (
                    <button onClick={() => setFocusIds([])} className="px-1 rounded bg-blue-50 text-blue-700 border border-blue-100 hover:bg-blue-100 transition-colors">
                      근거 발화 강조 끄기
                    </button>
                  )}
                </span>
              </div>
              <div className="flex-1 overflow-y-auto">
                {segments.length === 0 && (
                  <div className="flex items-center justify-center h-full text-[#94A3B8] text-sm">아직 전사본이 없습니다</div>
                )}
                {segments.map(seg => {
                  const isRisk = riskIds.has(seg.id);
                  const isFocus = focusIds.includes(seg.id);
                  return (
                    <div
                      key={seg.id}
                      id={`ai-seg-${seg.id}`}
                      className={`flex gap-3 px-5 py-3 border-b border-[#F1F5F9] transition-colors ${isFocus ? "bg-blue-50 ring-1 ring-inset ring-[#2563EB]" : ""}`}
                    >
                      <span className="text-[11px] font-mono text-[#94A3B8] shrink-0 pt-0.5 w-10">{seg.timestamp}</span>
                      <div>
                        <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded mr-2 ${seg.speaker === "COUNSELOR" ? "bg-blue-50 text-blue-700 border border-blue-100" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>{seg.speakerLabel}</span>
                        {isRisk ? (
                          <mark className="bg-[#FEF3C7] text-[#92400E] rounded px-0.5 font-medium text-sm leading-relaxed">{seg.text}</mark>
                        ) : (
                          <span className="text-sm text-[#172033] leading-relaxed">{seg.text}</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="px-5 py-3 border-t border-[#F1F5F9] bg-amber-50 shrink-0">
                <p className="text-xs font-semibold text-amber-800 mb-1.5">추가 확인 필요 발화 ({riskUtterances.length}건) — 상담사 검토 필요</p>
                {riskUtterances.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {riskUtterances.map((item, i) => (
                      <button
                        key={`${item.segmentId}-${i}`}
                        onClick={() => focusSegments([item.segmentId])}
                        title={item.reason || undefined}
                        className="px-2 py-0.5 bg-[#FEF3C7] border border-amber-200 text-[#92400E] rounded text-[11px] font-medium hover:bg-amber-100 transition-colors"
                      >
                        {item.timestamp && <span className="font-mono mr-1">{item.timestamp}</span>}"{item.text}"
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-amber-700">
                    {result ? "AI 분석 참고정보에 표시된 발화가 없습니다." : "AI 분석 결과가 나오면 여기에 표시됩니다."}
                  </p>
                )}
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
                {approved && <span className="text-xs text-green-700 bg-green-50 border border-green-200 px-2.5 py-1 rounded font-medium">상담사 검토 완료</span>}
                {!approved && summary?.is_edited && <span className="text-xs text-[#64748B] bg-[#F1F5F9] border border-[#E2E8F0] px-2.5 py-1 rounded font-medium">상담사 수정됨</span>}
              </div>

              {activeDoc === "report" ? (
                <div className="flex-1 flex flex-col items-center justify-center text-[#94A3B8] space-y-2 p-6 text-center">
                  <p className="text-sm text-[#172033] font-medium">사정기록지 초안은 아직 서버에 없습니다</p>
                  <p className="text-xs">AI 분석은 지금 상담 내용 요약(상담일지)만 만듭니다.</p>
                </div>
              ) : (
                <div className="flex-1 flex flex-col overflow-hidden">{renderDiaryBody()}</div>
              )}

              {activeDoc === "diary" && docReady && summary && (
                <div className="px-5 py-4 border-t border-[#F1F5F9] bg-[#F8FAFC] shrink-0 space-y-3">
                  <div className="space-y-1">
                    <p className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider">변경 이력</p>
                    <div className="flex items-center gap-2 text-xs text-[#64748B]">
                      <span className="font-mono">{toLocalDateTime(summary.created_at)}</span><span>AI 초안 생성</span>
                    </div>
                    {summary.is_edited && (
                      <div className="flex items-center gap-2 text-xs text-[#64748B]">
                        <span className="font-mono">{toLocalDateTime(summary.updated_at)}</span><span>상담사 수정</span>
                      </div>
                    )}
                    {summary.approved_at && (
                      <div className="flex items-center gap-2 text-xs text-[#64748B]">
                        <span className="font-mono">{toLocalDateTime(summary.approved_at)}</span>
                        <span className="text-green-700 font-medium">검토 완료</span>
                      </div>
                    )}
                  </div>
                  {editable ? (
                    <div className="flex items-center gap-2">
                      <p className="flex-1 text-xs text-[#94A3B8]">
                        {pendingUpdate ? "저장하지 않은 수정이 있습니다." : "수정한 내용은 저장하거나 검토 완료할 때 서버에 반영됩니다."}
                      </p>
                      <button
                        onClick={handleSave}
                        disabled={!pendingUpdate || saving || approving}
                        className="px-4 py-2 border border-[#E2E8F0] text-[#64748B] text-sm font-medium rounded-[6px] hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      >
                        {saving ? "저장 중..." : "수정 저장"}
                      </button>
                      <button
                        onClick={() => setShowApprove(true)}
                        disabled={saving || approving}
                        className="px-5 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-blue-700 disabled:opacity-60 transition-colors"
                      >
                        검토 완료
                      </button>
                    </div>
                  ) : (
                    <p className="text-xs text-[#94A3B8]">
                      {approved ? "검토 완료된 요약은 수정할 수 없습니다." : "지금 상태에서는 요약을 수정할 수 없습니다."}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 과거 중대사건 대조는 아직 Backend 에 없다. 가짜 위험요인 목록 대신 안내만 보여 준다. */}
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
            <div className="p-6">
              <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] p-4 space-y-1">
                <p className="text-sm font-semibold text-[#172033]">아직 서버에 없는 기능입니다</p>
                <p className="text-xs text-[#64748B]">
                  과거 중대사건 자료와 대조하는 기능은 준비 중입니다. 지금은 왼쪽 원문의 추가 확인 필요 발화와
                  상담일지의 AI 분석 참고정보만 확인할 수 있습니다.
                </p>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-[#F1F5F9] flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 border border-[#E2E8F0] text-[#64748B] text-sm rounded-[6px] hover:bg-[#F8FAFC] transition-colors">닫기</button>
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        open={showApprove}
        title="검토 완료"
        message={
          pendingUpdate
            ? "저장하지 않은 수정을 저장한 뒤 검토를 완료합니다. 검토를 완료하면 요약이 승인되어 더 이상 수정할 수 없습니다."
            : "검토를 완료하시겠습니까? 검토를 완료하면 요약이 승인되어 더 이상 수정할 수 없습니다."
        }
        confirmLabel={approving ? "처리 중..." : "검토 완료"}
        onConfirm={handleApprove}
        onCancel={() => { if (!approving) setShowApprove(false); }}
      />
    </div>
  );
}
