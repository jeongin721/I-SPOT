// Backend 회차(Session) → 화면에 보여 줄 문자열과 처리 단계.
//
// 화면 배치와 상관없이 쓸 수 있게 값만 만든다. 어느 칸에 어떻게 놓을지는 화면이 정한다.
// 상태 이름은 Backend 오류 문구의 이름(backend/app/core/state_machine.py _STATUS_LABELS)과 같게 둔다 —
// 화면과 오류 문구가 같은 상태를 다른 말로 부르지 않게.
//
// Backend 에 없는 값은 다른 값으로 대신 채우지 않는다(specs 대응표 "없는 값을 다른 값으로 대체하지 않기").
//  - 상담 유형(정기 · 방문 등): 회차에 없다. 제목(title)이나 장소(location)로 짐작하지 않는다.
//  - 신호 채택 · 보류 수, '질문 처리' 단계: Backend 에 없다(팀 결정 전).

import { CONSULTATION_TYPE_LABELS, type ConsultationType, type Session, type SessionStatus } from "../api/types";
import { NOT_PROVIDED } from "./caseRows";
import { toDateOnly, toDateTime } from "./time";

export const SESSION_STATUS_LABELS: Record<SessionStatus, string> = {
  CREATED: "음성 업로드 대기",
  AUDIO_UPLOADED: "원문 변환 대기",
  STT_PROCESSING: "원문 변환 중",
  STT_REVIEW_REQUIRED: "원문 검수 필요",
  STT_CONFIRMED: "AI 분석 대기",
  AI_PROCESSING: "AI 분석 중",
  AI_REVIEW_REQUIRED: "AI 결과 검수 필요",
  APPROVED: "승인 완료",
  STT_FAILED: "원문 변환 실패",
  AI_FAILED: "AI 분석 실패",
};

/**
 * 회차 처리의 큰 단계. 회차 상태 하나가 단계 하나에 들어간다.
 * upload 음성 올리기 → stt 원문 변환 → sttReview 원문 검수 → analysis AI 분석 → summaryReview 요약 검수 · 승인 → done
 */
export type SessionStep = "upload" | "stt" | "sttReview" | "analysis" | "summaryReview" | "done";

/**
 * 그 단계 안에서 어디쯤인가.
 * waiting    사람이 다음 요청을 보낼 차례(음성 올리기 · 변환 요청 · 분석 요청)
 * processing 서버가 처리 중이다. 끝날 때까지 조회를 되풀이한다(API_CONTRACT 1.4)
 * review     사람이 검수할 차례. 자동으로 건너뛸 수 없다
 * failed     실패. 같은 요청을 다시 보내면 된다(재시도)
 * done       끝났다(승인 완료)
 */
export type StepPhase = "waiting" | "processing" | "review" | "failed" | "done";

export const SESSION_STEP_LABELS: Record<SessionStep, string> = {
  upload: "음성 올리기",
  stt: "원문 변환",
  sttReview: "원문 검수",
  analysis: "AI 분석",
  summaryReview: "요약 검수 · 승인",
  done: "완료",
};

const STEP_OF: Record<SessionStatus, [SessionStep, StepPhase]> = {
  CREATED: ["upload", "waiting"],
  AUDIO_UPLOADED: ["stt", "waiting"],
  STT_PROCESSING: ["stt", "processing"],
  STT_FAILED: ["stt", "failed"],
  STT_REVIEW_REQUIRED: ["sttReview", "review"],
  STT_CONFIRMED: ["analysis", "waiting"],
  AI_PROCESSING: ["analysis", "processing"],
  AI_FAILED: ["analysis", "failed"],
  AI_REVIEW_REQUIRED: ["summaryReview", "review"],
  APPROVED: ["done", "done"],
};

export function sessionStep(status: SessionStatus): { step: SessionStep; phase: StepPhase } {
  const [step, phase] = STEP_OF[status];

  return { step, phase };
}

/** 서버가 처리 중이라 조회를 되풀이해야 하는 상태. */
export function isProcessing(status: SessionStatus): boolean {
  return status === "STT_PROCESSING" || status === "AI_PROCESSING";
}

/** 음성을 (다시) 올릴 수 있는 상태. backend/app/core/state_machine.py 에서 AUDIO_UPLOADED 로 갈 수 있는 상태다. */
export function canUploadAudio(status: SessionStatus): boolean {
  return (
    status === "CREATED" ||
    status === "AUDIO_UPLOADED" ||
    status === "STT_FAILED" ||
    status === "STT_REVIEW_REQUIRED"
  );
}

/** 원문 변환을 요청할 수 있는 상태(처음 · 실패 뒤 재시도 · 검수 중 다시 변환). API_CONTRACT 7절. */
export function canRequestStt(status: SessionStatus): boolean {
  return status === "AUDIO_UPLOADED" || status === "STT_FAILED" || status === "STT_REVIEW_REQUIRED";
}

/** AI 분석을 요청할 수 있는 상태(첫 분석 · 실패 뒤 재시도 · 검수 중 재분석). API_CONTRACT 8절. */
export function canRequestAnalysis(status: SessionStatus): boolean {
  return status === "STT_CONFIRMED" || status === "AI_FAILED" || status === "AI_REVIEW_REQUIRED";
}

/** 회차 상태 갈래. 칩 색 등을 고를 때 쓴다(색만으로 상태를 나타내지 않도록 statusLabel 도 함께 보여 준다). */
export type SessionTone = "progress" | "action" | "failed" | "done";

function toneOf(phase: StepPhase): SessionTone {
  if (phase === "failed") return "failed";
  if (phase === "done") return "done";
  if (phase === "processing") return "progress";

  return "action";
}

export interface SessionRow {
  /** Backend 조회에 쓰는 UUID. */
  id: string;
  caseId: string;
  /** 사례 안의 회차 번호(1부터). */
  sessionNumber: number;
  /** "3회차". */
  numberLabel: string;
  /** 회차 제목. 없으면 NOT_PROVIDED. */
  title: string;
  status: SessionStatus;
  statusLabel: string;
  step: SessionStep;
  stepLabel: string;
  phase: StepPhase;
  tone: SessionTone;
  /** 상담 일시(YYYY-MM-DD HH:mm). 입력하지 않았으면 NOT_PROVIDED. 등록일(created_at)로 대신하지 않는다. */
  consultedAt: string;
  /** 상담 날짜(YYYY-MM-DD). 입력하지 않았으면 NOT_PROVIDED. */
  consultedDate: string;
  /** 장소. 없으면 NOT_PROVIDED. */
  location: string;
  /** 회차 메모. 없으면 빈 문자열. */
  memo: string;
  /** 상담 유형 코드 · 이름(2026-10-30). 없으면 null · NOT_PROVIDED. */
  consultationType: ConsultationType | null;
  kindLabel: string;
  /** 회차를 등록한 날짜(YYYY-MM-DD). */
  createdDate: string;
  /** 승인한 일시. 승인 전이면 NOT_PROVIDED. */
  approvedAt: string;
}

export function toSessionRow(source: Session): SessionRow {
  const { step, phase } = sessionStep(source.status);

  return {
    id: source.id,
    caseId: source.case_id,
    sessionNumber: source.session_number,
    numberLabel: `${source.session_number}회차`,
    title: source.title?.trim() || NOT_PROVIDED,
    status: source.status,
    statusLabel: SESSION_STATUS_LABELS[source.status],
    step,
    stepLabel: SESSION_STEP_LABELS[step],
    phase,
    tone: toneOf(phase),
    consultedAt: toDateTime(source.consulted_at) || NOT_PROVIDED,
    consultedDate: toDateOnly(source.consulted_at) || NOT_PROVIDED,
    location: source.location?.trim() || NOT_PROVIDED,
    memo: source.memo ?? "",
    consultationType: source.consultation_type ?? null,
    kindLabel: source.consultation_type ? CONSULTATION_TYPE_LABELS[source.consultation_type] : NOT_PROVIDED,
    createdDate: toDateOnly(source.created_at),
    approvedAt: toDateTime(source.approved_at) || NOT_PROVIDED,
  };
}
