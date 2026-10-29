// 회차 상세(SessionDetail) 화면 값과, 회차를 다루는 화면들이 함께 쓰는 위치 표시 · 머리.
//
// 회차 정보는 useSessionDetail, 사례 별칭 · 다른 회차 목록은 useCaseDetail(회차의 사례)로 그린다.
// 화면 주소에 session 만 있어도 된다. 사례는 회차 정보의 case_id 를 믿는다(주소의 case 와 다르면 회차 쪽을 쓴다).
//
// Backend 에 없는 값: 상담 유형(정기 · 방문) · 위험 신호 채택/보류 · 추가 확인 · 질문 → '—' · 준비 중.

import type { CaseDetailState } from "../useCaseDetail";
import type { AuthSession } from "../useAuthSession";
import type { SessionDetailState, SessionDetailView } from "../useSessionDetail";
import { NOT_PROVIDED } from "../caseRows";
import type { ScreenGo } from "./useScreenGo";
import { NOT_READY, TONE_CHIP, notice, screenNotice, sidebarValues, type ScreenNotice } from "./common";
import { CARD_OF, LOCKED_HINT } from "./flow";
import { type ScreenIds, screenHref } from "./links";

/** 회차 화면이 쓸 사례 ID. 회차 정보를 받았으면 그 사례, 아직이면 주소의 사례. */
export function sessionCaseId(ids: ScreenIds, detail: SessionDetailState): string | null {
  return detail.session?.caseId ?? ids.caseId;
}

/** 주소에 회차 ID 가 없을 때 안내. 사례를 알면 그 사례의 상담 이력으로 보낸다. */
export function missingSession(caseId: string | null): ScreenNotice {
  return notice("회차가 정해지지 않았습니다. 상담 이력에서 회차를 골라 주세요.", {
    href: caseId ? screenHref("/CaseHistory", { caseId }) : "/CaseList",
    hrefLabel: caseId ? "상담 이력으로" : "사례 관리로",
  });
}

export interface SessionScreenInput {
  session: AuthSession;
  ids: ScreenIds;
  detail: SessionDetailState;
  caseDetail: CaseDetailState;
  /**
   * 화면 이동. 요청 응답 뒤에 옮길 때는 요청할 때 잡은 표를 확인하는 함수를 함께 넘겨, 그사이 대상이 바뀌었으면
   * (다른 회차 · 화면, 갔다 돌아옴, 다시 로그인) 옮기지 않는다(useScreenGo). 화면 파일은 useScreenGo(useNavigate()) 로 만들어 넘긴다.
   */
  go: ScreenGo;
}

/** 회차 화면 공통: 위치 표시 링크 · 머리 · 안내. */
export function sessionHeaderValues({ session, ids, detail, caseDetail }: SessionScreenInput) {
  const sv = detail.session;
  const info = caseDetail.caseInfo;
  const caseId = sessionCaseId(ids, detail);
  const sessionIds = { caseId, sessionId: sv?.id ?? ids.sessionId };

  return {
    ...sidebarValues(session),
    notice: screenNotice({
      session,
      missing: ids.sessionId ? null : missingSession(caseId),
      loading: detail.loading,
      // 회차는 받았는데 사례(별칭 · 다른 회차 목록)만 실패해도 알린다.
      error: detail.error ?? caseDetail.error,
      retry: detail.error ? detail.reload : caseDetail.reload,
    }),
    caseLabel: info ? `${info.alias} ${info.caseNumber}` : "",
    caseHref: screenHref("/CaseDetail", { caseId }),
    historyHref: screenHref("/CaseHistory", { caseId }),
    sessionHref: screenHref("/SessionDetail", sessionIds),
    sessionLabel: sv ? sv.numberLabel : "",
    alias: info ? info.alias : "",
    /** 상담일 · 장소. 넣지 않았으면 '—'. 상담 유형은 Backend 에 없다. */
    sub: sv ? `상담일 ${sv.consultedDate} · 장소 ${sv.location}` : "",
    ids: sessionIds,
  };
}

function sttCard(sv: SessionDetailView): { st: string; preview: string } {
  const audio = sv.audio ? `${sv.audio.fileName} · ${sv.audio.durationLabel} · ${sv.audio.sizeLabel}` : "녹음 파일 없음";
  const failed = sv.step === "stt" && sv.phase === "failed";

  if (sv.step === "upload") return { st: "녹취 업로드 필요", preview: "녹음 파일을 올리면 원문으로 바꿉니다." };
  if (sv.step === "stt") {
    return {
      st: sv.statusLabel,
      preview: failed && sv.errorMessage ? `${audio} · ${sv.errorMessage}` : audio,
    };
  }
  if (sv.step === "sttReview") return { st: "검수 필요", preview: `${audio} · 원문을 확인하고 확정해 주세요.` };

  return { st: "검수 완료", preview: audio };
}

function analysisCard(sv: SessionDetailView): { st: string; preview: string } {
  // STT 검수의 '원문 확정 · 유형별 위험도 →' 가 원문 확정과 함께 AI 분석을 요청한다(10/27 디자인).
  if (CARD_OF[sv.step] === 0) return { st: "대기", preview: "원문을 확정하면 AI 분석이 시작됩니다." };
  if (sv.step === "analysis") {
    const failed = sv.phase === "failed" && sv.errorMessage ? ` · ${sv.errorMessage}` : "";

    return { st: sv.statusLabel, preview: `유형별 심각도 · 근거 발화 · 상담원 판단${failed}` };
  }

  return { st: "AI 분석 완료", preview: "유형별 심각도 · 근거 발화 · 상담원 판단" };
}

function noteCard(sv: SessionDetailView): { st: string; preview: string } {
  let preview = "AI 분석이 끝나면 요약 초안이 생깁니다.";

  if (sv.summaryApproved) preview = `요약 승인 · ${sv.approvedAt}`;
  else if (sv.hasSummary) preview = "AI 요약 초안이 있습니다. 검수하고 승인해 주세요.";

  if (sv.step === "summaryReview") return { st: "요약 검수 필요", preview };
  if (sv.step === "done") return { st: "승인 완료", preview };

  return { st: "대기", preview };
}

export function sessionDetailValues(input: SessionScreenInput) {
  const { detail, caseDetail, go } = input;
  const header = sessionHeaderValues(input);
  const sv = detail.session;

  // 같은 사례의 회차를 오래된 것부터. 누르면 그 회차 주소로 옮긴다.
  const picks = [...caseDetail.sessions].reverse().map((row) => {
    const on = sv !== null && row.id === sv.id;
    const href = screenHref("/SessionDetail", { caseId: row.caseId, sessionId: row.id });

    return {
      label: `${row.sessionNumber}회`,
      on: on ? "true" : "false",
      bg: on ? "#F1EADA" : "#FFFFFF",
      bd: on ? "#2B2A26" : "#E7E4DC",
      fg: "#2B2A26",
      fw: on ? 700 : 400,
      go: () => {
        if (!on) go(href);
      },
    };
  });

  let steps: Record<string, unknown>[] = [];

  if (sv) {
    const ids = header.ids;
    const current = CARD_OF[sv.step];
    const defs = [
      {
        href: screenHref(sv.step === "upload" ? "/UploadModal" : "/SttReview", ids),
        label: "STT 검수",
        ...sttCard(sv),
      },
      { href: screenHref("/SignalReview", ids), label: "유형별 위험도", ...analysisCard(sv) },
      { href: screenHref("/NoteWrite", ids), label: "요약 · 일지 작성", ...noteCard(sv) },
      // 회차 상태에 '질문 처리 완료' 단계가 없어 칸 상태는 늘 '확인 메모' 다. 화면은 AI 확인 메모(followup_check_points)를
      // 읽기 전용으로 보이고, 수정 · 추가 질문은 준비 중이다(followupQ.ts).
      {
        href: screenHref("/FollowupQ", ids),
        label: "추가 확인 · 질문",
        st: "확인 메모",
        preview: `AI 확인 메모를 봅니다. 수정 · 추가 질문은 ${NOT_READY}입니다.`,
      },
    ];
    const lastDone = current === -1 ? 2 : current - 1;
    // 누를 수 있는 마지막 칸: 끝난 칸 다음(지금 할 단계). 그 뒤 칸은 잠긴다 — 회차 처리 화면의 단계 표시(flow.ts processNav)와
    // 같은 규칙. 승인 완료(current -1)면 앞 세 칸이 끝났으니 '추가 확인 · 질문' 까지 누를 수 있다.
    const reach = lastDone + 1;

    steps = defs.map((d, i) => {
      const done = i <= lastDone;
      const cur = i === current;
      const locked = !done && i > reach;

      return {
        ...d,
        /** 누르면 갈 주소. 잠긴 칸은 null(링크를 그리지 않는다). */
        href: locked ? null : d.href,
        locked,
        title: locked ? LOCKED_HINT : undefined,
        stCls: done ? "chip c-ok" : cur ? TONE_CHIP[sv.tone] : "chip c-normal",
        mark: done ? "✓" : String(i + 1),
        nBg: done ? "#F2EFE8" : cur ? "#2B2A26" : "#EAE7DF",
        nFg: done ? "#66625A" : cur ? "#EADBB5" : "#7A776F",
        ring: cur ? "inset 0 0 0 2px #2B2A26" : "none",
        bg: "#FFFFFF",
      };
    });
  }

  const counselor = caseDetail.caseInfo?.counselorName ?? NOT_PROVIDED;

  return {
    ...header,
    picks,
    steps,
    cur: sv
      ? {
          no: sv.numberLabel,
          meta: `${header.sub} · 상담 유형 ${NOT_PROVIDED} · 녹음 ${sv.audio ? sv.audio.durationLabel : NOT_PROVIDED} · 담당 ${counselor}`,
          status: sv.statusLabel,
          st: TONE_CHIP[sv.tone],
        }
      : { no: "", meta: "", status: "", st: "" },
  };
}
