// Backend endpoint 를 함수로 감싼 것. 쿼리 이름·응답 모양은 Backend OpenAPI(/openapi.json)와 같다.
// (음성 metadata 조회는 아직 쓰는 화면이 없어 감싸지 않았다.)
//
// 화면에서는 주소 문자열을 직접 쓰지 않고 이 함수들만 부른다.
// Backend 주소가 바뀌어도 고칠 곳이 여기 한 군데로 유지된다.

import { api, clearToken, setToken } from "./client";
import type {
  AnalysisEnvelope,
  AnalysisRequestResponse,
  AudioUploadResponse,
  Case,
  CaseCreateRequest,
  CaseDetail,
  CaseStatus,
  CaseUpdateRequest,
  Document,
  DocumentCreateRequest,
  DocumentUpdateRequest,
  LoginRequest,
  LoginResponse,
  PasswordChangeRequest,
  TemporaryPassword,
  UserCreateRequest,
  UserUpdateRequest,
  AuditLog,
  AuditStatus,
  Paged,
  STTRequestResponse,
  Session,
  SessionCreateRequest,
  SessionDetail,
  SessionStatus,
  Summary,
  SummaryEnvelope,
  SummaryUpdateRequest,
  TaskItem,
  TaskSummary,
  TaskType,
  Transcript,
  TranscriptEnvelope,
  TranscriptUpdateRequest,
  User,
} from "./types";

/**
 * 목록 조회 공통 쿼리. Backend 이름(page_size)을 그대로 쓴다. page 는 1 ~ 1,000,000, page_size 는 1 ~ 100.
 * 범위를 벗어나면 422 VALIDATION_ERROR 다(API_CONTRACT 1.1).
 * interface 가 아니라 type 으로 둔다 — client 의 query 인자(Record)에 그대로 넘기려면 필요하다.
 */
export type PageQuery = {
  page?: number;
  page_size?: number;
};

// =========================================================
// 인증
// =========================================================

export const auth = {
  /**
   * 로그인에 성공하면 토큰을 저장하고 사용자 정보를 돌려준다.
   *
   * 오류: 401 INVALID_CREDENTIALS(틀린 비밀번호·없는 계정·5회 실패 잠금이 모두 같은 응답·같은 문구),
   * 403 INACTIVE_USER · ACCOUNT_DORMANT · TEMP_PASSWORD_EXPIRED(비밀번호가 맞았을 때만).
   * 잠김은 응답으로 알려주지 않으므로 화면은 Backend 문구(`message`)를 그대로 보여준다.
   */
  async login(payload: LoginRequest): Promise<LoginResponse> {
    const result = await api.post<LoginResponse>("/auth/login", payload);

    setToken(result.access_token);

    return result;
  },

  /** 저장된 토큰으로 내 정보를 확인한다. 토큰이 만료됐으면 ApiError(401). */
  me(): Promise<User> {
    return api.get<User>("/auth/me");
  },

  logout(): void {
    clearToken();
  },

  /**
   * 본인 비밀번호 변경. 성공하면 응답 본문이 없다(204).
   *
   * 오류: 422 WEAK_PASSWORD(규칙 위반 — `details.reasons` 에 사유) · 422 SAME_PASSWORD(두 칸이 같음)는
   * 현재 비밀번호를 확인하기 전에 나간다. 400 INVALID_CURRENT_PASSWORD(현재 비밀번호 불일치 — 로그인 만료가
   * 아니므로 로그인 화면으로 보내지 않는다), 422 PASSWORD_REUSED(최근에 쓰던 비밀번호).
   * 현재 비밀번호를 정해진 횟수(LOGIN_MAX_FAILURES, 기본 5)만큼 틀리면 그 계정 토큰이 모두 끊기고 401 이다
   * (client 가 로그인 화면으로 보내고, 서버 문구를 로그인 화면에 보여 준다). 계정은 잠기지 않아 다시 로그인하면 된다.
   */
  changePassword(payload: PasswordChangeRequest): Promise<void> {
    return api.post<void>("/auth/me/password", payload);
  },

  /**
   * 관리자 전용 계정 생성(201). 비밀번호가 규칙에 맞지 않으면 422 WEAK_PASSWORD(`details.reasons`),
   * 같은 이메일이 있으면 409 DUPLICATE_RESOURCE. 첫 로그인 때 변경을 강제하려면 곧바로 resetPassword 를 부른다.
   */
  createUser(payload: UserCreateRequest): Promise<User> {
    return api.post<User>("/auth/users", payload);
  },

  /** 관리자 전용. 페이지 없이 전체 배열로 온다. */
  listUsers(): Promise<User[]> {
    return api.get<User[]>("/auth/users");
  },

  /**
   * 관리자 전용. 활성화·비활성화, 역할, 이름을 바꾼다.
   *
   * 마지막 활성 관리자를 비활성화하거나 역할을 내리면 409 VALIDATION_ERROR(details 없음)로 막힌다.
   * 역할·활성 상태를 바꾸면 그 계정의 Token 이 모두 무효가 된다.
   */
  updateUser(userId: string, payload: UserUpdateRequest): Promise<User> {
    return api.patch<User>(`/auth/users/${userId}`, payload);
  },

  /** 관리자 전용. 임시 비밀번호는 이 응답에서 한 번만 온다. */
  resetPassword(userId: string): Promise<TemporaryPassword> {
    return api.post<TemporaryPassword>(`/auth/users/${userId}/password-reset`, {});
  },

  /** 관리자 전용. 로그인 실패로 잠긴 계정을 푼다. */
  unlockUser(userId: string): Promise<void> {
    return api.post<void>(`/auth/users/${userId}/unlock`, {});
  },

  /** 관리자 전용. 휴면을 풀고 임시 비밀번호를 새로 발급한다. */
  reactivateUser(userId: string): Promise<TemporaryPassword> {
    return api.post<TemporaryPassword>(`/auth/users/${userId}/reactivate`, {});
  },

  /** 관리자 전용. 그 계정에 발급된 Token 을 전부 무효로 만든다. 자기 계정은 409 VALIDATION_ERROR. */
  logoutAll(userId: string): Promise<void> {
    return api.post<void>(`/auth/users/${userId}/logout-all`, {});
  },

  /** 관리자 전용. 접속 기록·보안 이벤트 화면이 쓰는 감사 로그. */
  auditLogs(
    params?: PageQuery & {
      action?: string;
      status?: AuditStatus;
      actor_id?: string;
      /**
       * UTC ISO 문자열(Date.toISOString()). 경계 포함. API_CONTRACT 1.5 · 3절.
       * datetime-local 입력값(표시 없는 지역 시각)을 그대로 보내면 UTC 로 읽혀 9시간 어긋난다.
       */
      since?: string;
      /** since 와 같은 형식. */
      until?: string;
    },
  ): Promise<Paged<AuditLog>> {
    return api.get<Paged<AuditLog>>("/auth/audit-logs", params);
  },
};

// =========================================================
// 사례
// =========================================================

export const cases = {
  /** search 는 제목·사례번호·아동 별칭에서 찾는다. */
  list(params?: PageQuery & { status?: CaseStatus; search?: string }): Promise<Paged<Case>> {
    return api.get<Paged<Case>>("/cases", params);
  },

  get(caseId: string): Promise<CaseDetail> {
    return api.get<CaseDetail>(`/cases/${caseId}`);
  },

  create(payload: CaseCreateRequest): Promise<Case> {
    return api.post<Case>("/cases", payload);
  },

  /** 바꿀 필드만 보낸다. status 로 종결, counselor_id 로 담당자 변경(관리자만). */
  update(caseId: string, payload: CaseUpdateRequest): Promise<Case> {
    return api.patch<Case>(`/cases/${caseId}`, payload);
  },

  remove(caseId: string): Promise<void> {
    return api.delete<void>(`/cases/${caseId}`);
  },

  listSessions(
    caseId: string,
    params?: PageQuery & { status?: SessionStatus },
  ): Promise<Paged<Session>> {
    return api.get<Paged<Session>>(`/cases/${caseId}/sessions`, params);
  },

  createSession(caseId: string, payload: SessionCreateRequest): Promise<Session> {
    return api.post<Session>(`/cases/${caseId}/sessions`, payload);
  },
};

// =========================================================
// 회차
// =========================================================

export const sessions = {
  /** 새로고침 후 화면 복원용. 진행 상황(has_audio 등)과 실패 정보(error)가 함께 온다. */
  get(sessionId: string): Promise<SessionDetail> {
    return api.get<SessionDetail>(`/sessions/${sessionId}`);
  },

  update(sessionId: string, payload: Partial<SessionCreateRequest>): Promise<Session> {
    return api.patch<Session>(`/sessions/${sessionId}`, payload);
  },

  remove(sessionId: string): Promise<void> {
    return api.delete<void>(`/sessions/${sessionId}`);
  },

  /** 상담 음성 업로드. 성공하면 회차 상태가 AUDIO_UPLOADED 가 된다. */
  uploadAudio(sessionId: string, file: File, durationMs?: number): Promise<AudioUploadResponse> {
    const form = new FormData();

    form.append("file", file);

    if (durationMs !== undefined) form.append("duration_ms", String(durationMs));

    return api.upload<AudioUploadResponse>(`/sessions/${sessionId}/audio`, form);
  },
};

// =========================================================
// 전사본
// =========================================================

export const transcript = {
  /**
   * STT 실행 요청. 202 로 즉시 돌아오고 처리는 뒤에서 진행된다.
   * 결과를 받으려면 get() 을 polling 해야 한다.
   */
  run(sessionId: string): Promise<STTRequestResponse> {
    return api.post<STTRequestResponse>(`/sessions/${sessionId}/transcript`);
  },

  /**
   * 전사본 조회.
   * STT 진행 중이면 transcript 가 null 이므로 session_status 로 판단한다.
   */
  get(sessionId: string): Promise<TranscriptEnvelope> {
    return api.get<TranscriptEnvelope>(`/sessions/${sessionId}/transcript`);
  },

  /**
   * 상담사 수정. 덮어쓰지 않고 새 version 이 만들어진다.
   * 바꾼 발화의 바꾼 필드만 보낸다. 전체 발화를 보내면 모두 "수정됨"으로 표시된다.
   * 다른 사람이 먼저 같은 version 을 수정했으면 409 DUPLICATE_RESOURCE — 새로고침 후 다시 수정한다.
   * 모든 발화 삭제는 409 VALIDATION_ERROR. 시각 역전(end_ms < start_ms)은 한 발화에 두 시각을 모두 보내 거꾸로면
   * 422 VALIDATION_ERROR(details.fields), 한쪽만 보내 저장된 값과 합친 결과가 거꾸로면 409 VALIDATION_ERROR.
   */
  update(sessionId: string, payload: TranscriptUpdateRequest): Promise<Transcript> {
    return api.patch<Transcript>(`/sessions/${sessionId}/transcript`, payload);
  },

  /** 검수 확정. 이 다음에야 AI 분석을 요청할 수 있다. */
  confirm(sessionId: string): Promise<Transcript> {
    return api.post<Transcript>(`/sessions/${sessionId}/transcript/confirm`);
  },
};

// =========================================================
// AI 분석
// =========================================================

export const analysis = {
  /**
   * 분석 실행 요청. 전사본이 확정된 상태여야 한다.
   * STT 와 마찬가지로 202 로 돌아오므로 get() 을 polling 한다.
   */
  run(sessionId: string): Promise<AnalysisRequestResponse> {
    return api.post<AnalysisRequestResponse>(`/sessions/${sessionId}/analysis`);
  },

  get(sessionId: string): Promise<AnalysisEnvelope> {
    return api.get<AnalysisEnvelope>(`/sessions/${sessionId}/analysis`);
  },
};

// =========================================================
// 요약 (검수 대상)
// =========================================================

export const summary = {
  /** 요약 조회. 근거 발화(summary_evidence)가 함께 온다. */
  get(sessionId: string): Promise<SummaryEnvelope> {
    return api.get<SummaryEnvelope>(`/sessions/${sessionId}/summary`);
  },

  update(sessionId: string, payload: SummaryUpdateRequest): Promise<Summary> {
    return api.patch<Summary>(`/sessions/${sessionId}/summary`, payload);
  },

  /** 승인. 회차가 APPROVED 로 넘어간다. */
  approve(sessionId: string): Promise<Summary> {
    return api.post<Summary>(`/sessions/${sessionId}/summary/approve`);
  },
};

// =========================================================
// 처리 대기 업무 (대시보드)
// =========================================================

export const tasks = {
  /**
   * 사람이 처리할 차례인 회차를 오래 기다린 순서로 가져온다.
   * 상담사는 담당 사례만 보인다. counselor_id 는 관리자만 쓸 수 있다(다른 사람 id 면 403).
   */
  list(
    params?: PageQuery & {
      task_type?: TaskType;
      overdue_only?: boolean;
      counselor_id?: string;
    },
  ): Promise<Paged<TaskItem>> {
    return api.get<Paged<TaskItem>>("/tasks", params);
  },

  /** 대시보드 숫자 (전체 · 지연 · 종류별). */
  summary(params?: { counselor_id?: string }): Promise<TaskSummary> {
    return api.get<TaskSummary>("/tasks/summary", params);
  },
};

// =========================================================
// 문서 (상담 기록)
// =========================================================

export const documents = {
  /** 회기의 문서 목록. 페이지 없이 전체 배열이 만든 순서(created_at 오름차순)로 온다. */
  list(sessionId: string): Promise<Document[]> {
    return api.get<Document[]>(`/sessions/${sessionId}/documents`);
  },

  /**
   * 새 문서. 항상 DRAFT 로 만들어진다(201). doc_type 을 빼면 CONSULTATION_RECORD.
   * 회기 상태와 상관없이 만들 수 있다.
   */
  create(sessionId: string, payload: DocumentCreateRequest): Promise<Document> {
    return api.post<Document>(`/sessions/${sessionId}/documents`, payload);
  },

  /**
   * 바꿀 필드만 보낸다. 아무것도 없으면 422 VALIDATION_ERROR.
   * 승인된 문서는 409 ALREADY_APPROVED, 다른 회기의 문서 id 면 404 DOCUMENT_NOT_FOUND.
   */
  update(sessionId: string, documentId: string, payload: DocumentUpdateRequest): Promise<Document> {
    return api.patch<Document>(`/sessions/${sessionId}/documents/${documentId}`, payload);
  },

  /** 승인. 이후에는 수정할 수 없다. 이미 승인됐으면 409 ALREADY_APPROVED. */
  approve(sessionId: string, documentId: string): Promise<Document> {
    return api.post<Document>(`/sessions/${sessionId}/documents/${documentId}/approve`);
  },
};
