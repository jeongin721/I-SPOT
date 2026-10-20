// 사례 상세 훅(GET /cases/{id} + GET /cases/{id}/sessions). 사례 상세 · 회차 목록(상담 이력) 화면이 쓴다.
//
// 화면은 사례 ID(UUID, 목록의 CaseRow.id)만 넘기고 사례 정보 · 회차 줄 · 상태를 받아 그린다.
// 담당이 아닌 사례나 없는 사례는 Backend 가 403 · 404 로 거절하고, 그 문구를 error 로 준다.
//
// 회차는 최신(번호 큰 것)부터 한 번에 SESSION_PAGE_SIZE 개까지 받는다. sessionTotal 이 더 크면 오래된 회차가 잘린 것이다.
// Backend 는 회차 목록을 줄 때 멈춘 처리 중 회차를 실패로 먼저 마감한다(API_CONTRACT 1.4 · 5절).
//
// Backend 에 없는 값(실명 · 신고접수일 · 위험도 · 가족 · 서비스 계획 등)은 caseRows 처럼 NOT_PROVIDED 로 둔다.
//
// 쓰기는 초기면접(서식 4 ②) 아동 특성 · 가정상황 고치기 하나다(saveIntake → PATCH /cases/{id}). 두 목록을 통째로 보낸다
// (비우면 [] — API_CONTRACT 'PATCH /cases/{id}'). 다른 쓰기 훅처럼 보낼 때 표(capture)를 잡고, 응답이 오면 그 표가 아직
// 지금 대상일 때만 반영한다(다른 사례로 옮김 · 다시 로그인 · 화면을 떠남이면 버린다).

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { cases } from "../api/endpoints";
import { GUARDIAN_LABELS, type CaseDetail } from "../api/types";
import { NOT_PROVIDED, toCaseRow, type CaseRow } from "./caseRows";
import { isProcessing, toSessionRow, type SessionRow } from "./sessionRows";
import { toDateOnly } from "./time";
import { errorMessage, usePolling, useRemote, type RemoteTicket } from "./useRemote";

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
  /** 초기면접 항목을 저장하는 중. */
  savingIntake: boolean;
  /** 초기면접 항목을 저장하지 못한 까닭. 다른 사례로 옮기거나 다시 로그인하면 지운다. */
  intakeError: string | null;
  /**
   * 초기면접 아동 특성 · 가정상황을 보낸 목록으로 바꾼다. 반영했으면 true.
   * 실패했거나, 이미 보내는 중이거나, 요청한 뒤 대상이 바뀌어(다른 사례, 다시 로그인, 화면을 떠남) 반영하지 못했으면 false.
   */
  saveIntake: (input: IntakeInput) => Promise<boolean>;
  /** 지금 대상의 표(useRemote). 화면이 고치던 값을 그 대상에 묶어 두는 데 쓴다. */
  capture: () => RemoteTicket | null;
  isCurrent: (ticket: RemoteTicket | null) => boolean;
}

export interface IntakeInput {
  childTraits: string[];
  familySituations: string[];
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

  const [savingIntake, setSavingIntake] = useState(false);
  // 보내는 중인가. state 는 같은 순간의 두 번째 누름을 막지 못해 ref 로도 든다.
  const inFlight = useRef(false);
  const [intakeError, setIntakeError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);
  // 응답을 반영할 때 볼 지금 값(saveIntake 를 만든 그리기 뒤에 다시 부른 값이 들어왔을 수 있어서 ref 로 든다).
  const latestData = useRef(remote.data);
  latestData.current = remote.data;

  // 대상 세대가 바뀌면(다른 사례, 로그아웃 · 다시 로그인, 다른 사례에 갔다 돌아옴) 앞 대상의 오류 · 진행 표시를 푼다
  // (앞 대상에 보낸 요청의 응답은 반영하지 않는다).
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    setIntakeError(null);
    inFlight.current = false;
    setSavingIntake(false);
  }

  const saveIntake = useCallback(
    async (input: IntakeInput): Promise<boolean> => {
      const ticket = remote.capture();

      if (!ticket || inFlight.current) return false;

      inFlight.current = true;
      setSavingIntake(true);
      setIntakeError(null);

      try {
        const saved = await cases.update(ticket.key, {
          intake_child_traits: input.childTraits,
          intake_family_situations: input.familySituations,
        });
        const held = latestData.current;

        // 들고 있는 사례 정보가 없으면 응답을 합칠 곳이 없다 — 다른 사례에 갔다 돌아와 · 다시 로그인해 첫 조회를 기다리는 중이거나,
        // 다시 불러오다 실패했다. 화면이 아직 이 사례를 보고 있으면(표가 지금 것이 아니어도) 지금 로그인으로 다시 조회해 저장한 값을
        // 받는다. 기다리던 첫 조회는 저장 전에 읽은 값일 수 있어서다(그 응답은 useRemote 가 버린다). 옛 응답 본문은 합치지 않는다.
        if (!held) {
          remote.resync(ticket);
          return false;
        }

        // 응답(Case)에는 담당자 · 회차 수가 없어 초기면접 두 칸만 바꿔 넣는다.
        return remote.setData(ticket, (current) => {
          const base = current ?? held;

          return {
            ...base,
            caseInfo: {
              ...base.caseInfo,
              intakeChildTraits: saved.intake_child_traits ?? [],
              intakeFamilySituations: saved.intake_family_situations ?? [],
            },
          };
        });
      } catch (caught) {
        // 대상이 바뀌었으면 오류 문구를 남기지 않는다(새 대상 화면에 앞 대상의 오류가 보이지 않게).
        if (!remote.isCurrent(ticket)) return false;

        if (!(caught instanceof ApiError && caught.isUnauthorized)) {
          setIntakeError(errorMessage(caught, "초기면접 항목을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }

        return false;
      } finally {
        // 대상 세대가 바뀌었으면 그때 이미 풀었다. 새 대상에서 보낸 요청의 표시를 끄지 않는다.
        if (remote.sameGeneration(ticket)) {
          inFlight.current = false;
          setSavingIntake(false);
        }
      }
    },
    [remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration, remote.resync],
  );

  return {
    caseInfo: remote.data?.caseInfo ?? null,
    sessions,
    sessionTotal: remote.data?.sessionTotal ?? null,
    hasProcessing,
    loading: remote.loading,
    error: remote.error,
    reload: remote.reload,
    savingIntake,
    intakeError,
    saveIntake,
    capture: remote.capture,
    isCurrent: remote.isCurrent,
  };
}
