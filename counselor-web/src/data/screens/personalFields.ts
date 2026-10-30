// 서식 4 실명 · 가족 칸(대상아동 이름 · 생년월일 · 사례관리대상자 · 면접대상자 · 가족관계 표 · 건강정도)의 화면 값.
// 새 사례 등록(caseRegister.ts)과 초기면접지(caseIntake.ts)가 같이 쓴다. 입력 모델 · 보낼 값은 data/personalInfo.ts.
// 표 · 건강정도 모양은 components/PersonalTables.jsx(10/29 디자인 ftg · hs-*).

import { PERSONAL_HEALTH_KINDS } from "../../api/types";
import {
  BIRTH_DATE_MIN,
  EMPTY_FAMILY_ROW,
  FAMILY_MAX_ROWS,
  HEALTH_DETAIL_HINTS,
  HEALTH_DETAIL_MAX,
  PERSON_JOB_MAX,
  PERSON_NAME_MAX,
  PERSON_SHORT_MAX,
  todayKst,
  type FamilyRowInput,
  type PersonalInput,
  type PersonalTextKey,
} from "../personalInfo";

/** 사례관리대상자 관계 고르기(10/30 디자인). 서버는 30자 자유 글이라 다른 값이 저장돼 있으면 그 값도 붙여 보인다. */
const TARGET_RELATIONS = ["친부", "친모", "계부", "계모", "조부모", "친인척", "기타"];

const FAMILY_COLUMNS: [Exclude<keyof FamilyRowInput, "living">, string, number][] = [
  ["name", "성명", PERSON_NAME_MAX],
  ["relation", "관계", PERSON_SHORT_MAX],
  ["age", "나이", 3],
  ["religion", "종교", PERSON_SHORT_MAX],
  ["education", "학력", PERSON_SHORT_MAX],
  ["job", "직업", PERSON_JOB_MAX],
];

/** 고른 단추 · 고르지 않은 단추 모양(초기면접 고르기 단추와 같은 색). */
const pickStyle = (on: boolean) => ({
  bg: on ? "#F1EADA" : "#FFFFFF",
  bd: on ? "#2B2A26" : "#DAD5C9",
  fg: "#2B2A26",
  fw: on ? 700 : 400,
});

/**
 * personal 이 null 이면(값을 아직 못 받음) 빈 칸으로 보이고 고칠 수 없다(locked).
 * change 는 지금 입력으로 새 입력을 만드는 함수를 받는다.
 */
export function personalFieldValues(
  personal: PersonalInput | null,
  change: (next: (current: PersonalInput) => PersonalInput) => void,
  locked: boolean,
) {
  const off = locked || personal === null;
  const update = (next: (current: PersonalInput) => PersonalInput) => {
    if (!off) change(next);
  };
  const text = (key: PersonalTextKey, max?: number) => ({
    value: personal ? personal[key] : "",
    max,
    onChange: (event: { target: { value: string } }) => {
      const value = event.target.value;
      update((current) => ({ ...current, [key]: value }));
    },
  });
  const date = (key: PersonalTextKey) => ({ ...text(key), min: BIRTH_DATE_MIN, max: todayKst() });

  const relation = personal ? personal.targetRelation : "";
  const relationOptions = relation && !TARGET_RELATIONS.includes(relation) ? [...TARGET_RELATIONS, relation] : TARGET_RELATIONS;

  const rows = personal ? personal.family : [];
  const setRow = (index: number, patch: Partial<FamilyRowInput>) =>
    update((current) => ({
      ...current,
      family: current.family.map((row, at) => (at === index ? { ...row, ...patch } : row)),
    }));

  return {
    personalLocked: off,
    childName: text("childName", PERSON_NAME_MAX),
    childBirthDate: date("childBirthDate"),
    targetName: text("targetName", PERSON_NAME_MAX),
    targetRelation: text("targetRelation"),
    targetRelationOptions: relationOptions,
    targetBirthDate: date("targetBirthDate"),
    intervieweeName: text("intervieweeName", PERSON_NAME_MAX),
    intervieweeRelation: text("intervieweeRelation", PERSON_SHORT_MAX),
    family: {
      locked: off,
      columns: FAMILY_COLUMNS.map(([, label]) => label),
      rows: rows.map((row, index) => ({
        cells: FAMILY_COLUMNS.map(([key, label, max]) => ({
          label,
          max,
          numeric: key === "age",
          value: row[key],
          onChange: (event: { target: { value: string } }) => setRow(index, { [key]: event.target.value }),
        })),
        living: {
          value: row.living,
          onChange: (event: { target: { value: string } }) =>
            setRow(index, { living: event.target.value as FamilyRowInput["living"] }),
        },
        remove: () =>
          update((current) => {
            const family = current.family.filter((_, at) => at !== index);
            return { ...current, family: family.length > 0 ? family : [{ ...EMPTY_FAMILY_ROW }] };
          }),
      })),
      canAdd: !off && rows.length < FAMILY_MAX_ROWS,
      add: () =>
        update((current) =>
          current.family.length < FAMILY_MAX_ROWS
            ? { ...current, family: [...current.family, { ...EMPTY_FAMILY_ROW }] }
            : current,
        ),
    },
    health: {
      locked: off,
      subject: text("healthSubject", PERSON_NAME_MAX),
      rows: PERSONAL_HEALTH_KINDS.map((kind) => {
        const row = personal ? personal.health[kind] : { present: "", detail: "" };
        const setHealth = (patch: Partial<typeof row>) =>
          update((current) => ({ ...current, health: { ...current.health, [kind]: { ...current.health[kind], ...patch } } }));

        return {
          kind,
          // 다시 누르면 고른 것을 푼다(유 · 무를 모름으로 되돌린다).
          pickers: (["무", "유"] as const).map((label) => ({
            label,
            on: row.present === label,
            ...pickStyle(row.present === label),
            pick: () => setHealth({ present: row.present === label ? "" : label }),
          })),
          detail: {
            value: row.detail,
            max: HEALTH_DETAIL_MAX,
            placeholder: HEALTH_DETAIL_HINTS[kind],
            onChange: (event: { target: { value: string } }) => setHealth({ detail: event.target.value }),
          },
        };
      }),
    },
  };
}
