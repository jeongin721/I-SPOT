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
  formatConfidencePercent,
  isLowConfidence,
  toUiCase,
  toUiSession,
  toUiTranscriptSegments,
  type UiTranscriptSegment,
} from "../api/adapters";

// 발화 목록은 Backend(GET /sessions/{id}/transcript)에서 온다. 발화별 "확정" 표시는 화면에서만
// 관리하는 검수 체크이고(Backend 에는 발화 단위 확정이 없다), 수정은 저장할 때마다 PATCH 로 바로
// 반영되며 "STT 검수 완료" 가 POST .../transcript/confirm 이다.
// 원문 변환 대기 · 실패 회기는 전사본 대신 "원문 변환 (다시) 요청"(POST .../transcript)을 보여 준다.

interface Segment extends UiTranscriptSegment {
  confirmed: boolean;
  editing: boolean;
  draft: string;
}

/**
 * 원문 변환(POST .../transcript)을 이 화면에서 요청할 수 있는 상태. Backend 도 이 두 상태에서
 * STT_PROCESSING 으로 넘어가는 것을 허용한다(state_machine, STT_FAILED 는 재시도).
 * 음성 업로드 대기(CREATED)는 올린 음성이 없어 요청할 수 없으니 업로드 창으로 안내만 한다.
 */
const STT_REQUESTABLE: SessionStatus[] = ["AUDIO_UPLOADED", "STT_FAILED"];

/**
 * 원문을 고칠 수 있는 상태. Backend 도 이 두 상태에서만 PATCH 를 받는다
 * (transcript_service._EDITABLE_STATUSES). 그 밖에서는 읽기 전용으로 보여 준다.
 */
const EDITABLE: SessionStatus[] = ["STT_REVIEW_REQUIRED", "STT_CONFIRMED"];

/** 읽기 전용일 때 띠에 보여 줄 이유. */
function readOnlyReason(status: SessionStatus): string {
  if (status === "APPROVED") return "승인된 전사본은 수정할 수 없습니다.";
  // 검수 중에 원문 변환을 다시 돌린 경우다(Backend 는 STT_REVIEW_REQUIRED 에서도 받는다). 보이는 것은 이전 전사본이다.
  if (status === "STT_PROCESSING") return "원문 변환 중에는 원문을 수정할 수 없습니다(이전 전사본).";
  if (status === "STT_FAILED") return "원문 변환이 실패해 이전 전사본을 보여 줍니다.";

  return "AI 분석 단계에서는 원문을 수정할 수 없습니다.";
}

/** STT 가 끝나기를 기다릴 때 다시 확인하는 간격과 횟수(약 2분). */
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_TRIES = 60;

/**
 * 검수가 필요한 발화. 저신뢰(값이 있고 0.7 미만, api/confidence.ts)이거나 화자 확인이 필요한 발화
 * (child_handoff 의 review_needed 또는 화자 UNKNOWN, adapters.ts 의 reviewReason)다.
 * 신뢰도 값 없음(0.0, ElevenLabs 등)은 그것만으로는 검수 필요로 세지 않는다. 검수가 필요 없다는 뜻은
 * 아니므로 따로 알린다. 모든 발화에 값이 없으면 안내 칩으로, 일부만 없으면 개수 괄호의 "신뢰도 값 없음 n개"
 * 로, "검수 필요만 보기" 에서 값 없는 발화가 빠지면 목록 위 안내(목록이 비면 빈 목록 문구)로 알린다.
 */
function needsReview(seg: UiTranscriptSegment): boolean {
  return seg.lowConfidence || seg.reviewReason !== null;
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

/** 신뢰도 값이 없을 때(STT 공급자가 주지 않음) 막대 · 퍼센트 대신 보여 줄 안내. */
const NO_CONFIDENCE_TITLE = "신뢰도 값 없음 · STT 공급자가 신뢰도를 제공하지 않았습니다";

/** 저신뢰 · 화자 확인 필요 개수를 나란히 보여 줄 때, 두 사유가 모두 해당하는 발화를 어떻게 셌는지 알린다. */
const OVERLAP_TITLE = "저신뢰이면서 화자 확인도 필요한 구간은 두 개수에 모두 셉니다";

/** 개수 괄호의 "신뢰도 값 없음 n개" 가 검수 필요 구간 수에 들어가지 않는다는 것을 알린다. */
const NO_CONF_COUNT_TITLE = "신뢰도 값이 없는 발화는 저신뢰 여부를 알 수 없어 검수 필요 구간 수에 들어가지 않습니다(추가 확인 필요)";

function ConfidenceBar({ value }: { value: number | null }) {
  // 퍼센트 문구는 공용 규칙(api/confidence.ts)으로 만든다. 저신뢰는 내림이라 기준(70%) 미만으로만 보인다.
  const label = value === null ? null : formatConfidencePercent(value);
  if (value === null || label === null) {
    return (
      <span className="text-[11px] font-mono font-semibold text-[#94A3B8]" title={NO_CONFIDENCE_TITLE}>
        <span aria-hidden="true">—</span>
        <span className="sr-only">{NO_CONFIDENCE_TITLE}</span>
      </span>
    );
  }

  const low = isLowConfidence(value);
  const color = !low ? "bg-green-400" : value >= 0.55 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="w-16 h-1.5 bg-[#F1F5F9] rounded overflow-hidden shrink-0">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(value, 1) * 100}%` }} />
      </div>
      <span className={`text-[11px] font-mono font-semibold shrink-0 ${low ? "text-amber-600" : "text-[#94A3B8]"}`}>
        {label}
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
  const [filterReview, setFilterReview] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [requesting, setRequesting] = useState(false);
  /** 원문 변환 요청이 거절된 이유. 버튼 아래에 보여 준다. */
  const [requestError, setRequestError] = useState<string | null>(null);

  function applyEnvelope(envelope: TranscriptEnvelope) {
    setStatus(envelope.session_status);
    setSttError(envelope.error);
    // 요청할 수 없는 상태(처리 중 등)로 바뀌면 지난 거절 문구는 지금 상태와 맞지 않는다.
    // 남겨 두면 재확인 끝에 다시 실패했을 때 새 실패 사유 아래에 옛 문구가 되살아난다.
    if (!STT_REQUESTABLE.includes(envelope.session_status)) setRequestError(null);
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
    setRequestError(null);

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
    filterReview ? segments.filter(needsReview) : segments,
    [segments, filterReview]
  );

  const confirmedCount     = segments.filter(s => s.confirmed).length;
  const reviewCount        = segments.filter(needsReview).length;
  // 저신뢰 개수는 수정 · 확정 여부와 관계없이 센다(Backend Mock AI 경고 "저신뢰 구간 N건" 과 같은 규칙).
  const lowConfCount       = segments.filter(s => s.lowConfidence).length;
  const speakerReviewCount = segments.filter(s => s.reviewReason !== null).length;
  // 저신뢰이면서 화자 확인도 필요한 발화. 위 두 개수에 모두 들어가므로 겹친 수를 따로 보여 준다.
  const overlapCount       = segments.filter(s => s.lowConfidence && s.reviewReason !== null).length;
  const pendingReviewCount = segments.filter(s => needsReview(s) && !s.confirmed).length;
  const allDone            = segments.length > 0 && segments.every(s => s.confirmed);
  const hasTranscript      = segments.length > 0;
  // 신뢰도 값이 없는 발화. 저신뢰 여부를 알 수 없어서 "검수 필요" 로 걸리지 않는다(검수가 필요 없다는 뜻이 아니다).
  const noConfCount        = segments.filter(s => s.confidence === null).length;
  // 모든 발화에 신뢰도 값이 없다(ElevenLabs 등). 저신뢰 구간을 표시할 수 없으니 발화를 직접 확인하도록 안내한다.
  const noConfidence       = hasTranscript && noConfCount === segments.length;
  // 일부 발화에만 신뢰도 값이 없다. 개수 괄호에 값 없는 발화 수를 덧붙인다.
  const partialNoConf      = noConfCount > 0 && noConfCount < segments.length;
  // 신뢰도 값이 없고 화자 확인도 필요 없어 "검수 필요만 보기" 에서 빠지는 발화.
  const hiddenNoConfCount  = segments.filter(s => s.confidence === null && !needsReview(s)).length;
  // "검수 필요만 보기" 에서 신뢰도 값 없는 발화가 빠졌다는 안내. 목록 위(목록이 비면 빈 목록 문구)에 보여 준다.
  const noConfFilterNote   = noConfidence
    ? "신뢰도 값이 없어 저신뢰 구간은 표시되지 않습니다(추가 확인 필요)"
    : `신뢰도 값이 없는 발화 ${hiddenNoConfCount}개는 이 목록에 나오지 않습니다(추가 확인 필요)`;
  const editable           = status !== null && EDITABLE.includes(status);
  const sttRequestable     = status !== null && STT_REQUESTABLE.includes(status);
  // 재확인을 다 쓰고도 처리 중이다. 새로고침 없이는 바뀌지 않으니 "다시 확인" 을 보여 준다(AIReviewView 와 같다).
  const sttGaveUp          = status === "STT_PROCESSING" && pollTries >= POLL_MAX_TRIES;

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
      if (caseId) navigate(`/cases/${caseId}/analyses/${sessionId}`);
    } catch (caught) {
      setShowConfirm(false);
      showToast(describeApiError(caught, "검수 확정에 실패했습니다.", "권한이 없거나 없는 회기입니다."), "error");
    } finally {
      setConfirming(false);
    }
  }

  /**
   * 원문 변환 요청(POST .../transcript). 202 로 돌아오고, 결과는 위의 재확인이 받아 온다.
   * 다시 실패하면 재확인이 STT_FAILED 를 받아 버튼이 다시 보인다.
   * Backend 는 검수 중(STT_REVIEW_REQUIRED)에도 다시 변환을 받는다. 화면을 연 뒤 다른 탭 · 다른 사람이 먼저
   * 변환 · 수정을 했으면 그 위에 새 STT 버전이 생겨 고친 문구가 최신본에서 빠지므로, 보내기 직전에 서버 상태를
   * 다시 받아 이 화면이 보던 상태(요청 가능 · 전사본 없음)일 때만 보낸다. 그 사이에 끼는 짧은 경쟁까지 막으려면
   * Backend 에 기대 상태 조건이 있어야 한다.
   */
  async function handleRequestStt() {
    if (!sessionId || requesting) return;

    setRequesting(true);
    setRequestError(null);
    try {
      const latest = await transcriptApi.get(sessionId);
      if (!STT_REQUESTABLE.includes(latest.session_status) || latest.transcript) {
        applyEnvelope(latest);
        setPollTries(0);
        showToast("회기 상태가 바뀌어 원문 변환을 요청하지 않았습니다. 바뀐 상태를 확인해 주세요.", "info");
        return;
      }

      const response = await transcriptApi.run(sessionId);
      setStatus(response.session_status);
      setSttError(null);
      setPollTries(0);
      showToast("원문 변환을 요청했습니다.", "success");
    } catch (caught) {
      setRequestError(describeApiError(caught, "원문 변환 요청에 실패했습니다.", "권한이 없거나 없는 회기입니다."));
      // 다른 사람이 먼저 요청했을 수 있으니 서버 상태로 다시 맞춘다(처리 중이면 재확인이 이어서 돈다).
      transcriptApi
        .get(sessionId)
        .then((envelope) => {
          applyEnvelope(envelope);
          setPollTries(0);
        })
        .catch(() => {
          // 다시 맞추지 못해도 화면은 그대로 둔다. 새로고침하면 된다.
        });
    } finally {
      setRequesting(false);
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
              검수 필요 구간을 확인하고 수정·확정하세요
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
            <span className="text-[#64748B] text-xs">검수 필요 구간</span>
            <span className={`font-semibold ${reviewCount > 0 ? "text-amber-600" : "text-[#172033]"}`}>{reviewCount}개</span>
            {/* 신뢰도 값 없는 발화가 있으면 검수 필요 구간이 0개여도 괄호를 보여 준다(0개가 "검수할 것 없음" 으로 읽히지 않게). */}
            {(reviewCount > 0 || noConfCount > 0) && (
              <span className="text-[11px] text-[#94A3B8]" title={overlapCount > 0 ? OVERLAP_TITLE : undefined}>
                (저신뢰 {noConfidence ? "—" : `${lowConfCount}개`} · 화자 확인 필요 {speakerReviewCount}개
                {overlapCount > 0 && ` · 두 사유 겹침 ${overlapCount}개`}
                {partialNoConf && <span title={NO_CONF_COUNT_TITLE}>{` · 신뢰도 값 없음 ${noConfCount}개`}</span>})
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
            <span className="text-[#64748B] text-xs">확정 완료</span>
            <span className="font-semibold text-green-700">{confirmedCount}/{segments.length}</span>
          </div>
          {editable && pendingReviewCount > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 border border-amber-200 rounded text-xs font-medium text-amber-700">
              검수 필요 {pendingReviewCount}개 미검수
            </div>
          )}
          {noConfidence && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded text-xs font-medium text-[#64748B]" title={NO_CONFIDENCE_TITLE}>
              STT 신뢰도 값 없음(공급자 미제공)
              {/* 신뢰도 정보가 없으니 인식 오류는 어느 발화에나 있을 수 있다. 화자 확인 필요 구간이 있어도 그것만 보면
                  된다고 읽히지 않게, 나머지 발화도 직접 확인하도록 안내한다. */}
              {editable && (speakerReviewCount > 0 && speakerReviewCount < segments.length
                ? ` · 화자 확인 필요 ${speakerReviewCount}개와 함께 나머지 발화도 직접 확인해 주세요`
                : " · 저신뢰 구간을 표시할 수 없으니 발화를 직접 확인해 주세요")}
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
              <input type="checkbox" checked={filterReview} onChange={e => setFilterReview(e.target.checked)} className="accent-amber-500" />
              검수 필요만 보기
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
                  {/* 음성 업로드는 이 화면에 없다. 업로드 창이 있는 메뉴를 알려 준다. */}
                  {status === "CREATED" && " · 상담 자료 검수 → 상담 자료 업로드에서 음성을 올려 주세요"}
                  {status === "AUDIO_UPLOADED" && " · 원문 변환을 요청하면 여기에 발화가 나타납니다"}
                  {status === "STT_PROCESSING" && (sttGaveUp
                    ? " · 오래 걸리고 있습니다. 잠시 뒤 다시 확인해 주세요."
                    : " · 끝나면 여기에 발화가 나타납니다")}
                </p>
              )}
              {sttGaveUp && (
                <button
                  onClick={() => setPollTries(0)}
                  className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
                >
                  다시 확인
                </button>
              )}
              {sttError && <p className="text-xs text-red-600">{sttError.message}</p>}
              {sttRequestable && (
                <>
                  <button
                    onClick={handleRequestStt}
                    disabled={requesting}
                    className="px-4 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-[6px] hover:bg-blue-700 disabled:opacity-60 transition-colors"
                  >
                    {requesting ? "요청 중..." : status === "STT_FAILED" ? "원문 변환 다시 요청" : "원문 변환 요청"}
                  </button>
                  {/* 요청이 거절돼 상태가 바뀌었으면(다른 사람이 먼저 요청 등) 위 현재 상태가 이유를 보여 준다.
                      요청할 수 없는 상태로 바뀌면 applyEnvelope 가 이 문구를 지운다. */}
                  {requestError && <p className="text-xs text-red-600">{requestError}</p>}
                </>
              )}
            </div>
          )}

          {/* 신뢰도 값이 없는 발화가 있으면 저신뢰 여부를 알 수 없으므로 "검수가 필요 없다" 고 단정하지 않는다. */}
          {!loading && !loadError && hasTranscript && displayed.length === 0 && noConfCount > 0 && (
            <div className="flex flex-col items-center justify-center h-full text-[#94A3B8] space-y-3 px-6 text-center">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              <p className="text-sm">표시된 검수 필요 구간이 없습니다</p>
              <p className="text-xs">{noConfFilterNote}</p>
              <button
                onClick={() => setFilterReview(false)}
                className="px-3 py-1.5 border border-[#E2E8F0] text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
              >
                전체 발화 보기
              </button>
            </div>
          )}

          {!loading && !loadError && hasTranscript && displayed.length === 0 && noConfCount === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-[#94A3B8] space-y-3">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><polyline points="20 6 9 17 4 12"/></svg>
              <p className="text-sm">검수가 필요한 구간이 없습니다</p>
            </div>
          )}

          {/* 목록에 행이 남아 있어도 신뢰도 값 없는 발화가 빠졌으면 알린다(목록이 비면 위의 빈 목록 문구가 같은 안내를 한다). */}
          {!loading && !loadError && filterReview && displayed.length > 0 && hiddenNoConfCount > 0 && (
            <div className="px-6 py-2.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between gap-3 flex-wrap">
              <p className="text-xs text-[#64748B]">{noConfFilterNote}</p>
              <button
                onClick={() => setFilterReview(false)}
                className="px-3 py-1.5 border border-[#E2E8F0] bg-white text-[#64748B] text-xs font-medium rounded-[6px] hover:bg-[#F8FAFC] transition-colors shrink-0"
              >
                전체 발화 보기
              </button>
            </div>
          )}

          {displayed.map(seg => {
            const flagged = needsReview(seg);
            const isSaving = savingId === seg.id;
            return (
              <div
                key={seg.id}
                className={`px-6 py-3.5 border-b border-[#F1F5F9] transition-colors ${
                  seg.confirmed ? "bg-[#F0FDF4]/40" : flagged ? "bg-[#FFFBEB]" : "bg-white hover:bg-[#F8FAFC]"
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className="flex flex-col items-start gap-1.5 shrink-0 w-24 pt-0.5">
                    <span className="text-[11px] font-mono text-[#94A3B8]">{seg.timestamp}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold ${seg.speaker === "COUNSELOR" ? "bg-blue-50 text-blue-700 border border-blue-100" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>
                      {seg.speakerLabel}
                    </span>
                    <ConfidenceBar value={seg.confidence} />
                    {/* 두 사유가 겹치면 배지를 둘 다 보여 준다(화자 확인 필요만 보이면 저신뢰라는 사실이 빠진다). */}
                    {!seg.confirmed && seg.reviewReason !== null && (
                      <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">{seg.reviewReason}</span>
                    )}
                    {!seg.confirmed && seg.lowConfidence && (
                      <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">저신뢰</span>
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
                      <p className={`text-sm leading-relaxed ${flagged && !seg.confirmed ? "text-amber-900" : seg.confirmed ? "text-[#64748B]" : "text-[#172033]"}`}>
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
        message="STT 검수를 완료하시겠습니까? 완료 후 AI 분석 화면으로 이동합니다."
        confirmLabel={confirming ? "처리 중..." : "완료"}
        onConfirm={handleConfirmComplete}
        onCancel={() => { if (!confirming) setShowConfirm(false); }}
      />
    </div>
  );
}
