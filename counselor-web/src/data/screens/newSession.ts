// 상담 이력 '새 상담 등록' 창(10/29 디자인 CaseHistory.dc.html 의 ns-*) 값. 녹음 없이 상담 내용 · 상담사 소견을 적는다.
//
// 서버에 '상담 내용' · '상담사 소견' 칸이 따로 없어 회차 메모(session.memo, 4000자) 하나에 두 칸을 머리말로 나눠 담는다.
// 새 회차면 회차를 만들며(POST /cases/{id}/sessions), 있는 회차면 그 회차 메모를 고친다(PATCH /sessions/{id}).
// 있는 회차에 메모가 있으면 칸에 불러와 보이고 저장하면 바뀐다(모르게 덮어쓰지 않게). 승인 완료 회차는 서버가 고치기를
// 거절하므로(409) 목록에는 보이되 다음으로 못 간다. 회차 메모는 AI 분석에 넘기지 않는다(case_context 에도 없음).

import type { SessionRow } from "../sessionRows";
import { NOT_PROVIDED } from "../caseRows";
import { NEW_SESSION } from "./uploadModal";

export const MEMO_MAX = 4000;
const BODY_HEAD = "[상담 내용]";
const NOTE_HEAD = "[상담사 소견]";
const NOTE_SEP = `\n\n${NOTE_HEAD}\n`;
/** 상담 내용 머리말에 그 글자 수를 적는다 — 본문에 '[상담사 소견]' 줄이 있어도 소견과 섞이지 않게(민규 #122 교차검증). */
const BODY_HEAD_RE = /^\[상담 내용 (\d+)자\]\n/;

/** 글자 수(코드포인트). 서버(파이썬 str 길이)와 같은 기준이다 — JS length(UTF-16)는 이모지를 둘로 센다. */
export function memoLength(text: string): number {
  return [...text].length;
}

/** 두 칸을 회차 메모 하나로. 소견이 비면 상담 내용만. */
export function composeMemo(body: string, note: string): string {
  const b = body.trim();
  const n = note.trim();
  const head = `[상담 내용 ${memoLength(b)}자]\n${b}`;
  return n ? `${head}${NOTE_SEP}${n}` : head;
}

/** 회차 메모를 두 칸으로. 이 창이 쓴 모양이 아니면 메모 전체를 상담 내용으로 본다(10/29 첫 모양 '[상담 내용]' 도 읽는다). */
export function parseMemo(memo: string): { body: string; note: string } {
  const text = memo ?? "";
  const matched = BODY_HEAD_RE.exec(text);

  if (matched) {
    const chars = [...text.slice(matched[0].length)];
    const length = Number(matched[1]);
    if (length <= chars.length) {
      const body = chars.slice(0, length).join("");
      const rest = chars.slice(length).join("");
      return { body, note: rest.startsWith(NOTE_SEP) ? rest.slice(NOTE_SEP.length) : rest.replace(/^\n+/, "") };
    }
  }

  if (!text.startsWith(BODY_HEAD)) return { body: text, note: "" };
  const rest = text.slice(BODY_HEAD.length);
  const at = rest.indexOf(NOTE_SEP);
  if (at < 0) return { body: rest.replace(/^\n/, ""), note: "" };
  return { body: rest.slice(0, at).replace(/^\n/, ""), note: rest.slice(at + NOTE_SEP.length) };
}

export interface NewSessionTarget {
  value: string;
  label: string;
  meta: string;
  /** 창 위 칩 · 등록 확인에 쓰는 짧은 이름. */
  short: string;
  /** 고칠 수 있는가(승인 완료 회차는 아니다). */
  editable: boolean;
  memo: string;
}

const today = () => {
  const d = new Date();
  return `${d.getMonth() + 1}/${d.getDate()}`;
};

/** 맨 위 새 회차(지금 가장 큰 회차 + 1), 그 아래 모든 회차를 최근 것부터. */
export function newSessionTargets(rows: SessionRow[]): NewSessionTarget[] {
  const sorted = [...rows].sort((a, b) => b.sessionNumber - a.sessionNumber);
  const next = (sorted[0]?.sessionNumber ?? 0) + 1;

  return [
    {
      value: NEW_SESSION,
      label: `새 회차 · ${next}회차`,
      meta: `오늘 ${today()} · 새 회차 만들기`,
      short: `${next}회차 (새 회차)`,
      editable: true,
      memo: "",
    },
    ...sorted.map((row) => {
      const date = row.consultedDate !== NOT_PROVIDED ? row.consultedDate : `${row.createdDate} 등록`;
      const editable = row.status !== "APPROVED";
      return {
        value: row.id,
        label: row.numberLabel,
        meta: editable ? `${date} · ${row.statusLabel}` : `${date} · 승인 완료 · 고칠 수 없음`,
        short: `${row.numberLabel} · ${date}`,
        editable,
        memo: row.memo,
      };
    }),
  ];
}

export const APPROVED_NOTE = "승인 완료한 회차는 상담 내용을 고칠 수 없습니다. 새 회차를 고르거나 승인을 풀어 주세요.";
