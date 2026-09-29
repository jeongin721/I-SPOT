import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router";
import { useToast } from "../components/ui/Toast";
import ConfirmModal from "../components/ui/ConfirmModal";
import {
  cases as casesApi,
  documents as documentsApi,
  sessions as sessionsApi,
  summary as summaryApi,
  transcript as transcriptApi,
} from "../api/endpoints";
import { DOC_TYPE_CONSULTATION_RECORD, type Document as ApiDocument, type ReviewStatus } from "../api/types";
import type { CaseRecord } from "../data/cases";
import type { Session as UiSession } from "../data/mockData";
import { describeApiError, toUiCase, toUiSession } from "../api/adapters";
import {
  DOCUMENT_CONTENT_MAX,
  buildConsultationDraft,
  defaultRecordTitle,
  pickConsultationRecord,
  toLocalDateTime,
  toUiDocumentEvidence,
  type UiDocumentEvidence,
} from "../api/documentAdapters";

// 상담일지는 Backend 문서 API(/sessions/{id}/documents)에 저장한다. 주소의 caseId · sessionId 는 Backend UUID 다.
// 이 회기에 상담일지가 있으면 그 본문을 불러오고, 없으면 요약(GET /sessions/{id}/summary)으로 초안을 채운다.
// "임시저장" 은 처음이면 생성(DRAFT), 그 뒤로는 수정이고, "상담일지 저장" 은 저장 뒤 승인까지 한다(승인 뒤 수정 불가).
// 작성 근거는 요약 항목의 근거 발화(summary_evidence)를 전사본에서 찾아 보여 준다.
// 근거별 "상담사 확인 상태" 는 화면에서만 쓰는 검수 체크다(Backend 에 저장하지 않는다).

interface EvidenceItem extends UiDocumentEvidence {
  status: "확인필요" | "확인완료" | "보류" | null;
}

/** 초안이 어디서 왔는지. 본문 위 안내 띠 문구를 고르는 데 쓴다. */
type DraftOrigin = "document" | ReviewStatus | "none";

export default function DocumentWritePage() {
  const { caseId, sessionId } = useParams<{ caseId: string; sessionId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [caseObj, setCaseObj] = useState<CaseRecord | null>(null);
  const [sessionInfo, setSessionInfo] = useState<UiSession | null>(null);
  const [record, setRecord] = useState<ApiDocument | null>(null);
  const [draftOrigin, setDraftOrigin] = useState<DraftOrigin>("none");
  const [hasSummary, setHasSummary] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState<"draft" | "final" | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const [docText, setDocText] = useState("");
  const [evidences, setEvidences] = useState<EvidenceItem[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId || !sessionId) {
      setLoading(false);
      setLoadError("사례 또는 회기 정보가 없습니다.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setLoadError(null);

    Promise.all([
      casesApi.get(caseId),
      sessionsApi.get(sessionId),
      documentsApi.list(sessionId),
      summaryApi.get(sessionId),
    ])
      .then(async ([c, s, docs, summaryEnvelope]) => {
        // 근거 발화가 있을 때만 전사본에서 원문을 찾는다.
        const transcriptEnvelope = summaryEnvelope.summary_evidence.length > 0
          ? await transcriptApi.get(sessionId)
          : null;

        return { c, s, docs, summaryEnvelope, transcriptEnvelope };
      })
      .then(({ c, s, docs, summaryEnvelope, transcriptEnvelope }) => {
        if (cancelled) return;

        if (s.case_id !== c.id) {
          setLoadError("이 사례의 회기가 아닙니다.");
          return;
        }

        const existing = pickConsultationRecord(docs);
        const summary = summaryEnvelope.summary;
        const items = toUiDocumentEvidence(summaryEnvelope.summary_evidence, transcriptEnvelope?.transcript ?? null)
          .map((e): EvidenceItem => ({ ...e, status: null }));

        setCaseObj(toUiCase(c, { sessionCount: c.session_count }));
        setSessionInfo(toUiSession(s, c.case_number));
        setRecord(existing);
        setDocText(existing ? existing.content : buildConsultationDraft(summary, s));
        setDraftOrigin(existing ? "document" : summary ? summary.status : "none");
        setHasSummary(summary !== null);
        setEvidences(items);
        setSelectedEvidence(items[0]?.id ?? null);
      })
      .catch((caught) => {
        if (!cancelled) setLoadError(describeApiError(caught, "상담일지를 불러오지 못했습니다."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId, sessionId]);

  const readOnly = record?.status === "APPROVED";
  const unconfirmed = evidences.filter(e => e.status === null || e.status === "확인필요").length;
  const activeEvidence = evidences.find(e => e.id === selectedEvidence);

  function setEvidenceStatus(id: string, status: EvidenceItem["status"]) {
    setEvidences(prev => prev.map(e => e.id === id ? { ...e, status } : e));
  }

  /** 지금 본문을 저장한다. 상담일지가 없으면 만들고(DRAFT), 있으면 바뀐 경우에만 고친다. */
  async function saveRecord(targetSessionId: string): Promise<ApiDocument> {
    if (record) {
      if (record.content === docText) return record;

      return documentsApi.update(targetSessionId, record.id, { content: docText });
    }

    return documentsApi.create(targetSessionId, {
      title: defaultRecordTitle(sessionInfo?.sessionNumber ?? 0),
      content: docText,
      doc_type: DOC_TYPE_CONSULTATION_RECORD,
    });
  }

  function checkLength(): boolean {
    if (docText.length <= DOCUMENT_CONTENT_MAX) return true;

    showToast(`상담일지는 ${DOCUMENT_CONTENT_MAX.toLocaleString()}자까지 저장할 수 있습니다.`, "error");
    return false;
  }

  async function handleTempSave() {
    if (!sessionId || saving || readOnly || !checkLength()) return;

    setSaving("draft");
    try {
      setRecord(await saveRecord(sessionId));
      setDraftOrigin("document");
      showToast("임시저장되었습니다.", "success");
    } catch (caught) {
      showToast(describeApiError(caught, "임시저장에 실패했습니다.", "권한이 없거나 없는 회기입니다."), "error");
    } finally {
      setSaving(null);
    }
  }

  function handleFinalClick() {
    if (unconfirmed > 0) {
      showToast(`미확인 근거 ${unconfirmed}건을 먼저 처리해주세요.`, "error");
      return;
    }
    if (!docText.trim()) {
      showToast("상담일지 내용을 입력해주세요.", "error");
      return;
    }
    if (!checkLength()) return;
    setShowConfirm(true);
  }

  /** 저장한 뒤 승인한다. 승인에 실패해도 저장된 본문은 임시저장 상태로 남는다. */
  async function handleFinalSave() {
    if (!sessionId || saving) return;

    setSaving("final");
    try {
      const saved = await saveRecord(sessionId);
      setRecord(saved);
      setDraftOrigin("document");
      setRecord(await documentsApi.approve(sessionId, saved.id));
      setShowConfirm(false);
      showToast("상담일지가 저장되었습니다.", "success");
      navigate(-1);
    } catch (caught) {
      setShowConfirm(false);
      showToast(describeApiError(caught, "상담일지 저장에 실패했습니다.", "권한이 없거나 없는 회기입니다."), "error");
    } finally {
      setSaving(null);
    }
  }

  const draftBadge = readOnly
    ? `승인 완료${record?.approved_at ? ` (${toLocalDateTime(record.approved_at)})` : ""} — 수정할 수 없습니다`
    : draftOrigin === "document"
      ? `임시저장됨${record ? ` (${toLocalDateTime(record.updated_at)})` : ""} — 상담사 검토 후 확정`
      : draftOrigin === "APPROVED"
        ? "승인된 요약 기반 초안 — 상담사 검토 후 확정"
        : draftOrigin === "DRAFT"
          ? "AI 생성 초안 — 상담사 검토 후 확정"
          : "AI 요약 없음 — 직접 작성";

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#F6F8FB]">
      {/* Header */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 flex items-center gap-4 shrink-0">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-[13px] text-[#64748B] hover:text-[#172033] transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          돌아가기
        </button>
        <div className="h-5 w-px bg-[#E2E8F0]" />
        <div className="flex-1 flex items-center gap-3">
          <span className="text-[16px] font-semibold text-[#172033]">{caseObj?.childName ?? "—"}</span>
          <span className="text-[#94A3B8]">·</span>
          <span className="text-[13px] font-mono text-[#64748B]">{caseObj?.id ?? "—"}</span>
          <span className="text-[#94A3B8]">·</span>
          <span className="text-[13px] text-[#64748B]">{sessionInfo ? `${sessionInfo.sessionNumber}회차` : "—"}</span>
          <span className="text-[#94A3B8]">·</span>
          <span className="text-[13px] text-[#64748B]">{sessionInfo?.date || "—"}</span>
          <span className="text-[#94A3B8]">·</span>
          <span className="text-[13px] text-[#64748B]">담당: {caseObj?.counselor ?? "—"}</span>
        </div>
        {!loading && !loadError && !readOnly && (
          <div className="flex items-center gap-2">
            {unconfirmed > 0 && (
              <span className="text-[12px] font-medium px-3 py-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] text-[#64748B]">
                미확인 근거 {unconfirmed}건
              </span>
            )}
            <button
              onClick={handleTempSave}
              disabled={saving !== null}
              className="px-3 py-2 text-[13px] font-medium text-[#64748B] border border-[#E2E8F0] rounded-[6px] hover:bg-[#F8FAFC] disabled:opacity-60 transition-colors"
            >
              {saving === "draft" ? "저장 중..." : "임시저장"}
            </button>
            <button
              onClick={handleFinalClick}
              disabled={saving !== null}
              className="px-4 py-2 text-[13px] font-medium text-white bg-[#2563EB] hover:bg-[#1D4ED8] disabled:opacity-60 rounded-[6px] transition-colors"
            >
              상담일지 저장
            </button>
          </div>
        )}
      </div>

      {/* Body */}
      {loading && (
        <div className="flex-1 flex items-center justify-center text-[13px] text-[#94A3B8]">상담일지를 불러오는 중...</div>
      )}

      {!loading && loadError && (
        <div className="flex-1 flex items-center justify-center text-[13px] text-red-600">{loadError}</div>
      )}

      {!loading && !loadError && (
      <div className="flex-1 flex overflow-hidden">
        {/* Main edit area */}
        <div className="flex-1 flex flex-col overflow-hidden p-5 gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-[16px] font-semibold text-[#172033]">상담일지 작성</h2>
            <span className="text-[11px] font-medium px-2 py-0.5 border border-[#94A3B8] rounded text-[#64748B] bg-white">
              {draftBadge}
            </span>
          </div>
          <textarea
            value={docText}
            onChange={e => setDocText(e.target.value)}
            readOnly={readOnly}
            placeholder={draftOrigin === "none"
              ? "아직 AI 요약이 없습니다. 전사 검수와 AI 분석이 끝나면 요약을 바탕으로 초안이 채워집니다. 직접 작성할 수도 있습니다."
              : undefined}
            className="flex-1 w-full px-5 py-4 text-[14px] leading-relaxed text-[#172033] bg-white border border-[#E2E8F0] rounded-[8px] resize-none focus:outline-none focus:border-[#2563EB] font-mono read-only:bg-[#F8FAFC] read-only:text-[#475569]"
          />
        </div>

        {/* Right panel: evidence */}
        <div className="w-[360px] shrink-0 border-l border-[#E2E8F0] bg-white flex flex-col overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E2E8F0]">
            <h3 className="text-[14px] font-semibold text-[#172033]">작성 근거</h3>
            <p className="text-[12px] text-[#94A3B8] mt-0.5">AI 참고정보 — 상담사가 직접 확인·판단</p>
          </div>

          {/* Evidence list */}
          <div className="flex flex-col overflow-hidden flex-1">
            {evidences.length === 0 && (
              <div className="flex-1 flex flex-col items-center justify-center px-6 text-center space-y-2">
                <p className="text-[13px] text-[#64748B]">근거 발화가 없습니다</p>
                <p className="text-[12px] text-[#94A3B8] leading-relaxed">
                  {!hasSummary
                    ? "AI 요약이 만들어지면 요약 항목의 근거 발화가 여기에 보입니다."
                    : "요약 항목에 연결된 근거 발화가 없습니다."}
                </p>
              </div>
            )}

            {evidences.length > 0 && (
            <div className="flex border-b border-[#F1F5F9] overflow-x-auto">
              {evidences.map(e => (
                <button
                  key={e.id}
                  onClick={() => setSelectedEvidence(e.id)}
                  className="flex-1 min-w-[64px] shrink-0 py-2.5 text-[12px] font-medium transition-colors border-b-2"
                  style={{
                    borderBottomColor: selectedEvidence === e.id ? "#2563EB" : "transparent",
                    color: selectedEvidence === e.id ? "#2563EB" : "#64748B",
                  }}
                >
                  {e.timestamp}
                </button>
              ))}
            </div>
            )}

            {activeEvidence && (
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {/* Quote */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">원문 발화</p>
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] px-4 py-3">
                    <p className="text-[12px] text-[#94A3B8] mb-1">{activeEvidence.timestamp} · {activeEvidence.speaker}</p>
                    {activeEvidence.quote !== null ? (
                      <p className="text-[14px] font-medium text-[#172033]">"{activeEvidence.quote}"</p>
                    ) : (
                      <p className="text-[13px] text-[#94A3B8]">전사본에서 이 발화({activeEvidence.id})를 찾지 못했습니다.</p>
                    )}
                  </div>
                </div>

                {/* Signal — 요약 근거에는 위험 신호 분류가 없다. */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">관련 신호</p>
                  <span className="text-[13px] text-[#94A3B8]">—</span>
                </div>

                {/* Checklist — Backend 에 아직 없다. */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">연결 체크리스트</p>
                  <p className="text-[13px] text-[#94A3B8] bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] px-3 py-2">—</p>
                </div>

                {/* AI Reference — 이 발화를 근거로 든 AI 요약 항목.
                    근거는 분석 당시 AI 가 만든 문장 기준이라, 상담사가 요약을 고쳤어도 원래 문장으로 보인다. */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">AI 참고정보</p>
                  <div className="text-[12px] text-[#64748B] bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] px-3 py-2 leading-relaxed space-y-1">
                    {activeEvidence.keyPoints.length > 0
                      ? activeEvidence.keyPoints.map((point, i) => <p key={i}>AI 원본 요약 항목: {point}</p>)
                      : <p>—</p>}
                  </div>
                </div>

                {/* Status buttons */}
                <div>
                  <p className="text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider mb-2">상담사 확인 상태</p>
                  <div className="flex flex-col gap-2">
                    {(["확인필요", "확인완료", "보류"] as NonNullable<EvidenceItem["status"]>[]).map(s => (
                      <button
                        key={s}
                        onClick={() => setEvidenceStatus(activeEvidence.id, activeEvidence.status === s ? null : s)}
                        className="w-full py-2 text-[13px] rounded-[6px] border transition-all text-left px-3"
                        style={{
                          borderColor: activeEvidence.status === s ? "#2563EB" : "#E2E8F0",
                          background: activeEvidence.status === s ? "#EFF6FF" : "white",
                          color: activeEvidence.status === s ? "#2563EB" : "#64748B",
                          fontWeight: activeEvidence.status === s ? 600 : 400,
                        }}
                      >
                        {s === "확인필요" ? "확인 필요" : s === "확인완료" ? "확인 완료 (상담사 확인)" : "보류"}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      )}

      <ConfirmModal
        open={showConfirm}
        title="상담일지 저장"
        message="저장하면 상담일지가 승인되어 더 이상 수정할 수 없습니다. 저장하시겠습니까?"
        confirmLabel={saving === "final" ? "저장 중..." : "저장"}
        onConfirm={handleFinalSave}
        onCancel={() => { if (!saving) setShowConfirm(false); }}
      />
    </div>
  );
}
