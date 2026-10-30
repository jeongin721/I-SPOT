// 4 · 다음 상담 준비 '다음 상담 전 확인할 사항' 카드 값(10/29 디자인 FollowupQ.dc.html, 2026-10-30 저장 연결).
//
// 저장: GET/PUT /sessions/{id}/followup-checks(API_CONTRACT 18.1절, useFollowupChecks). 목록 통째 바꾸기.
//  - 저장한 적이 없으면 AI 확인 메모 초안(분석 결과 followup_check_points)을 보인다. 한 번 저장하면 그 목록이 이 회차의
//    확인 사항이다(이후 AI 초안은 다시 보이지 않는다).
//  - 체크(브리핑에 넣기)는 누르면 바로 저장한다. 상담 전 브리핑은 체크한 것만 보인다.
//  - '수정' 은 모든 줄을 한 번에 고치는 모드(디자인), '확인' 을 누르면 저장한다. 비운 줄은 빠진다. AI 메모를 고치면 '상담사 수정'.
//  - '+ 확인 사항 직접 추가' 는 수정 모드에서 새 줄을 더한다(상담사가 쓴 줄, source COUNSELOR).
// 저장할 수 없는 상태(원문 확정 전 · AI 분석 중)면 단추를 멈추고 이유를 보인다(추가 질문과 같은 규칙).

import type { FollowupCheck, FollowupCheckPoint, SessionStatus } from "../../api/types";
import type { FollowupChecksState } from "../useFollowupChecks";
import type { RiskSignalsState } from "../useRiskSignals";
import { segmentHref } from "./sttReview";

export interface CheckUiState {
  ckEditing: boolean;
  /** 수정 중인 줄 문장(순서대로). */
  ckDraft: string[];
  /** 수정 중 새로 쓰는 줄. */
  ckNew: string[];
}

export function initialCheckState(): CheckUiState {
  return { ckEditing: false, ckDraft: [], ckNew: [] };
}

const EDITABLE: SessionStatus[] = ["STT_CONFIRMED", "AI_REVIEW_REQUIRED", "AI_FAILED", "APPROVED"];

function blockedReason(status: SessionStatus | null | undefined): string | null {
  if (!status || EDITABLE.includes(status)) return null;
  if (status === "AI_PROCESSING") return "AI 분석 중에는 확인 사항을 저장할 수 없습니다.";
  return "원문(STT)을 확정한 뒤 확인 사항을 저장할 수 있습니다.";
}

/** AI 확인 메모 초안 → 저장 꼴(아직 저장 전). 글이 빈 메모는 뺀다. */
export function draftChecks(points: FollowupCheckPoint[]): FollowupCheck[] {
  return points
    .filter((point) => point && typeof point.text === "string" && point.text.trim())
    .map((point) => ({
      text: point.text.trim(),
      source: "AI" as const,
      segment_ids: Array.isArray(point.segment_ids) ? point.segment_ids.filter((id) => typeof id === "string") : [],
      edited: false,
      in_briefing: false,
    }));
}

export interface CheckInput {
  state: CheckUiState;
  setState: (patch: Partial<CheckUiState>) => void;
  checks: FollowupChecksState;
  /** 분석이 끝났을 때의 AI 확인 메모(아니면 []). */
  points: FollowupCheckPoint[];
  locate: RiskSignalsState["locate"];
  ids: { caseId?: string | null; sessionId?: string | null };
  status: SessionStatus | null | undefined;
}

export function checkValues(input: CheckInput) {
  const { state, setState, checks, locate, ids } = input;
  const base: FollowupCheck[] = checks.saved ? checks.items : draftChecks(input.points);
  const blocked = blockedReason(input.status);
  const canSave = checks.loaded && !checks.loadError && !checks.submitting && !blocked;

  const save = async (next: FollowupCheck[]) => (canSave ? checks.save(next) : false);

  const rows = base.map((item, index) => {
    const located = locate(item.segment_ids);
    const first = located.evidence[0]?.segmentId ?? null;

    return {
      key: `c${index}`,
      text: item.text,
      why: located.label || "근거 위치 없음",
      href: first ? segmentHref(ids, first) : null,
      on: item.in_briefing,
      edited: item.edited,
      mine: item.source === "COUNSELOR",
      toggle: () => {
        if (state.ckEditing) return;
        void save(base.map((other, i) => (i === index ? { ...other, in_briefing: !other.in_briefing } : other)));
      },
      draft: state.ckDraft[index] ?? item.text,
      setDraft: (event: { target: { value: string } }) => {
        const next = base.map((other, i) => state.ckDraft[i] ?? other.text);
        next[index] = event.target.value;
        setState({ ckDraft: next });
      },
    };
  });

  const newRows = state.ckNew.map((draft, index) => ({
    key: `n${index}`,
    draft,
    setDraft: (event: { target: { value: string } }) => {
      const next = [...state.ckNew];
      next[index] = event.target.value;
      setState({ ckNew: next });
    },
  }));

  const startEdit = () => {
    if (!canSave) return;
    setState({ ckEditing: true, ckDraft: base.map((item) => item.text), ckNew: [] });
  };

  let note = "";
  if (blocked) note = blocked;
  else if (checks.loadError) note = checks.loadError;
  else if (!checks.loaded) note = "확인 사항을 불러오는 중…";
  else if (checks.error) note = checks.error;
  else if (checks.saved) note = "체크한 확인 사항은 상담 전 브리핑에 보입니다.";
  else if (base.length > 0) note = "AI 확인 메모 초안입니다. 체크 · 수정 · 직접 추가하면 이 회차의 확인 사항으로 저장됩니다.";

  return {
    checks: rows,
    newRows,
    ckIsEdit: state.ckEditing,
    ckNotEdit: !state.ckEditing,
    ckCanEdit: canSave,
    ckSubmitting: checks.submitting,
    ckNote: note,
    ckStart: startEdit,
    ckAdd: () => {
      if (!canSave) return;
      setState({
        ckEditing: true,
        ckDraft: state.ckEditing ? state.ckDraft : base.map((item) => item.text),
        ckNew: [...(state.ckEditing ? state.ckNew : []), ""],
      });
    },
    ckCancel: () => setState(initialCheckState()),
    ckOk: async () => {
      const next: FollowupCheck[] = [];
      base.forEach((item, index) => {
        const text = (state.ckDraft[index] ?? item.text).trim();
        if (!text) return;
        next.push({ ...item, text, edited: item.edited || (item.source === "AI" && text !== item.text) });
      });
      state.ckNew.forEach((draft) => {
        const text = draft.trim();
        if (text) next.push({ text, source: "COUNSELOR", segment_ids: [], edited: false, in_briefing: false });
      });
      if (await save(next)) setState(initialCheckState());
    },
  };
}
