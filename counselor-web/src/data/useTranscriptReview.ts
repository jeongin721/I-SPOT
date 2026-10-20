// 원문(STT) 검수 훅(GET · PATCH /sessions/{id}/transcript, POST …/confirm, 다시 변환 POST …/transcript).
//
// 화면은 회차 ID 를 넘기고 rows(발화 줄) · counts · 상태를 받아 그린다. 화자 · 문장을 고치면 이 훅이 '고친 칸' 으로
// 들고 있다가 save() 때 **바꾼 발화의 바꾼 필드만** 보낸다(전체를 보내면 모든 발화가 '수정됨' 이 된다 — API_CONTRACT 7절).
//
//  - 저장할 때마다 서버에 새 버전이 생기고 이전 버전은 이력으로 남는다.
//  - 확정(confirm)해야 AI 분석을 요청할 수 있다. 저장하지 않은 수정이 있으면 confirm() 이 먼저 저장한다.
//  - 확정 뒤에도 고칠 수 있다. 고치면 회차가 다시 '원문 검수 필요' 로 돌아간다.
//  - 다른 창에서 같은 버전을 먼저 고쳤으면 409 DUPLICATE_RESOURCE. 최신 원문을 다시 받고, 고친 칸은 남겨 둔다
//    (최신 원문과 같아진 칸은 저절로 빠진다). 다시 save() 하면 된다.
//  - 화면의 줄별 '확인' 표시는 화면 상태다. 서버에는 '원문 확정' 하나만 있다(specs 대응표 SttReview).
//  - 원문 변환 중이면 POLL_INTERVAL_MS 마다 조용히 다시 조회한다.

import { useCallback, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { transcript as transcriptApi } from "../api/endpoints";
import type {
  SessionStatus,
  Speaker,
  Transcript,
  TranscriptEnvelope,
  TranscriptSegmentUpdate,
  TranscriptUpdateRequest,
} from "../api/types";
import { SPEAKER_LABELS, toSegmentRow, type SegmentRow } from "./transcriptRows";
import { notifySessionChanged } from "./sessionEvents";
import { canRequestStt, isProcessing } from "./sessionRows";
import { toDateTime } from "./time";
import { errorMessage, usePolling, useRemote, type RemoteTicket } from "./useRemote";

interface SegmentDraft {
  speaker?: Speaker;
  text?: string;
}

export interface TranscriptCounts {
  total: number;
  /** 저신뢰 발화(상담사가 고친 것은 뺀다). */
  lowConfidence: number;
  /** 화자 미확인 발화. */
  speakerUnknown: number;
  /** 서버에 저장된 수정이 있는 발화. */
  edited: number;
  /** 아직 저장하지 않은 수정 · 삭제. */
  pending: number;
}

export interface TranscriptInfo {
  version: number;
  confirmed: boolean;
  /** 확정 일시. 확정 전이면 빈 문자열. */
  confirmedAt: string;
  /** "STT" 면 변환 결과 그대로, "COUNSELOR_EDIT" 면 상담사가 고친 버전. */
  source: Transcript["source"];
  sttProvider: string | null;
}

export interface TranscriptReviewOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface TranscriptReviewState {
  sessionStatus: SessionStatus | null;
  /** 원문이 아직 없으면(변환 전 · 변환 중 · 변환 실패) null. */
  info: TranscriptInfo | null;
  /** 시간 순 발화 줄. 고친 칸이 반영돼 있다. 지울 발화도 removed=true 로 남아 있다. */
  rows: SegmentRow[];
  counts: TranscriptCounts;
  /** 원문 변환 · 실패 문구(변환 실패 때). */
  sessionError: string | null;
  /** 지금 고칠 수 있는가(원문 검수 필요 · 확정 상태). */
  canEdit: boolean;
  /** 지금 확정할 수 있는가(원문 검수 필요 상태이고 원문이 있음). */
  canConfirm: boolean;
  /** 원문 변환을 (다시) 요청할 수 있는가. */
  canRequestStt: boolean;
  /** 저장 · 확정 · 변환 요청 중. */
  submitting: boolean;
  loading: boolean;
  /** 불러오기 · 저장 · 확정 오류. */
  error: string | null;
  editSpeaker: (segmentId: string, speaker: Speaker) => void;
  editText: (segmentId: string, text: string) => void;
  removeSegment: (segmentId: string) => void;
  restoreSegment: (segmentId: string) => void;
  /** 고친 칸을 모두 버린다. */
  discardChanges: () => void;
  /**
   * 고친 칸을 저장한다. 고친 것이 없으면 아무것도 보내지 않고 true.
   * 요청한 뒤 대상이 바뀌어(다른 회차, 갔다 돌아옴, 다시 로그인, 화면을 떠남) 반영하지 못했으면 false.
   */
  save: () => Promise<boolean>;
  /** (고친 칸을 먼저 저장하고) 원문을 확정한다. 저장 뒤 대상이 바뀌었으면 확정하지 않고 false. */
  confirm: () => Promise<boolean>;
  /** 원문 변환을 다시 요청한다(실패 뒤 재시도, 검수 중 다시 변환). 고친 칸은 버린다. 반영하지 못했으면 false. */
  requestStt: () => Promise<boolean>;
  reload: () => void;
  /** 지금 대상의 표(useRemote). 확정 뒤 이동처럼 응답 뒤에 이어 하는 일은 누를 때 잡아 두고 isCurrent 로 확인한다. */
  capture: () => RemoteTicket | null;
  isCurrent: (ticket: RemoteTicket | null) => boolean;
}

export function useTranscriptReview(
  sessionId: string | null | undefined,
  { enabled = true }: TranscriptReviewOptions = {},
): TranscriptReviewState {
  const key = enabled && sessionId ? sessionId : null;
  const remote = useRemote<TranscriptEnvelope>(key, transcriptApi.get, "원문을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
  const [drafts, setDrafts] = useState<Record<string, SegmentDraft>>({});
  const [removed, setRemoved] = useState<Record<string, true>>({});
  const [submitting, setSubmitting] = useState(false);
  // 요청 중인가. state 는 같은 순간의 두 번째 누름을 막지 못해 ref 로도 든다.
  const inFlight = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [draftKey, setDraftKey] = useState(key);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);

  // 다른 회차로 바뀌면 고친 칸을 버린다(그리는 중에 맞춘다 — 앞 회차의 고친 칸이 한 번도 보이지 않게).
  if (draftKey !== key) {
    setDraftKey(key);
    setDrafts({});
    setRemoved({});
    setActionError(null);
  }

  // 대상 세대가 바뀌면(다른 회차, 로그아웃 · 다시 로그인, 다른 회차에 갔다 돌아옴) 앞 대상에서 보낸 요청이 아직 안 끝났어도
  // 새 대상에서는 보낼 수 있게 한다(그 요청의 응답은 반영하지 않는다).
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setActionError(null);
    inFlight.current = false;
    setSubmitting(false);
  }

  const envelope = remote.data;
  const saved = envelope?.transcript ?? null;
  const sessionStatus = envelope?.session_status ?? null;

  usePolling(sessionStatus !== null && isProcessing(sessionStatus), remote.refresh, remote.settled);

  const savedById = useMemo(() => {
    const map = new Map<string, Transcript["segments"][number]>();

    saved?.segments.forEach((segment) => map.set(segment.segment_id, segment));

    return map;
  }, [saved]);

  /** 저장된 값과 다른 고친 칸만 남긴 것. 최신 원문과 같아진 칸은 빠진다. */
  const effectiveDrafts = useMemo(() => {
    const result: Record<string, SegmentDraft> = {};

    for (const [segmentId, draft] of Object.entries(drafts)) {
      const base = savedById.get(segmentId);

      if (!base) continue;

      const change: SegmentDraft = {};

      if (draft.speaker !== undefined && draft.speaker !== base.speaker) change.speaker = draft.speaker;
      if (draft.text !== undefined && draft.text !== base.text) change.text = draft.text;
      if (change.speaker !== undefined || change.text !== undefined) result[segmentId] = change;
    }

    return result;
  }, [drafts, savedById]);

  const effectiveRemoved = useMemo(
    () => Object.keys(removed).filter((segmentId) => savedById.has(segmentId)),
    [removed, savedById],
  );

  const rows = useMemo(() => {
    if (!saved) return [];

    const edited = new Set(saved.edited_segment_ids);

    return [...saved.segments]
      .sort((a, b) => a.start_ms - b.start_ms)
      .map((segment) => {
        const row = toSegmentRow(segment, edited.has(segment.segment_id));
        const draft = effectiveDrafts[segment.segment_id];
        const isRemoved = segment.segment_id in removed;

        if (!draft && !isRemoved) return row;

        const speaker = draft?.speaker ?? row.speaker;

        return {
          ...row,
          speaker,
          speakerLabel: SPEAKER_LABELS[speaker] ?? speaker,
          text: draft?.text ?? row.text,
          speakerUnknown: speaker === "UNKNOWN",
          // 고친 발화는 상담사가 본 것이라 저신뢰 표시를 끈다(저장 뒤 서버 표시와 같게).
          lowConfidence: draft ? false : row.lowConfidence,
          dirty: Boolean(draft) || isRemoved,
          removed: isRemoved,
        };
      });
  }, [saved, effectiveDrafts, removed]);

  const pendingCount = Object.keys(effectiveDrafts).length + effectiveRemoved.length;

  const counts: TranscriptCounts = {
    total: rows.length,
    lowConfidence: rows.filter((row) => !row.removed && row.lowConfidence).length,
    speakerUnknown: rows.filter((row) => !row.removed && row.speakerUnknown).length,
    edited: rows.filter((row) => row.edited).length,
    pending: pendingCount,
  };

  const canEdit = saved !== null && (sessionStatus === "STT_REVIEW_REQUIRED" || sessionStatus === "STT_CONFIRMED");
  const canConfirm = saved !== null && sessionStatus === "STT_REVIEW_REQUIRED";

  const editSpeaker = useCallback((segmentId: string, speaker: Speaker) => {
    setDrafts((current) => ({ ...current, [segmentId]: { ...current[segmentId], speaker } }));
  }, []);

  const editText = useCallback((segmentId: string, text: string) => {
    setDrafts((current) => ({ ...current, [segmentId]: { ...current[segmentId], text } }));
  }, []);

  const removeSegment = useCallback((segmentId: string) => {
    setRemoved((current) => ({ ...current, [segmentId]: true }));
  }, []);

  const restoreSegment = useCallback((segmentId: string) => {
    setRemoved((current) => {
      const next = { ...current };

      delete next[segmentId];

      return next;
    });
  }, []);

  const discardChanges = useCallback(() => {
    setDrafts({});
    setRemoved({});
    setActionError(null);
  }, []);

  /** 응답으로 받은 원문을 반영한다. 요청한 뒤 대상이 바뀌었으면 버리고 false. */
  const applyTranscript = useCallback(
    (ticket: RemoteTicket, next: Transcript, status: SessionStatus) =>
      remote.setData(ticket, (current) => ({
        session_id: ticket.key,
        ...current,
        session_status: status,
        transcript: next,
        error: null,
      })),
    [remote.setData],
  );

  /**
   * 요청 하나를 한 번에 하나만 보낸다. 시작하면 지금 대상의 표, 이미 요청 중이거나 대상이 없으면 null
   * (같은 순간 두 번 눌러도 두 번째는 null). 이 함수를 만든 그리기 뒤에 대상이 바뀌었어도 null.
   */
  const begin = useCallback((): RemoteTicket | null => {
    const ticket = remote.capture();

    if (!ticket || ticket.key !== key || inFlight.current) return null;

    inFlight.current = true;
    setSubmitting(true);
    setActionError(null);

    return ticket;
  }, [key, remote.capture]);

  /** 요청이 끝났다. 대상 세대가 바뀌었으면 그때 이미 풀었으므로 새 대상에서 보낸 요청의 표시를 끄지 않는다. */
  const end = useCallback(
    (ticket: RemoteTicket) => {
      if (!remote.sameGeneration(ticket)) return;

      inFlight.current = false;
      setSubmitting(false);
    },
    [remote.sameGeneration],
  );

  /** 실패를 알린다. 요청한 뒤 대상이 바뀌었으면 앞 대상의 오류는 보이지 않는다. */
  const report = useCallback(
    (ticket: RemoteTicket, caught: unknown, fallback: string) => {
      if (!remote.isCurrent(ticket)) return;
      if (caught instanceof ApiError && caught.isUnauthorized) return;

      setActionError(errorMessage(caught, fallback));
    },
    [remote.isCurrent],
  );

  /**
   * 고친 칸을 보낸다. 성공하면 새 원문 버전(없으면 null — 보낼 것이 없음). 실패하면 undefined(오류는 알렸다).
   * 요청한 뒤 대상이 바뀌어 반영하지 못했어도 undefined 다(다음 요청 · 이동을 이어 하지 않게).
   * 고친 칸은 비우지 않는다. 새 원문과 같아진 칸은 effectiveDrafts 에서 저절로 빠지고,
   * 저장을 기다리는 사이 더 고친 칸은 그대로 남는다(통째로 비우면 그 입력이 사라진다).
   */
  const sendChanges = useCallback(
    async (ticket: RemoteTicket): Promise<Transcript | null | undefined> => {
      const segments: TranscriptSegmentUpdate[] = Object.entries(effectiveDrafts)
        .filter(([segmentId]) => !(segmentId in removed))
        .map(([segmentId, change]) => ({ segment_id: segmentId, ...change }));

      if (segments.length === 0 && effectiveRemoved.length === 0) return null;

      const payload: TranscriptUpdateRequest = {};

      if (segments.length > 0) payload.segments = segments;
      if (effectiveRemoved.length > 0) payload.removed_segment_ids = effectiveRemoved;

      try {
        const next = await transcriptApi.update(ticket.key, payload);

        // 확정 뒤에 고치면 서버가 '원문 검수 필요' 로 되돌린다(API_CONTRACT 7절).
        const applied = applyTranscript(ticket, next, "STT_REVIEW_REQUIRED");
        notifySessionChanged({ sessionId: ticket.key });

        return applied ? next : undefined;
      } catch (caught) {
        if (caught instanceof ApiError && caught.code === "DUPLICATE_RESOURCE") {
          // 대상이 바뀌었으면 문구도 다시 조회도 하지 않는다.
          if (remote.isCurrent(ticket)) {
            setActionError("다른 곳에서 원문이 먼저 수정됐습니다. 최신 원문을 불러왔으니 확인한 뒤 다시 저장해 주세요.");
            remote.refresh();
          }
        } else {
          report(ticket, caught, "원문을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.");
        }

        return undefined;
      }
    },
    [effectiveDrafts, effectiveRemoved, removed, applyTranscript, report, remote.isCurrent, remote.refresh],
  );

  const save = useCallback(async () => {
    const ticket = begin();

    if (!ticket) return false;

    try {
      return (await sendChanges(ticket)) !== undefined;
    } finally {
      end(ticket);
    }
  }, [begin, end, sendChanges]);

  const confirm = useCallback(async () => {
    const ticket = begin();

    if (!ticket) return false;

    try {
      if ((await sendChanges(ticket)) === undefined) return false;
      // 저장하는 사이 대상이 바뀌었으면(다른 회차, 갔다 돌아옴, 다시 로그인) 확정하지 않는다
      // (사람이 보고 있지 않은 회차나 돌아와서 새로 고친 칸이 저장되지 않은 원문을 확정하지 않게).
      if (!remote.isCurrent(ticket)) return false;

      const confirmed = await transcriptApi.confirm(ticket.key);

      const applied = applyTranscript(ticket, confirmed, "STT_CONFIRMED");
      // 같은 화면의 AI 분석 훅 등이 '분석 요청 가능' 상태를 받아 가게 알린다.
      notifySessionChanged({ sessionId: ticket.key });

      return applied;
    } catch (caught) {
      report(ticket, caught, "원문을 확정하지 못했습니다. 잠시 후 다시 시도해 주세요.");
      // 상태가 어긋났을 수 있다(다른 창에서 확정 · 다시 변환). 대상이 그대로면 최신 상태를 다시 받는다.
      if (remote.isCurrent(ticket)) remote.refresh();

      return false;
    } finally {
      end(ticket);
    }
  }, [begin, end, sendChanges, applyTranscript, report, remote.isCurrent, remote.refresh]);

  const requestStt = useCallback(async () => {
    const ticket = begin();

    if (!ticket) return false;

    try {
      const requested = await transcriptApi.run(ticket.key);

      // 요청 응답의 '변환 중' 을 바로 반영한다. 이어지는 조회가 한 번 실패해도 되풀이 조회가 시작되게.
      // 대상이 바뀌었으면(갔다 돌아옴, 다시 로그인) 반영하지 않고 그 뒤에 고친 칸도 지우지 않는다.
      const applied = remote.setData(ticket, (current) => ({
        session_id: ticket.key,
        transcript: null,
        ...current,
        session_status: requested.session_status,
        error: null,
      }));

      if (applied) {
        setDrafts({});
        setRemoved({});
      }

      // 이 훅과 같은 회차를 보는 훅이 모두 다시 조회한다.
      notifySessionChanged({ sessionId: ticket.key });

      return applied;
    } catch (caught) {
      report(ticket, caught, "원문 변환을 요청하지 못했습니다. 잠시 후 다시 시도해 주세요.");
      // 그사이 다른 곳에서 요청해 409 일 수 있다. 대상이 그대로면 최신 상태를 다시 받는다.
      if (remote.isCurrent(ticket)) remote.refresh();

      return false;
    } finally {
      end(ticket);
    }
  }, [begin, end, report, remote.setData, remote.isCurrent, remote.refresh]);


  return {
    sessionStatus,
    info: saved
      ? {
          version: saved.version,
          confirmed: saved.is_confirmed,
          confirmedAt: toDateTime(saved.confirmed_at),
          source: saved.source,
          sttProvider: saved.stt_provider,
        }
      : null,
    rows,
    counts,
    sessionError: envelope?.error?.message ?? null,
    canEdit,
    canConfirm,
    canRequestStt: sessionStatus !== null && canRequestStt(sessionStatus),
    submitting,
    loading: remote.loading,
    error: actionError ?? remote.error,
    editSpeaker,
    editText,
    removeSegment,
    restoreSegment,
    discardChanges,
    save,
    confirm,
    requestStt,
    reload: remote.reload,
    capture: remote.capture,
    isCurrent: remote.isCurrent,
  };
}
