import { useState, useMemo, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import CaseSelectorPanel from "../components/CaseSelectorPanel";
import Breadcrumb from "../components/ui/Breadcrumb";
import ConfirmModal from "../components/ui/ConfirmModal";
import { useToast } from "../components/ui/Toast";
import { cases as casesApi, sessions as sessionsApi, transcript as transcriptApi } from "../api/endpoints";
import type { SessionErrorInfo, SessionStatus, Transcript, TranscriptEnvelope } from "../api/types";
import type { CaseRecord } from "../data/cases";
import type { Session as UiSession } from "../data/mockData";
import {
  describeApiError,
  deriveStatus,
  toUiCase,
  toUiSession,
  toUiTranscriptSegments,
  type UiTranscriptSegment,
} from "../api/adapters";

// 발화 목록은 Backend(GET /sessions/{id}/transcript)에서 온다. 발화별 "확정" 표시는 화면에서만
// 관리하는 검수 체크이고(Backend 에는 발화 단위 확정이 없다), 수정은 저장할 때마다 PATCH 로 바로
// 반영되며 "STT 검수 완료" 가 POST .../transcript/confirm 이다.

interface Segment extends UiTranscriptSegment {
  confirmed: boolean;
  editing: boolean;
  draft: string;
}

// 저신뢰 기준. ElevenLabs 결과는 confidence 0.0 = 값 없음이라 기준 재검토 필요.
const LOW_CONF = 0.75;

/** 아직 전사본이 만들어지기 전 상태. 이때는 발화 목록 대신 안내를 보여 준다. */
const BEFORE_STT: SessionStatus[] = ["CREATED", "AUDIO_UPLOADED", "STT_PROCESSING"];

/**
 * 원문을 고칠 수 있는 상태. Backend 도 이 두 상태에서만 PATCH 를 받는다
 * (transcript_service._EDITABLE_STATUSES). 그 밖에서는 읽기 전용으로 보여 준다.
 */
const EDITABLE: SessionStatus[] = ["STT_REVIEW_REQUIRED", "STT_CONFIRMED"];

/** 읽기 전용일 때 띠에 보여 줄 이유. */
function readOnlyReason(status: SessionStatus): string {
  if (status === "APPROVED") return "승인된 전사본은 수정할 수 없습니다.";

  return "AI 분석 단계에서는 원문을 수정할 수 없습니다.";
}

/** STT 가 끝나기를 기다릴 때 다시 확인하는 간격과 횟수(약 2분). */
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_TRIES = 60;

/** 저신뢰이거나 child_handoff 가 사람 확인이 필요하다고 표시한 발화. */
function needsReview(seg: UiTranscriptSegment): boolean {
  return seg.confidence < LOW_CONF || seg.reviewReason !== null;
}

function toSegments(source: Transcript, confirmedIds: Set<string> = new Set()): Segment[] {
  return toUiTranscriptSegments(source).map(s => ({
    ...s,
    // 상담사가 이미 고친 발화는 확인한 것으로 본다.
    confirmed: s.edited || confirmedIds.has(s.id),
    editing: false,
    draft: "",
  }));
}

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

  // 주소의 caseId · sessionId 는 Backend UUID 다. 주소 없이 열리면(현재 경로 설정에는 없다) 왼쪽 선택 패널만 보인다.
  const [selectedId, setSelectedId] = useState(caseId ?? "");
  const [caseInfo, setCaseInfo] = useState<CaseRecord | null>(null);
  const [sessionInfo, setSessionInfo] = useState<UiSession | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [sttError, setSttError] = useState<SessionErrorInfo | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [filterLow, setFilterLow] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  function applyEnvelope(envelope: TranscriptEnvelope) {
    setStatus(envelope.session_status);
    setSttError(envelope.error);
    if (envelope.transcript) {
      setVersion(envelope.transcript.version);
      setIsConfirmed(envelope.transcript.is_confirmed);
      setSegments(toSegments(envelope.transcript));
    } else {
      setVersion(null);
      setIsConfirmed(false);
      setSegments([]);
    }
  }

  useEffect(() => {
    if (!caseId || !sessionId) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setLoadError(null);

    Promise.all([casesApi.get(caseId), sessionsApi.get(sessionId), transcriptApi.get(sessionId)])
      .then(([c, s, envelope]) => {
        if (cancelled) return;
        setCaseInfo(toUiCase(c, { sessionCount: c.session_count }));
        setSessionInfo(toUiSession(s, c.case_number));
        applyEnvelope(envelope);
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "전사본을 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId, sessionId]);

  // STT 가 아직 도는 중이면 끝날 때까지 전사본을 다시 확인한다.
  // 실제 공급자(ElevenLabs)는 업로드 창의 대기 시간보다 오래 걸릴 수 있다.
  const [pollTries, setPollTries] = useState(0);

  useEffect(() => {
    if (status !== "STT_PROCESSING" || !sessionId || pollTries >= POLL_MAX_TRIES) return;

    const timer = window.setTimeout(() => {
      transcriptApi
        .get(sessionId)
        .then(applyEnvelope)
        .catch(() => {
          // 한 번 실패해도 다음 확인에서 다시 시도한다.
        })
        .finally(() => setPollTries(n => n + 1));
    }, POLL_INTERVAL_MS);

    return () => window.clearTimeout(timer);
  }, [status, sessionId, pollTries]);

  const displayed = useMemo(() =>
    filterLow ? segments.filter(needsReview) : segments,
    [segments, filterLow]
  );

  const confirmedCount  = segments.filter(s => s.confirmed).length;
  const lowConfCount    = segments.filter(needsReview).length;
  const pendingLowCount = segments.filter(s => needsReview(s) && !s.confirmed).length;
  const allDone         = segments.length > 0 && segments.every(s => s.confirmed);
  const hasTranscript   = segments.length > 0;
  const beforeStt       = status !== null && BEFORE_STT.includes(status);
  const editable        = status !== null && EDITABLE.includes(status);

  function startEdit(id: string) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, editing: true, draft: s.text } : s));
  }

  /** 고친 문장을 Backend 에 저장한다. 새 version 이 만들어지므로 목록 전체를 응답으로 다시 채운다. */
  async function saveDraft(id: string) {
    const target = segments.find(s => s.id === id);
    if (!target || !sessionId || savingId) return;

    const text = target.draft.trim();
    if (!text) {
      showToast("빈 문장으로는 저장할 수 없습니다.", "error");
      return;
    }

    // 바뀐 게 없으면 서버에 보내지 않고 확정 표시만 한다.
    if (text === target.text) {
      setSegments(prev => prev.map(s => s.id === id ? { ...s, editing: false, draft: "", confirmed: true } : s));
      return;
    }

    setSavingId(id);
    try {
      const updated = await transcriptApi.update(sessionId, { segments: [{ segment_id: id, text }] });
      const confirmedIds = new Set(segments.filter(s => s.confirmed).map(s => s.id));
      confirmedIds.add(id);
      setSegments(toSegments(updated, confirmedIds));
      setVersion(updated.version);
      setIsConfirmed(updated.is_confirmed);
      // 확정된 전사본을 고치면 Backend 가 다시 검수 필요 상태로 되돌린다.
      if (!updated.is_confirmed) setStatus("STT_REVIEW_REQUIRED");
      showToast("발화를 수정했습니다.", "success");
    } catch (caught) {
      showToast(describeApiError(caught, "발화 수정에 실패했습니다.", "권한이 없거나 없는 회기입니다."), "error");
    } finally {
      setSavingId(null);
    }
  }
  function cancelEdit(id: string) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, editing: false, draft: "" } : s));
  }
  function confirm(id: string) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, confirmed: true } : s));
  }
  function unconfirm(id: string) {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, confirmed: false } : s));
  }
  function confirmAll() {
    setSegments(prev => prev.map(s => ({ ...s, confirmed: true })));
  }

  function handleComplete() {
    setShowConfirm(true);
  }

  /** 검수 확정(POST .../transcript/confirm). 이 다음에야 AI 분석을 요청할 수 있다. */
  async function handleConfirmComplete() {
    if (!sessionId || confirming) return;

    setConfirming(true);
    try {
      const confirmed = await transcriptApi.confirm(sessionId);
      setIsConfirmed(confirmed.is_confirmed);
      setStatus("STT_CONFIRMED");
      setShowConfirm(false);
      showToast("STT 검수가 완료되었습니다.", "success");
      if (caseId) navigate(`/case-management`);
    } catch (caught) {
      setShowConfirm(false);
      showToast(describeApiError(caught, "검수 확정에 실패했습니다.", "권한이 없거나 없는 회기입니다."), "error");
    } finally {
      setConfirming(false);
    }
  }

  const isRouted = !!caseId;
  const childName = caseInfo?.childName ?? "—";
  const caseNumber = caseInfo?.id ?? "—";

  return (
    <div className="flex h-full overflow-hidden">
      {!isRouted && (
        <CaseSelectorPanel selectedId={selectedId} onSelect={id => setSelectedId(id)} />
      )}

      <div className="flex-1 flex flex-col overflow-hidden bg-[#F6F8FB]">
        {/* Breadcrumb header */}
        {isRouted && (
          <div className="px-6 pt-4 pb-2 shrink-0">
            <Breadcrumb items={[
              { label: "STT 검수", to: "/stt-cases" },
              { label: childName, to: `/cases/${caseId}/sessions` },
              { label: sessionInfo ? `${sessionInfo.date} 상담` : "STT 검수" },
              { label: "STT 검수" },
            ]} />
          </div>
        )}

        {/* Header */}
        <div className="px-6 py-4 border-b border-[#E2E8F0] bg-white shrink-0 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#172033]">STT 검수</h1>
            <p className="text-[#64748B] text-sm mt-0.5">
              <span className="font-semibold text-[#172033]">{childName}</span>
              <span className="mx-1.5 text-[#94A3B8]">·</span>
              <span className="font-mono text-xs">{caseNumber}</span>
              {sessionInfo && (
                <>
                  <span className="mx-1.5 text-[#94A3B8]">·</span>
                  <span className="text-xs">{sessionInfo.sessionNumber}회차</span>
                </>
              )}
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
            {editable && allDone && !isConfirmed && (
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
          {editable && pendingLowCount > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 border border-amber-200 rounded text-xs font-medium text-amber-700">
              저신뢰 {pendingLowCount}개 미검수
            </div>
          )}
          {editable && isConfirmed && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-green-50 border border-green-200 rounded text-xs font-medium text-green-700">
              확정된 전사본{version !== null ? ` (v${version})` : ""} · 수정하면 다시 검수 필요 상태가 됩니다
            </div>
          )}
          {!editable && hasTranscript && status && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded text-xs font-medium text-[#64748B]">
              읽기 전용{version !== null ? ` (v${version})` : ""} · {readOnlyReason(status)}
            </div>
          )}
          <div className="ml-auto flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-[#64748B] cursor-pointer select-none">
              <input type="checkbox" checked={filterLow} onChange={e => setFilterLow(e.target.checked)} className="accent-amber-500" />
              저신뢰만 보기
            </label>
            {editable && (
              <button onClick={confirmAll} disabled={allDone || !hasTranscript}
                className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                전체 확정
              </button>
            )}
          </div>
        </div>

        {/* Segment list */}
        <div className="flex-1 overflow-y-auto bg-white">
          {loading && (
            <div className="flex items-center justify-center h-full text-[#94A3B8] text-sm">전사본을 불러오는 중...</div>
          )}

          {!loading && loadError && (
            <div className="flex items-center justify-center h-full text-red-600 text-sm">{loadError}</div>
          )}

          {!loading && !loadError && !hasTranscript && (
            <div className="flex flex-col items-center justify-center h-full text-[#94A3B8] space-y-3">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>
              <p className="text-sm">{status === "STT_FAILED" ? "STT 처리에 실패했습니다" : "아직 전사본이 없습니다"}</p>
              {status && (
                <p className="text-xs">
                  현재 상태: {deriveStatus(status).label}
                  {beforeStt && status !== "STT_PROCESSING" && " · 음성을 올리고 STT 를 실행하면 여기에 발화가 나타납니다"}
                </p>
              )}
              {sttError && <p className="text-xs text-red-600">{sttError.message}</p>}
            </div>
          )}

          {!loading && !loadError && hasTranscript && displayed.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-[#94A3B8] space-y-3">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><polyline points="20 6 9 17 4 12"/></svg>
              <p className="text-sm">모든 저신뢰 구간이 검수되었습니다</p>
            </div>
          )}

          {displayed.map(seg => {
            const isLow = needsReview(seg);
            const isSaving = savingId === seg.id;
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
                    <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold ${seg.speaker === "COUNSELOR" ? "bg-blue-50 text-blue-700 border border-blue-100" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>
                      {seg.speakerLabel}
                    </span>
                    <ConfidenceBar value={seg.confidence} />
                    {isLow && !seg.confirmed && (
                      <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">{seg.reviewReason ?? "검수 필요"}</span>
                    )}
                    {seg.edited && (
                      <span className="text-[10px] font-medium text-[#64748B] bg-[#F1F5F9] border border-[#E2E8F0] px-1.5 py-0.5 rounded">수정됨</span>
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
                          disabled={isSaving}
                          className="w-full px-3 py-2 rounded-[6px] border border-[#2563EB] text-sm text-[#172033] resize-none focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                        />
                        <div className="flex items-center gap-2">
                          <button onClick={() => saveDraft(seg.id)} disabled={isSaving} className="px-3 py-1.5 bg-[#2563EB] text-white text-xs font-semibold rounded-[6px] hover:bg-blue-700 disabled:opacity-60 transition-colors">
                            {isSaving ? "저장 중..." : "저장 및 확정"}
                          </button>
                          <button onClick={() => cancelEdit(seg.id)} disabled={isSaving} className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors">
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

                  {editable && !seg.editing && (
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
        {editable && allDone && !isConfirmed && (
          <div className="px-6 py-4 border-t border-[#E2E8F0] bg-white shrink-0 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-green-700">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span className="font-medium">모든 구간 검수 완료</span>
              <span className="text-[#94A3B8] text-xs">· {segments.length}개 확정</span>
            </div>
            <div className="flex gap-2">
              {/* 수정한 문장은 "저장 및 확정" 때마다 이미 서버에 반영돼 있어 따로 저장할 것이 없다. */}
              <button
                onClick={() => showToast("수정한 발화는 저장할 때마다 바로 반영되어 있습니다.", "info")}
                className="px-4 py-2 border border-[#E2E8F0] text-[#64748B] text-sm font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
              >
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
        message="STT 검수를 완료하시겠습니까? 완료 후 사례 관리 화면으로 이동합니다."
        confirmLabel={confirming ? "처리 중..." : "완료"}
        onConfirm={handleConfirmComplete}
        onCancel={() => { if (!confirming) setShowConfirm(false); }}
      />
    </div>
  );
}
