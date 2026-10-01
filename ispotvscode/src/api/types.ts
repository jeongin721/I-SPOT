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

  /**
   * 계정 상태. 넷은 뜻이 다르므로 화면에서 구분해 보여준다.
   * is_active=false 관리자 정지 / is_locked 로그인 실패 잠금 /
   * dormant_at 2개월 미접속 휴면 / must_change_password 임시 비밀번호
   *
   * 잠김 여부는 is_locked 로 본다. 기본 설정에서는 시간이 지나도 풀리지 않아 locked_until 이
   * 비어 있다. locked_until 은 시간 잠금(Backend LOGIN_LOCK_MINUTES > 0)일 때 풀리는 시각이다.
   */
  last_login_at?: string | null;
  must_change_password?: boolean;
  is_locked?: boolean;
  locked_until?: string | null;
  dormant_at?: string | null;
}

export interface UserUpdateRequest {
  is_active?: boolean;
  role?: UserRole;
  name?: string;
}

/** 임시 비밀번호는 이 응답에서 한 번만 온다. 다시 조회할 수 없다. */
export interface TemporaryPassword {
  temporary_password: string;
  expires_at: string;
  must_change_password: boolean;
}

export type AuditStatus = "SUCCESS" | "FAILURE";

/** 감사 로그. 상담 원문과 아동 실명은 담기지 않는다. */
export interface AuditLog {
  id: string;
  action: string;
  status: AuditStatus;
  error_code?: string | null;
  actor_id?: string | null;
  actor_name?: string | null;
  entity_type: string;
  entity_id?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  detail?: Record<string, unknown> | null;
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
 * 주의: 숫자(8자·3종류)는 Backend 설정값이다. 기관 기준이 바뀌어 설정을 고치면
 * 이 문구도 같이 고쳐야 한다. 그때는 API_CONTRACT.md 3절의 표를 그대로 옮긴다.
 * 긴 비밀번호 종류 면제(`PASSWORD_PASSPHRASE_LENGTH`)는 기본값이 꺼짐(0)이라 적지 않는다.
 */
export const PASSWORD_RULE_TEXT =
  "8자 이상이고 영문·숫자·특수문자를 모두 넣어 주세요(한글도 글자로 셉니다). " +
  "이메일 아이디·이름과 흔한 단어는 쓸 수 없습니다.";

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
  /**
   * STT 신뢰도(0~1). 0.0 은 공급자가 값을 주지 않았다는 뜻이다(ElevenLabs 는 모두 0.0).
   * 저신뢰 표시는 0 < confidence < 0.7 로 한다(API_CONTRACT.md 7절).
   */
  confidence: number;
}

/** 아동 발화 인계 보기의 발화 하나(child_handoff). */
export interface ChildHandoffSegment {
  segment_id: string;
  text: string;
  start_ms: number;
  end_ms: number;
}

/** 화자가 불확실해 사람이 확인해야 하는 발화. reason 은 지금 "UNRESOLVED_SPEAKER" 하나뿐이다. */
export interface ChildHandoffReviewSegment extends ChildHandoffSegment {
  reason: string;
}

/**
 * 전사본에 덧붙는 아동 발화 인계 보기(API_CONTRACT.md 7절).
 * segments 의 speaker 로 응답마다 다시 만든다. 분류 모델의 판단이 아니라 참고용이다.
 */
export interface ChildHandoff {
  /** 문장이 있는 CHILD 발화를 시간 순으로 공백 하나로 이은 것. 없으면 "". */
  child_analysis_text: string;
  /**
   * speaker 가 CHILD 인 발화. 시작 시각 순.
   * 문장이 있는 CHILD 발화가 하나도 없으면 빈 배열이다(문장이 빈 CHILD 발화만 있을 때 포함).
   */
  confirmed_child_segments: ChildHandoffSegment[];
  /** speaker 가 UNKNOWN 인 발화. 시작 시각 순. */
  review_needed_segments: ChildHandoffReviewSegment[];
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
  /** 아동 발화 인계 보기. Backend 가 STT 모듈(stt/)을 불러오지 못하는 배포에서는 null. */
  child_handoff: ChildHandoff | null;
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

/**
 * 위험 관련 항목(risk_utterances · abuse_signals · risk_factors) 하나.
 * 항목 구조는 팀 합의 전(PROPOSAL_risk_fields.md §7)이라 Backend 는 항목 구조를 검증하지 않는다
 * (langgraph 결과만 근거 발화가 없는 항목을 빼고 넘긴다. API_CONTRACT 8절).
 * 키가 없을 수 있다고 보고 하나씩 확인하며 읽는다. 지금은 mock · pipeline · langgraph 모두 빈 배열이다.
 */
export type RiskItem = Record<string, unknown>;

export interface AnalysisSummary {
  overview: string;
  /** 현재 Contract 는 문자열 배열이다. 근거 연결 구조로 바꾸려면 팀 협의가 필요하다. */
  key_points: string[];
}

export interface AnalysisResult {
  /** AI Output Contract 버전. 지금은 "1.0". */
  schema_version: string;
  summary: AnalysisSummary;
  risk_utterances: RiskItem[];
  abuse_signals: RiskItem[];
  risk_factors: RiskItem[];
  warnings: string[];
}

/**
 * AI 가 요약 항목과 근거 발화를 연결한 정보.
 * key_point 는 AI 원본 요약 문장이라 상담사가 고친 key_points 와 다를 수 있다.
 * 요약 문장과 문자열 일치로 연결하지 말고 segment_ids 로 근거 발화를 표시한다.
 */
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
   * summary.analysis_id(마지막으로 성공한 분석) 기준이라, 재분석이 실패하거나 도는 중이어도 사라지지 않는다.
   * 상담사가 고친 요약에서 재분석이 성공하면 요약 문장은 그대로, 근거는 새 분석 것이 된다.
   */
  summary_evidence: SummaryEvidenceItem[];
  error: SessionErrorInfo | null;
}

// =========================================================
// 처리 대기 업무 (대시보드)
// =========================================================

/** 사람이 처리할 차례인 업무 종류. 회차 상태 하나에 하나씩 대응한다. */
export type TaskType =
  | "UPLOAD_AUDIO"
  | "REQUEST_STT"
  | "REVIEW_TRANSCRIPT"
  | "REQUEST_ANALYSIS"
  | "REVIEW_ANALYSIS"
  | "RETRY_STT"
  | "RETRY_ANALYSIS";

/** 화면에 표시할 한글 이름. */
export const TASK_LABELS: Record<TaskType, string> = {
  UPLOAD_AUDIO: "녹음 업로드",
  REQUEST_STT: "원문 변환 요청",
  REVIEW_TRANSCRIPT: "원문 검수",
  REQUEST_ANALYSIS: "AI 분석 요청",
  REVIEW_ANALYSIS: "분석 결과 검토",
  RETRY_STT: "원문 변환 재시도",
  RETRY_ANALYSIS: "AI 분석 재시도",
};

/** 처리 대기 업무 하나. 오래 기다린 것부터 온다. */
export interface TaskItem {
  session_id: string;
  case_id: string;
  case_number: string;
  /** 실명이 아닌 별칭. */
  child_alias: string;
  session_number: number;
  session_title: string | null;
  session_status: SessionStatus;
  task_type: TaskType;
  /** 이 상태로 기다리기 시작한 시각(UTC, 항상 Z 로 끝남). */
  waiting_since: string;
  /**
   * 기다린 시간이 기준(기본 48시간)을 넘었는지.
   * 화면에는 "지연"으로 표시한다. 위험 신호와 헷갈리지 않게 "긴급"이라고 쓰지 않는다.
   */
  is_overdue: boolean;
  counselor_id: string;
  counselor_name: string | null;
  /** 재시도 업무에만 값이 있다. 메시지는 회차 상세(error)에서 본다. */
  last_error_code: string | null;
}

/** 대시보드 숫자. by_type 에는 업무 종류가 항상 모두 들어 있다(없으면 0). */
export interface TaskSummary {
  total: number;
  overdue: number;
  by_type: Record<TaskType, number>;
}

// =========================================================
// 문서 (상담 기록) — backend/app/schemas/document.py
// =========================================================

/**
 * 문서 유형. Backend 는 enum 이 아니라 50자 이하 자유 문자열로 받는다(검사하지 않는다).
 * 지금 정해진 값은 상담일지(CONSULTATION_RECORD) 하나다. 사정기록지 등 다른 유형은
 * 팀이 코드를 정한 뒤 여기에 상수로 적는다.
 */
export type DocumentType = string;

/** 상담일지. 생성 요청에서 doc_type 을 빼면 Backend 가 이 값으로 채운다. */
export const DOC_TYPE_CONSULTATION_RECORD: DocumentType = "CONSULTATION_RECORD";

/** 문서 상태. 요약과 같은 검수 상태를 쓴다. 항상 DRAFT 로 만들어지고, 승인되면 수정할 수 없다. */
export type DocumentStatus = ReviewStatus;

/**
 * 상담 기록 문서(DocumentResponse). 파일이 아니라 제목 · 본문 텍스트다.
 * 이름이 브라우저의 Document 타입과 같으니, 가져다 쓰는 파일에서는 필요하면 별칭으로 가져온다.
 */
export interface Document {
  id: string;
  session_id: string;
  doc_type: DocumentType;
  title: string;
  content: string;
  status: DocumentStatus;
  /** 만든 사람. 계정이 삭제되었으면 null. */
  created_by_id: string | null;
  approved_by_id: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

/** 문서 생성 요청(POST /sessions/{id}/documents). 201 로 DRAFT 문서가 돌아온다. */
export interface DocumentCreateRequest {
  /** 1~200자. */
  title: string;
  /** 50000자 이하. 빼면 빈 문자열. */
  content?: string;
  /** 50자 이하. 빼면 CONSULTATION_RECORD. */
  doc_type?: DocumentType;
}

/**
 * 문서 수정 요청(PATCH /sessions/{id}/documents/{document_id}). 바꿀 필드만 보낸다.
 * 둘 다 빼면(또는 null 이면) 422. 유형(doc_type)은 바꿀 수 없다. 승인된 문서는 409 ALREADY_APPROVED.
 */
export interface DocumentUpdateRequest {
  /** 1~200자. */
  title?: string;
  /** 50000자 이하. */
  content?: string;
}
