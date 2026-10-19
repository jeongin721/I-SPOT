// 사례 상세 훅(GET /cases/{id} + GET /cases/{id}/sessions). 사례 상세 · 회차 목록(상담 이력) 화면이 쓴다.
//
// 화면은 사례 ID(UUID, 목록의 CaseRow.id)만 넘기고 사례 정보 · 회차 줄 · 상태를 받아 그린다.
// 담당이 아닌 사례나 없는 사례는 Backend 가 403 · 404 로 거절하고, 그 문구를 error 로 준다.
//
// 회차는 최신(번호 큰 것)부터 한 번에 SESSION_PAGE_SIZE 개까지 받는다. sessionTotal 이 더 크면 오래된 회차가 잘린 것이다.
// Backend 는 회차 목록을 줄 때 멈춘 처리 중 회차를 실패로 먼저 마감한다(API_CONTRACT 1.4 · 5절).
//
// Backend 에 없는 값(실명 · 신고접수일 · 위험도 · 가족 · 서비스 계획 등)은 caseRows 처럼 NOT_PROVIDED 로 둔다.

import { cases } from "../api/endpoints";
import { GUARDIAN_LABELS, type CaseDetail } from "../api/types";
import { NOT_PROVIDED, toCaseRow, type CaseRow } from "./caseRows";
import { isProcessing, toSessionRow, type SessionRow } from "./sessionRows";
import { toDateOnly } from "./time";
import { usePolling, useRemote } from "./useRemote";

/** 한 번에 받는 최대 회차 수. Backend 상한(page_size ≤ 100)과 같다. */
export const SESSION_PAGE_SIZE = 100;

export interface CaseDetailView extends CaseRow {
  /** 사례 제목. */
  title: string;
  /** Backend 에 적힌 그대로(자유 문자열, 10자 이하). 없으면 NOT_PROVIDED. */
  genderLabel: string;
  /** 보호자 유형 한글 이름. OTHER 면 guardian_note 를 괄호로 붙인다. 없으면 NOT_PROVIDED. */
  guardianLabel: string;
  /** 사례 메모. 없으면 빈 문자열. */
  notes: string;
  /** 회차 수(Backend 가 센 값). */
  sessionCount: number;
  /** 사례를 등록한 날짜. 신고접수일이 아니다. */
  createdDate: string;
  /** 담당 상담사 이메일. 계정이 지워졌으면 NOT_PROVIDED. */
  counselorEmail: string;
  /** 초기면접(서식 4 ②)에서 고른 아동 특성 · 가정상황. 고르지 않았으면 빈 목록. */
  intakeChildTraits: string[];
  intakeFamilySituations: string[];
}

export function toCaseDetailView(source: CaseDetail): CaseDetailView {
  const guardian = source.guardian_type ? GUARDIAN_LABELS[source.guardian_type] : "";
  const guardianNote = source.guardian_note?.trim();

  return {
    ...toCaseRow(source),
    title: source.title,
    genderLabel: source.child_gender?.trim() || NOT_PROVIDED,
    guardianLabel: guardian ? (guardianNote ? `${guardian}(${guardianNote})` : guardian) : NOT_PROVIDED,
    notes: source.notes ?? "",
    sessionCount: source.session_count,
    createdDate: toDateOnly(source.created_at),
    counselorEmail: source.counselor?.email ?? NOT_PROVIDED,
    intakeChildTraits: source.intake_child_traits ?? [],
    intakeFamilySituations: source.intake_family_situations ?? [],
  };
}

export interface CaseDetailOptions {
  /** false 면 부르지 않는다(로그인 확인 전 등). 기본 true. */
  enabled?: boolean;
}

export interface CaseDetailState {
  caseInfo: CaseDetailView | null;
  /** 최신 회차부터. */
  sessions: SessionRow[];
  /** 전체 회차 수. 아직 모르면 null. sessions.length 보다 크면 오래된 회차가 잘렸다. */
  sessionTotal: number | null;
  /** 처리 중(원문 변환 · AI 분석)인 회차가 있는가. 있으면 이 훅이 끝날 때까지 조용히 다시 조회한다. */
  hasProcessing: boolean;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

interface CaseDetailData {
  caseInfo: CaseDetailView;
  sessions: SessionRow[];
  sessionTotal: number;
}

async function loadCaseDetail(caseId: string): Promise<CaseDetailData> {
  const [detail, sessionPage] = await Promise.all([
    cases.get(caseId),
    cases.listSessions(caseId, { page: 1, page_size: SESSION_PAGE_SIZE }),
  ]);

  return {
    caseInfo: toCaseDetailView(detail),
    sessions: sessionPage.items.map(toSessionRow),
    sessionTotal: sessionPage.meta.total,
  };
}

export function useCaseDetail(caseId: string | null | undefined, { enabled = true }: CaseDetailOptions = {}): CaseDetailState {
  // 401 · 403 PASSWORD_CHANGE_REQUIRED 는 client 가 이벤트로 알리고, 화면은 useAuthSession 상태로 움직인다.
  const remote = useRemote(
    enabled && caseId ? caseId : null,
    loadCaseDetail,
    "사례 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    // 이 사례에 회차가 생겼거나(업로드 창의 새 회차) 이 사례의 회차 상태가 바뀌었으면 다시 부른다.
    (change, current, data) =>
      change.caseId === current || Boolean(data?.sessions.some((row) => row.id === change.sessionId)),
  );
  const sessions = remote.data?.sessions ?? [];
  const hasProcessing = sessions.some((row) => isProcessing(row.status));

  // 처리 중인 회차가 있으면 끝날 때까지 조용히 다시 조회한다.
  usePolling(hasProcessing, remote.refresh, remote.settled);

  return {
    caseInfo: remote.data?.caseInfo ?? null,
    sessions,
    sessionTotal: remote.data?.sessionTotal ?? null,
    hasProcessing,
    loading: remote.loading,
    error: remote.error,
    reload: remote.reload,
  };
}
