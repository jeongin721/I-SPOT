// 초기면접지 화면(CaseIntake · 사례 상세 안의 서식 4) 입력 값 · 보낼 값 · 담당 상담원 목록.
//
// 사례에 저장된 칸만 고치고, 바꾼 칸만 보낸다(PATCH /cases/{id} — 저장은 useCaseDetail 의 saveCase, API_CONTRACT 'PATCH /cases/{id}').
//  - 사례 제목 · 아동 별칭: 비울 수 없다(null 은 422).
//  - 성별 · 출생연도 · 사례 메모: 비우면 null 로 보낸다.
//  - 보호자 유형: 기타일 때만 관계 메모를 보낸다. 기타가 아닌 유형으로 바꾸면 Backend 가 메모를 지운다.
//  - ② 가정상황 · 아동 특성: 보내면 목록을 통째로 바꾼다(모두 빼면 []). 서식 순서로 보낸다(새 사례 등록과 같음).
//  - 담당 상담원: 관리자만 바꾼다(상담원이 보내면 403). 담당자를 비우는 기능은 없다.
// 개별사건번호는 수정 요청이 받지 않아(backend CaseUpdateRequest 에 칸이 없음) 읽기만 한다.
// 서식 4 의 나머지 칸은 새 사례 등록처럼 개인정보 저장 범위가 팀 결정 전이라 보내지 않는다(useCaseRegister.ts 머리말).
// 입력 확인 문구 · 길이 제한은 새 사례 등록(toCaseCreateRequest)과 같다.

import { useMemo } from "react";

import { auth } from "../api/endpoints";
import { GUARDIAN_LABELS, type CaseUpdateRequest, type User } from "../api/types";
import { adminKey } from "./adminAccess";
import type { AuthSession } from "./useAuthSession";
import type { CaseDetailView } from "./useCaseDetail";
import {
  BIRTH_YEAR_MIN,
  CASE_ALIAS_MAX,
  CASE_GENDER_MAX,
  CASE_NOTES_MAX,
  CASE_TITLE_MAX,
  GUARDIAN_NOTE_MAX,
  type CaseRegisterInput,
  type CounselorOption,
} from "./useCaseRegister";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS } from "./screens/intakeItems";
import { useRemote } from "./useRemote";

/**
 * 초기면접지 입력칸(화면 입력 그대로, 문자열). 새 사례 등록 입력과 같은 모양에서 개별사건번호만 뺐다(고칠 수 없음).
 * counselorId 는 지금 담당 상담원 ID 다(새 사례 등록의 '"" 면 본인' 과 다르다).
 */
export type IntakeForm = Omit<CaseRegisterInput, "caseNumber">;
export type IntakeField = keyof IntakeForm;

/** 사례의 서버 값으로 입력칸을 채운다. */
export function intakeFormOf(info: CaseDetailView): IntakeForm {
  return {
    title: info.title,
    alias: info.alias,
    gender: info.childGender,
    birthYear: info.childBirthYear === null ? "" : String(info.childBirthYear),
    guardianType: info.guardianType ?? "",
    guardianNote: info.guardianNote,
    notes: info.notes,
    childTraits: info.intakeChildTraits,
    familySituations: info.intakeFamilySituations,
    counselorId: info.counselorId,
  };
}

/** 순서는 보지 않고 같은 항목인가(caseDetail.ts 의 초기면접 수정과 같은 기준). */
function sameItems(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((item) => b.includes(item));
}

/**
 * 고친 칸(edits)을 서버 값(saved)과 견주어 보낼 값을 만든다. 고친 칸만 확인하고, 서버 값과 같아진 칸은 보내지 않는다.
 * 보낼 것이 없으면 payload 가 null. 문제가 있으면 { problem } 에 화면에 보일 문장. 서버가 최종으로 거절한다(422).
 */
export function toCaseUpdateRequest(
  edits: Partial<IntakeForm>,
  saved: IntakeForm,
  { isAdmin, thisYear = new Date().getFullYear() }: { isAdmin: boolean; thisYear?: number },
): { payload: CaseUpdateRequest | null; problem: null } | { payload: null; problem: string } {
  const fail = (problem: string) => ({ payload: null, problem });
  const payload: CaseUpdateRequest = {};

  if (edits.title !== undefined) {
    const title = edits.title.trim();

    if (!title) return fail("사례 제목을 입력해 주세요.");
    if (title.length > CASE_TITLE_MAX) return fail(`사례 제목은 ${CASE_TITLE_MAX}자까지 쓸 수 있습니다.`);
    if (title !== saved.title.trim()) payload.title = title;
  }

  if (edits.alias !== undefined) {
    const alias = edits.alias.trim();

    if (!alias) return fail("아동 별칭을 입력해 주세요(실명은 저장하지 않습니다).");
    if (alias.length > CASE_ALIAS_MAX) return fail(`아동 별칭은 ${CASE_ALIAS_MAX}자까지 쓸 수 있습니다.`);
    if (alias !== saved.alias.trim()) payload.child_alias = alias;
  }

  if (edits.gender !== undefined) {
    const gender = edits.gender.trim();

    if (gender.length > CASE_GENDER_MAX) return fail(`성별은 ${CASE_GENDER_MAX}자까지 쓸 수 있습니다.`);
    if (gender !== saved.gender.trim()) payload.child_gender = gender || null;
  }

  if (edits.birthYear !== undefined) {
    const text = edits.birthYear.trim();
    let year: number | null = null;

    if (text) {
      if (!/^\d{4}$/.test(text)) return fail("출생연도는 네 자리 숫자로 입력해 주세요(예: 2015).");
      year = Number(text);
      if (year < BIRTH_YEAR_MIN || year > thisYear) {
        return fail(`출생연도는 ${BIRTH_YEAR_MIN}년부터 ${thisYear}년까지 입력할 수 있습니다.`);
      }
    }
    if (year !== (saved.birthYear ? Number(saved.birthYear) : null)) payload.child_birth_year = year;
  }

  const savedType = saved.guardianType || null;
  const type = edits.guardianType !== undefined ? edits.guardianType || null : savedType;

  if (type && !(type in GUARDIAN_LABELS)) return fail("보호자 유형을 다시 골라 주세요.");
  if (type !== savedType) payload.guardian_type = type;
  // 관계 메모는 (바꾼 뒤) 유형이 기타일 때만 보낸다. 그 밖에 메모를 보내면 422 다.
  if (type === "OTHER" && edits.guardianNote !== undefined) {
    const note = edits.guardianNote.trim();
    const savedNote = savedType === "OTHER" ? saved.guardianNote.trim() : "";

    if (note.length > GUARDIAN_NOTE_MAX) return fail(`보호자 메모는 ${GUARDIAN_NOTE_MAX}자까지 쓸 수 있습니다.`);
    if (note !== savedNote) payload.guardian_note = note || null;
  }

  if (edits.notes !== undefined) {
    const notes = edits.notes.trim();

    if (notes.length > CASE_NOTES_MAX) return fail(`사례 메모는 ${CASE_NOTES_MAX.toLocaleString()}자까지 쓸 수 있습니다.`);
    if (notes !== saved.notes.trim()) payload.notes = notes || null;
  }

  // 초기면접 항목은 서식 순서로 보낸다(서식에 없는 값은 빠진다).
  if (edits.childTraits !== undefined) {
    const picked = edits.childTraits;
    const traits = INTAKE_CHILD_ITEMS.filter((item) => picked.includes(item));

    if (!sameItems(traits, saved.childTraits)) payload.intake_child_traits = traits;
  }

  if (edits.familySituations !== undefined) {
    const picked = edits.familySituations;
    const homes = INTAKE_HOME_ITEMS.filter((item) => picked.includes(item));

    if (!sameItems(homes, saved.familySituations)) payload.intake_family_situations = homes;
  }

  if (isAdmin && edits.counselorId && edits.counselorId !== saved.counselorId) payload.counselor_id = edits.counselorId;

  return { payload: Object.keys(payload).length > 0 ? payload : null, problem: null };
}

export interface IntakeCounselors {
  /** 관리자일 때 담당 상담원으로 고를 수 있는 활성 계정(이름순, 본인 포함). 관리자가 아니면 빈 목록. */
  options: CounselorOption[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * 관리자만 담당 상담원 목록(GET /auth/users)을 부른다. 상담원이면 부르지 않는다.
 * 계정이 바뀌면 key 가 바뀌어 앞 계정이 받은 목록을 보이지 않는다(adminKey).
 */
export function useIntakeCounselors(session: AuthSession): IntakeCounselors {
  const users = useRemote<User[]>(
    adminKey(session, true, "intake-counselors"),
    auth.listUsers,
    "담당 상담원 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );

  const options = useMemo(() => {
    if (!session.isAdmin) return [];

    // 정지된 계정은 Backend 가 거절한다(400). 지금 담당자가 목록에 없으면 화면 값 함수가 따로 붙인다.
    return (users.data ?? [])
      .filter((user) => user.is_active)
      .sort((a, b) => a.name.localeCompare(b.name, "ko"))
      .map((user) => ({ id: user.id, label: `${user.name} (${user.role === "ADMIN" ? "관리자" : "상담원"}) · ${user.email}` }));
  }, [session.isAdmin, users.data]);

  return {
    options,
    loading: session.isAdmin && users.loading,
    error: session.isAdmin ? users.error : null,
    reload: users.reload,
  };
}
