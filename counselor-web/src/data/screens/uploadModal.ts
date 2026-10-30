// 녹취 · 자료 올리기(UploadModal) 화면 값. 사례 고르기 → 회차 고르기(새 회차 · 모든 회차, 녹취 있는 회차는 못 넘어감) → 파일 고르기 → 올리기.
//
// 올리기 · 원문 변환 · 끝날 때까지 기다리기는 useAudioUpload 가 한다. 실패하면 그 단계부터 다시 하고, 새 회차를
// 또 만들지 않는다. 끝나면 확인창에서 그 회차의 STT 검수(이동) · 회차 상세(나중에)로 간다.
//
// 화면 주소 ?case=…(&session=…) 로 열면 그 사례(회차)를 미리 고른 채 회차 단계부터 시작한다.
// ?back=… 이 있으면 닫기 · 취소 · 나중에가 그 화면으로 돌아간다(10/21 디자인, links.ts 의 readBackHref).
// 문서 파일(PDF · HWPX 등) 첨부는 Backend 에 없어 준비 중이다. 진행률(%)은 Backend 가 주지 않아 단계 이름으로 보인다.

import { NOT_PROVIDED } from "../caseRows";
import { AUDIO_ACCEPT, AUDIO_RULE_TEXT, checkAudioFile, readAudioDuration } from "../audioFile";
import type { AuthSession } from "../useAuthSession";
import type { AudioUploadState } from "../useAudioUpload";
import type { CaseDetailState } from "../useCaseDetail";
import type { CaseListState } from "../useCaseList";
import { type SessionRow, canUploadAudio } from "../sessionRows";
import { formatBytes, formatDuration } from "../time";
import { NOT_READY, sidebarValues } from "./common";
import { type ScreenIds, screenHref } from "./links";

/** 새 회차를 고른 값. */
export const NEW_SESSION = "new";

export interface UploadTarget {
  value: string;
  label: string;
  short: string;
  meta: string;
  /** 이 회차에 음성을 올릴 수 있는가(새 회차 · 음성을 처음 올리거나 다시 올릴 수 있는 회차). */
  uploadable: boolean;
}

/** 녹취가 이미 있는 회차를 골랐을 때 보이는 말(문서 첨부는 Backend 에 없다). */
export const HAS_AUDIO_NOTE = "녹취가 이미 있는 회차입니다. 추가 자료(문서) 올리기는 준비 중입니다.";

/**
 * 회차 목록(10/21 디자인): 맨 위가 새 회차(서버가 매길 번호 = 지금 가장 큰 회차 + 1), 그 아래 모든 회차를 최근 것부터.
 * 음성을 올릴 수 있는 회차는 CREATED · AUDIO_UPLOADED · STT_FAILED 다. 원문 검수 중 · 그 뒤 회차는 원문을 새로 만들게
 * 되므로 uploadable 이 false 다(녹취 올리기 창은 보이되 다음으로 못 가고, 사례 상세 '녹음하기' 창은 뺀다).
 */
export function uploadTargets(rows: SessionRow[]): UploadTarget[] {
  const sorted = [...rows].sort((a, b) => b.sessionNumber - a.sessionNumber);
  const nextNumber = (sorted[0]?.sessionNumber ?? 0) + 1;

  return [
    { value: NEW_SESSION, label: `새 회차 · ${nextNumber}회차`, short: `${nextNumber}회차 (새 회차)`, meta: "새로 등록", uploadable: true },
    ...sorted.map((row) => {
      const uploadable = canUploadAudio(row.status) && row.status !== "STT_REVIEW_REQUIRED";

      return {
        value: row.id,
        label: `${row.numberLabel} · ${row.consultedDate !== NOT_PROVIDED ? row.consultedDate : `${row.createdDate} 등록`}`,
        short: row.numberLabel,
        meta: row.status === "CREATED" ? "녹취 아직 없음" : uploadable ? row.statusLabel : "녹취 있음 · 추가 자료",
        uploadable,
      };
    }),
  ];
}

/** 화면이 들고 있는 상태(Logic.state). 사례 검색어 · 고른 사례는 훅에 넘겨야 해서 화면 함수의 useState 로 든다. */
export interface UploadUiState {
  step: 1 | 2 | 3;
  /** 고른 회차 ID 또는 NEW_SESSION. null 이면 아직 안 골랐다(주소의 회차 → 새 회차 순으로 고른 것으로 본다). */
  choice: string | null;
  file: File | null;
  fileError: string | null;
  /** 브라우저가 읽은 음성 길이. 못 읽으면 undefined(WAV 는 서버가 잰다). */
  durationMs: number | undefined;
  /** 길이를 읽는 중. */
  measuring: boolean;
  /** 확인창(진행 · 완료 · 실패)을 보이는가. */
  dialog: boolean;
  /** 파일 칸을 새로 그릴 때 바꾸는 값('빼기' 뒤 같은 파일을 다시 고를 수 있게). */
  fileKey: number;
}

export function initialUploadState(ids: ScreenIds): UploadUiState {
  return {
    step: ids.caseId ? 2 : 1,
    choice: ids.sessionId,
    file: null,
    fileError: null,
    durationMs: undefined,
    measuring: false,
    dialog: false,
    fileKey: 0,
  };
}

const radio = (on: boolean) => ({
  bd: on ? "#2B2A26" : "#E7E4DC",
  bg: on ? "#F1EADA" : "#FFFFFF",
  dot: on ? "#2B2A26" : "#DAD5C9",
  fill: on ? "#2B2A26" : "transparent",
});

export interface UploadScreenInput {
  session: AuthSession;
  ids: ScreenIds;
  /** 주소의 back(연 화면). 없으면 null. */
  back: string | null;
  list: CaseListState;
  search: string;
  setSearch: (value: string) => void;
  /** 고른 사례 ID. */
  caseId: string | null;
  setCaseId: (caseId: string) => void;
  caseDetail: CaseDetailState;
  upload: AudioUploadState;
  state: UploadUiState;
  /** Logic.setState. 함수를 넘기면 그때 상태로 바꿀 값을 만든다. */
  setState: (patch: Partial<UploadUiState> | ((current: UploadUiState) => Partial<UploadUiState>)) => void;
  go: (href: string) => void;
}

export function uploadModalValues(input: UploadScreenInput) {
  const { session, ids, back, list, search, setSearch, caseId, setCaseId, caseDetail, upload, state, setState, go } = input;

  const labels = ["사례 선택", "상담 회차", "파일 선택"];
  const steps = labels.map((label, i) => {
    const n = i + 1;
    const done = n < state.step;
    const cur = n === state.step;

    return {
      label,
      mark: done ? "✓" : String(n),
      bg: cur ? "#F1EADA" : "transparent",
      fg: cur || done ? "#2B2A26" : "#7A776F",
      fw: cur ? 700 : 400,
      dotBg: cur ? "#2B2A26" : done ? "#F2EFE8" : "#EAE7DF",
      dotFg: cur ? "#EADBB5" : done ? "#66625A" : "#7A776F",
    };
  });

  // 1단계: 사례
  const cases = list.rows.map((row) => ({
    name: row.alias,
    // 최근 상담일은 쓰지 않는다(목록의 last_session_at 은 상담일이 없으면 회차 등록일로 채워진다).
    meta: `${row.caseNumber} · ${row.birthYearLabel}`,
    ...radio(row.id === caseId),
    pick: () => setCaseId(row.id),
  }));
  let casesNote = "";
  if (list.loading) casesNote = "불러오는 중…";
  else if (list.error) casesNote = list.error;
  else if (cases.length === 0) casesNote = search.trim() ? "검색 결과가 없습니다." : "사례가 없습니다.";

  // 2단계: 회차(uploadTargets).
  const info = caseDetail.caseInfo;
  const options = uploadTargets(caseDetail.sessions);
  const choice = options.some((option) => option.value === state.choice) ? state.choice! : NEW_SESSION;
  const chosen = options.find((option) => option.value === choice)!;
  const sessions = options.map((option) => ({
    label: option.label,
    meta: option.meta,
    ...radio(option.value === choice),
    pick: () => setState({ choice: option.value }),
  }));
  let sessionsNote = "";
  if (caseDetail.loading) sessionsNote = "불러오는 중…";
  else if (caseDetail.error) sessionsNote = caseDetail.error;
  else if (!chosen.uploadable) sessionsNote = HAS_AUDIO_NOTE;

  const caseName = info ? `${info.alias} · ${info.caseNumber}` : "";

  // 3단계: 파일
  const pickFile = (event: { target: { files: FileList | null } }) => {
    const file = event.target.files?.[0] ?? null;

    if (!file) {
      setState({ file: null, fileError: null, durationMs: undefined, measuring: false });
      return;
    }

    setState({ file, fileError: checkAudioFile(file), durationMs: undefined, measuring: true });
    readAudioDuration(file).then((durationMs) => {
      // 그사이 다른 파일을 골랐으면 버린다.
      setState((current) => (current.file === file ? { durationMs, measuring: false } : {}));
    });
  };
  const file = state.file;
  const fileMeta = file
    ? `${state.measuring ? "길이 확인 중" : formatDuration(state.durationMs) || "길이 모름"} · ${formatBytes(file.size)}`
    : "";

  // 확인창
  const sessionIds = { caseId, sessionId: upload.sessionId };
  const laterHref =
    back ?? (upload.sessionId ? screenHref("/SessionDetail", sessionIds) : screenHref("/CaseDetail", { caseId }));
  const closeHref = back ?? (ids.caseId || caseId ? screenHref("/CaseDetail", { caseId: caseId ?? ids.caseId }) : "/Main");
  const fileName = file ? file.name : "";
  // 새 회차를 만든 뒤에는 서버가 매긴 회차 번호로 보인다.
  const target = caseDetail.sessions.find((row) => row.id === upload.sessionId);
  let dialogMark = "…";
  let dialogTitle = "올리는 중";
  let dialogText = `${caseName} · ${target ? target.numberLabel : chosen.short} · ${fileName}`;
  let dialogAsk = `${upload.phaseLabel}… 창을 닫아도 서버의 변환은 계속됩니다.`;
  let dialogActions: { label: string; href?: string; onClick?: () => void; primary?: boolean; disabled?: boolean }[] = [
    { label: "나중에", href: laterHref },
    { label: "이동", primary: true, disabled: true },
  ];

  if (upload.phase === "done") {
    dialogMark = "✓";
    dialogTitle = "업로드했어요";
    dialogAsk = "원문 변환 완료 · 검수 화면으로 이동할까요?";
    dialogActions = [
      { label: "나중에", href: laterHref },
      { label: "이동", href: screenHref("/SttReview", sessionIds), primary: true },
    ];
  } else if (upload.phase === "failed") {
    dialogMark = "!";
    dialogTitle = "올리지 못했어요";
    dialogAsk = upload.error ?? "처리하지 못했습니다.";
    dialogActions = [
      { label: "닫기", onClick: () => setState({ dialog: false }) },
      ...(upload.failedStep && upload.failedStep !== "file"
        ? [{ label: "다시 시도", onClick: () => void upload.retry(), primary: true }]
        : []),
    ];
  }

  const canNext =
    (state.step === 1 && caseId !== null) || (state.step === 2 && info !== null && !caseDetail.loading && chosen.uploadable);

  return {
    ...sidebarValues(session),
    steps,
    search: { value: search, onChange: (e: { target: { value: string } }) => setSearch(e.target.value) },
    cases,
    casesNote,
    sessions,
    sessionsNote,
    caseName,
    sesLabel: chosen.short,
    accept: AUDIO_ACCEPT,
    pickFile,
    fileKey: state.fileKey,
    clearFile: () =>
      setState({ file: null, fileError: null, durationMs: undefined, measuring: false, fileKey: state.fileKey + 1 }),
    hasFile: file !== null,
    fileName,
    fileMeta,
    fileError: state.fileError,
    audioRule: AUDIO_RULE_TEXT,
    docRule: NOT_READY,
    s1: state.step === 1,
    s2: state.step === 2,
    s3: state.step === 3,
    notFirst: state.step > 1,
    notLast: state.step < 3,
    canNext,
    closeHref,
    registerHref: "/CaseRegister",
    next: () => {
      if (canNext) setState({ step: Math.min(3, state.step + 1) as UploadUiState["step"] });
    },
    prev: () => setState({ step: Math.max(1, state.step - 1) as UploadUiState["step"] }),
    // 길이를 읽는 중에는 막는다(WAV 가 아니면 서버가 길이를 재지 않아 그대로 올리면 길이가 빠진다).
    canUpload: Boolean(caseId && file && chosen.uploadable && !state.fileError && !state.measuring && !upload.busy),
    upload: () => {
      if (!caseId || !file || !chosen.uploadable || state.fileError || state.measuring || upload.busy) return;
      setState({ dialog: true });
      void upload.start({
        caseId,
        sessionId: choice === NEW_SESSION ? null : choice,
        file,
        durationMs: state.durationMs,
      });
    },
    confirm: state.dialog,
    dialogMark,
    dialogTitle,
    dialogText,
    dialogAsk,
    dialogActions: dialogActions.map((action) => ({
      ...action,
      onClick: action.onClick ?? (action.href ? () => go(action.href!) : undefined),
    })),
  };
}
