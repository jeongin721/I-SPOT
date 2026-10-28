// 3 · 상담 요약 · 상담 일지(NoteWrite) 화면 값.
//
// 상담 요약 카드 = useSummaryReview. 10/27 디자인대로 사정 관점 4칸(조사 후 변화 · 강점과 자원 · 위험요인 · 원하는 변화)의
// AI 초안을 고치고 저장 · 승인한다(summary.assessment, 2026-10-27).
//  - **요약 승인은 회차를 '승인 완료' 로 바꾼다.** '요약 승인' 단추를 누르면 (고친 칸을 저장하고) 바로 승인한다.
//    한 번 더 묻지 않는다 — 승인한 뒤에도 '요약 수정' 으로 풀 수 있어서다(2026-10-16 최민규 결정).
//    승인한 뒤에는 '요약 수정' 단추만 보인다. 누르면 승인이 풀려 쓴 내용 그대로 다시 고칠 수 있고(회차는 'AI 결과 검수 필요'),
//    고친 뒤 다시 승인한다. 상담 일지도 같다('일지 수정', 회차 상태는 바뀌지 않는다).
//    아래 '저장 · 추가 확인 · 질문 →' 단추는 저장만 하고 승인하지 않는다(specs 대응표 '승인 시점').
//  - 칸마다 AI 초안의 근거 위치('근거 · 01:08 아동')를 칸 이름 옆에 보인다(디자인의 src). 상담사가 문장을 고쳐도 근거는 AI 초안 것이다.
//  - 개요 · 핵심 내용 · 상담사 메모와 핵심 내용별 'AI 근거' 줄은 디자인에 없어 보이지 않는다(서버에는 그대로 남는다).
//    핵심 내용의 근거 발화는 유형별 위험도 화면에서 본다.
//  - '조사 후 변화된 사항' 은 이전 회차와의 비교라 서버 경로에서는 AI 초안이 비어 온다 — 상담원이 쓴다.
//
// 상담 일지 카드 = useSessionDocuments 의 상담일지(CONSULTATION_RECORD) 한 건. 문서는 제목 · 본문 텍스트뿐이라
// 화면의 칸(아동 진술 · 대상자 태도 · … · 소견)을 '[칸 이름]' 머리줄로 나눠 본문 하나에 담는다(formatNote · parseNote).
// 기관 양식별 구조는 팀 결정 전이라 이 형식은 임시다. 문서 승인은 회차 상태를 바꾸지 않는다(요약 승인과 따로).
//  - AI 일지 초안 · 아동 특성 · 가정상황 AI 제안은 Backend 에 없어 보이지 않는다(빈 칸에서 상담원이 쓴다).
//    10/21 디자인은 AI 제안 항목('불안' 등)을 미리 골라 두지만 앱은 미리 고르지 않는다(AI 제안이 상담원 선택처럼 보이지 않게).
//  - 아동 특성 · 가정상황: 사례의 초기면접(서식 4 ②, 사례 등록 때 고름 · useCaseDetail)에서 고른 항목은 단어로만 보이고,
//    나머지 서식 4 항목을 고르기 단추로 추가해 고른다. 본문 '[아동 특성]' · '[가정상황]' 에는 이 일지에서 추가로 고른 항목만 담는다
//    (초기면접 항목은 사례에 속한다). 사례 정보를 받기 전에는 고르기 단추를 잠근다(받은 뒤 빠질 항목을 고르지 않게).
//    일지를 쓴 뒤 사례 상세에서 초기면접을 고쳐 일지 항목과 겹치면, 그 항목은 '초기면접에도 있음' 을 붙여 고른 채 남긴다
//    (풀고 저장하면 본문에서 빠진다. 저절로 지우지 않는다 — 승인한 일지도 있어서).
//  - 10/21 디자인의 칸별 '수정 → 확인'(pickSection): '수정' 을 누르면 고르기 단추가 펼쳐지고, '확인' 을 누르면 접혀 고른 항목만
//    ✓ 로 보인다. '확인' 은 화면 상태라 서버에 보내지 않는다 — 고른 항목은 누를 때 바로 일지 초안(draft)에 들어가고(떠날 때 확인 ·
//    저장 대상), 저장 · 승인은 지금처럼 '일지 저장' · '일지 승인' · 아래 '저장 · …' 이 한다. 승인된 일지는 '일지 수정' 으로
//    승인을 풀기 전에는 펼치지 않고, '일지 승인' 을 누르면 펼친 칸을 접는다.
//  - 면접대상자/관계 · 상담 유형은 Backend 에 없어 '—'.

import { NOT_PROVIDED } from "../caseRows";
import type { RemoteTicket } from "../useRemote";
import type { DocumentRow, SessionDocumentsState } from "../useSessionDocuments";
import type { SummaryAssessmentKey } from "../../api/types";
import { positionLabel } from "../riskRows";
import { ASSESSMENT_KEYS, type SummaryReviewState } from "../useSummaryReview";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS } from "./intakeItems";
import { intakeChoices, toggleItem } from "./intakePick";
import { screenHref } from "./links";
import { processHeaderValues } from "./process";
import { sessionCaseId, type SessionScreenInput } from "./sessionDetail";

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

/**
 * 화면 상태(Logic.state). 화면은 계정이 바뀌어도 새로 만들어지지 않으므로, 고친 일지는 그때의 대상 표
 * (docs.capture() — 회차 · 대상 세대 · 로그인 토큰)와 함께 두고 표가 지금 대상일 때만 쓴다.
 * 다른 회차로 옮기거나, 갔다 돌아오거나(A → B → A), 다른 탭에서 다시 로그인하면 버린 것으로 본다
 * (요약 훅의 고친 칸이 대상이 바뀔 때 비워지는 것과 같은 기준. 앞 로그인이 쓴 초안이 새 로그인 화면 · 요청에 실리지 않게).
 */
export interface NoteUiState {
  /** 고친 일지. null 이면 서버 값 그대로. */
  draft: NoteDraft | null;
  /** draft 를 쓴 대상의 표. */
  draftFor: RemoteTicket | null;
  /** '수정' 을 눌러 고르기 단추를 펼친 칸(아동 특성 · 가정상황). 화면 상태라 서버에 보내지 않는다. */
  picking: ListKey[];
  /** picking 을 연 대상의 표. draftFor 와 같은 기준으로, 대상이 바뀌면 접힌 것으로 본다. */
  pickingFor: RemoteTicket | null;
}

export const INITIAL_NOTE_STATE: NoteUiState = { draft: null, draftFor: null, picking: [], pickingFor: null };

export interface NoteScreenInput extends SessionScreenInput {
  summary: SummaryReviewState;
  docs: SessionDocumentsState;
  state: NoteUiState;
  setState: (patch: Partial<NoteUiState> | ((current: NoteUiState) => Partial<NoteUiState>)) => void;
}

/**
 * 일지에서 추가로 고를 항목(고르기 단추). 서식 항목 중 초기면접에서 고른 것은 뺀다.
 * 일지에 담긴 항목(kept)은 지울 수 있게 늘 남긴다. 서식 항목에 없는 것(예전 목록의 이름 등)은 뒤에 붙이고,
 * 초기면접 항목과 겹치는 것(일지를 쓴 뒤 사례 상세에서 초기면접을 고쳐 겹침)은 서식 순서 자리에 둔다.
 * kept 에는 저장된 일지의 항목과 지금 고친 항목을 함께 넘긴다 — 이미 저장된 일지에 담긴 겹친 항목은 고른 것을 풀어도 일지를 저장하기
 * 전까지 목록에 남아 다시 고를 수 있다. 저장하지 않은 초안에만 있던 항목이 겹치게 된 경우는 풀면 바로 목록에서 빠진다
 * (초기면접 항목으로는 그대로 보인다).
 */
export function addableItems(options: string[], intake: string[], kept: string[]): string[] {
  const fromIntake = new Set(intake);
  const listed = new Set(options);
  const held = new Set(kept);

  return [...options.filter((item) => !fromIntake.has(item) || held.has(item)), ...[...held].filter((item) => !listed.has(item))];
}

/** 사정 관점 4칸의 화면 이름(10/27 디자인 NoteWrite 그대로). */
export const ASSESSMENT_LABELS: Record<SummaryAssessmentKey, string> = {
  safety_changes: "(안전관련) 조사 후 변화된 사항",
  strengths_resources: "아동안전과 관련된 강점과 자원",
  safety_risks: "아동안전과 관련된 위험요인",
  desired_changes: "앞으로 원하는 변화 · 원하는 서비스/지원",
};

export function noteWriteValues(input: NoteScreenInput) {
  const { summary, docs, state, setState, go, detail, caseDetail } = input;
  const header = processHeaderValues(input, 2);
  const ids = header.ids;
  const sv = detail.session;
  const info = caseDetail.caseInfo;
  const signalHref = screenHref("/SignalReview", ids);

  const busy = summary.submitting || docs.submitting;

  // ---------------- 상담 요약 ----------------
  // 저장 · 승인을 기다리는 동안에는 잠근다(보낸 내용 뒤에 친 글자가 승인된 내용과 다르게 남지 않게).
  const readOnly = !summary.canEdit || busy;
  const fields = summary.fields;
  const sums = summary.hasSummary
    ? ASSESSMENT_KEYS.map((key) => ({
        k: ASSESSMENT_LABELS[key],
        v: fields.assessment[key],
        src: positionLabel(summary.assessmentEvidence[key]),
        onChange: (e: { target: { value: string } }) => summary.setAssessment(key, e.target.value),
        readOnly,
      }))
    : [];

  let summaryChip = "요약 없음";
  if (summary.status === "APPROVED") summaryChip = `승인 · ${summary.approvedAt}`;
  else if (summary.hasSummary) summaryChip = summary.edited ? "AI 초안 · 상담사 수정" : "AI 초안";

  const status = summary.sessionStatus;
  let summaryNote = "";
  let summaryLink: { href: string; label: string } | null = null;

  if (!summary.hasSummary && status !== null) {
    if (status === "AI_PROCESSING") summaryNote = "AI 분석 중입니다. 끝나면 요약 초안이 생깁니다.";
    else if (status === "AI_FAILED") {
      summaryNote = `AI 분석에 실패했습니다${summary.sessionError ? `(${summary.sessionError})` : ""}. 유형별 위험도에서 다시 분석해 주세요.`;
      summaryLink = { href: signalHref, label: "유형별 위험도로" };
    } else {
      summaryNote = "AI 분석이 끝나면 요약 초안이 생깁니다. 유형별 위험도에서 AI 분석을 요청해 주세요.";
      summaryLink = { href: signalHref, label: "유형별 위험도로" };
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
  const draft = state.draft && docs.isCurrent(state.draftFor) ? state.draft : null;
  const note = draft ?? saved;
  const content = formatNote(note);
  const docDirty = draft !== null && content !== (record?.content ?? "");
  const docReadOnly = record ? !record.editable : false;
  // 일지를 불러오는 중이거나 저장 · 승인을 기다리는 동안에도 잠근다. 불러오기 전에 쓰면 빈 일지를 바탕으로 초안이 생겨
  // 저장할 때 원래 있던 다른 칸이 지워진다.
  const docLocked = docReadOnly || docs.loading || busy;
  const edit = (patch: Partial<NoteDraft>) =>
    setState((current) => {
      const kept = current.draft && docs.isCurrent(current.draftFor) ? current : null;
      const ticket = kept ? kept.draftFor : docs.capture();

      // 대상이 없으면(회차 ID 없음 · 로그인 확인 중) 쓸 곳이 없다.
      if (!ticket) return {};

      return { draft: { ...(kept?.draft ?? note), ...patch }, draftFor: ticket };
    });
  const textField = (key: TextKey) => ({
    value: note[key],
    onChange: (e: { target: { value: string } }) => {
      if (!docLocked) edit({ [key]: e.target.value });
    },
    readOnly: docLocked,
  });
  // 초기면접 항목은 사례 정보에서 온다. 받기 전(불러오는 중)에는 고르기 단추를 잠근다.
  // 사례 정보를 못 받았으면(오류) · 이 회차에 연결된 사례가 없으면 초기면접 항목 없이 전 항목을 고르게 둔다(일지 쓰기를 막지 않는다).
  // 예전에는 '정보도 오류도 없음' 을 모두 받는 중으로 봐서, 받을 사례가 없을 때 '불러오는 중…' 이 끝나지 않고 고르기도 잠겼다.
  const caseKnown = sessionCaseId(input.ids, detail) !== null;
  const intakeWaiting =
    !info && !caseDetail.error && (caseDetail.loading || detail.loading || (caseKnown && !detail.error));
  const noCase = !info && !caseDetail.error && !intakeWaiting;
  /** 초기면접에서 고른 항목(단어로만 보인다). 없거나 아직 모르면 words 는 비고 note 로 까닭을 보인다. */
  const intakeWords = (words: string[] | null) => {
    let empty = "초기면접에서 고른 항목 없음";
    if (words === null) {
      if (intakeWaiting) empty = "초기면접 항목을 불러오는 중…";
      else if (noCase) empty = "연결된 사례 정보가 없어 초기면접 항목이 없습니다.";
      else empty = "사례 정보를 불러오지 못해 초기면접 항목을 보일 수 없습니다.";
    }

    return { words: words ?? [], note: empty };
  };
  // 펼친 칸. 다른 회차로 옮기거나 다시 로그인하면(표가 지금 대상이 아니면) 접힌 것으로 본다.
  const picking = docs.isCurrent(state.pickingFor) ? state.picking : [];
  // 고르기 단추를 누를 수 없을 때(승인된 일지 · 불러오는 중 · 저장 중 · 사례 정보를 받기 전). 이때는 '수정' 으로 펼치지도 못한다.
  const pickLocked = docLocked || intakeWaiting;
  /**
   * 아동 특성 · 가정상황 한 칸(10/21 디자인의 '수정 → 확인'). 펼치면 choices(고르기 단추), 접으면 picked(고른 항목만 ✓).
   * 단추를 누르면 바로 일지 초안에 들어간다(edit). '확인' 은 접기만 한다.
   */
  const pickSection = (key: ListKey, options: string[], fromIntake: string[]) => {
    // 승인된 일지는 펼치지 않는다('일지 수정' 으로 승인을 풀어야 고칠 수 있다).
    const open = picking.includes(key) && !docReadOnly;
    const choices = intakeChoices(
      addableItems(options, fromIntake, [...saved[key], ...note[key]]),
      note[key],
      pickLocked,
      (label) => edit({ [key]: toggleItem(note[key], label) }),
    ).map((choice) => ({
      ...choice,
      // 초기면접 항목과 겹친 채 일지에 남은 항목. 풀고 저장하면 목록에서 빠진다(초기면접 항목으로는 그대로 보인다).
      hint: fromIntake.includes(choice.label) ? "초기면접에도 있음" : "",
    }));
    // 접기는 늘 된다(저장 · 승인을 기다리는 중에도). 펼치기는 고를 수 있을 때만.
    const canToggle = open || !pickLocked;

    return {
      open,
      choices,
      picked: choices.filter((choice) => choice.on),
      btnLabel: open ? "확인" : "수정",
      btnCls: open ? "btn-p" : "btn-s",
      btnTitle: !open && docReadOnly ? "승인된 일지입니다. 아래 '일지 수정' 을 누르면 고칠 수 있습니다." : undefined,
      canToggle,
      toggle: () => {
        if (!canToggle) return;
        setState((current) => {
          const now = docs.isCurrent(current.pickingFor) ? current.picking : [];

          if (now.includes(key)) return { picking: now.filter((item) => item !== key) };

          const ticket = now.length ? current.pickingFor : docs.capture();

          // 대상이 없으면(회차 ID 없음 · 로그인 확인 중) 고른 것을 담을 일지도 없다.
          if (!ticket) return {};

          return { picking: [...now, key], pickingFor: ticket };
        });
      },
    };
  };

  /**
   * 일지를 저장한다. 성공하면 저장된 문서, 바꾼 것이 없으면 지금 문서, 실패하면 null.
   * 요청한 뒤 대상이 바뀌어(다른 회차, 갔다 돌아옴, 다시 로그인, 화면을 떠남) 반영하지 못했어도 null 이다(docs 훅).
   */
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

  const docApproved = record !== null && record.status === "APPROVED";
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
    summaryNote,
    summaryLink,
    summaryError: summary.error,
    canSaveSummary: summary.canEdit && summary.dirty && !busy,
    saveSummary: () => void summary.save(),
    canApproveSummary: summary.canApprove && !busy,
    // 고친 칸을 먼저 저장하고 바로 승인한다(한 번 더 묻지 않는다).
    approveSummary: () => void summary.approve(),
    // 승인된 요약이면 저장 · 승인 대신 '요약 수정' 단추만 보인다.
    summaryApproved: summary.status === "APPROVED",
    canReopenSummary: summary.canReopen && !busy,
    reopenSummary: () => void summary.reopen(),
    // 상담 일지
    docChip,
    docNote,
    fhead,
    statement: textField("statement"),
    attitude: textField("attitude"),
    environment: textField("environment"),
    signals: textField("signals"),
    opinion: textField("opinion"),
    traitIntake: intakeWords(info ? info.intakeChildTraits : null),
    homeIntake: intakeWords(info ? info.intakeFamilySituations : null),
    traitPick: pickSection("traits", INTAKE_CHILD_ITEMS, info ? info.intakeChildTraits : []),
    homePick: pickSection("homes", INTAKE_HOME_ITEMS, info ? info.intakeFamilySituations : []),
    traitEv: [] as { label: string; ev: string }[],
    homeEv: [] as { label: string; ev: string }[],
    aiDraft: false,
    docError: docs.error,
    canSaveDoc: docDirty && !docReadOnly && !busy,
    saveDoc: () => void saveDoc(),
    canApproveDoc: !docReadOnly && (record !== null || docDirty) && !busy,
    // 고친 일지를 먼저 저장하고 바로 승인한다(한 번 더 묻지 않는다).
    approveDoc: async () => {
      // 승인하면 고를 칸도 끝난 것으로 보고 펼친 칸을 접는다('확인' 과 같다. 고른 항목은 이미 초안에 있다).
      setState({ picking: [], pickingFor: null });
      // 저장하는 사이 대상이 바뀌면 새 로그인으로 앞 회차의 일지를 승인하지 않는다.
      const ticket = docs.capture();
      const target = await saveDoc();

      if (target && docs.isCurrent(ticket)) await docs.approve(target.id);
    },
    // 승인된 일지면 저장 · 승인 대신 '일지 수정' 단추만 보인다. 쓴 내용은 그대로 남아 이어서 고친다.
    docApproved,
    canReopenDoc: docApproved && !busy,
    reopenDoc: () => {
      if (record && docApproved) void docs.reopen(record.id);
    },
    // 아래 단추
    backHref: signalHref,
    nextLabel: busy ? "저장 중…" : "저장 · 추가 확인 · 질문 →",
    canNext: !busy,
    next: async () => {
      // 누를 때의 대상(표). 저장을 기다리는 사이 대상이 바뀌었으면(다른 회차 · 화면, 갔다 돌아옴, 다시 로그인)
      // 다음 저장을 이어 보내지 않고 앞 회차의 다음 화면으로 끌고 가지도 않는다.
      // 대상이 없으면(회차 ID 없음 · 로그인 확인 중) 저장할 것도 없어 바로 옮긴다.
      const ticket = docs.capture();
      const stillHere = () => ticket === null || docs.isCurrent(ticket);

      if (summary.canEdit && summary.dirty && !(await summary.save())) return;
      if (!stillHere()) return;
      if (docDirty && !(await saveDoc())) return;
      go(screenHref("/FollowupQ", ids), stillHere);
    },
    /** 저장하지 않은 수정이 있는가(useLeaveGuard 에 넘긴다). */
    unsaved: (summary.canEdit && summary.dirty) || docDirty,
  };
}
