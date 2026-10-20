// 1 · STT 검수(SttReview) 화면 값. 원문은 useTranscriptReview 가 부르고 고치고 확정한다.
//
//  - 변환 중이면 진행 카드(단계 이름만. Backend 가 진행률 %를 주지 않는다), 끝나면 발화 줄을 보인다.
//  - 변환 전 · 실패면 진행 카드에서 변환 요청 · 다시 변환, 녹음이 없으면 녹취 올리기로 보낸다.
//  - 화자 · 문장을 고치면 '저장' 으로 바꾼 발화만 보낸다. '원문 확정 · 신호 분석' 은 저장하지 않은 수정을 먼저 저장하고
//    확정한 뒤 위험 신호 검토(AI 분석) 화면으로 간다.
//  - 줄별 '확인' 표시는 화면 상태다(서버에는 '원문 확정' 하나만 있다). 핵심 · 안전 발화 고르기는 팀 결정 전이라 없다.
//  - 화자는 Backend 5종(아동 · 상담원 · 보호자 · 기타 · 화자 미확인)만 쓴다. '사례관리대상자' 는 Backend 에 없다.

import type { TranscriptReviewState } from "../useTranscriptReview";
import { SPEAKER_OPTIONS } from "../transcriptRows";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";

export interface SttUiState {
  /** all 전체 STT · check 확인할 곳(저신뢰 · 화자 미확인)만. */
  view: "all" | "check";
  /** 줄별 '확인' 표시(화면 상태). '회차 ID:발화 ID' → true(발화 ID 는 회차마다 seg_001 부터라 회차 ID 를 붙인다). */
  ok: Record<string, boolean>;
}

export const INITIAL_STT_STATE: SttUiState = { view: "all", ok: {} };

export interface SttScreenInput extends SessionScreenInput {
  review: TranscriptReviewState;
  state: SttUiState;
  setState: (patch: Partial<SttUiState>) => void;
}

export function sttReviewValues(input: SttScreenInput) {
  const { review, state, setState, go } = input;
  const header = processHeaderValues(input, 0);
  const ids = header.ids;
  const status = review.sessionStatus;
  const signalHref = screenHref("/SignalReview", ids);

  // 진행 카드: 원문이 아직 없을 때(변환 전 · 변환 중 · 실패 · 녹음 없음).
  let progress: { chip: string; stage: string; actionLabel: string; action: (() => void) | null } | null = null;

  if (status === null && review.error) {
    // 원문 조회 자체가 실패했다(오류 문구는 카드 아래 error 로 보인다).
    progress = { chip: "불러오기 실패", stage: "", actionLabel: "다시 시도", action: review.reload };
  } else if (status !== null && !review.info) {
    if (status === "STT_PROCESSING") {
      progress = { chip: "변환 중", stage: "원문으로 바꾸는 중… 끝나면 이 화면이 저절로 바뀝니다.", actionLabel: "", action: null };
    } else if (status === "CREATED") {
      progress = {
        chip: "녹음 없음",
        stage: "녹음 파일을 먼저 올려 주세요.",
        actionLabel: "녹취 올리기",
        action: () => go(screenHref("/UploadModal", ids)),
      };
    } else {
      const failed = status === "STT_FAILED";

      progress = {
        chip: failed ? "변환 실패" : "변환 대기",
        stage: failed ? review.sessionError ?? "원문 변환에 실패했습니다." : "원문 변환을 요청해 주세요.",
        actionLabel: failed ? "다시 변환" : "원문 변환 요청",
        action: review.canRequestStt && !review.submitting ? () => void review.requestStt() : null,
      };
    }
  }

  const needsCheck = (row: { lowConfidence: boolean; speakerUnknown: boolean }) => row.lowConfidence || row.speakerUnknown;
  // '확인할 곳' 보기에서 고친 줄은 그대로 둔다(고치면 저신뢰 표시가 꺼져 고치던 줄이 사라지지 않게).
  const visible = review.rows.filter((row) => !row.removed && (state.view === "all" || needsCheck(row) || row.dirty));
  // 저장 · 확정을 기다리는 동안에는 고치지 못하게 한다(보낸 내용 뒤에 친 글자가 저장되지 않고 사라지지 않게).
  const editable = review.canEdit && !review.submitting;
  const okKey = (segmentId: string) => `${ids.sessionId}:${segmentId}`;
  const left = review.rows.filter((row) => !row.removed && needsCheck(row) && !state.ok[okKey(row.segmentId)]).length;

  const lines = visible.map((row) => {
    const done = Boolean(state.ok[okKey(row.segmentId)]);
    const check = needsCheck(row);
    const next = SPEAKER_OPTIONS[(SPEAKER_OPTIONS.indexOf(row.speaker) + 1) % SPEAKER_OPTIONS.length];
    let hint = "";

    if (done) hint = "확인했어요";
    else if (row.lowConfidence) hint = "저신뢰 · 다시 듣고 확인해 주세요";
    else if (row.speakerUnknown) hint = "화자 확인 필요";
    if (row.dirty) hint = hint ? `${hint} · 저장 전` : "저장 전";

    return {
      t: row.startLabel,
      sp: row.speakerLabel,
      aria: `${row.startLabel} 발화 고치기`,
      spFw: row.speaker === "CHILD" ? 700 : 500,
      spFix: row.edited || row.dirty,
      canEdit: editable,
      nextSp: () => review.editSpeaker(row.segmentId, next),
      onText: (event: { target: { value: string } }) => review.editText(row.segmentId, event.target.value),
      conf: row.confidenceLabel,
      edit: review.canEdit,
      read: !review.canEdit,
      text: row.text,
      check,
      hint,
      hintFg: "#7A776F",
      bg: check && !done ? "#F1E3BF" : "#FFFFFF",
      okLabel: done ? "확인됨 ✓" : "확인",
      ok: () => setState({ ok: { ...state.ok, [okKey(row.segmentId)]: !done } }),
    };
  });

  const confirmed = review.info?.confirmed ?? false;
  let chipText = left ? `확인할 곳 ${left}` : "모두 확인";
  if (review.counts.pending) chipText = `저장 안 한 수정 ${review.counts.pending}`;
  else if (confirmed) chipText = `원문 확정 · ${review.info?.confirmedAt}`;

  // 다음 단계: 확정할 수 있거나(검수 중) 확정 뒤 고친 칸이 있으면 '확정 · 신호 분석'(고친 칸을 저장하고 다시 확정),
  // 이미 확정했고 고친 칸이 없으면 그냥 이동.
  const mustConfirm = review.canConfirm || (review.canEdit && review.counts.pending > 0);
  const canGoOn = status !== null && status !== "STT_REVIEW_REQUIRED" && confirmed;
  const nextLabel = mustConfirm ? "원문 확정 · 신호 분석 →" : "신호 분석 →";

  return {
    ...header,
    analyzing: progress !== null,
    done: review.info !== null,
    progressChip: progress?.chip ?? "",
    stageLabel: progress?.stage ?? "",
    progressActionLabel: progress?.actionLabel ?? "",
    progressAction: progress?.action ?? null,
    lines,
    lowLeft: `${left}곳`,
    viewTitle: state.view === "all" ? "전체 STT" : "확인할 곳(저신뢰 · 화자 미확인)",
    chipText,
    chipCls: review.counts.pending || left ? "chip c-check" : "chip c-ok",
    allCls: state.view === "all" ? "btn-p" : "btn-s",
    lowCls: state.view === "check" ? "btn-p" : "btn-s",
    showAll: () => setState({ view: "all" }),
    showLow: () => setState({ view: state.view === "check" ? "all" : "check" }),
    versionLabel: review.info
      ? `원문 ${review.info.version}판 · 고친 발화 ${review.counts.edited} · 발화 ${review.counts.total}`
      : "",
    error: review.error,
    canSave: review.canEdit && review.counts.pending > 0 && !review.submitting,
    save: () => void review.save(),
    canNext: (mustConfirm || canGoOn) && !review.submitting,
    nextLabel: review.submitting ? "처리 중…" : nextLabel,
    next: async () => {
      if (mustConfirm) {
        // 누를 때의 대상(표). 확정을 기다리는 사이 대상이 바뀌었으면(다른 회차 · 화면, 갔다 돌아옴, 다시 로그인)
        // 앞 회차의 다음 화면으로 끌고 가지 않는다.
        const ticket = review.capture();
        const ok = await review.confirm();

        if (ok) go(signalHref, () => review.isCurrent(ticket));
      } else if (canGoOn) {
        go(signalHref);
      }
    },
    /** 저장하지 않은 수정이 있는가(useLeaveGuard 에 넘긴다). */
    unsaved: review.counts.pending > 0,
  };
}
