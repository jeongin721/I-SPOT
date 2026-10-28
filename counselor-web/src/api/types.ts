// Backend Contract 의 TypeScript 표현.
//
// backend/app/schemas/ 및 backend/docs/API_CONTRACT.md 와 1:1 로 대응한다.
// Backend 가 필드를 바꾸면 여기도 함께 바꾼다. 화면에서 쓰는 형태로의 변환은
// src/data/ 의 변환 함수가 담당하고, 이 파일은 서버가 주는 그대로만 적는다.
// ispotvscode/src/api/types.ts 를 그대로 옮겨 왔다.

// =========================================================
// 공통 응답 봉투
// =========================================================

/** 모든 성공 응답은 data 로 감싸진다. */
export interface DataResponse<T> {
  data: T;
}

/**
 * 모든 실패 응답은 error 로 감싸진다. message 는 한국어라 그대로 보여 줄 수 있다
 * (없는 경로 404 · 허용되지 않는 method 405 · 해석할 수 없는 multipart 본문 400 처럼 서버 프레임워크가 만드는 오류도 같다).
 * JSON 문법 오류는 400 이 아니라 422 VALIDATION_ERROR 이고 details.fields 로 온다
 * (field 는 글자 위치, reason 은 "JSON decode error" — API_CONTRACT 1.2).
 * UTF-8 로 읽을 수 없는 바이트가 든 JSON 본문은 400 VALIDATION_ERROR(details 없음)다. 화면은 fetch 로
 * JSON.stringify 한 문자열을 보내 늘 UTF-8 이므로 이 경우를 만나지 않는다.
 */
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
   * (must_change_password 면 GET /auth/me · POST /auth/me/password 외에는 403 PASSWORD_CHANGE_REQUIRED)
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

/**
 * 관리자 전용 계정 생성(POST /auth/users). password 를 그대로 쓰고 첫 로그인 때 변경을 강제하지 않는다.
 * 관리자 화면은 임의 비밀번호로 만든 뒤 곧바로 password-reset 으로 임시 비밀번호를 발급한다.
 */
export interface UserCreateRequest {
  email: string;
  password: string;
  name: string;
  role?: UserRole;
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
  /** 초기면접(서식 4 ②)에서 고른 아동 특성(서식 항목 이름). 없으면 빈 목록. */
  intake_child_traits: string[];
  /** 초기면접(서식 4 ②)에서 고른 가정상황(서식 항목 이름). 없으면 빈 목록. */
  intake_family_situations: string[];
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
  /** 서식 4 항목(intakeItems.ts)만 받는다. 그 밖은 422. 겹친 항목은 하나로 합쳐진다. */
  intake_child_traits?: string[];
  intake_family_situations?: string[];
  notes?: string | null;
  /**
   * 담당 상담사. 보내지 않으면 요청자 본인. 다른 사람 지정은 관리자만 할 수 있다(403).
   * 없는 계정은 404 USER_NOT_FOUND, 정지된 계정은 400 VALIDATION_ERROR(details 없이 message 만, API_CONTRACT 4절).
   */
  counselor_id?: string;
  /** 개별사건번호. 빼면 Backend 가 C-YYYY-NNNN 으로 만든다. 1~50자, 이미 있는 번호면 409 DUPLICATE_RESOURCE. */
  case_number?: string;
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
  /** 보내면 목록을 통째로 바꾼다. 비우려면 [](null 은 422). */
  intake_child_traits?: string[];
  intake_family_situations?: string[];
  notes?: string | null;
  /** CLOSED 로 바꾸면 사례 종결. */
  status?: CaseStatus;
  /**
   * 담당 상담사 변경. 관리자만 할 수 있다(403).
   * 없는 계정은 404 USER_NOT_FOUND, 정지된 계정은 400 VALIDATION_ERROR(details 없이 message 만). 거절되면 바뀌지 않는다.
   */
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
// 구간별 음성 참고 표시 (stt/voice_marks, API_CONTRACT 16절)
// =========================================================

/** 분석 상태. "탐지 없음" 은 ANALYZED 이면서 모든 flag 가 false 인 경우이고, UNDETERMINED(분석하지 못함)와 다르다. */
export type VoiceMarkStatus = "ANALYZED" | "UNDETERMINED";

/** 지표 하나(떨림 cent · 웅얼거림 Hz · 작은 소리 LUFS). z 는 이 녹음 안의 아동 구간끼리 비교한 상대값. */
export interface VoiceMarkMetric {
  value: number | null;
  unit: string;
  z: number | null;
  flag: boolean | null;
}

export interface VoiceMarkSegment {
  segment_id: string;
  /** 분석 당시의 화자. 화면은 최신 원문의 화자를 쓰고 이 값은 참고만 한다. */
  speaker: Speaker | string;
  start_ms: number;
  end_ms: number;
  status: VoiceMarkStatus;
  /** UNDETERMINED 일 때 이유 코드(stt/voice_marks.md 5절). ANALYZED 면 null. */
  reason: string | null;
  tremor: VoiceMarkMetric | null;
  mumble: VoiceMarkMetric | null;
  soft: VoiceMarkMetric | null;
  /** 하나라도 표시면 true, 계산된 flag 가 모두 false 면 false, UNDETERMINED 면 null. */
  flag_any: boolean | null;
}

/** 분석 모듈이 돌려준 결과 그대로(`stt/voice_marks.md` 3절). Backend 는 안을 바꾸지 않는다. */
export interface VoiceMarksResult {
  schema_version: string;
  analyzer: string;
  analyzer_version: string | null;
  status: VoiceMarkStatus;
  reason: string | null;
  reference: {
    child_segments_total: number;
    child_segments_used: number;
    min_required: number | null;
    note: string;
  };
  /** 표시 기준값. 화면 코드에 숫자를 적지 않고 여기서 읽는다. Backend 실패 행은 null. */
  thresholds: {
    tremor_z_above: number | null;
    mumble_z_below: number | null;
    soft_z_below: number | null;
    basis: string;
  };
  segments: VoiceMarkSegment[];
}

/** GET /sessions/{id}/voice-marks 의 data. 아직 계산 전이면 data 자체가 null. */
export interface VoiceMarks {
  id: string;
  audio_file_id: string;
  transcript_id: string | null;
  /** 분석할 때 쓴 원문 판. 지금 보는 원문과 다르면 화면이 알린다. */
  transcript_version: number | null;
  extractor: string | null;
  schema_version: string;
  created_at: string;
  result: VoiceMarksResult;
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

/**
 * 전사본 수정 요청(PATCH /sessions/{id}/transcript). 둘 중 하나는 있어야 한다(없으면 422 VALIDATION_ERROR).
 * 모든 발화를 지우면 409 VALIDATION_ERROR(details 없음). 시각 역전(end_ms < start_ms)은 한 발화에 두 시각을 모두 보내
 * 거꾸로면 422 VALIDATION_ERROR(details.fields), 한쪽만 보내 저장된 값과 합친 결과가 거꾸로면 409 VALIDATION_ERROR
 * (details 없음). API_CONTRACT 7절.
 */
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
 * STT 가 발화를 하나도 찾지 못하면 실패(STT_FAILED, error.code STT_FAILED)로 끝나고 빈 전사본은 만들지 않는다.
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
 * 위험 관련 항목 하나(risk_factors 용). 구조가 보류된 필드라 키를 정하지 않는다.
 * Backend 는 위험 3필드의 항목 구조를 아직 검증하지 않으므로(API_CONTRACT 8절 "위험 3필드 항목 구조")
 * 화면은 키가 없을 수 있다고 보고 하나씩 확인하며 읽는다. 지금은 mock · pipeline · langgraph 모두 빈 배열이다.
 */
export type RiskItem = Record<string, unknown>;

/**
 * 위험 관련 발화 하나(PROPOSAL_risk_fields.md §7-0, 2026-10-22 확정). 판정이 아니라 '관련 신호' 다.
 * 서버는 근거 발화 번호(segment_ids)가 없거나 원문에 없는 항목을 저장 전에 뺀다(API_CONTRACT 8절).
 * 값은 영문 대문자이고 한글 이름은 화면에서만 바꾼다.
 */
export interface RiskUtterance {
  segment_ids: string[];
  text: string;
  /** PHYSICAL | EMOTIONAL | SEXUAL | NEGLECT */
  abuse_type: string;
  /** 2차 세부유형명(한글). 없으면 null. */
  subtype: string | null;
  /** 근거의 직접성. 확률이 아니다. */
  evidence_strength: "HIGH" | "MEDIUM" | "LOW";
  /** AI 가 그 강도로 본 이유 한 문장. */
  reason: string;
  /** 인용문이 원문과 맞는지 대조한 결과. */
  evidence_verified: boolean;
  /**
   * 관련 조문(2026-10-27). 그 유형을 직접 가리키는 금지행위 조문(아동복지법 제17조의 해당 호) 하나까지.
   * 법 위반을 확정하는 값이 아니라 참고 링크다. 이 필드가 생기기 전 결과 · 법령 데이터를 못 쓴 서버에서는 없거나 빈 배열이다.
   */
  legal_references?: LegalReference[];
}

export interface LegalReference {
  /** "아동복지법" */
  law_name: string;
  /** "제17조" */
  article: string;
  /** "제3호". 해당 호를 못 찾았으면 "". */
  item_label: string;
  /** 호의 본문(또는 조 제목). */
  text: string;
  /** 국가법령정보센터 조문 주소. 없으면 "". */
  portal_url: string;
}

/**
 * 학대 유형별 종합 신호(PROPOSAL_risk_fields.md §7-0). 네 유형이 모두 오고 detected 로 검출 여부를 적는다.
 * detected 는 모델 내부 값이므로 화면에는 "관련 신호" · "추가 확인 필요" 로만 표시한다(05_RULES).
 */
export interface AbuseSignal {
  /** PHYSICAL | EMOTIONAL | SEXUAL | NEGLECT */
  abuse_type: string;
  detected: boolean;
  /** MODEL(1차 모델 검출) · FILTERED(아동이 명확히 부정해 필터가 내림, detected=false) · null(둘 다 아님). LLM_SUPPLEMENTARY 는 예약. */
  detection_source: "MODEL" | "FILTERED" | "LLM_SUPPLEMENTARY" | null;
  /** FILTERED 일 때만 사유 문구. */
  filtered_reason: string | null;
  /** 같은 유형 risk_utterances 의 근거를 모은 것. 검출됐는데 비어 있으면 서버가 뺀다. */
  segment_ids: string[];
}

export interface AnalysisSummary {
  overview: string;
  /** 현재 Contract 는 문자열 배열이다. 근거 연결 구조로 바꾸려면 팀 협의가 필요하다. */
  key_points: string[];
  /** 사정 관점 4칸(2026-10-27). 이 필드가 생기기 전 서버 · 결과에는 없다. */
  assessment?: SummaryAssessment;
}

/**
 * 상담 요약 사정 관점 4칸의 키(API_CONTRACT 9절 "사정 관점 4칸", 2026-10-27).
 *  - safety_changes: (안전관련) 조사 후 변화된 사항
 *  - strengths_resources: 아동안전과 관련된 강점과 자원
 *  - safety_risks: 아동안전과 관련된 위험요인
 *  - desired_changes: 앞으로 원하는 변화 · 원하는 서비스/지원
 */
export type SummaryAssessmentKey = "safety_changes" | "strengths_resources" | "safety_risks" | "desired_changes";

/** 4칸 중 한 칸. segment_ids 는 AI 초안의 근거 발화이고 상담사가 문장을 고쳐도 그대로다. */
export interface SummaryAssessmentField {
  text: string;
  segment_ids: string[];
}

export type SummaryAssessment = Record<SummaryAssessmentKey, SummaryAssessmentField>;

// 아래 4개는 AI 분석 결과의 선택 필드다(API_CONTRACT 8절 "선택 필드", 10/16 추가).
// 서버는 값이 없으면 빈 배열로 준다. 모두 AI 제안이고 판단은 상담원이 한다.
// 근거 없는 항목을 서버가 빼지 않으므로 segment_ids 는 빈 배열일 수 있다. 근거 위치가 있으면 함께 보여 주고(README "지켜야 할
// 원칙" 3번), 빈 항목을 어떻게 보일지는 필드마다 정한다: severity_ratings 는 level · reason · matched_evidence 만 쓰고 근거 발화는
// 같은 유형 risk_utterances 로, followup_check_points 는 segment_ids 가 있으면 원문 위치로 · 없으면(옛 결과) "근거 위치 없음" 으로
// 보인다(10/26 · 10/27). protective_factors ·
// session_change_notes 는 아직 정하지 않았다(화면에 안 보임).

/** 학대 유형별 심각도 참고값. 판정이 아니다. */
export interface SeverityRating {
  /** 지금은 한글 유형명(예: "신체학대")이 그대로 온다. */
  major_type: string;
  /** 1~5 정수. 정보가 부족하면 null. */
  level: number | null;
  reason: string;
  /** AI 가 뽑은 발췌문. 원문과 글자가 다를 수 있어 근거 위치는 segment_ids 로 본다. */
  matched_evidence: string;
  segment_ids: string[];
  reviewed: boolean;
}

export interface ProtectiveFactor {
  category: string;
  text: string;
  segment_ids: string[];
}

/** 이전 회기와 달라진 점 메모. */
export interface SessionChangeNote {
  text: string;
  segment_ids: string[];
}

/**
 * 다음에 확인할 점에 대한 AI 확인 메모. 질문 은행의 질문이 아니다.
 * '추가 확인 · 질문' 화면의 '다음 상담 전 확인할 사항'(10/26 에는 유형별 위험도 카드)이 'AI 확인 메모 · 질문 아님' 으로
 * 읽기 전용 표시한다(2026-10-26 결정: 메모로만 보이면 원칙 7번(추가 질문은 질문 은행에서만)과 어긋나지 않는다).
 * 아이에게 할 질문으로 보여 주지 않는다. segment_ids 는 2026-10-27(#84)부터 modeling 이 채우고(근거 없는 메모는 모델이 뺌),
 * 그 전 결과는 빈 배열이다(API_CONTRACT 8절 선택 필드).
 */
export interface FollowupCheckPoint {
  text: string;
  segment_ids: string[];
}

export interface AnalysisResult {
  /** AI Output Contract 버전. 지금은 "1.0". */
  schema_version: string;
  summary: AnalysisSummary;
  risk_utterances: RiskUtterance[];
  abuse_signals: AbuseSignal[];
  /** 구조 보류. 지금은 늘 빈 배열이다. */
  risk_factors: RiskItem[];
  warnings: string[];
  severity_ratings: SeverityRating[];
  protective_factors: ProtectiveFactor[];
  session_change_notes: SessionChangeNote[];
  followup_check_points: FollowupCheckPoint[];
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
  /** 사정 관점 4칸. 이 필드가 생기기 전 서버(2026-10-27 이전 배포)에는 없다. */
  assessment?: SummaryAssessment;
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
  /** 고친 칸의 문장만 보낸다. 근거 번호는 서버가 그대로 둔다. */
  assessment?: Partial<Record<SummaryAssessmentKey, string>>;
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

/** 문서 상태. 요약과 같은 검수 상태를 쓴다. 항상 DRAFT 로 만들어지고, 승인되면 승인을 풀어야(reopen) 고칠 수 있다. */
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

// =========================================================
// 상담원 위험도 판단 — backend/app/schemas/risk_assessment.py (API_CONTRACT 11절)
// =========================================================

/** 학대 유형 대분류. 서버 값은 영문 대문자이고 한글 이름은 화면에서만 쓴다(ABUSE_TYPE_LABELS). */
export type AbuseType = "PHYSICAL" | "EMOTIONAL" | "SEXUAL" | "NEGLECT";

/** 서버가 목록을 주는 순서와 같다. */
export const ABUSE_TYPES: readonly AbuseType[] = ["PHYSICAL", "EMOTIONAL", "SEXUAL", "NEGLECT"];

export const ABUSE_TYPE_LABELS: Record<AbuseType, string> = {
  PHYSICAL: "신체학대",
  EMOTIONAL: "정서학대",
  SEXUAL: "성학대",
  NEGLECT: "방임",
};

/**
 * 상담원 위험도 판단(상 · 중 · 하). AI 심각도(1~5)와 척도가 다르고, 둘을 대응시키는 규칙은 팀 결정 전이다.
 * 화면에서 이 값을 '학대 확정' · '위험 확정' 으로 쓰지 않는다.
 */
export type RiskLevel = "HIGH" | "MEDIUM" | "LOW";

export const RISK_LEVELS: readonly RiskLevel[] = ["HIGH", "MEDIUM", "LOW"];

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  HIGH: "상",
  MEDIUM: "중",
  LOW: "하",
};

/**
 * 사례 단위 신호 이력(GET /cases/{id}/signal-history, API_CONTRACT 4절, 2026-10-28) — 한 회차 · 한 유형.
 * detected · ai_level 은 AI 제안이지 판정이 아니고, 위험도 표시는 counselor_level 만 쓴다(05_RULES §1).
 * 값 규칙은 회차 창구와 같다: detected 는 abuse_signals, ai_level 은 severity_ratings(11절 ai_level 규칙), 판단은 risk-assessments.
 */
export interface SignalHistoryType {
  abuse_type: AbuseType;
  detected: boolean | null;
  ai_level: number | null;
  counselor_level: RiskLevel | null;
  assessed_at: string | null;
}

/** 회차 한 줄. 분석이 끝나지 않았고 판단도 없으면 types 는 빈 배열(분석 전). */
export interface SignalHistorySession {
  session_id: string;
  session_number: number;
  consulted_at: string | null;
  status: SessionStatus;
  /** 가장 최근 분석 상태. 요청한 적 없으면 null. */
  analysis_status: AnalysisStatus | null;
  types: SignalHistoryType[];
}

/** session_number 오름차순, 분석 전 회차 포함 전부. */
export interface SignalHistory {
  case_id: string;
  sessions: SignalHistorySession[];
}

/** 한 회차 · 한 유형의 상담원 판단(RiskAssessmentResponse). */
export interface RiskAssessment {
  id: string;
  session_id: string;
  abuse_type: AbuseType;
  counselor_level: RiskLevel;
  /** 판단 이유. 적지 않았으면 null. */
  reason: string | null;
  /**
   * 판단을 저장할 때 그 회차 AI 분석 결과에 있던 같은 유형의 심각도(1~5). 서버가 채운다.
   * 분석이 없거나 · 실패했거나 · 그 유형 항목이 없거나 · 정보 부족이면 null.
   * 저장한 뒤 재분석해도 바뀌지 않는다(판단 당시 기록). 'AI 판정' 이 아니라 'AI 제안' 이다.
   */
  ai_level: number | null;
  /** 마지막으로 저장한 사람. 계정이 삭제되었으면 null. */
  assessed_by_id: string | null;
  assessed_at: string;
  created_at: string;
  updated_at: string;
}

/**
 * 판단 저장 · 수정 요청(PUT /sessions/{id}/risk-assessments/{abuse_type}). 판단 전체를 바꾼다.
 * reason 을 빼면 전에 적은 이유도 지워진다. ai_level 은 보내지 않는다(서버가 채운다).
 */
export interface RiskAssessmentSaveRequest {
  counselor_level: RiskLevel;
  /** 1000자 이하. 빼거나 null · 공백만이면 null 로 저장. */
  reason?: string | null;
}

/**
 * 법령 · 매뉴얼 AI 질문(POST /law-guide/questions, API_CONTRACT 17절, 2026-10-28). 질문 하나(앞뒤 공백 뺀 뒤 1~500자).
 * 답변은 참고용이고 판정이 아니다(05_RULES §1). 서버는 질문 · 답변을 저장하지 않는다.
 */
export interface LawGuideQuestionRequest {
  question: string;
}

/** 답변이 근거로 쓴 조문. 실제 조문 목록과 대조해 통과한 것만 온다. */
export interface LawSource {
  law_name: string;
  article: string;
  title: string;
  content: string;
  /** 조문시행일자("20261002" 꼴). 자료에 없으면 null. */
  effective_date: string | null;
  /** 국가법령정보센터 조문 주소. 없으면 null. */
  portal_url: string | null;
}

/** 답변이 근거로 쓴 매뉴얼 자료. 매뉴얼 사진은 기관 대외비라 기본으로 첨부하지 않으므로 보통 빈 배열이다. */
export interface ManualSource {
  id: string;
  title: string;
  /** 쪽수 문자열. 모르면 "?". */
  page: string;
}

export interface LawGuideAnswer {
  /** 끝에 모듈이 붙인 참고용 안내 문장이 있다. */
  answer: string;
  sources: { laws: LawSource[]; manual: ManualSource[] };
  /** 답한 모델 이름(mock 이면 "mock"). */
  model: string;
  answered_at: string;
}
