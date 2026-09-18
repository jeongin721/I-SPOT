// Backend Contract 의 TypeScript 표현.
//
// backend/app/schemas/ 및 backend/docs/API_CONTRACT.md 와 1:1 로 대응한다.
// Backend 가 필드를 바꾸면 여기도 함께 바꾼다. 화면에서 쓰는 형태로의 변환은
// adapters.ts 가 담당하고, 이 파일은 서버가 주는 그대로만 적는다.

// =========================================================
// 공통 응답 봉투
// =========================================================

/** 모든 성공 응답은 data 로 감싸진다. */
export interface DataResponse<T> {
  data: T;
}

/** 모든 실패 응답은 error 로 감싸진다. */
export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export interface PageMeta {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Paged<T> {
  items: T[];
  meta: PageMeta;
}

/**
 * 재시도 가능한 실패 정보.
 * 이 값이 있으면 화면에 재시도 버튼을 보여줄 수 있다.
 */
export interface SessionErrorInfo {
  code: string;
  message: string;
}

// =========================================================
// 열거형 — backend/app/core/enums.py
// =========================================================

export type UserRole = "COUNSELOR" | "ADMIN";

export type CaseStatus = "ACTIVE" | "CLOSED";

/**
 * 보호자 유형.
 * 목록에 없는 관계는 OTHER 로 두고 guardian_note 에 적는다.
 * Backend 는 보호자 실명을 저장하지 않는다(아동 실명과 같은 원칙).
 */
export type GuardianType =
  | "PARENTS"
  | "FATHER"
  | "MOTHER"
  | "GRANDPARENTS"
  | "RELATIVE"
  | "FOSTER"
  | "FACILITY"
  | "OTHER";

/** 화면에 표시할 한글 이름. */
export const GUARDIAN_LABELS: Record<GuardianType, string> = {
  PARENTS: "부모",
  FATHER: "부",
  MOTHER: "모",
  GRANDPARENTS: "조부모",
  RELATIVE: "친인척",
  FOSTER: "위탁",
  FACILITY: "시설",
  OTHER: "기타",
};

/** 회차 상태. Backend 가 전이 규칙을 강제하므로 임의로 바꾸지 않는다. */
export type SessionStatus =
  | "CREATED"
  | "AUDIO_UPLOADED"
  | "STT_PROCESSING"
  | "STT_REVIEW_REQUIRED"
  | "STT_CONFIRMED"
  | "AI_PROCESSING"
  | "AI_REVIEW_REQUIRED"
  | "APPROVED"
  | "STT_FAILED"
  | "AI_FAILED";

export type Speaker = "COUNSELOR" | "CHILD" | "GUARDIAN" | "OTHER" | "UNKNOWN";

export type AnalysisStatus = "PROCESSING" | "COMPLETED" | "FAILED";

export type ReviewStatus = "DRAFT" | "APPROVED";

// =========================================================
// 사용자 / 인증
// =========================================================

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

/**
 * 비밀번호 규칙 안내 문구. Backend `API_CONTRACT.md` 3절과 같은 내용이다.
 * 화면에서 따로 규칙을 적지 말고 이 값을 쓴다 — 두 곳에 적으면 어긋난다.
 *
 * 규칙 위반은 `422 WEAK_PASSWORD` 이고, 사유가 `details.reasons` 에 문장 배열로 온다.
 * 그 문장을 그대로 보여주면 된다.
 *
 * 주의: 숫자(12자·3종류)는 Backend 설정값이다. 기관 기준이 바뀌어 설정을 고치면
 * 이 문구도 같이 고쳐야 한다. 그때는 API_CONTRACT.md 3절의 표를 그대로 옮긴다.
 */
export const PASSWORD_RULE_TEXT =
  "12자 이상, 대문자·소문자·숫자·특수문자·한글 중 3종류 이상을 섞어 주세요. " +
  "20자 이상이면 섞지 않아도 됩니다. 이메일 아이디·이름과 흔한 단어는 쓸 수 없습니다.";

// =========================================================
// 사례
// =========================================================

export interface Case {
  id: string;
  case_number: string;
  title: string;
  /** 실명이 아닌 별칭. Backend 는 아동 실명을 저장하지 않는다. */
  child_alias: string;
  child_birth_year: number | null;
  child_gender: string | null;
  guardian_type: GuardianType | null;
  /** guardian_type 이 OTHER 일 때만 값이 있다. */
  guardian_note: string | null;
  status: CaseStatus;
  notes: string | null;
  counselor_id: string;
  /** 담당 상담사 이름. 계정이 삭제되었으면 null. */
  counselor_name: string | null;
  created_at: string;
  updated_at: string;
  /** 가장 최근 상담 일시. 회차가 없으면 null. */
  last_session_at: string | null;
}

/** 사례 상세(GET /cases/{id}). 목록 응답에는 없는 담당자 정보와 회차 수가 함께 온다. */
export interface CaseDetail extends Case {
  counselor: User | null;
  session_count: number;
}

export interface CaseCreateRequest {
  title: string;
  child_alias: string;
  child_birth_year?: number | null;
  child_gender?: string | null;
  guardian_type?: GuardianType | null;
  /** guardian_type 이 OTHER 일 때만 보낼 수 있다. 그 외에는 422. */
  guardian_note?: string | null;
  notes?: string | null;
  /** 담당 상담사. 보내지 않으면 요청자 본인. 다른 사람 지정은 관리자만 할 수 있다(403). */
  counselor_id?: string;
}

/**
 * 사례 수정 요청(PATCH /cases/{id}). 바꿀 필드만 보낸다.
 * title · child_alias · status 는 null 로 보낼 수 없다(422). 바꾸지 않으려면 빼고 보낸다.
 */
export interface CaseUpdateRequest {
  title?: string;
  child_alias?: string;
  child_birth_year?: number | null;
  child_gender?: string | null;
  /** OTHER 가 아닌 값(또는 null)으로 바꾸면 Backend 가 기존 guardian_note 를 지운다. */
  guardian_type?: GuardianType | null;
  /** 사례의 guardian_type 이 OTHER 일 때만 보낼 수 있다(함께 보내거나 이미 OTHER). 그 외에는 422. */
  guardian_note?: string | null;
  notes?: string | null;
  /** CLOSED 로 바꾸면 사례 종결. */
  status?: CaseStatus;
  /** 담당 상담사 변경. 관리자만 할 수 있다(403). */
  counselor_id?: string;
}

// =========================================================
// 회차
// =========================================================

export interface Session {
  id: string;
  case_id: string;
  session_number: number;
  title: string | null;
  status: SessionStatus;
  counselor_id: string;
  consulted_at: string | null;
  location: string | null;
  memo: string | null;
  created_at: string;
  updated_at: string;
  stt_started_at: string | null;
  stt_completed_at: string | null;
  ai_started_at: string | null;
  ai_completed_at: string | null;
  approved_at: string | null;
}

/** session_number 는 Backend 가 자동으로 매긴다. 요청으로 지정할 수 없다. */
export interface SessionCreateRequest {
  title?: string | null;
  consulted_at?: string | null;
  location?: string | null;
  memo?: string | null;
}

/**
 * 회차 상세. 새로고침 후 화면 상태를 복원할 때 쓴다(GET /sessions/{id}).
 * 처리 중에 서버가 재시작돼 멈춘 회차는 이 조회에서 STT_FAILED / AI_FAILED 로 바뀌고 error 가 채워진다.
 */
export interface SessionDetail extends Session {
  has_audio: boolean;
  has_transcript: boolean;
  transcript_version: number | null;
  transcript_confirmed: boolean;
  has_analysis: boolean;
  has_summary: boolean;
  summary_approved: boolean;
  error: SessionErrorInfo | null;
}

// =========================================================
// 음성
// =========================================================

export interface AudioFile {
  id: string;
  session_id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  duration_ms: number | null;
  checksum_sha256: string;
  created_at: string;
}

export interface AudioUploadResponse {
  audio: AudioFile;
  session_status: SessionStatus;
}

// =========================================================
// 전사본 (STT 결과)
// =========================================================

export interface TranscriptSegment {
  segment_id: string;
  speaker: Speaker;
  start_ms: number;
  end_ms: number;
  text: string;
  confidence: number;
}

export interface Transcript {
  id: string;
  session_id: string;
  version: number;
  schema_version: string;
  source: "STT" | "COUNSELOR_EDIT";
  is_confirmed: boolean;
  confirmed_at: string | null;
  stt_provider: string | null;
  stt_model: string | null;
  segments: TranscriptSegment[];
  /** 상담사가 수정한 발화의 segment_id. 검수 화면에서 표시에 쓴다. */
  edited_segment_ids: string[];
  created_at: string;
}

/**
 * 상담사가 고친 발화 하나. 바꾼 필드만 보낸다.
 * 보내지 않은 필드는 그대로 유지되고, 보낸 발화만 "수정됨"(edited_segment_ids)으로 표시된다.
 * confidence 는 STT 값이라 수정할 수 없다.
 */
export interface TranscriptSegmentUpdate {
  segment_id: string;
  speaker?: Speaker;
  text?: string;
  start_ms?: number;
  end_ms?: number;
}

/** 전사본 수정 요청(PATCH /sessions/{id}/transcript). 둘 중 하나는 있어야 한다. */
export interface TranscriptUpdateRequest {
  segments?: TranscriptSegmentUpdate[];
  removed_segment_ids?: string[];
}

/**
 * STT 실행 요청 결과. 202 로 돌아오며 처리는 아직 진행 중이다.
 * 완료 여부는 세션 상태를 polling 해서 판단한다.
 */
export interface STTRequestResponse {
  session_id: string;
  session_status: SessionStatus;
  message: string;
}

/**
 * 전사본 조회 응답.
 * STT 가 끝나지 않았으면 transcript 가 null 이고 session_status 로 판단한다.
 */
export interface TranscriptEnvelope {
  session_id: string;
  session_status: SessionStatus;
  transcript: Transcript | null;
  error: SessionErrorInfo | null;
}

// =========================================================
// AI 분석
// =========================================================

export interface RiskUtterance {
  segment_id: string;
  text: string;
  reason: string;
  severity?: string;
}

export interface AnalysisSummary {
  overview: string;
  /** 현재 Contract 는 문자열 배열이다. 근거 연결 구조로 바꾸려면 팀 협의가 필요하다. */
  key_points: string[];
}

export interface AnalysisResult {
  summary: AnalysisSummary;
  risk_utterances: RiskUtterance[];
  abuse_signals: string[];
  risk_factors: string[];
  warnings: string[];
}

/** AI 가 요약 항목과 근거 발화를 연결한 정보. */
export interface SummaryEvidenceItem {
  key_point: string;
  segment_ids: string[];
  score: number;
}

export interface AIAnalysis {
  id: string;
  session_id: string;
  transcript_id: string | null;
  transcript_version: number | null;
  status: AnalysisStatus;
  schema_version: string;
  provider: string | null;
  model: string | null;
  created_at: string;
  completed_at: string | null;
  result: AnalysisResult | null;
  summary_evidence: SummaryEvidenceItem[];
  error: SessionErrorInfo | null;
}

/** AI 분석 실행 요청 결과. 202 로 돌아오며 처리는 아직 진행 중이다. */
export interface AnalysisRequestResponse {
  session_id: string;
  session_status: SessionStatus;
  analysis_id: string;
  message: string;
}

export interface AnalysisEnvelope {
  session_id: string;
  session_status: SessionStatus;
  analysis: AIAnalysis | null;
  error: SessionErrorInfo | null;
}

// =========================================================
// 요약 (상담사 검수 대상)
// =========================================================

export interface Summary {
  id: string;
  session_id: string;
  analysis_id: string | null;
  overview: string;
  key_points: string[];
  counselor_note: string | null;
  status: ReviewStatus;
  is_edited: boolean;
  approved_at: string | null;
  approved_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SummaryUpdateRequest {
  overview?: string;
  key_points?: string[];
  counselor_note?: string;
}

export interface SummaryEnvelope {
  session_id: string;
  session_status: SessionStatus;
  summary: Summary | null;
  /**
   * 요약 항목별 근거 발화. 검수 화면에서 "왜 이렇게 요약됐는지" 표시에 쓴다.
   * 요약을 만든 분석 기준이라, 재분석이 실패하거나 도는 중이어도 사라지지 않는다.
   */
  summary_evidence: SummaryEvidenceItem[];
  error: SessionErrorInfo | null;
}
