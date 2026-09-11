// Backend 의 29개 endpoint 를 함수로 감싼 것.
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
  LoginRequest,
  LoginResponse,
  Paged,
  STTRequestResponse,
  Session,
  SessionCreateRequest,
  Summary,
  SummaryEnvelope,
  SummaryUpdateRequest,
  Transcript,
  TranscriptEnvelope,
  User,
} from "./types";

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

  /** 관리자 전용 */
  listUsers(): Promise<Paged<User>> {
    return api.get<Paged<User>>("/auth/users");
  },
};

// =========================================================
// 사례
// =========================================================

export const cases = {
  list(params?: { page?: number; size?: number; status?: string; q?: string }): Promise<Paged<Case>> {
    return api.get<Paged<Case>>("/cases", params);
  },

  get(caseId: string): Promise<Case> {
    return api.get<Case>(`/cases/${caseId}`);
  },

  create(payload: CaseCreateRequest): Promise<Case> {
    return api.post<Case>("/cases", payload);
  },

  update(caseId: string, payload: Partial<CaseCreateRequest>): Promise<Case> {
    return api.patch<Case>(`/cases/${caseId}`, payload);
  },

  remove(caseId: string): Promise<void> {
    return api.delete<void>(`/cases/${caseId}`);
  },

  listSessions(caseId: string, params?: { page?: number; size?: number }): Promise<Paged<Session>> {
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
  get(sessionId: string): Promise<Session> {
    return api.get<Session>(`/sessions/${sessionId}`);
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

  /** 상담사 수정. 덮어쓰지 않고 새 version 이 만들어진다. */
  update(sessionId: string, segments: Transcript["segments"]): Promise<Transcript> {
    return api.patch<Transcript>(`/sessions/${sessionId}/transcript`, { segments });
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
