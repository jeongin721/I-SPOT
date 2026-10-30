# 사례 개인 식별 정보(서식 4 의 실명 · 생년월일 · 가족 정보) 요청 · 응답. API_CONTRACT 4절 '개인 식별 정보'.
#
# 이 값은 GET/PUT /cases/{id}/personal-info 와 POST /cases 의 personal_info 로만 오간다.
# 일반 사례 응답(CaseResponse)에는 넣지 않는다(목록의 child_name 은 with_child_name=true 일 때만).
# 서버는 이 값을 암호화해 저장한다(app/services/personal_info_service.py).

from datetime import date, datetime, timedelta, timezone
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.schemas.common import RequestModel

# 이름은 앞뒤 공백을 떼고 1~50자. 빈 이름은 보내지 않는다(null).
NameText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]
JobText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
DetailText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]

# 가족관계 표 줄 수 상한(서식 4 는 몇 줄이지만 넉넉히).
FAMILY_MAX_ROWS = 30

# 건강정도 세부 항목(10/30 디자인 CaseRegister · CaseIntake 의 건강정도 표, 서식 4 이름 그대로).
HealthKind = Literal["질병", "장애", "병원치료", "정신과 진단", "타기관 상담"]

_KST = timezone(timedelta(hours=9))
_EARLIEST_BIRTH_DATE = date(1900, 1, 1)


def _check_birth_date(value: Optional[date]) -> Optional[date]:
    """1900-01-01 ~ 오늘(한국 날짜). 값은 오류 문구에 넣지 않는다."""

    if value is None:
        return None

    if value < _EARLIEST_BIRTH_DATE or value > datetime.now(_KST).date():
        raise ValueError("생년월일은 1900-01-01 부터 오늘까지여야 합니다.")

    return value


class _Hidden:
    def __repr__(self) -> str:
        return "<가림>"


_HIDDEN = _Hidden()


class _HidesValues:
    """repr · str 에 값을 넣지 않는다(칸 이름만). 객체를 디버그 로그에 찍어도 실명이 새지 않게(Codex #127 R4).

    검증 오류 문구에도 입력값을 넣지 않는다(hide_input_in_errors) — 422 응답은 원래 값을 빼지만(main.py),
    ValidationError 를 그대로 문자열로 남기는 곳이 생겨도 새지 않게.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    def __repr_args__(self):
        for name in type(self).model_fields:
            yield name, _HIDDEN


class _PersonalRequest(_HidesValues, RequestModel):
    pass


class TargetPerson(_PersonalRequest):
    """사례관리대상자(대개 보호자)."""

    name: Optional[NameText] = None
    relation: Optional[ShortText] = None
    birth_date: Optional[date] = None

    check_birth_date = field_validator("birth_date")(_check_birth_date)


class Interviewee(_PersonalRequest):
    """면접대상자 / 관계."""

    name: Optional[NameText] = None
    relation: Optional[ShortText] = None


class FamilyMember(_PersonalRequest):
    """가족관계 표 한 줄(성명 · 관계 · 나이 · 종교 · 학력 · 직업 · 동거여부)."""

    name: NameText
    relation: Optional[ShortText] = None
    age: Optional[int] = Field(default=None, ge=0, le=150)
    religion: Optional[ShortText] = None
    education: Optional[ShortText] = None
    job: Optional[JobText] = None
    living_together: Optional[bool] = None


class HealthItem(_PersonalRequest):
    """건강정도 한 칸 — 있음(present) · 세부(횟수 · 기간 · 진단명 등)."""

    kind: HealthKind
    present: Optional[bool] = None
    detail: Optional[DetailText] = None


class HealthInfo(_PersonalRequest):
    """건강정도(대상자 이름 + 세부 항목). 같은 항목은 한 번만."""

    subject_name: Optional[NameText] = None
    items: List[HealthItem] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _unique_kinds(self) -> "HealthInfo":
        kinds = [item.kind for item in self.items]

        if len(kinds) != len(set(kinds)):
            raise ValueError("건강정도 항목이 겹칩니다.")

        return self


class PersonalInfoRequest(_PersonalRequest):
    """PUT /cases/{id}/personal-info 본문 · POST /cases 의 personal_info. 보낸 값으로 통째로 바꾼다(빠진 칸은 지움)."""

    child_name: Optional[NameText] = None
    child_birth_date: Optional[date] = None
    target_person: Optional[TargetPerson] = None
    interviewee: Optional[Interviewee] = None
    family_members: List[FamilyMember] = Field(default_factory=list, max_length=FAMILY_MAX_ROWS)
    health: Optional[HealthInfo] = None

    check_birth_date = field_validator("child_birth_date")(_check_birth_date)


class PersonalInfoResponse(_HidesValues, BaseModel):
    """복호화한 값. registered=false 면 아직 아무 칸도 저장하지 않은 사례다."""

    registered: bool = False
    child_name: Optional[str] = None
    child_birth_date: Optional[date] = None
    target_person: Optional[TargetPerson] = None
    interviewee: Optional[Interviewee] = None
    family_members: List[FamilyMember] = Field(default_factory=list)
    health: Optional[HealthInfo] = None
    updated_at: Optional[datetime] = None
