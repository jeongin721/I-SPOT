// 회차 상세 훅(GET /sessions/{id}, 음성이 있으면 GET /sessions/{id}/audio). 회차 상세 화면과
// 업로드 · 검수 화면의 '지금 어느 단계인가' 표시가 쓴다. 새로고침 뒤 화면 복원도 이 조회로 한다(API_CONTRACT 5절).
//
// 원문 변환 · AI 분석이 도는 동안에는 POLL_INTERVAL_MS 마다 조용히 다시 조회한다. 서버가 재시작돼 멈춘 처리는
// 이 조회에서 실패(STT_FAILED · AI_FAILED)로 바뀌고 errorMessage 가 채워진다(API_CONTRACT 1.4).
//
// 전사 · 요약 · 문서 내용은 여기서 부르지 않는다. 같은 회차 ID 로 useTranscriptReview · useSummaryReview ·
// useSessionDocuments 를 함께 쓴다.

import { ApiError } from "../api/client";
import { sessions } from "../api/endpoints";
import type { AudioFile, SessionDetail } from "../api/types";
import { NOT_PROVIDED } from "./caseRows";
import { canRequestAnalysis, canRequestStt, canUploadAudio, isProcessing, toSessionRow, type SessionRow } from "./sessionRows";
import { formatBytes, formatDuration, toDateTime } from "./time";
import { usePolling, useRemote } from "./useRemote";

export interface AudioInfo {
  fileName: string;
  /** "12.4 MB". */
  sizeLabel: string;
  /** "24분". 길이를 모르면(WAV 가 아니고 올릴 때 길이를 보내지 않음) NOT_PROVIDED. */
  durationLabel: string;
  durationMs: number | null;
  /** 올린 일시(YYYY-MM-DD HH:mm). */
  uploadedAt: string;
}

export interface SessionDetailView extends SessionRow {
  hasAudio: boolean;
  hasTranscript: boolean;
  /** 지금 전사본 버전. 상담사가 고칠 때마다 1씩 오른다. 없으면 null. */
  transcriptVersion: number | null;
  transcriptConfirmed: boolean;
  hasAnalysis: boolean;
  hasSummary: boolean;
  summaryApproved: boolean;
  /** 원문 변환 · AI 분석이 실패했을 때 서버 문구. 없으면 null. */
  errorMessage: string | null;
  errorCode: string | null;
  /** 지금 할 수 있는 요청. 단추를 켜고 끌 때 쓴다(서버가 최종으로 거절할 수 있다). */
  canUploadAudio: boolean;
  canRequestStt: boolean;
  canRequestAnalysis: boolean;
  /** 음성 파일 정보. 음성이 없으면 null. */
  audio: AudioInfo | null;
}

export function toAudioInfo(source: AudioFile): AudioInfo {
  return {
    fileName: source.original_filename,
    sizeLabel: formatBytes(source.size_bytes),
    durationLabel: formatDuration(source.duration_ms) || NOT_PROVIDED,
    durationMs: source.duration_ms,
    uploadedAt: toDateTime(source.created_at),
  };
}

export function toSessionDetailView(source: SessionDetail, audio: AudioFile | null): SessionDetailView {
  return {
    ...toSessionRow(source),
    hasAudio: source.has_audio,
    hasTranscript: source.has_transcript,
    transcriptVersion: source.transcript_version,
    transcriptConfirmed: source.transcript_confirmed,
    hasAnalysis: source.has_analysis,
    hasSummary: source.has_summary,
    summaryApproved: source.summary_approved,
    errorMessage: source.error?.message ?? null,
    errorCode: source.error?.code ?? null,
    canUploadAudio: canUploadAudio(source.status),
    canRequestStt: canRequestStt(source.status),
    canRequestAnalysis: canRequestAnalysis(source.status),
    audio: audio ? toAudioInfo(audio) : null,
  };
}

async function loadSessionDetail(sessionId: string): Promise<SessionDetailView> {
  const detail = await sessions.get(sessionId);
  let audio: AudioFile | null = null;

  if (detail.has_audio) {
    try {
      audio = await sessions.getAudio(sessionId);
    } catch (caught) {
      // 그사이 회차가 지워지는 등으로 음성 정보만 못 받았으면 회차 정보는 그대로 보여 준다.
      // 로그인이 끝난 401 은 client 가 알리고, 그 밖의 오류는 위로 올린다.
      if (!(caught instanceof ApiError && caught.code === "AUDIO_NOT_FOUND")) throw caught;
    }
  }

  return toSessionDetailView(detail, audio);
}

export interface SessionDetailOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
  /** 처리 중일 때 되풀이 조회할지. 기본 true. */
  poll?: boolean;
}

export interface SessionDetailState {
  session: SessionDetailView | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  /** '불러오는 중' 없이 다시 조회한다(다른 훅에서 요청을 보낸 뒤 단계를 맞출 때). */
  refresh: () => void;
}

export function useSessionDetail(
  sessionId: string | null | undefined,
  { enabled = true, poll = true }: SessionDetailOptions = {},
): SessionDetailState {
  const remote = useRemote(
    enabled && sessionId ? sessionId : null,
    loadSessionDetail,
    "회차 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  );
  const session = remote.data;

  usePolling(poll && session !== null && isProcessing(session.status), remote.refresh, remote.settled);

  return { session, loading: remote.loading, error: remote.error, reload: remote.reload, refresh: remote.refresh };
}
