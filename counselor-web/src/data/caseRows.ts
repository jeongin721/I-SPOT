// Backend 사례(Case) → 사례 목록 한 줄.
//
// 화면 배치와 상관없이 쓸 수 있게 문자열만 만든다. 어느 칸에 어떻게 놓을지는 화면이 정한다.
//
// Backend 에 없는 값은 다른 값으로 대신 채우지 않는다(specs 대응표 "없는 값을 다른 값으로 대체하지 않기").
//  - 아동 실명: 목록을 with_child_name=true 로 부른 줄에만 있다(암호화 저장, 미등록이면 null). 이름 칸은 실명, 없으면 별칭.
//  - 신고접수일: 없다. 사례 생성일(created_at)은 신고접수일이 아니다.
//  - 위험도(상 · 중 · 하): 사례 단위 값이 없다. AI 참고 신호로 채우면 안 된다.
//  - 정확한 나이: 출생연도만 있다.

import type { CaseListItem, CaseStatus } from "../api/types";
import { toDateOnly } from "./time";

/** Backend 가 값을 주지 않아 비워 둔 칸에 쓰는 표시. */
export const NOT_PROVIDED = "—";

export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  ACTIVE: "진행",
  CLOSED: "종결",
};

export interface CaseRow {
  /** Backend 조회에 쓰는 UUID. 화면에 보이는 사례 ID(caseNumber)와 다르다. */
  id: string;
  /** 화면에 보이는 사례 ID(예: C-2026-0001). */
  caseNumber: string;
  /** 아동 별칭. 실명이 아니다. */
  alias: string;
  /** 아동 실명. 목록을 실명과 함께 부르지 않았거나 등록 전이면 null. */
  realName: string | null;
  /** 화면 이름 칸: 실명, 없으면 별칭. */
  name: string;
  /** 아바타에 쓰는 첫 글자(이름 칸 기준). */
  initial: string;
  /** "2016년생". 출생연도가 없으면 NOT_PROVIDED. */
  birthYearLabel: string;
  /**
   * 사례의 last_session_at(YYYY-MM-DD). 회차가 없으면 NOT_PROVIDED.
   * Backend 는 상담 일시를 넣지 않은 회차를 등록일로 채워 계산하므로 '최근 상담일' 로 보이면 안 된다.
   */
  lastSessionDate: string;
  /** 담당 상담사 이름. 계정이 지워졌으면 NOT_PROVIDED. */
  counselorName: string;
  status: CaseStatus;
  statusLabel: string;
  /** Backend 에 없는 값. 팀 결정 전까지 항상 NOT_PROVIDED. */
  reportDate: string;
  /** Backend 에 없는 값. 팀 결정 전까지 항상 NOT_PROVIDED. */
  riskLabel: string;
}

export function toCaseRow(source: CaseListItem): CaseRow {
  const alias = source.child_alias.trim();
  const realName = source.child_name?.trim() || null;
  const name = realName ?? alias;

  return {
    id: source.id,
    caseNumber: source.case_number,
    alias,
    realName,
    name,
    initial: name ? Array.from(name)[0] : NOT_PROVIDED,
    birthYearLabel: source.child_birth_year ? `${source.child_birth_year}년생` : NOT_PROVIDED,
    lastSessionDate: toDateOnly(source.last_session_at) || NOT_PROVIDED,
    counselorName: source.counselor_name ?? NOT_PROVIDED,
    status: source.status,
    statusLabel: CASE_STATUS_LABELS[source.status],
    reportDate: NOT_PROVIDED,
    riskLabel: NOT_PROVIDED,
  };
}
