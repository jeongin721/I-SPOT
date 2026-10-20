# 공통 요청/응답 Schema.

import re
from typing import Any, ClassVar, Dict, FrozenSet, Optional

from pydantic import AfterValidator, BaseModel, ValidationInfo, field_validator

# 사유 문구에는 받은 값을 넣지 않는다. 오류 응답 · 로그에 원문이 나가지 않게 한다.
UNSTORABLE_TEXT_MESSAGE = "저장할 수 없는 문자(NUL · 짝 없는 서로게이트)가 있습니다."

# NUL(U+0000)과 짝 없는 서로게이트(U+D800~U+DFFF).
_UNSTORABLE_CHARACTER = re.compile("[\x00\ud800-\udfff]")


def has_unstorable_character(value: str) -> bool:
    """
    PostgreSQL 이 저장할 수 없는 글자가 있는가.

    - NUL(U+0000): text · JSONB 칸에 넣거나 SQL 파라미터로 보내면 DataError 로 500 이 된다.
    - 짝 없는 서로게이트(U+D800~U+DFFF): UTF-8 로 바꿀 수 없어 500 이 된다.
    둘 다 JSON 이스케이프(\\u0000, \\ud800)로 들어올 수 있다. 저장 단계까지 가면
    오류 로그에 원문이 실릴 수 있어 입력에서 막는다.
    본문 검증은 이벤트 루프에서 돈다. 글자마다 파이썬으로 훑으면 2MB 본문 하나가 0.3초쯤
    루프를 막아, 미리 컴파일한 정규식으로 한 번에 찾는다.
    """

    return _UNSTORABLE_CHARACTER.search(value) is not None


def _contains_unstorable_text(value: Any) -> bool:
    """글자 · 목록 · 튜플 · 사전(키와 값)을 끝까지 훑는다. 중첩 모델은 그 모델이 따로 검사한다."""

    if isinstance(value, str):
        return has_unstorable_character(value)

    if isinstance(value, (list, tuple, set, frozenset)):
        # 글자만 든 목록은 이어 붙여 한 번에 찾는다. 항목 수 제한이 없는 칸도 있어 항목마다 파이썬으로 돌지 않는다.
        # 찾는 글자는 한 글자씩이라 이어 붙여도 없던 것이 생기거나 있던 것이 사라지지 않는다.
        try:
            return has_unstorable_character("".join(value))
        except TypeError:
            return any(_contains_unstorable_text(item) for item in value)

    if isinstance(value, dict):
        return any(
            _contains_unstorable_text(key) or _contains_unstorable_text(item)
            for key, item in value.items()
        )

    return False


def reject_unstorable_text(value: Any) -> Any:
    """저장할 수 없는 글자가 있으면 ValueError(422) 를 낸다. 쿼리의 StorableQueryText 표시와 RequestModel 이 함께 쓴다."""

    if _contains_unstorable_text(value):
        raise ValueError(UNSTORABLE_TEXT_MESSAGE)

    return value


# 글자 쿼리 파라미터의 Annotated 맨 뒤에 붙인다. 본문은 RequestModel 이 막지만 쿼리는 따로 붙여야 한다.
# 쿼리는 저장되지 않아도 SQL 파라미터로 쓰이고, PostgreSQL 은 NUL 이 든 파라미터를 거절한다.
#
#   search: Annotated[Optional[str], Query(max_length=100), StorableQueryText] = None
#
# Query(...) 보다 앞에 두면 max_length · pattern 이 이 검사를 거친 값에 걸려, OpenAPI 에서 pattern 이 빠지고
# maxLength 자리가 바뀌며 오류 사유도 pydantic 의 다른 문구가 된다(tests/test_request_model_guard.py 가 순서도 본다).
# 타입이 아니라 표시라 Annotated[StorableQueryText, ...] 처럼 맨 앞에 쓰면 불러올 때 바로 오류가 난다.
StorableQueryText = AfterValidator(reject_unstorable_text)


class RequestModel(BaseModel):
    """
    요청 본문 모델의 공통 부모.

    모든 칸의 글자(목록 · 튜플 · 사전 안까지)에서 NUL 과 짝 없는 서로게이트를 422 로 거절한다.
    요청 본문 모델과 그 안에 든 모델은 모두 이것을 상속한다(tests/test_request_model_guard.py 가 확인).
    응답 모델과 계약 모델(contracts.py)에는 붙이지 않는다. STT · AI 결과 검증까지 막힌다.
    """

    # 검사하지 않는 칸. 평문이 저장되지 않고 SQL 파라미터로도 쓰이지 않는 비밀번호 확인 칸만 둔다.
    unstorable_text_exempt_fields: ClassVar[FrozenSet[str]] = frozenset()

    @field_validator("*", mode="after")
    @classmethod
    def _reject_unstorable_text(cls, value: Any, info: ValidationInfo) -> Any:
        if info.field_name in cls.unstorable_text_exempt_fields:
            return value

        return reject_unstorable_text(value)


class SessionErrorInfo(BaseModel):
    """
    재시도 가능한 실패 정보.

    Frontend 는 이 값이 존재하면 재시도 버튼을 노출할 수 있다.
    """

    code: str
    message: str


class HealthStatus(BaseModel):
    status: str
    app_name: str
    env: str
    database: str
    stt_provider: str
    ai_provider: str
    detail: Optional[Dict[str, Any]] = None
