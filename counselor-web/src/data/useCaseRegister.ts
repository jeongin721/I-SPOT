// 새 사례 등록 훅(POST /cases). 관리자면 담당 상담사로 고를 계정 목록(GET /auth/users)도 부른다.
//
// 서버가 받는 칸만 보낸다: 제목 · 아동 별칭(필수), 사례번호 · 출생연도 · 성별 · 보호자 유형 · 보호자 메모(기타일 때만) · 사례 메모,
// 초기면접(서식 4 ②)의 아동 특성 · 가정상황(서식 항목만), 담당 상담사(관리자만, 빼면 요청자 본인).
// Backend 는 아동 · 보호자 실명을 저장하지 않는다(API types Case · GuardianType).
// 서식 4(초기면접지)의 나머지 칸(실명 · 생년월일 · 사례관리대상자 · 신고 · 연계일 · 학대유형 · 조치 · 가족 · 문제력 · 태도 · 소견)은
// 개인정보 저장 범위가 팀 결정 전이라 보내지 않는다. 다른 칸(사례 메모 등)에 옮겨 담지도 않는다.
//
// 한 번에 한 요청만 보낸다. 성공하면 만든 사례를 돌려주고, 그 뒤에는 다시 보내지 않는다(같은 사례를 두 번 만들지 않게).
// 입력 · 요청 상태는 로그인한 계정 하나의 것이다. 화면은 계정이 확인된 동안에만 이 훅을 쓰고, 계정이 바뀌면 새로 만든다
// (CaseRegister.jsx 의 key). 그래도 요청을 보낸 뒤 계정이 바뀌었거나 화면을 떠났으면 그 응답(성공 · 실패)은 버린다.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { auth, cases } from "../api/endpoints";
import { GUARDIAN_LABELS, type Case, type CaseCreateRequest, type GuardianType, type User } from "../api/types";
import type { AuthSession } from "./useAuthSession";
import { adminKey } from "./adminAccess";
import { INTAKE_CHILD_ITEMS, INTAKE_HOME_ITEMS } from "./screens/intakeItems";
import { errorMessage, useRemote } from "./useRemote";

/** Backend 제한(backend/app/schemas/case.py CaseCreateRequest). */
export const CASE_TITLE_MAX = 200;
export const CASE_ALIAS_MAX = 100;
export const CASE_NUMBER_MAX = 50;
export const CASE_GENDER_MAX = 10;
export const GUARDIAN_NOTE_MAX = 100;
export const CASE_NOTES_MAX = 4000;
export const BIRTH_YEAR_MIN = 1900;

/** 화면 입력 그대로(문자열). 보내기 전에 toCaseCreateRequest 로 바꾼다. */
export interface CaseRegisterInput {
  title: string;
  alias: string;
  caseNumber: string;
  /** "" · "여" · "남". Backend 는 10자 이하 자유 문자열로 받는다. */
  gender: string;
  birthYear: string;
  guardianType: GuardianType | "";
  guardianNote: string;
  notes: string;
  /** 신고접수일 · 사례연계일 · 최초면접일(날짜 입력칸 값 YYYY-MM-DD, 비우면 ""). */
  reportDate: string;
  linkedDate: string;
  firstInterviewDate: string;
  /** 초기면접에서 고른 아동 특성 · 가정상황(서식 4 항목, 고른 순서). */
  childTraits: string[];
  familySituations: string[];
  /** 관리자가 고른 담당 상담사. "" 면 본인. */
  counselorId: string;
}

export const EMPTY_CASE_INPUT: CaseRegisterInput = {
  title: "",
  alias: "",
  caseNumber: "",
  gender: "",
  birthYear: "",
  guardianType: "",
  guardianNote: "",
  notes: "",
  reportDate: "",
  linkedDate: "",
  firstInterviewDate: "",
  childTraits: [],
  familySituations: [],
  counselorId: "",
};

/** 날짜 셋 이름(입력 키 · 서버 키 · 화면 이름). */
export const CASE_DATE_FIELDS = [
  { key: "reportDate", api: "report_date", label: "신고접수일" },
  { key: "linkedDate", api: "linked_date", label: "사례연계일" },
  { key: "firstInterviewDate", api: "first_interview_date", label: "최초면접일" },
] as const;

/** 날짜 입력값 확인. 비었으면 null, 틀리면 문제 문장. 서버와 같이 1900~2100 날짜만. */
export function checkCaseDate(value: string, label: string): { value: string | null; problem: string | null } {
  const text = value.trim();
  if (!text) return { value: null, problem: null };
  const matched = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  const parsed = matched ? new Date(`${text}T00:00:00Z`) : null;
  if (!matched || !parsed || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== text) {
    return { value: null, problem: `${label}을 연도-월-일로 입력해 주세요.` };
  }
  const year = Number(matched[1]);
  if (year < 1900 || year > 2100) return { value: null, problem: `${label}은 1900년부터 2100년까지 입력할 수 있습니다.` };
  return { value: text, problem: null };
}

/**
 * 보낼 값으로 바꾼다. 문제가 있으면 { problem } 에 화면에 보일 문장. 서버가 최종으로 거절한다(422).
 * meId 는 로그인한 사람. 관리자가 아니면 담당 상담사를 보내지 않는다.
 */
export function toCaseCreateRequest(
  input: CaseRegisterInput,
  { isAdmin, meId, thisYear = new Date().getFullYear() }: { isAdmin: boolean; meId: string | null; thisYear?: number },
): { payload: CaseCreateRequest; problem: null } | { payload: null; problem: string } {
  const fail = (problem: string) => ({ payload: null, problem });
  const title = input.title.trim();
  const alias = input.alias.trim();
  const caseNumber = input.caseNumber.trim();
  const gender = input.gender.trim();
  const birthYearText = input.birthYear.trim();
  const note = input.guardianNote.trim();
  const notes = input.notes.trim();

  if (!title) return fail("사례 제목을 입력해 주세요.");
  if (title.length > CASE_TITLE_MAX) return fail(`사례 제목은 ${CASE_TITLE_MAX}자까지 쓸 수 있습니다.`);
  if (!alias) return fail("아동 별칭을 입력해 주세요(실명은 저장하지 않습니다).");
  if (alias.length > CASE_ALIAS_MAX) return fail(`아동 별칭은 ${CASE_ALIAS_MAX}자까지 쓸 수 있습니다.`);
  if (caseNumber.length > CASE_NUMBER_MAX) return fail(`개별사건번호는 ${CASE_NUMBER_MAX}자까지 쓸 수 있습니다.`);
  if (gender.length > CASE_GENDER_MAX) return fail(`성별은 ${CASE_GENDER_MAX}자까지 쓸 수 있습니다.`);

  let birthYear: number | null = null;
  if (birthYearText) {
    if (!/^\d{4}$/.test(birthYearText)) return fail("출생연도는 네 자리 숫자로 입력해 주세요(예: 2015).");
    birthYear = Number(birthYearText);
    if (birthYear < BIRTH_YEAR_MIN || birthYear > thisYear) {
      return fail(`출생연도는 ${BIRTH_YEAR_MIN}년부터 ${thisYear}년까지 입력할 수 있습니다.`);
    }
  }

  const guardianType = input.guardianType || null;
  if (guardianType && !(guardianType in GUARDIAN_LABELS)) return fail("보호자 유형을 다시 골라 주세요.");
  if (guardianType === "OTHER" && note.length > GUARDIAN_NOTE_MAX) {
    return fail(`보호자 메모는 ${GUARDIAN_NOTE_MAX}자까지 쓸 수 있습니다.`);
  }
  if (notes.length > CASE_NOTES_MAX) return fail(`사례 메모는 ${CASE_NOTES_MAX.toLocaleString()}자까지 쓸 수 있습니다.`);

  const payload: CaseCreateRequest = { title, child_alias: alias };
  for (const field of CASE_DATE_FIELDS) {
    const checked = checkCaseDate(input[field.key], field.label);
    if (checked.problem) return fail(checked.problem);
    if (checked.value) payload[field.api] = checked.value;
  }
  if (caseNumber) payload.case_number = caseNumber;
  if (gender) payload.child_gender = gender;
  if (birthYear !== null) payload.child_birth_year = birthYear;
  if (guardianType) payload.guardian_type = guardianType;
  // 보호자 메모는 보호자 유형이 기타일 때만 보낼 수 있다(그 밖에는 422).
  if (guardianType === "OTHER" && note) payload.guardian_note = note;
  if (notes) payload.notes = notes;
  // 초기면접 항목은 서식 순서로 보낸다(서식에 없는 값은 빠진다).
  const childTraits = INTAKE_CHILD_ITEMS.filter((item) => input.childTraits.includes(item));
  const familySituations = INTAKE_HOME_ITEMS.filter((item) => input.familySituations.includes(item));
  if (childTraits.length) payload.intake_child_traits = childTraits;
  if (familySituations.length) payload.intake_family_situations = familySituations;
  if (isAdmin && input.counselorId && input.counselorId !== meId) payload.counselor_id = input.counselorId;

  return { payload, problem: null };
}

export interface CounselorOption {
  id: string;
  label: string;
}

export interface CaseRegisterState {
  /** 관리자일 때 담당 상담사로 고를 수 있는 다른 활성 계정(이름순, 본인 제외). 관리자가 아니면 빈 목록. */
  counselors: CounselorOption[];
  counselorsLoading: boolean;
  counselorsError: string | null;
  reloadCounselors: () => void;
  submitting: boolean;
  /** 입력 확인 · 서버 거절 문구. */
  error: string | null;
  /** 만든 사례. 만들기 전이면 null. */
  created: Case | null;
  /** 성공하면 만든 사례, 실패하거나 이미 보내는 중 · 이미 만들었으면 null. */
  submit: (input: CaseRegisterInput) => Promise<Case | null>;
}

export function useCaseRegister(session: AuthSession): CaseRegisterState {
  const me = session.status === "signedIn" ? session.me : null;
  const users = useRemote<User[]>(
    adminKey(session, true, "register-counselors"),
    auth.listUsers,
    "담당 상담사 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Case | null>(null);
  // 같은 순간의 두 번째 누름 · 만든 뒤 다시 누름을 막는다(state 는 바로 바뀌지 않아 ref 로도 든다).
  const inFlight = useRef(false);
  const done = useRef(false);
  // 지금 로그인한 계정 · 화면에 붙어 있는가. 늦게 온 응답을 버릴지 보는 데 쓴다.
  const currentUser = useRef<string | null>(me?.id ?? null);
  currentUser.current = me?.id ?? null;
  const alive = useRef(false);

  useEffect(() => {
    alive.current = true;

    return () => {
      alive.current = false;
    };
  }, []);

  const counselors = useMemo(() => {
    if (!session.isAdmin) return [];

    // 본인은 화면의 '본인'(기본값) 칸이 맡는다. 정지된 계정은 Backend 가 거절한다(400).
    return (users.data ?? [])
      .filter((user) => user.is_active && user.id !== me?.id)
      .sort((a, b) => a.name.localeCompare(b.name, "ko"))
      .map((user) => ({ id: user.id, label: `${user.name} (${user.role === "ADMIN" ? "관리자" : "상담원"}) · ${user.email}` }));
  }, [session.isAdmin, users.data, me?.id]);

  const submit = useCallback(
    async (input: CaseRegisterInput) => {
      if (!me || inFlight.current || done.current) return null;

      const checked = toCaseCreateRequest(input, { isAdmin: session.isAdmin, meId: me.id });

      if (checked.problem !== null) {
        setError(checked.problem);
        return null;
      }

      const forUser = me.id;
      const stillMine = () => alive.current && currentUser.current === forUser;

      inFlight.current = true;
      setSubmitting(true);
      setError(null);

      try {
        const result = await cases.create(checked.payload);

        done.current = true;
        // 그사이 다른 계정으로 바뀌었거나 화면을 떠났으면 결과를 화면에 쓰지 않고 이동도 하지 않는다
        // (사례는 보낸 계정으로 이미 만들어졌다 — 취소된 것이 아니다).
        if (!stillMine()) return null;

        setCreated(result);

        return result;
      } catch (caught) {
        // 401 · 403 PASSWORD_CHANGE_REQUIRED 는 client 가 이벤트로 알리고, 화면은 useAuthSession 상태로 움직인다.
        if (stillMine() && !(caught instanceof ApiError && caught.isUnauthorized)) {
          setError(errorMessage(caught, "사례를 등록하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }

        return null;
      } finally {
        inFlight.current = false;
        if (alive.current) setSubmitting(false);
      }
    },
    [me, session.isAdmin],
  );

  return {
    counselors,
    counselorsLoading: session.isAdmin && users.loading,
    counselorsError: session.isAdmin ? users.error : null,
    reloadCounselors: users.reload,
    submitting,
    error,
    created,
    submit,
  };
}
