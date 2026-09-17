// Backend endpoint 를 함수로 감싼 것. 쿼리 이름·응답 모양은 Backend OpenAPI(/openapi.json)와 같다.
// (문서 API · 계정 생성 · 음성 metadata 조회는 아직 쓰는 화면이 없어 감싸지 않았다.)
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
  LoginRequest,
  LoginResponse,
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
 * 목록 조회 공통 쿼리. Backend 이름(page_size)을 그대로 쓴다. page 는 1부터, page_size 는 최대 100.
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
  /** 로그인에 성공하면 토큰을 저장하고 사용자 정보를 돌려준다. */
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

  /** 관리자 전용. 페이지 없이 전체 배열로 온다. */
  listUsers(): Promise<User[]> {
    return api.get<User[]>("/auth/users");
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
