// 요약 검수 · 승인 훅(GET · PATCH /sessions/{id}/summary, POST …/approve · …/reopen). 근거 발화를 보이려고 원문(GET …/transcript)도 함께 받는다.
//
// AI 요약은 항상 초안(DRAFT)으로 시작하고 자동 승인되지 않는다(AI 생성 → 상담사 확인 → 수정 → 승인 → 저장).
// 화면은 overview · keyPoints · counselorNote 를 고치고(set…), save() 로 바꾼 칸만 보낸다.
//
//  - 고칠 수 있는 것은 회차가 'AI 결과 검수 필요' 이고 요약이 초안일 때뿐이다. 재분석이 도는 중이거나 실패하면 막힌다.
//  - 상담사가 고친 요약은 재분석이 덮어쓰지 않는다. 근거(evidence)는 새 분석 것으로 바뀐다(API_CONTRACT 9절).
//  - **approve() 는 회차를 '승인 완료' 로 바꾼다.** 그 뒤에 고치려면 reopen() 으로 승인을 푼다(내용은 그대로 초안이 되고
//    회차도 'AI 결과 검수 필요' 로 돌아간다. 고친 뒤 다시 승인한다). approve() 를 새 화면의 '일지 저장' 이나
//    '질문 처리 완료' 단추에 그대로 붙이지 않는다(specs 대응표 '승인 시점'). 상담일지 문서 승인은 useSessionDocuments 로 따로 한다.
//  - 근거는 요약 문장과 글자로 맞추지 않는다. 근거의 keyPoint 는 AI 원본 문장이고, 발화는 segment_id 로 찾는다.
//  - AI 분석 중이면 POLL_INTERVAL_MS 마다 조용히 다시 조회한다.

import { useCallback, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { summary as summaryApi, transcript as transcriptApi } from "../api/endpoints";
import type { ReviewStatus, SessionStatus, SummaryEnvelope, SummaryUpdateRequest, TranscriptEnvelope } from "../api/types";
import { notifySessionChanged } from "./sessionEvents";
import { isProcessing } from "./sessionRows";
import { formatClock, toDateTime } from "./time";
import { SPEAKER_LABELS } from "./transcriptRows";
import { errorMessage, usePolling, useRemote } from "./useRemote";

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  DRAFT: "검수 중",
  APPROVED: "승인",
};

export interface EvidenceSegment {
  segmentId: string;
  /**
   * 원문에서 찾았는가. 못 찾으면(원문이 바뀜 등) 아래 칸이 비어 있다.
   * 원문을 아직 못 받았으면(evidenceLoading · evidenceError) 모두 false 다 — 그때는 '없음' 이 아니라 '모름' 이다.
   */
  found: boolean;
  startLabel: string;
  speakerLabel: string;
  text: string;
}

export interface EvidenceItem {
  /** AI 원본 요약 문장. 상담사가 고친 요약 문장과 다를 수 있다. */
  keyPoint: string;
  score: number;
  segments: EvidenceSegment[];
}

export interface SummaryFields {
  overview: string;
  keyPoints: string[];
  /** 상담사 메모. 없으면 빈 문자열. */
  counselorNote: string;
}

export interface SummaryReviewOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface SummaryReviewState {
  sessionStatus: SessionStatus | null;
  /** 요약이 아직 없으면(분석 전 · 분석 중 첫 요약) false. */
  hasSummary: boolean;
  /** 화면에 보일 값. 고친 칸이 반영돼 있다. */
  fields: SummaryFields;
  status: ReviewStatus | null;
  statusLabel: string;
  /** 상담사가 고친 적이 있는가(서버에 저장된 것 기준). */
  edited: boolean;
  approvedAt: string;
  evidence: EvidenceItem[];
  /** 근거 발화를 찾을 원문을 불러오는 중. */
  evidenceLoading: boolean;
  /** 근거 발화를 찾을 원문을 못 불러왔으면 그 문구. 이때 evidence 의 found 는 믿을 수 없다. reload() 로 다시 부른다. */
  evidenceError: string | null;
  /** 저장하지 않은 수정이 있는가. */
  dirty: boolean;
  canEdit: boolean;
  canApprove: boolean;
  /** 승인된 요약이라 승인을 풀 수(reopen) 있는가. */
  canReopen: boolean;
  sessionError: string | null;
  submitting: boolean;
  loading: boolean;
  error: string | null;
  setOverview: (value: string) => void;
  setKeyPoint: (index: number, value: string) => void;
  addKeyPoint: (value?: string) => void;
  removeKeyPoint: (index: number) => void;
  setCounselorNote: (value: string) => void;
  discardChanges: () => void;
  /** 바꾼 칸만 저장한다. 바꾼 것이 없으면 아무것도 보내지 않고 true. */
  save: () => Promise<boolean>;
  /** (바꾼 칸을 먼저 저장하고) 승인한다. 회차가 '승인 완료' 가 된다. */
  approve: () => Promise<boolean>;
  /** 승인을 풀어 다시 고칠 수 있게 한다. 내용은 그대로 두고, 회차는 'AI 결과 검수 필요' 로 돌아간다. */
  reopen: () => Promise<boolean>;
  /** 요약과 근거용 원문을 함께 다시 부른다. */
  reload: () => void;
}

const EMPTY_FIELDS: SummaryFields = { overview: "", keyPoints: [], counselorNote: "" };

function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

export function useSummaryReview(
  sessionId: string | null | undefined,
  { enabled = true }: SummaryReviewOptions = {},
): SummaryReviewState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<SummaryEnvelope>(key, summaryApi.get, "요약을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
  const source = useRemote<TranscriptEnvelope>(key, transcriptApi.get, "근거 발화를 불러오지 못했습니다.");
  // 고친 칸. null 이면 고친 것이 없다(서버 값을 그대로 보인다).
  const [draft, setDraft] = useState<SummaryFields | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // 요청 중인가. state 는 같은 순간의 두 번째 누름을 막지 못해 ref 로도 든다.
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [draftKey, setDraftKey] = useState(key);

  if (draftKey !== key) {
    setDraftKey(key);
    setDraft(null);
    setActionError(null);
  }

  const envelope = remote.data;
  const saved = envelope?.summary ?? null;
  const sessionStatus = envelope?.session_status ?? null;
  const processing = sessionStatus !== null && isProcessing(sessionStatus);

  usePolling(processing, remote.refresh, remote.settled);

  const savedFields: SummaryFields = useMemo(
    () =>
      saved
        ? { overview: saved.overview, keyPoints: saved.key_points, counselorNote: saved.counselor_note ?? "" }
        : EMPTY_FIELDS,
    [saved],
  );

  const fields = draft ?? savedFields;

  const changes = useMemo(() => {
    const payload: SummaryUpdateRequest = {};

    if (!draft) return payload;
    if (draft.overview !== savedFields.overview) payload.overview = draft.overview;
    if (!sameList(draft.keyPoints, savedFields.keyPoints)) payload.key_points = draft.keyPoints;
    if (draft.counselorNote !== savedFields.counselorNote) payload.counselor_note = draft.counselorNote;

    return payload;
  }, [draft, savedFields]);

  const dirty = Object.keys(changes).length > 0;
  const canEdit = saved !== null && saved.status === "DRAFT" && sessionStatus === "AI_REVIEW_REQUIRED";
  const canReopen = saved !== null && saved.status === "APPROVED" && sessionStatus === "APPROVED";

  const evidence = useMemo<EvidenceItem[]>(() => {
    const segments = new Map((source.data?.transcript?.segments ?? []).map((segment) => [segment.segment_id, segment]));

    return (envelope?.summary_evidence ?? []).map((item) => ({
      keyPoint: item.key_point,
      score: item.score,
      segments: item.segment_ids.map((segmentId) => {
        const segment = segments.get(segmentId);

        return segment
          ? {
              segmentId,
              found: true,
              startLabel: formatClock(segment.start_ms),
              speakerLabel: SPEAKER_LABELS[segment.speaker] ?? segment.speaker,
              text: segment.text,
            }
          : { segmentId, found: false, startLabel: "", speakerLabel: "", text: "" };
      }),
    }));
  }, [envelope, source.data]);

  const edit = useCallback(
    (change: (current: SummaryFields) => SummaryFields) => setDraft((current) => change(current ?? savedFields)),
    [savedFields],
  );

  const setOverview = useCallback((value: string) => edit((current) => ({ ...current, overview: value })), [edit]);

  const setKeyPoint = useCallback(
    (index: number, value: string) =>
      edit((current) => ({
        ...current,
        keyPoints: current.keyPoints.map((point, at) => (at === index ? value : point)),
      })),
    [edit],
  );

  const addKeyPoint = useCallback(
    (value = "") => edit((current) => ({ ...current, keyPoints: [...current.keyPoints, value] })),
    [edit],
  );

  const removeKeyPoint = useCallback(
    (index: number) => edit((current) => ({ ...current, keyPoints: current.keyPoints.filter((_, at) => at !== index) })),
    [edit],
  );

  const setCounselorNote = useCallback((value: string) => edit((current) => ({ ...current, counselorNote: value })), [edit]);

  const discardChanges = useCallback(() => {
    setDraft(null);
    setActionError(null);
  }, []);

  /** 요청 하나를 한 번에 하나만 보낸다. 같은 순간 두 번 눌러도 두 번째는 false. */
  const begin = useCallback(() => {
    if (inFlight.current) return false;

    inFlight.current = true;
    setSubmitting(true);
    setActionError(null);

    return true;
  }, []);

  const end = useCallback(() => {
    inFlight.current = false;
    setSubmitting(false);
  }, []);

  /**
   * 바꾼 칸을 보낸다. 성공하면 true(바꾼 것이 없어도 true). 실패하면 던진다.
   * 응답이 오면 **보낸 그 고친 칸일 때만** 비운다. 저장을 기다리는 사이 더 고쳤으면 그 입력은 남는다.
   * 요청한 뒤 다른 회차로 옮겼으면 응답을 반영하지 않는다(앞 회차에는 저장됐다).
   */
  const sendChanges = useCallback(
    async (forKey: string) => {
      if (!dirty) return true;

      const sent = draft;
      // 빈 요약 항목은 보내지 않는다(입력 칸만 만들고 비워 둔 것).
      const payload = changes.key_points
        ? { ...changes, key_points: changes.key_points.map((point) => point.trim()).filter(Boolean) }
        : changes;
      const next = await summaryApi.update(forKey, payload);

      const applied = remote.setData(forKey, (current) => ({
        session_id: forKey,
        session_status: "AI_REVIEW_REQUIRED",
        summary_evidence: [],
        error: null,
        ...current,
        summary: next,
      }));

      if (applied) setDraft((current) => (current === sent ? null : current));

      return true;
    },
    [dirty, draft, changes, remote.setData],
  );

  const report = useCallback(
    (forKey: string, caught: unknown, fallback: string) => {
      // 요청한 뒤 다른 회차로 옮겼으면 앞 회차의 오류는 보이지 않는다.
      if (!remote.isCurrent(forKey)) return;
      if (!(caught instanceof ApiError && caught.isUnauthorized)) setActionError(errorMessage(caught, fallback));

      // 상태가 어긋났을 수 있다(다른 창에서 승인 · 재분석). 최신 상태를 다시 받는다. 고친 칸은 남겨 둔다.
      remote.refresh();
    },
    [remote.isCurrent, remote.refresh],
  );

  const save = useCallback(async () => {
    if (!key || !begin()) return false;

    const forKey = key;

    try {
      return await sendChanges(forKey);
    } catch (caught) {
      report(forKey, caught, "요약을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.");

      return false;
    } finally {
      end();
    }
  }, [key, begin, end, sendChanges, report]);

  const approve = useCallback(async () => {
    if (!key || !begin()) return false;

    const forKey = key;

    try {
      if (!(await sendChanges(forKey))) return false;
      // 저장하는 사이 다른 회차로 옮겼으면 승인하지 않는다(사람이 보고 있지 않은 요약을 승인하지 않게).
      if (!remote.isCurrent(forKey)) return false;

      const approved = await summaryApi.approve(forKey);

      remote.setData(forKey, (current) => ({
        session_id: forKey,
        summary_evidence: [],
        error: null,
        ...current,
        summary: approved,
        session_status: "APPROVED",
      }));
      // 같은 화면의 회차 상세 · 사례 상세 · 분석 훅이 '승인 완료' 를 받아 가게 알린다.
      notifySessionChanged({ sessionId: forKey });

      return true;
    } catch (caught) {
      report(forKey, caught, "요약을 승인하지 못했습니다. 잠시 후 다시 시도해 주세요.");

      return false;
    } finally {
      end();
    }
  }, [key, begin, end, sendChanges, report, remote.isCurrent, remote.setData]);

  const reopen = useCallback(async () => {
    if (!key || !begin()) return false;

    const forKey = key;

    try {
      const reopened = await summaryApi.reopen(forKey);

      remote.setData(forKey, (current) => ({
        session_id: forKey,
        summary_evidence: [],
        error: null,
        ...current,
        summary: reopened,
        session_status: "AI_REVIEW_REQUIRED",
      }));
      // 같은 화면의 회차 상세 · 사례 상세 · 분석 훅이 'AI 결과 검수 필요' 를 받아 가게 알린다.
      notifySessionChanged({ sessionId: forKey });

      return true;
    } catch (caught) {
      report(forKey, caught, "요약을 수정 상태로 바꾸지 못했습니다. 잠시 후 다시 시도해 주세요.");

      return false;
    } finally {
      end();
    }
  }, [key, begin, end, report, remote.setData]);

  const reload = useCallback(() => {
    remote.reload();
    source.reload();
  }, [remote.reload, source.reload]);

  return {
    sessionStatus,
    hasSummary: saved !== null,
    fields,
    status: saved?.status ?? null,
    statusLabel: saved ? REVIEW_STATUS_LABELS[saved.status] : "",
    edited: saved?.is_edited ?? false,
    approvedAt: toDateTime(saved?.approved_at),
    evidence,
    evidenceLoading: source.loading,
    evidenceError: source.error,
    dirty,
    canEdit,
    canApprove: canEdit,
    canReopen,
    sessionError: envelope?.error?.message ?? null,
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    setOverview,
    setKeyPoint,
    addKeyPoint,
    removeKeyPoint,
    setCounselorNote,
    discardChanges,
    save,
    approve,
    reopen,
    reload,
  };
}
