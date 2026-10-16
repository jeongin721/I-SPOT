// 3 · 상담 요약 · 상담 일지(NoteWrite) 화면 값.
//
// 상담 요약 카드 = useSummaryReview. AI 요약 초안(개요 · 핵심 내용) · 상담사 메모를 고치고 저장 · 승인한다.
//  - **요약 승인은 회차를 '승인 완료' 로 바꾼다**(그 뒤 요약을 고칠 수 없다). 그래서 '요약 승인' 단추를 따로 두고 한 번 더 묻는다.
//    아래 '저장 · 추가 확인 · 질문 →' 단추는 저장만 하고 승인하지 않는다(specs 대응표 '승인 시점').
//  - 근거 발화는 AI 원본 요약 문장별로 보인다(고친 요약 문장과 글자로 맞추지 않는다).
//  - 화면의 사정 관점 4영역(조사 후 변화 · 강점 · 위험요인 · 원하는 변화)은 Backend 요약에 없다. 개요 · 핵심 내용 · 메모로 보인다.
//
// 상담 일지 카드 = useSessionDocuments 의 상담일지(CONSULTATION_RECORD) 한 건. 문서는 제목 · 본문 텍스트뿐이라
// 화면의 칸(아동 진술 · 대상자 태도 · … · 소견)을 '[칸 이름]' 머리줄로 나눠 본문 하나에 담는다(formatNote · parseNote).
// 기관 양식별 구조는 팀 결정 전이라 이 형식은 임시다. 문서 승인은 회차 상태를 바꾸지 않는다(요약 승인과 따로).
//  - AI 일지 초안 · 아동 특성 · 가정상황 AI 제안은 Backend 에 없어 보이지 않는다(빈 칸에서 상담원이 쓴다).
//  - 아동 특성 · 가정상황: 사례의 초기면접(서식 4 ②)에서 고른 항목은 단어로만 보이고, 나머지 서식 4 항목을 체크리스트로 추가해 고른다.
//    본문 '[아동 특성]' · '[가정상황]' 에는 이 일지에서 추가로 고른 항목만 담는다(초기면접 항목은 사례에 속한다).
//    초기면접 내용은 서버에 저장하지 않아(팀 결정 전 · caseRegister.ts 머리말) 화면이 넘겨주지 않으면 '저장 전' 으로 보이고 전 항목을 고를 수 있다.
//  - 면접대상자/관계 · 상담 유형은 Backend 에 없어 '—'.

import { NOT_PROVIDED } from "../caseRows";
import type { DocumentRow, SessionDocumentsState } from "../useSessionDocuments";
import type { SummaryReviewState } from "../useSummaryReview";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS, type IntakeChecks } from "./intakeItems";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import type { SessionScreenInput } from "./sessionDetail";

export interface NoteDraft {
  statement: string;
  attitude: string;
  environment: string;
  traits: string[];
  homes: string[];
  signals: string;
  opinion: string;
}

type TextKey = "statement" | "attitude" | "environment" | "signals" | "opinion";
type ListKey = "traits" | "homes";

/** 본문에 쓰는 칸 순서와 머리줄 이름. */
const SECTIONS: { key: TextKey | ListKey; title: string }[] = [
  { key: "statement", title: "아동 진술" },
  { key: "attitude", title: "대상자 태도" },
  { key: "environment", title: "물리적 환경" },
  { key: "traits", title: "아동 특성" },
  { key: "homes", title: "가정상황" },
  { key: "signals", title: "위험 신호 검토 결과" },
  { key: "opinion", title: "상담원 소견 및 향후 계획" },
];

const LIST_KEYS = new Set<string>(["traits", "homes"]);

export const EMPTY_NOTE: NoteDraft = {
  statement: "",
  attitude: "",
  environment: "",
  traits: [],
  homes: [],
  signals: "",
  opinion: "",
};

/** 칸 머리줄로 읽히는 줄. 앞에 역슬래시가 붙은 것은 본문에 쓴 같은 모양의 글이다(escapeLine). */
const HEADING_LIKE = /^(\\*)\[(.+)\]$/;
const TITLES = new Set(SECTIONS.map((section) => section.title));

/**
 * 본문 줄이 칸 머리줄과 같은 모양이면 '[' 바로 앞(앞쪽 공백 뒤)에 역슬래시를 하나 붙인다(parseNote 가 하나 떼어 낸다).
 * 공백 앞에 붙이면 읽을 때 머리줄 모양으로 알아보지 못해 역슬래시가 남는다.
 */
function escapeLine(line: string): string {
  const match = HEADING_LIKE.exec(line.trim());

  return match && TITLES.has(match[2]) ? line.replace(/^(\s*)/, "$1\\") : line;
}

/** 칸 → 본문. 빈 칸은 쓰지 않는다. 고르기 칸은 ', ' 로 잇는다. */
export function formatNote(note: NoteDraft): string {
  return SECTIONS.map(({ key, title }) => {
    const value = note[key];
    const text = Array.isArray(value) ? value.join(", ") : value.trim().split("\n").map(escapeLine).join("\n");

    return text ? `[${title}]\n${text}` : "";
  })
    .filter(Boolean)
    .join("\n\n");
}

/** 본문 → 칸. '[칸 이름]' 머리줄이 하나도 없으면(다른 곳에서 쓴 일지) 본문 전체를 첫 칸(아동 진술)에 둔다. */
export function parseNote(content: string): NoteDraft {
  const byTitle = new Map(SECTIONS.map((section) => [section.title, section.key]));
  const parts: Record<string, string[]> = {};
  let current: string | null = null;
  const loose: string[] = [];

  for (const raw of content.split(/\r?\n/)) {
    const heading = HEADING_LIKE.exec(raw.trim());
    const key = heading && heading[1] === "" ? byTitle.get(heading[2]) : undefined;
    // 본문에 쓴 머리줄 모양의 글(앞에 역슬래시)은 역슬래시 하나를 떼고 글로 둔다.
    const line = heading && heading[1] !== "" && TITLES.has(heading[2]) ? raw.replace("\\", "") : raw;

    if (key) {
      current = key;
      parts[key] = parts[key] ?? [];
    } else if (current) {
      parts[current].push(line);
    } else {
      loose.push(line);
    }
  }

  const note: NoteDraft = { ...EMPTY_NOTE, traits: [], homes: [] };

  if (Object.keys(parts).length === 0) {
    note.statement = content.trim();
    return note;
  }

  for (const [key, lines] of Object.entries(parts)) {
    const text = lines.join("\n").trim();

    if (LIST_KEYS.has(key)) {
      note[key as ListKey] = text
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    } else {
      note[key as TextKey] = text;
    }
  }

  // 첫 머리줄 앞에 쓴 글이 있으면 첫 칸 앞에 붙여 잃지 않게 한다.
  const lead = loose.join("\n").trim();
  if (lead) note.statement = note.statement ? `${lead}\n${note.statement}` : lead;

  return note;
}

/** 화면 상태(Logic.state). */
export interface NoteUiState {
  /** 고친 일지. null 이면 서버 값 그대로. */
  draft: NoteDraft | null;
  /** draft 가 어느 회차 것인가(다른 회차로 옮기면 버린다). */
  draftFor: string | null;
  /** 승인을 한 번 더 묻는 중인 것과 그 회차. 다른 회차로 옮기면 확인창은 닫힌 것으로 본다. */
  ask: { kind: "summary" | "document"; sessionId: string | null } | null;
}

export const INITIAL_NOTE_STATE: NoteUiState = { draft: null, draftFor: null, ask: null };

export interface NoteScreenInput extends SessionScreenInput {
  summary: SummaryReviewState;
  docs: SessionDocumentsState;
  /** 사례의 초기면접에서 고른 항목. 서버에 저장하지 않아 지금은 넘기지 않는다(undefined · null = 저장 전). */
  intake?: IntakeChecks | null;
  state: NoteUiState;
  setState: (patch: Partial<NoteUiState> | ((current: NoteUiState) => Partial<NoteUiState>)) => void;
}

/**
 * 일지에서 추가로 고를 체크리스트 항목. 서식 항목 중 초기면접에서 고른 것은 뺀다.
 * 일지에 담긴 항목 중 서식 항목에 없는 것(예전 목록의 이름 등)은 지울 수 있게 고른 채로 뒤에 붙인다.
 */
export function addableItems(options: string[], intake: string[], picked: string[]): string[] {
  const fromIntake = new Set(intake);
  const listed = new Set(options);
  const extra = picked.filter((item) => !listed.has(item) && !fromIntake.has(item));

  return [...options.filter((item) => !fromIntake.has(item)), ...extra.filter((item, i) => extra.indexOf(item) === i)];
}

export function noteWriteValues(input: NoteScreenInput) {
  const { summary, docs, state, setState, go, detail, caseDetail, intake = null } = input;
  const header = processHeaderValues(input, 2);
  const ids = header.ids;
  const sessionId = ids.sessionId;
  const sv = detail.session;
  const info = caseDetail.caseInfo;
  const signalHref = screenHref("/SignalReview", ids);

  const busy = summary.submitting || docs.submitting;
  const asking = state.ask && state.ask.sessionId === sessionId ? state.ask.kind : null;

  // ---------------- 상담 요약 ----------------
  // 저장 · 승인을 기다리는 동안에는 잠근다(보낸 내용 뒤에 친 글자가 승인된 내용과 다르게 남지 않게).
  const readOnly = !summary.canEdit || busy;
  const fields = summary.fields;
  const sums = summary.hasSummary
    ? [
        { k: "요약", v: fields.overview, onChange: (e: { target: { value: string } }) => summary.setOverview(e.target.value) },
        ...fields.keyPoints.map((point, index) => ({
          k: `핵심 내용 ${index + 1}`,
          v: point,
          onChange: (e: { target: { value: string } }) => summary.setKeyPoint(index, e.target.value),
        })),
        {
          k: "상담사 메모",
          v: fields.counselorNote,
          onChange: (e: { target: { value: string } }) => summary.setCounselorNote(e.target.value),
        },
      ].map((row) => ({ ...row, src: "", readOnly }))
    : [];

  const summaryEv = summary.evidence.map((item) => ({
    label: "AI 근거",
    ev: `${item.keyPoint} — ${item.segments
      .map((segment) =>
        segment.found ? `${segment.startLabel} ${segment.speakerLabel} "${segment.text}"` : "원문에서 찾지 못한 발화",
      )
      .join(" / ")}`,
  }));

  let summaryChip = "요약 없음";
  if (summary.status === "APPROVED") summaryChip = `승인 · ${summary.approvedAt}`;
  else if (summary.hasSummary) summaryChip = summary.edited ? "AI 초안 · 상담사 수정" : "AI 초안";

  const status = summary.sessionStatus;
  let summaryNote = "";
  let summaryLink: { href: string; label: string } | null = null;

  if (!summary.hasSummary && status !== null) {
    if (status === "AI_PROCESSING") summaryNote = "AI 분석 중입니다. 끝나면 요약 초안이 생깁니다.";
    else if (status === "AI_FAILED") {
      summaryNote = `AI 분석에 실패했습니다${summary.sessionError ? `(${summary.sessionError})` : ""}. 위험 신호 검토에서 다시 분석해 주세요.`;
      summaryLink = { href: signalHref, label: "위험 신호 검토로" };
    } else {
      summaryNote = "AI 분석이 끝나면 요약 초안이 생깁니다. 위험 신호 검토에서 AI 분석을 요청해 주세요.";
      summaryLink = { href: signalHref, label: "위험 신호 검토로" };
    }
  } else if (summary.hasSummary && status === "AI_PROCESSING") {
    summaryNote = "AI 가 다시 분석하는 중입니다. 끝날 때까지 요약을 고칠 수 없습니다.";
  } else if (summary.evidenceError) {
    summaryNote = `근거 발화를 불러오지 못했습니다(${summary.evidenceError}).`;
  } else if (summary.evidenceLoading && summary.hasSummary) {
    summaryNote = "근거 발화를 불러오는 중…";
  }

  // ---------------- 상담 일지 ----------------
  const record = docs.consultationRecord;
  const saved = record ? parseNote(record.content) : EMPTY_NOTE;
  const draft = state.draft && state.draftFor === sessionId ? state.draft : null;
  const note = draft ?? saved;
  const content = formatNote(note);
  const docDirty = draft !== null && content !== (record?.content ?? "");
  const docReadOnly = record ? !record.editable : false;
  // 일지를 불러오는 중이거나 저장 · 승인을 기다리는 동안에도 잠근다. 불러오기 전에 쓰면 빈 일지를 바탕으로 초안이 생겨
  // 저장할 때 원래 있던 다른 칸이 지워진다.
  const docLocked = docReadOnly || docs.loading || busy;
  const edit = (patch: Partial<NoteDraft>) =>
    setState((current) => {
      const base = current.draft && current.draftFor === sessionId ? current.draft : note;

      return { draft: { ...base, ...patch }, draftFor: sessionId };
    });
  const textField = (key: TextKey) => ({
    value: note[key],
    onChange: (e: { target: { value: string } }) => {
      if (!docLocked) edit({ [key]: e.target.value });
    },
    readOnly: docLocked,
  });
  /** 초기면접에서 고른 항목(단어로만 보인다). 저장 전이면 words 는 비고 note 로 까닭을 보인다. */
  const intakeWords = (words: string[] | null) => ({
    words: words ?? [],
    note: words === null ? "초기면접 내용은 아직 서버에 저장하지 않아(준비 중) 보일 항목이 없습니다." : "초기면접에서 고른 항목 없음",
  });
  const checklist = (key: ListKey, options: string[], fromIntake: string[]) =>
    addableItems(options, fromIntake, note[key]).map((label) => {
      const checked = note[key].includes(label);

      return {
        label,
        checked,
        disabled: docLocked,
        onChange: () => {
          if (!docLocked) edit({ [key]: checked ? note[key].filter((item) => item !== label) : [...note[key], label] });
        },
      };
    });

  /** 일지를 저장한다. 성공하면 저장된 문서, 바꾼 것이 없으면 지금 문서, 실패하면 null. */
  const saveDoc = async (): Promise<DocumentRow | null> => {
    if (!docDirty) return record;

    const sent = draft;
    const result = record
      ? await docs.update(record.id, { content })
      : await docs.create({ title: `${sv ? sv.numberLabel : ""} 상담일지`.trim(), content });

    // 저장을 기다리는 사이 더 고쳤으면 그 입력은 남긴다.
    if (result) setState((current) => (current.draft === sent ? { draft: null, draftFor: null } : {}));

    return result;
  };

  const docChip = record ? `상담원 작성 · ${record.statusLabel}` : "상담원 작성 · 작성 전";
  const docNote = record?.approvedAt ? `일지 승인 · ${record.approvedAt}` : record ? `마지막 저장 · ${record.updatedAt}` : "";

  const fhead = [
    { k: "사건번호", v: info ? info.caseNumber : NOT_PROVIDED },
    { k: "대상아동", v: info ? `${info.alias} (${info.genderLabel}, ${info.birthYearLabel})` : NOT_PROVIDED },
    { k: "상담일시", v: sv ? sv.consultedAt : NOT_PROVIDED },
    { k: "장소 · 유형", v: sv ? `${sv.location} · 상담 유형 ${NOT_PROVIDED} · ${sv.numberLabel}` : NOT_PROVIDED },
    { k: "면접대상자/관계", v: NOT_PROVIDED },
    { k: "담당 상담원", v: info ? info.counselorName : NOT_PROVIDED },
  ];

  return {
    ...header,
    // 상담 요약
    summaryChip,
    sums,
    summaryEv,
    summaryNote,
    summaryLink,
    summaryError: summary.error,
    canSaveSummary: summary.canEdit && summary.dirty && !busy,
    saveSummary: () => void summary.save(),
    canApproveSummary: summary.canApprove && !busy,
    askSummary: () => setState({ ask: { kind: "summary", sessionId } }),
    summaryAsk: asking === "summary",
    summaryAskText: "승인하면 이 회차가 '승인 완료' 가 되고 요약을 더 고칠 수 없습니다. 상담일지 승인은 따로 합니다.",
    approveSummary: async () => {
      if (asking !== "summary") return;

      const ok = await summary.approve();

      if (ok) setState({ ask: null });
    },
    // 상담 일지
    docChip,
    docNote,
    fhead,
    statement: textField("statement"),
    attitude: textField("attitude"),
    environment: textField("environment"),
    signals: textField("signals"),
    opinion: textField("opinion"),
    traitIntake: intakeWords(intake ? intake.traits : null),
    homeIntake: intakeWords(intake ? intake.homes : null),
    traits: checklist("traits", INTAKE_CHILD_ITEMS, intake ? intake.traits : []),
    homes: checklist("homes", INTAKE_HOME_ITEMS, intake ? intake.homes : []),
    traitEv: [] as { label: string; ev: string }[],
    homeEv: [] as { label: string; ev: string }[],
    aiDraft: false,
    docError: docs.error,
    canSaveDoc: docDirty && !docReadOnly && !busy,
    saveDoc: () => void saveDoc(),
    canApproveDoc: !docReadOnly && (record !== null || docDirty) && !busy,
    askDoc: () => setState({ ask: { kind: "document", sessionId } }),
    docAsk: asking === "document",
    docAskText: "승인하면 상담일지를 더 고칠 수 없습니다. 회차 상태는 바뀌지 않습니다.",
    approveDoc: async () => {
      if (asking !== "document") return;

      const target = await saveDoc();

      if (target && (await docs.approve(target.id))) setState({ ask: null });
    },
    cancelAsk: () => setState({ ask: null }),
    // 아래 단추
    backHref: signalHref,
    nextLabel: busy ? "저장 중…" : "저장 · 추가 확인 · 질문 →",
    canNext: !busy,
    next: async () => {
      const forSession = sessionId;

      if (summary.canEdit && summary.dirty && !(await summary.save())) return;
      if (docDirty && !(await saveDoc())) return;
      // 저장을 기다리는 사이 다른 회차 · 화면으로 옮겼으면 앞 회차의 다음 화면으로 끌고 가지 않는다.
      go(screenHref("/FollowupQ", ids), forSession);
    },
    /** 저장하지 않은 수정이 있는가(useLeaveGuard 에 넘긴다). */
    unsaved: (summary.canEdit && summary.dirty) || docDirty,
  };
}
