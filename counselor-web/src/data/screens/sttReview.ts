// 1 · STT 검수(SttReview) 화면 값. 원문은 useTranscriptReview 가 부르고 고치고 확정한다.
//
//  - 변환 중이면 진행 카드(단계 이름만. Backend 가 진행률 %를 주지 않는다), 끝나면 발화 줄을 보인다.
//  - 변환 전 · 실패면 진행 카드에서 변환 요청 · 다시 변환, 녹음이 없으면 녹취 올리기로 보낸다.
//  - 화자 · 문장을 고치면 '저장' 으로 바꾼 발화만 보낸다. '원문 확정 · 유형별 위험도 →' 는 저장하지 않은 수정을 먼저 저장하고
//    확정한 뒤 AI 분석을 요청하고 유형별 위험도 화면으로 간다(10/27 디자인에는 분석 요청 단계가 따로 없다).
//  - 줄별 '확인' 표시는 화면 상태다(서버에는 '원문 확정' 하나만 있다). 핵심 · 안전 발화 고르기는 팀 결정 전이라 없다.
//  - 화자는 Backend 5종(아동 · 상담원 · 보호자 · 기타 · 화자 미확인)만 쓴다. '사례관리대상자' 는 Backend 에 없다.
//
// 10/21 디자인(counselor-design/screens/SttReview.dc.html) 반영:
//  - 화자는 누를 때마다 바뀌던 것을 목록에서 고른다(연 목록은 화면 상태).
//  - 주소의 seg(발화 ID)가 가리키는 줄을 금색 테두리로 표시하고 그 줄로 한 번 스크롤한다(useSttFocus). 디자인은 브라우저
//    저장소(ispot-stt)를 300ms 마다 읽고 시간('00:41')으로 줄을 찾지만, 앱은 주소 쿼리와 발화 ID 로 한다.
//  - 시간을 눌러 다시 듣기(서버에 녹음 재생 없음), 목소리 신호(서버에 구간별 값 없음), 관련 조문(팀 결정 전 보류)은 준비 중이다.
//  - 옮기지 않은 것: 디자인 범례 끝줄의 예시 표시, 화자 라벨 뒤 번호(그 화자의 몇 번째 발화인지 — 뜻이 팀 확인 전),
//    '핵심 발화' 보기(원문 확정 전 미리 분석하는 API 가 없음), 가짜 진행률 · 토스트.
//
// 10/27 디자인 반영: 단계 이름 '유형별 위험도'. 다음 단추가 원문 확정 + AI 분석 요청 + 이동을 한 번에 한다.
//  - 이미 확정했고 분석을 아직 요청하지 않았으면(STT_CONFIRMED) 요청하고 간다. 분석 중 · 끝남 · 실패면 그냥 간다
//    (실패한 분석을 저절로 다시 돌리지 않는다 — 다시 분석은 유형별 위험도 화면에서 상담원이 누른다).
//  - 분석 요청이 실패해도 원문 확정은 끝났으므로 유형별 위험도로 간다. 그 화면이 '분석 대기' 와 다시 요청 단추를 보인다.
//
// 10/22 디자인 반영:
//  - 아래쪽 '위험 신호' 구역(10/21 에 준비 중 안내로 옮겼던 것)을 뺐다.
//  - '전체 STT' 보기는 일정 높이 상자(.ln-box.scroll) 안에서 스크롤한다. '확인할 곳' 보기는 높이 제한 없이 늘어놓는다(디자인과 같다).
//  - 하단 고정 재생 바(player): 서버는 녹음 파일 · 재생 주소를 주지 않고 음성 정보(GET /sessions/{id}/audio, 길이 포함)만 준다.
//    그래서 5초 뒤로 · 재생/일시정지 · 정지 · 5초 앞으로 · 재생 위치는 꺼 두고 '준비 중' 이라고 쓴다(가짜 재생 없음).
//    재생 바 위 표시는 실제로 동작한다: 확인 안 한 저신뢰 · 화자 미확인 발화를 '시작 시각 ÷ 녹음 길이' 위치에 놓고,
//    누르면 '확인할 곳' 보기로 바꿔 그 줄로 스크롤하고 금색 테두리를 옮긴다(주소 seg 와 같은 방법, useSttFocus).
//    녹음 길이는 useSessionDetail 이 이미 부르는 음성 정보를 쓴다. 길이를 모르면 마지막 발화가 끝나는 시각으로 나누고,
//    둘 다 없으면 표시를 숨긴다.

import { NOT_PROVIDED } from "../caseRows";
import { formatClock } from "../time";
import type { SessionAnalysisState } from "../useSessionAnalysis";
import type { TranscriptReviewState } from "../useTranscriptReview";
import { SPEAKER_LABELS, SPEAKER_OPTIONS } from "../transcriptRows";
import { NOT_READY } from "./common";
import { type ScreenIds, screenHref, withBack } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";

export interface SttUiState {
  /** all 전체 STT · check 확인할 곳(저신뢰 · 화자 미확인)만. */
  view: "all" | "check";
  /** 줄별 '확인' 표시(화면 상태). '회차 ID:발화 ID' → true(발화 ID 는 회차마다 seg_001 부터라 회차 ID 를 붙인다). */
  ok: Record<string, boolean>;
  /** 화자 목록을 연 줄('회차 ID:발화 ID'). 닫혀 있으면 null. */
  spOpen: string | null;
  /** 재생 바 표시를 눌러 옮겨 간 줄. 없으면 null(주소의 seg 를 따른다). */
  jump: SttJump | null;
}

/** 재생 바 표시를 눌러 옮겨 간 줄. 그 회차이고 주소의 seg 가 누를 때와 같을 때만 주소의 seg 대신 쓴다. */
export interface SttJump {
  sessionId: string;
  segmentId: string;
  /** 누를 때 주소의 seg. 그사이 주소가 바뀌었으면(앞 · 뒤로 가기) 주소를 따른다. */
  from: string | null;
  /** 몇 번째 누름인가. 같은 표시를 다시 눌러도 다시 스크롤하게 useSttFocus 에 넘긴다. */
  n: number;
}

export const INITIAL_STT_STATE: SttUiState = { view: "all", ok: {}, spOpen: null, jump: null };

/** 가리킬 발화 ID 를 담는 주소 쿼리 이름(#/SttReview?case=…&session=…&seg=<발화 ID>). */
export const SEGMENT_PARAM = "seg";

/** 주소 쿼리에서 가리킬 발화 ID 를 읽는다. 없으면 null. 발화 ID 는 회차 안에서만 뜻이 있어 session 과 함께 쓴다. */
export function readFocusSegment(search: URLSearchParams | string): string | null {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;

  return params.get(SEGMENT_PARAM)?.trim() || null;
}

/** 그 회차 STT 검수에서 발화 하나를 가리키는 주소(근거 발화 링크). 회차 ID 가 없으면 발화를 붙이지 않는다. */
export function segmentHref(ids: Partial<ScreenIds>, segmentId: string): string {
  const href = screenHref("/SttReview", ids);

  if (!ids.sessionId || !segmentId) return href;

  return `${href}&${SEGMENT_PARAM}=${encodeURIComponent(segmentId)}`;
}

export interface SttScreenInput extends SessionScreenInput {
  review: TranscriptReviewState;
  /** 원문 확정 뒤 AI 분석을 요청한다. */
  analysis: Pick<SessionAnalysisState, "run" | "submitting">;
  /** 주소의 seg(발화 ID). 그 줄을 표시하고, '확인할 곳' 보기에서도 숨기지 않는다(재생 바 표시를 눌러 다른 줄로 옮기기 전까지). */
  focusSegment: string | null;
  state: SttUiState;
  setState: (patch: Partial<SttUiState>) => void;
}

export function sttReviewValues(input: SttScreenInput) {
  const { review, analysis, state, setState, go, focusSegment } = input;
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
        // 링크가 아니라 코드로 옮기므로 A.jsx 가 back 을 붙이지 못한다. 이 화면으로 돌아오게 직접 붙인다.
        action: () => go(withBack(screenHref("/UploadModal", ids), screenHref("/SttReview", ids))),
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
  // 표시할 줄: 재생 바 표시를 눌러 옮겨 간 줄(이 회차 · 누를 때와 같은 주소일 때), 아니면 주소의 seg 가 가리킨 줄.
  const jump =
    state.jump && state.jump.sessionId === ids.sessionId && state.jump.from === focusSegment ? state.jump : null;
  const focusId = jump ? jump.segmentId : focusSegment;
  // '확인할 곳' 보기에서 고친 줄은 그대로 둔다(고치면 저신뢰 표시가 꺼져 고치던 줄이 사라지지 않게). 표시할 줄도 둔다.
  const visible = review.rows.filter(
    (row) => !row.removed && (state.view === "all" || needsCheck(row) || row.dirty || row.segmentId === focusId),
  );
  // 저장 · 확정을 기다리는 동안에는 고치지 못하게 한다(보낸 내용 뒤에 친 글자가 저장되지 않고 사라지지 않게).
  const editable = review.canEdit && !review.submitting;
  const okKey = (segmentId: string) => `${ids.sessionId}:${segmentId}`;
  const unchecked = review.rows.filter((row) => !row.removed && needsCheck(row) && !state.ok[okKey(row.segmentId)]);
  const left = unchecked.length;

  const lines = visible.map((row) => {
    const key = okKey(row.segmentId);
    const done = Boolean(state.ok[key]);
    const check = needsCheck(row);
    // 고칠 수 없을 때(확정 뒤 다음 단계 · 저장 중)는 목록을 닫는다.
    const open = editable && state.spOpen === key;
    const focus = row.segmentId === focusId;
    let hint = "";

    if (done) hint = "확인했어요";
    else if (row.lowConfidence) hint = "저신뢰 · 다시 듣고 확인해 주세요";
    else if (row.speakerUnknown) hint = "화자 확인 필요";
    if (row.dirty) hint = hint ? `${hint} · 저장 전` : "저장 전";

    return {
      /** React 줄 키. 보기를 바꿔도 줄(입력칸 · 연 목록)이 다른 발화로 옮겨 가지 않게 발화 ID 로 둔다. */
      key: row.segmentId,
      t: row.startLabel,
      // 시간을 눌러 그 위치부터 다시 듣기: 서버가 녹음 파일 · 재생 주소를 주지 않아 꺼 둔다(준비 중).
      // 생기면 여기에 재생 함수를 넣고, 아래 재생 바(player)의 단추도 함께 켠다.
      play: null,
      playAria: `${row.startLabel}부터 듣기 · ${NOT_READY}`,
      focus,
      ring: focus ? "inset 0 0 0 2px #C2A36B" : "none",
      sp: row.speakerLabel,
      aria: `${row.startLabel} 발화 고치기`,
      spFw: row.speaker === "CHILD" ? 700 : 500,
      spFix: row.edited || row.dirty,
      canEdit: editable,
      spMenu: open,
      toggleSp: () => setState({ spOpen: open ? null : key }),
      /** 목록에서 Esc 를 누르면 닫는다. */
      spKey: (event: { key: string }) => {
        if (open && event.key === "Escape") setState({ spOpen: null });
      },
      // 원래 화자를 다시 고르면 고친 칸에서 빠진다(useTranscriptReview 가 저장된 값과 같은 칸을 뺀다).
      spOpts: SPEAKER_OPTIONS.map((speaker) => ({
        value: speaker,
        label: SPEAKER_LABELS[speaker],
        sel: speaker === row.speaker,
        cls: speaker === row.speaker ? "spopt on" : "spopt",
        pick: () => {
          review.editSpeaker(row.segmentId, speaker);
          setState({ spOpen: null });
        },
      })),
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
      ok: () => setState({ ok: { ...state.ok, [key]: !done } }),
    };
  });

  // 재생 바 위 표시(10/22 디자인): 확인 안 한 저신뢰 · 화자 미확인 발화의 시작 위치. 녹음 길이는 useSessionDetail 이
  // 이미 받은 음성 정보(GET /sessions/{id}/audio 의 duration_ms)다. 모르면 마지막 발화가 끝나는 시각으로 나누고,
  // 둘 다 없으면 표시를 숨긴다.
  const audioMs = input.detail.session?.audio?.durationMs ?? null;
  const lastEndMs = review.rows.reduce((max, row) => Math.max(max, row.endMs), 0);
  const spanMs = audioMs !== null && audioMs > 0 ? audioMs : lastEndMs > 0 ? lastEndMs : null;
  const sessionId = ids.sessionId;
  const marks =
    spanMs !== null && sessionId
      ? unchecked.map((row) => {
          const kind = row.lowConfidence ? "저신뢰 구간" : "화자 미확인";
          const ratio = Math.min(Math.max(row.startMs / spanMs, 0), 1);

          return {
            key: row.segmentId,
            left: `${(ratio * 100).toFixed(2)}%`,
            title: `${kind} ${row.startLabel}`,
            aria: `${kind} ${row.startLabel} 확인하기`,
            // 디자인처럼 '확인할 곳' 보기로 바꾸고 그 줄로 옮긴다(스크롤 · 금색 테두리는 주소 seg 와 같은 useSttFocus).
            go: () =>
              setState({
                view: "check",
                jump: { sessionId, segmentId: row.segmentId, from: focusSegment, n: (state.jump?.n ?? 0) + 1 },
              }),
          };
        })
      : [];
  const notReady = (name: string) => `${name} · ${NOT_READY}`;

  const confirmed = review.info?.confirmed ?? false;
  let chipText = left ? `확인할 곳 ${left}` : "모두 확인";
  if (review.counts.pending) chipText = `저장 안 한 수정 ${review.counts.pending}`;
  else if (confirmed) chipText = `원문 확정 · ${review.info?.confirmedAt}`;

  // 다음 단계: 확정할 수 있거나(검수 중) 확정 뒤 고친 칸이 있으면 '확정 · 신호 분석'(고친 칸을 저장하고 다시 확정),
  // 이미 확정했고 고친 칸이 없으면 그냥 이동.
  const mustConfirm = review.canConfirm || (review.canEdit && review.counts.pending > 0);
  const canGoOn = status !== null && status !== "STT_REVIEW_REQUIRED" && confirmed;
  const nextLabel = mustConfirm ? "원문 확정 · 유형별 위험도 →" : "유형별 위험도 →";

  return {
    ...header,
    analyzing: progress !== null,
    done: review.info !== null,
    progressChip: progress?.chip ?? "",
    stageLabel: progress?.stage ?? "",
    progressActionLabel: progress?.actionLabel ?? "",
    progressAction: progress?.action ?? null,
    lines,
    /** '전체 STT' 보기면 일정 높이 상자 안에서 스크롤한다. */
    boxCls: state.view === "all" ? "ln-box scroll" : "ln-box",
    /** 표시할 줄의 발화 ID 와 누른 횟수. 화면 파일이 useSttFocus 에 넘겨 그 줄로 스크롤한다. */
    focusId,
    focusRequest: jump?.n ?? 0,
    /** 재생 바 표시로 옮겨 간 줄을 잊는다. 주소의 seg · 회차가 바뀌면 화면이 부른다(앞뒤로 오가다 옛 표시가 살아나지 않게). */
    clearJump: () => {
      if (state.jump) setState({ jump: null });
    },
    // 하단 재생 바. 원문이 있을 때만 보인다. 재생 단추 · 재생 위치는 서버에 녹음 재생이 없어 꺼 둔다(ready: false).
    player:
      review.info === null
        ? null
        : {
            ready: false,
            note: `녹음 재생 ${NOT_READY}`,
            back: notReady("5초 뒤로"),
            play: notReady("재생"),
            stop: notReady("정지"),
            fwd: notReady("5초 앞으로"),
            seek: notReady("재생 위치"),
            cur: NOT_PROVIDED,
            dur: (audioMs !== null && audioMs > 0 && formatClock(audioMs)) || NOT_PROVIDED,
            marks,
            markLabel: marks.length ? `확인할 곳 ${marks.length}곳` : "",
          },
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
    // 범례(디자인의 STT 카드 아래). 서버에 없는 기능은 준비 중이라고만 쓴다(디자인 끝줄의 예시 표시는 옮기지 않음).
    playNote:
      `왼쪽 시간이나 아래 재생 바로 녹음을 다시 듣기는 ${NOT_READY}입니다. ` +
      "서버가 녹음 파일은 주지 않고 파일 정보(이름 · 크기 · 길이)만 줍니다.",
    cueNote: `${NOT_READY}입니다. 서버가 발화 구간별 목소리 값을 주지 않습니다.`,
    lawNote: `${NOT_READY}입니다. 발화별 관련 조문은 팀 결정 전입니다.`,
    error: review.error,
    canSave: review.canEdit && review.counts.pending > 0 && !review.submitting,
    // 저장 · 확정을 누르면 연 화자 목록을 닫는다(저장이 끝나 다시 고칠 수 있게 되어도 저절로 다시 열리지 않게).
    save: () => {
      setState({ spOpen: null });
      void review.save();
    },
    canNext: (mustConfirm || canGoOn) && !review.submitting && !analysis.submitting,
    nextLabel: review.submitting || analysis.submitting ? "처리 중…" : nextLabel,
    nextHint: mustConfirm ? "누르면 원문을 확정하고 AI 분석을 요청합니다." : "",
    next: async () => {
      setState({ spOpen: null });

      if (mustConfirm) {
        // 누를 때의 대상(표). 확정을 기다리는 사이 대상이 바뀌었으면(다른 회차 · 화면, 갔다 돌아옴, 다시 로그인)
        // 앞 회차의 다음 화면으로 끌고 가지 않는다.
        const ticket = review.capture();
        const ok = await review.confirm();

        if (!ok || !review.isCurrent(ticket)) return;

        await analysis.run();
        go(signalHref, () => review.isCurrent(ticket));
      } else if (canGoOn) {
        if (status === "STT_CONFIRMED") await analysis.run();

        go(signalHref);
      }
    },
    /** 저장하지 않은 수정이 있는가(useLeaveGuard 에 넘긴다). */
    unsaved: review.counts.pending > 0,
  };
}
