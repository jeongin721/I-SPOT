// Backend 응답 → 화면이 쓰는 형태로 변환.
//
// 화면(data/cases.ts, data/mockData.ts)의 타입은 mock 데이터 기준으로 먼저 만들어졌고,
// Backend Contract 와 모양이 다르다. 컴포넌트를 전부 고치는 대신 여기서 변환해서
// 기존 화면 코드가 그대로 동작하게 한다.
//
// ⚠️ Backend 에 아직 없는 값은 아래 MISSING 목록에 정리해 두었다.
//    임시값으로 채우되, 무엇이 가짜인지 분명히 표시한다.

import type { CaseRecord, RiskLevel } from "../data/cases";
import type { Session as UiSession } from "../data/mockData";
import type { Case, Session, SessionStatus } from "./types";

// =========================================================
// Backend 가 아직 제공하지 않는 값
// =========================================================
//
//  화면 필드          | 상태
//  ------------------|---------------------------------------------------
//  guardian          | Backend Case 에 보호자 필드 없음
//  abuseTypes        | 사례 단위로는 없음. AI 분석 결과(abuse_signals)에 있음
//  riskLevel/Score   | 사례 단위로는 없음. 회차별 AI 분석에서 집계해야 함
//  keywords          | Backend 에 없음
//  sessionCount      | Case 응답에 없음. 회차 목록의 meta.total 로 얻는다
//
//  counselor(이름) 은 Backend 가 counselor_name 으로 내려주므로 해결되었다.
//
// 위 항목이 필요하면 Backend 에 필드 추가를 요청해야 한다.
// 지금은 화면이 깨지지 않도록 중립값을 넣는다.

/** Backend 가 값을 주지 않아 화면에서 임시로 채운 자리. */
export const NOT_PROVIDED = "—";

// =========================================================
// 사례
// =========================================================

function toAge(birthYear: number | null): number {
  if (!birthYear) return 0;

  return new Date().getFullYear() - birthYear;
}

function toDateOnly(iso: string | null): string {
  if (!iso) return "";

  return iso.slice(0, 10);
}

/** 사례 상태: Backend 는 ACTIVE/CLOSED 두 가지뿐이다. */
function toUiCaseStatus(status: Case["status"]): CaseRecord["status"] {
  return status === "CLOSED" ? "pending" : "active";
}

export interface CaseAdapterExtras {
  /** 회차 목록에서 얻은 총 회차 수. 없으면 0. */
  sessionCount?: number;
  /** Backend 의 counselor_name 을 덮어써야 할 때만 쓴다. */
  counselorName?: string;
  /** AI 분석에서 집계한 위험도. 없으면 표시하지 않는다. */
  riskLevel?: RiskLevel;
  riskScore?: number;
}

/**
 * Backend Case 를 화면의 CaseRecord 로 바꾼다.
 *
 * Backend 에 없는 값은 extras 로 채워 넣을 수 있고, 채우지 않으면 빈 값이 된다.
 * child_alias 는 실명이 아니라 별칭이다(Backend 는 아동 실명을 저장하지 않는다).
 */
export function toUiCase(source: Case, extras: CaseAdapterExtras = {}): CaseRecord {
  return {
    id: source.case_number,
    childName: source.child_alias,
    age: toAge(source.child_birth_year),
    guardian: NOT_PROVIDED,
    abuseTypes: [],
    riskLevel: extras.riskLevel ?? "low",
    riskScore: extras.riskScore ?? 0,
    lastSession: toDateOnly(source.last_session_at),
    sessionCount: extras.sessionCount ?? 0,
    counselor: extras.counselorName ?? source.counselor_name ?? NOT_PROVIDED,
    status: toUiCaseStatus(source.status),
    keywords: [],
  };
}

/** 화면에서 사례를 다시 조회할 때 필요한 실제 id(UUID)를 함께 들고 다니기 위한 형태. */
export interface CaseWithId extends CaseRecord {
  /** Backend 조회에 쓰는 UUID. 화면에 보이는 id(case_number)와 다르다. */
  backendId: string;
}

export function toUiCaseWithId(source: Case, extras: CaseAdapterExtras = {}): CaseWithId {
  return { ...toUiCase(source, extras), backendId: source.id };
}

// =========================================================
// 회차 상태
// =========================================================
//
// Backend 는 회차 상태를 하나로 관리하고, 화면은 STT/AI/기록 세 갈래로 나눠 보여준다.
// 하나의 Backend 상태에서 세 값을 유도한다.

type UiSttStatus = UiSession["sttStatus"];
type UiAiStatus = UiSession["aiStatus"];
type UiRecordStatus = UiSession["recordStatus"];

interface DerivedStatus {
  stt: UiSttStatus;
  ai: UiAiStatus;
  record: UiRecordStatus;
  /** 실패 상태인가. 화면 타입에는 실패 표현이 없어 별도로 알린다. */
  failed: boolean;
  /** 실패나 진행 상황을 사람에게 보여줄 문구. */
  label: string;
}

const STATUS_MAP: Record<SessionStatus, DerivedStatus> = {
  CREATED: {
    stt: "처리중", ai: "대기중", record: "미작성", failed: false, label: "음성 업로드 대기",
  },
  AUDIO_UPLOADED: {
    stt: "처리중", ai: "대기중", record: "미작성", failed: false, label: "STT 실행 대기",
  },
  STT_PROCESSING: {
    stt: "처리중", ai: "대기중", record: "미작성", failed: false, label: "받아쓰는 중",
  },
  STT_REVIEW_REQUIRED: {
    stt: "검수필요", ai: "대기중", record: "미작성", failed: false, label: "원문 검수 필요",
  },
  STT_CONFIRMED: {
    stt: "검수완료", ai: "대기중", record: "미작성", failed: false, label: "AI 분석 대기",
  },
  AI_PROCESSING: {
    stt: "검수완료", ai: "분석중", record: "미작성", failed: false, label: "AI 분석 중",
  },
  AI_REVIEW_REQUIRED: {
    stt: "검수완료", ai: "검토필요", record: "작성중", failed: false, label: "AI 결과 검수 필요",
  },
  APPROVED: {
    stt: "분석완료", ai: "승인완료", record: "승인완료", failed: false, label: "승인 완료",
  },
  STT_FAILED: {
    stt: "처리중", ai: "대기중", record: "미작성", failed: true, label: "STT 실패 — 재시도 필요",
  },
  AI_FAILED: {
    stt: "검수완료", ai: "대기중", record: "미작성", failed: true, label: "AI 분석 실패 — 재시도 필요",
  },
};

export function deriveStatus(status: SessionStatus): DerivedStatus {
  return STATUS_MAP[status];
}

/** 다음에 해야 할 행동. 버튼 활성화 판단에 쓴다. */
export function nextAction(status: SessionStatus): string {
  switch (status) {
    case "CREATED":
      return "음성 업로드";
    case "AUDIO_UPLOADED":
    case "STT_FAILED":
      return "STT 실행";
    case "STT_PROCESSING":
    case "AI_PROCESSING":
      return "처리 중";
    case "STT_REVIEW_REQUIRED":
      return "원문 검수";
    case "STT_CONFIRMED":
    case "AI_FAILED":
      return "AI 분석 실행";
    case "AI_REVIEW_REQUIRED":
      return "요약 검수";
    case "APPROVED":
      return "완료";
  }
}

// =========================================================
// 회차
// =========================================================

function toTimePart(iso: string | null): string {
  if (!iso) return "";

  return iso.slice(11, 16);
}

export interface SessionAdapterExtras {
  counselorName?: string;
  /** 상담 유형은 Backend 에 없다. 화면 기본값을 쓴다. */
  type?: UiSession["type"];
  durationLabel?: string;
}

/** Backend Session 을 화면의 Session 으로 바꾼다. */
export function toUiSession(
  source: Session,
  caseNumber: string,
  extras: SessionAdapterExtras = {},
): UiSession {
  const derived = deriveStatus(source.status);
  const at = source.consulted_at ?? source.created_at;

  return {
    id: source.id,
    caseId: caseNumber,
    date: toDateOnly(at),
    time: toTimePart(at),
    sessionNumber: source.session_number,
    counselor: extras.counselorName ?? NOT_PROVIDED,
    duration: extras.durationLabel ?? NOT_PROVIDED,
    type: extras.type ?? "정기상담",
    location: source.location ?? NOT_PROVIDED,
    sttStatus: derived.stt,
    aiStatus: derived.ai,
    recordStatus: derived.record,
  };
}
