// 관리자 영구 삭제(사례 · 회차, 2026-11-03). 화면의 '삭제' 단추 → 확인 창(components/DeleteConfirmDialog) → 서버 삭제.
// 시험 · 잘못 올린 사례를 지우려고 서버 터미널에서 파이썬 명령을 돌리지 않아도 되게 한다.
//
//  - 사례: DELETE /cases/{id}(관리자 전용, API_CONTRACT 4절). 회차와 그 아래 자료 · 음성 파일 · 개인 식별 정보 ·
//    종결 검토 · 그 사례의 일정이 함께 지워진다. 감사 기록(CASE_DELETED)은 남는다.
//  - 회차: DELETE /sessions/{id}(API_CONTRACT 5절). 서버는 담당 상담사도 받지만 화면 단추는 관리자에게만 보인다.
//  - 되돌릴 수 없어 확인 창에서 confirmText(사례는 사례 번호, 회차는 'N회차')를 그대로 쳐야 지운다.
//  - 사례를 지울 때는 함께 지워질 회차 수를 먼저 받아 보인다(GET /cases/{id}/sessions 의 meta.total). 못 받으면 '전부' 로 쓴다.
//  - 지우면 onDeleted(목록 다시 부르기)를 부르고, 지운 회차(사례면 그 사례 회차)의 원문 변환 알림을 닫는다.

import { useCallback, useEffect, useRef, useState } from "react";
import { cases, sessions } from "../api/endpoints";
import { dismissTranscription, getTranscriptionJobs } from "./transcriptionJobs";
import { errorMessage } from "./useRemote";

export interface DeleteTarget {
  kind: "case" | "session";
  /** 지울 사례 · 회차의 UUID. */
  id: string;
  /** 그 사례의 UUID(사례를 지우면 id 와 같다). */
  caseId: string;
  /** 확인 창 · 안내에 보일 대상(예: 'C-2026-0005 · 이하준', 'C-2026-0005 · 3회차 · 2026-11-02'). */
  label: string;
  /** 지우려면 그대로 입력해야 하는 글자. */
  confirmText: string;
  /** 음성 변환 · AI 분석이 진행 중인 회차인가(확인 창에 주의를 더 적는다). */
  processing?: boolean;
}

export function caseDeleteTarget(row: { id: string; caseNumber: string; name: string }): DeleteTarget {
  return {
    kind: "case",
    id: row.id,
    caseId: row.id,
    label: `${row.caseNumber} · ${row.name}`,
    confirmText: row.caseNumber,
  };
}

export function sessionDeleteTarget(row: {
  id: string;
  caseId: string;
  caseNumber: string;
  numberLabel: string;
  date: string;
  processing: boolean;
}): DeleteTarget {
  return {
    kind: "session",
    id: row.id,
    caseId: row.caseId,
    label: [row.caseNumber, row.numberLabel, row.date].filter(Boolean).join(" · "),
    confirmText: row.numberLabel,
    processing: row.processing,
  };
}

export interface AdminDeleteState {
  target: DeleteTarget | null;
  /** 확인 창 제목. */
  title: string;
  /** 함께 지워지는 것(확인 창 목록). */
  items: string[];
  busy: boolean;
  /** 지우지 못한 이유(서버 문구 그대로). */
  error: string | null;
  /** 지운 뒤 화면에 보일 안내. */
  done: string | null;
  ask: (target: DeleteTarget) => void;
  close: () => void;
  run: () => Promise<void>;
}

const SESSION_ITEMS = ["상담 음성 파일", "전사본(STT)과 고친 내용", "AI 분석 · 상담원 판단 · 상담 요약 · 문서 · 확인 질문"];

export function useAdminDelete(onDeleted: () => void): AdminDeleteState {
  const [target, setTarget] = useState<DeleteTarget | null>(null);
  // 사례의 회차 수: 받는 중이면 null, 못 받았으면 -1.
  const [count, setCount] = useState<{ caseId: string; total: number | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const inFlight = useRef(false);

  const caseId = target?.kind === "case" ? target.id : null;
  useEffect(() => {
    if (!caseId) return;
    let live = true;
    setCount({ caseId, total: null });
    cases
      .listSessions(caseId, { page: 1, page_size: 1 })
      .then((page) => live && setCount({ caseId, total: page.meta.total }))
      .catch(() => live && setCount({ caseId, total: -1 }));
    return () => {
      live = false;
    };
  }, [caseId]);

  const ask = useCallback((next: DeleteTarget) => {
    setError(null);
    setDone(null);
    setTarget(next);
  }, []);

  const close = useCallback(() => {
    if (inFlight.current) return;
    setTarget(null);
    setError(null);
  }, []);

  const run = useCallback(async () => {
    if (!target || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      if (target.kind === "case") await cases.remove(target.id);
      else await sessions.remove(target.id);
      for (const job of getTranscriptionJobs()) {
        if (target.kind === "case" ? job.caseId === target.id : job.sessionId === target.id) dismissTranscription(job.sessionId);
      }
      setTarget(null);
      setDone(`지웠습니다 — ${target.label}`);
      onDeleted();
    } catch (caught) {
      setError(errorMessage(caught, "지우지 못했습니다. 잠시 후 다시 시도해 주세요."));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }, [target, onDeleted]);

  let items = SESSION_ITEMS;
  if (target?.kind === "case") {
    const total = count?.caseId === target.id ? count.total : null;
    let sessionsLine = "회차 수를 확인하는 중…";
    if (total === -1) sessionsLine = "이 사례의 회차 전부(회차 수를 불러오지 못함)";
    else if (total !== null) sessionsLine = total > 0 ? `회차 ${total}개 전부` : "회차 없음";
    items = [
      sessionsLine,
      "회차마다의 상담 음성 파일 · 전사본(STT) · AI 분석 · 상담원 판단 · 상담 요약 · 문서",
      "개인 식별 정보(실명 · 생년월일 · 가족 정보) · 종결 검토 기록 · 이 사례에 연결된 일정",
    ];
  }

  return {
    target,
    title: target?.kind === "case" ? "사례 영구 삭제" : "회차 영구 삭제",
    items,
    busy,
    error,
    done,
    ask,
    close,
    run,
  };
}
