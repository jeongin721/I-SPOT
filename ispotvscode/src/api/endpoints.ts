// Backend 의 29개 endpoint 를 함수로 감싼 것.
//
// 화면에서는 주소 문자열을 직접 쓰지 않고 이 함수들만 부른다.
// Backend 주소가 바뀌어도 고칠 곳이 여기 한 군데로 유지된다.

import { api, clearToken, setToken } from "./client";
import type {
  AIAnalysis,
  AudioUploadResponse,
  Case,
  CaseCreateRequest,
  LoginRequest,
  LoginResponse,
  Paged,
  Session,
  SessionCreateRequest,
  Summary,
  SummaryUpdateRequest,
  Transcript,
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
  /** STT 실행. 완료되면 회차가 STT_REVIEW_REQUIRED 가 된다. */
  run(sessionId: string): Promise<Transcript> {
    return api.post<Transcript>(`/sessions/${sessionId}/transcript`);
  },

  get(sessionId: string): Promise<Transcript> {
    return api.get<Transcript>(`/sessions/${sessionId}/transcript`);
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
  /** 분석 실행. 전사본이 확정된 상태여야 한다. */
  run(sessionId: string): Promise<AIAnalysis> {
    return api.post<AIAnalysis>(`/sessions/${sessionId}/analysis`);
  },

  get(sessionId: string): Promise<AIAnalysis> {
    return api.get<AIAnalysis>(`/sessions/${sessionId}/analysis`);
  },
};

// =========================================================
// 요약 (검수 대상)
// =========================================================

export const summary = {
  get(sessionId: string): Promise<Summary> {
    return api.get<Summary>(`/sessions/${sessionId}/summary`);
  },

  update(sessionId: string, payload: SummaryUpdateRequest): Promise<Summary> {
    return api.patch<Summary>(`/sessions/${sessionId}/summary`, payload);
  },

  /** 승인. 회차가 APPROVED 로 넘어간다. */
  approve(sessionId: string): Promise<Summary> {
    return api.post<Summary>(`/sessions/${sessionId}/summary/approve`);
  },
};
