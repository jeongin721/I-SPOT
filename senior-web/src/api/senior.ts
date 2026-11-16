// 고령자(온담 시니어) 전용 API — backend/docs/API_CONTRACT.md 27절. 사례 · 회차 · 녹음 · STT · 요약 · 일정 · 로그인은
// counselor-web 의 src/api(endpoints.ts)를 '@cw/api/endpoints' 로 그대로 쓴다(사례 목록만 subject_type: "SENIOR" 를 넘긴다).

import { api } from "@cw/api/client";

export type LivingArrangement = "ALONE" | "COUPLE" | "WITH_FAMILY" | "FACILITY" | "OTHER";
export type CareGrade =
  | "GRADE_1" | "GRADE_2" | "GRADE_3" | "GRADE_4" | "GRADE_5" | "COGNITIVE_SUPPORT" | "NONE" | "UNKNOWN";
export type CareNeed =
  | "MEAL" | "HOUSEWORK" | "MOBILITY" | "MEDICATION" | "HOSPITAL_ESCORT" | "EMOTIONAL" | "SAFETY_CHECK" | "OTHER";
export type CareStatus = "CONSULT_DONE" | "REVISIT_NEEDED" | "FOLLOWUP_IN_PROGRESS" | "SERVICE_ENDED";
export type CareDomain = "MEAL" | "SLEEP" | "OUTING" | "SOCIAL" | "MOOD";
export type DomainChange = "SIMILAR" | "CHANGED" | "NEW" | "NOT_MENTIONED";
export type Origin = "AI" | "RULE" | "COUNSELOR";
export type NextCheckKind = "CHECK" | "ACTION";
export type NextCheckStatus = "OPEN" | "DONE" | "DROPPED";
export type GlucoseTiming = "FASTING" | "POST_MEAL" | "RANDOM";

export const LIVING_LABELS: Record<LivingArrangement, string> = {
  ALONE: "독거", COUPLE: "부부 가구", WITH_FAMILY: "가족 동거", FACILITY: "시설", OTHER: "기타",
};
export const CARE_GRADE_LABELS: Record<CareGrade, string> = {
  GRADE_1: "장기요양 1등급", GRADE_2: "장기요양 2등급", GRADE_3: "장기요양 3등급", GRADE_4: "장기요양 4등급",
  GRADE_5: "장기요양 5등급", COGNITIVE_SUPPORT: "인지지원등급", NONE: "장기요양등급 없음", UNKNOWN: "등급 모름",
};
export const CARE_NEED_LABELS: Record<CareNeed, string> = {
  MEAL: "식사", HOUSEWORK: "가사", MOBILITY: "이동", MEDICATION: "복약 관리", HOSPITAL_ESCORT: "병원 동행",
  EMOTIONAL: "정서 지원", SAFETY_CHECK: "안부 확인", OTHER: "기타",
};
export const CARE_STATUS_LABELS: Record<CareStatus, string> = {
  CONSULT_DONE: "상담 완료", REVISIT_NEEDED: "재방문 필요", FOLLOWUP_IN_PROGRESS: "후속조치 진행", SERVICE_ENDED: "서비스 종료",
};
export const DOMAIN_LABELS: Record<CareDomain, string> = {
  MEAL: "식사", SLEEP: "수면", OUTING: "외출", SOCIAL: "사회활동", MOOD: "정서",
};
export const CHANGE_LABELS: Record<DomainChange, string> = {
  SIMILAR: "비슷함", CHANGED: "달라짐", NEW: "처음 기록", NOT_MENTIONED: "이야기 없음",
};

export interface SeniorProfile {
  case_id: string;
  living_arrangement: LivingArrangement | null;
  care_grade: CareGrade | null;
  health_notes: string | null;
  care_notes: string | null;
  takes_medication: boolean | null;
  medication_notes: string | null;
  care_needs: CareNeed[];
  care_needs_note: string | null;
  care_status: CareStatus | null;
  care_status_note: string | null;
  care_status_changed_at: string | null;
  updated_at: string | null;
}
export type SeniorProfileUpdate = Partial<Omit<SeniorProfile, "case_id" | "care_status" | "care_status_note" | "care_status_changed_at" | "updated_at">>;

export interface ExtraResult { kind: "COGNITIVE_SCREENING" | "OTHER"; name: string; value: number; max_value?: number | null; unit?: string | null }
export interface MeasurementValues {
  systolic?: number | null; diastolic?: number | null; pulse?: number | null; blood_glucose?: number | null;
  glucose_timing?: GlucoseTiming | null; weight_kg?: number | null; body_temp_c?: number | null;
  extra_results?: ExtraResult[] | null; note?: string | null;
}
export interface Measurement extends MeasurementValues {
  id: string; case_id: string; session_id: string | null; measured_at: string; extra_results: ExtraResult[];
  created_at: string; updated_at: string;
}
export interface TrendPoint { measurement_id: string; measured_at: string; value: number }
export interface MetricTrend {
  metric: string; label: string; unit: string; kind: string | null; max_value: number | null; count: number;
  latest: TrendPoint | null; previous: TrendPoint | null; change: number | null; min: number | null; max: number | null;
  points: TrendPoint[];
}
export interface HealthTrend {
  case_id: string; measurement_count: number; first_measured_at: string | null; last_measured_at: string | null; metrics: MetricTrend[];
}

export interface Basis { kind: "SEGMENT" | "MEASUREMENT" | "SESSION" | "PROFILE"; metric?: string | null; measurement_id?: string | null; session_number?: number | null; segment_ids?: string[] | null }
export interface NextCheck {
  id: string; case_id: string; source_session_id: string | null; kind: NextCheckKind; text: string; due_date: string | null;
  schedule_event_id: string | null; basis: Basis[]; origin: Origin; edited: boolean; status: NextCheckStatus;
  checked_session_id: string | null; checked_at: string | null; result_note: string | null; created_at: string; updated_at: string;
}
export interface NextCheckItemIn { kind?: NextCheckKind; text: string; due_date?: string | null; origin?: Origin; edited?: boolean; basis?: Basis[] }
export interface NextCheckUpdate {
  kind?: NextCheckKind; text?: string; due_date?: string | null; schedule_event_id?: string | null; status?: NextCheckStatus;
  checked_session_id?: string | null; result_note?: string | null;
}
export interface RecentDomainChange { domain: CareDomain; label: string; session_id: string; session_number: number; date: string; text: string | null; change_note: string | null }
export interface UpcomingVisit { schedule_event_id: string; date: string; time: string | null; consult_type: string | null; place: string | null }
export interface SeniorBrief {
  case_id: string; source: "RULE" | "AI"; model: string | null; summary: string; check_items: { text: string; basis: Basis[] }[];
  generated_at: string; care_status: CareStatus | null; open_checks: NextCheck[]; recent_changes: RecentDomainChange[];
  next_visit: UpcomingVisit | null;
}

export interface DomainNote {
  id: string; case_id: string; session_id: string; domain: CareDomain; text: string | null; change: DomainChange;
  change_note: string | null; segment_ids: string[]; origin: Origin; edited: boolean; compared_session_id: string | null; confirmed_at: string;
}
export interface DomainDraft { domain: CareDomain; text: string | null; change: DomainChange | null; change_note: string | null; segment_ids: string[]; source: "RULE" | "AI" }
export interface CareDomainRow {
  domain: CareDomain; label: string;
  previous: { session_id: string; session_number: number; date: string; text: string } | null;
  draft: DomainDraft | null; saved: DomainNote | null;
}
export interface SessionCareDomains { session_id: string; session_number: number; confirmed: boolean; domains: CareDomainRow[] }
export interface CareDomainItemIn { domain: CareDomain; change: DomainChange; text?: string | null; change_note?: string | null; segment_ids?: string[]; origin?: Origin; edited?: boolean }
export interface CareDomainTimeline {
  case_id: string;
  domains: { domain: CareDomain; label: string; entries: { session_id: string; session_number: number; date: string; text: string | null; change: DomainChange; change_note: string | null; segment_ids: string[] }[] }[];
}

export interface HistoryEntry {
  kind: "VISIT" | "MEASUREMENT"; at: string; session_id?: string | null; session_number?: number | null; session_title?: string | null;
  session_status?: string | null; summary?: { overview: string; key_points: string[]; status: string } | null;
  measurements: Measurement[]; checks_created?: NextCheck[]; checks_resolved?: NextCheck[]; care_domains?: DomainNote[];
}
export interface SeniorHistory { case_id: string; entries: HistoryEntry[]; open_checks: NextCheck[] }

export interface OverviewRow {
  case_id: string; alias: string; counselor_id: string | null; counselor_name: string | null; case_status: string;
  care_status: CareStatus | null; care_status_changed_at: string | null; last_visit_at: string | null; last_measured_at: string | null;
  measurement_stale: boolean; open_checks: number; overdue_checks: number; next_visit: UpcomingVisit | null;
}
export interface SeniorOverview {
  counts: {
    total: number; by_care_status: Record<CareStatus | "NONE", number>; open_checks: number; overdue_checks: number;
    visits_next_7_days: number; measurement_stale: number;
  };
  rows: OverviewRow[];
}

export interface FollowupVisitIn { consult_type: "VISIT" | "PHONE" | "REGULAR"; date: string; time?: string | null; place?: string | null; check_ids?: string[] }

const c = (caseId: string) => `/cases/${caseId}`;

export const senior = {
  profile: (caseId: string) => api.get<SeniorProfile>(`${c(caseId)}/senior-profile`),
  updateProfile: (caseId: string, body: SeniorProfileUpdate) => api.patch<SeniorProfile>(`${c(caseId)}/senior-profile`, body),
  setCareStatus: (caseId: string, status: CareStatus, note?: string | null) =>
    api.put<SeniorProfile>(`${c(caseId)}/care-status`, { status, note: note ?? null }),

  measurements: (caseId: string) => api.get<Measurement[]>(`${c(caseId)}/health-measurements`),
  addMeasurement: (caseId: string, body: MeasurementValues & { measured_at: string; session_id?: string | null }) =>
    api.post<Measurement>(`${c(caseId)}/health-measurements`, body),
  updateMeasurement: (caseId: string, id: string, body: MeasurementValues & { measured_at?: string; session_id?: string | null }) =>
    api.patch<Measurement>(`${c(caseId)}/health-measurements/${id}`, body),
  removeMeasurement: (caseId: string, id: string) => api.delete<void>(`${c(caseId)}/health-measurements/${id}`),
  trend: (caseId: string) => api.get<HealthTrend>(`${c(caseId)}/health-trend`),

  brief: (caseId: string) => api.post<SeniorBrief>(`${c(caseId)}/senior-brief`),

  nextChecks: (caseId: string, status?: NextCheckStatus) =>
    api.get<NextCheck[]>(`${c(caseId)}/next-checks`, status ? { status } : undefined),
  saveNextChecks: (caseId: string, items: NextCheckItemIn[], sourceSessionId?: string | null) =>
    api.post<NextCheck[]>(`${c(caseId)}/next-checks`, { source_session_id: sourceSessionId ?? null, items }),
  updateNextCheck: (caseId: string, id: string, body: NextCheckUpdate) => api.patch<NextCheck>(`${c(caseId)}/next-checks/${id}`, body),
  removeNextCheck: (caseId: string, id: string) => api.delete<void>(`${c(caseId)}/next-checks/${id}`),
  scheduleFollowup: (caseId: string, body: FollowupVisitIn) =>
    api.post<{ visit: UpcomingVisit; checks: NextCheck[] }>(`${c(caseId)}/followup-visits`, body),

  history: (caseId: string) => api.get<SeniorHistory>(`${c(caseId)}/senior-history`),
  domainTimeline: (caseId: string) => api.get<CareDomainTimeline>(`${c(caseId)}/care-domains`),
  sessionDomains: (sessionId: string) => api.get<SessionCareDomains>(`/sessions/${sessionId}/care-domains`),
  saveSessionDomains: (sessionId: string, items: CareDomainItemIn[]) =>
    api.put<SessionCareDomains>(`/sessions/${sessionId}/care-domains`, { items }),

  overview: () => api.get<SeniorOverview>("/senior-overview"),
};
