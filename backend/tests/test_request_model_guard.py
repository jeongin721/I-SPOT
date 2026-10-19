# 요청 모델 누락 방지 테스트 (app/schemas/common.py 의 RequestModel · StorableQueryText).
#
# 저장할 수 없는 문자(NUL · 짝 없는 서로게이트) 검사는 요청 본문 모델이 RequestModel 을 상속해야,
# 글자 쿼리는 Annotated 맨 뒤에 StorableQueryText 를 붙여야 걸린다. 새 요청 모델 · 쿼리를 만들며 빠뜨리거나
# Query(...) 보다 앞에 두면(제약이 검사 뒤의 값에 걸려 OpenAPI · 오류 사유가 바뀐다) 여기서 실패한다.
#
# fastapi 0.141.1 의 app.routes 에는 /health 만 APIRoute 로 나온다. 포함한 라우터는 _IncludedRouter 로
# 감싸져 있어 original_router 를 따라 내려가야 한다. 비공개 속성이라 FastAPI 를 올리면 바뀔 수 있으므로,
# 찾은 수를 최소 개수 · OpenAPI 문서와 맞춰 보아 아무것도 검사하지 않고 통과하지 않게 한다.

import sys
import typing
from typing import Annotated, Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

import pytest
from fastapi import APIRouter, FastAPI, Query
from fastapi.routing import APIRoute
from pydantic import AfterValidator, BaseModel, ValidationError

from app.main import app
from app.schemas.common import (
    RequestModel,
    StorableQueryText,
    has_unstorable_character,
    reject_unstorable_text,
)

# 지금 본문이 있는 라우트 수(음성 업로드의 자동 생성 모델은 뺀다). 줄면 순회가 깨진 것이다.
MIN_BODY_ROUTES = 13

# 검사하지 않는 칸. 평문이 저장되지 않고 SQL 파라미터로도 쓰이지 않는 로그인 · 현재 비밀번호뿐이다.
EXPECTED_EXEMPT_FIELDS = {
    ("LoginRequest", "password"),
    ("PasswordChangeRequest", "current_password"),
}


# =========================================================
# 라우트 · 모델 훑기
# =========================================================

def _api_routes(routes: List[Any]) -> Iterator[APIRoute]:
    for route in routes:
        if isinstance(route, APIRoute):
            yield route

        included = getattr(route, "original_router", None)

        if included is not None:
            yield from _api_routes(included.routes)


def _query_params(dependant) -> Iterator[Any]:
    yield from dependant.query_params

    for sub in dependant.dependencies:
        yield from _query_params(sub)


def _types_in(annotation: Any) -> Iterator[Any]:
    """Optional · List · Dict · Annotated 안의 타입을 모두 꺼낸다."""

    yield annotation

    for arg in typing.get_args(annotation):
        yield from _types_in(arg)


def _models_in(annotation: Any) -> Iterator[type]:
    for found in _types_in(annotation):
        if isinstance(found, type) and issubclass(found, BaseModel):
            yield found


def _is_auto_body(model: type) -> bool:
    # File · Form 을 받는 라우트에 FastAPI 가 만드는 본문 모델(예: Body_upload_audio_…).
    return model.__name__.startswith("Body_") and model.__module__.startswith("fastapi.")


def _query_text_problem(param) -> Optional[str]:
    """글자 쿼리에 StorableQueryText 가 없거나 맨 뒤가 아니면 그 내용을 돌려준다."""

    # Annotated 에 적은 순서대로 들어 있다(Query 의 max_length · pattern 도 여기 풀려 들어온다).
    metadata = list(param.field_info.metadata)
    checks = [
        index
        for index, item in enumerate(metadata)
        if isinstance(item, AfterValidator) and item.func is reject_unstorable_text
    ]

    if not checks:
        return "가 StorableQueryText 를 쓰지 않음"

    # 검사 뒤에 제약이 있으면 제약이 검사 뒤의 값에 걸려 OpenAPI 와 오류 사유가 바뀐다.
    if checks[-1] != len(metadata) - 1:
        return "의 StorableQueryText 가 Annotated 맨 뒤에 있지 않음"

    return None


def _collect(target: FastAPI) -> Tuple[List[str], Dict[str, int]]:
    """검사를 빠뜨린 곳과, 찾은 라우트 · 모델 · 쿼리 수를 돌려준다."""

    problems: List[str] = []
    counts = {"routes": 0, "body_routes": 0, "models": 0, "str_queries": 0}
    seen: Set[type] = set()

    def check_model(model: type, where: str) -> None:
        if model in seen:
            return

        seen.add(model)
        counts["models"] += 1

        if not issubclass(model, RequestModel):
            problems.append(f"{where}: {model.__name__} 가 RequestModel 을 상속하지 않음")

        for name, field in model.model_fields.items():
            for nested in _models_in(field.annotation):
                check_model(nested, f"{where} → {model.__name__}.{name}")

    for route in _api_routes(target.routes):
        counts["routes"] += 1
        where = f"{sorted(route.methods)} {route.path}"

        if route.body_field is not None:
            counts["body_routes"] += 1

            for model in _models_in(route.body_field.field_info.annotation):
                if _is_auto_body(model):
                    # 자동 모델은 상속을 바꿀 수 없다. 대신 글자 칸이 생기면 알린다.
                    for name, field in model.model_fields.items():
                        if str in set(_types_in(field.annotation)):
                            problems.append(f"{where}: 자동 본문 모델의 글자 칸 {name}")

                    continue

                check_model(model, where)

        for param in _query_params(route.dependant):
            if str not in set(_types_in(param.field_info.annotation)):
                continue

            counts["str_queries"] += 1
            problem = _query_text_problem(param)

            if problem is not None:
                problems.append(f"{where}: 쿼리 {param.name} {problem}")

    return problems, counts


def _openapi_counts(target: FastAPI) -> Dict[str, int]:
    """같은 수를 OpenAPI 문서에서 센다(비공개 속성 순회와 맞춰 보기용)."""

    counts = {"body_routes": 0, "str_queries": 0}

    for operations in target.openapi()["paths"].values():
        for operation in operations.values():
            if "requestBody" in operation:
                counts["body_routes"] += 1

            for param in operation.get("parameters", []):
                schema = param.get("schema", {})
                options = schema.get("anyOf", [schema])

                if param["in"] == "query" and any(
                    option.get("type") == "string" and "format" not in option and "enum" not in option
                    for option in options
                ):
                    counts["str_queries"] += 1

    return counts


# =========================================================
# 실제 앱
# =========================================================

def test_every_request_body_and_text_query_is_checked() -> None:
    problems, counts = _collect(app)

    assert problems == []
    # 순회가 깨져 아무것도 찾지 못하면 빈 통과가 되므로 수를 함께 본다.
    assert counts["body_routes"] - 1 >= MIN_BODY_ROUTES  # 음성 업로드(자동 모델) 하나를 뺀다
    assert counts["models"] >= MIN_BODY_ROUTES
    assert counts["str_queries"] >= 1
    assert _openapi_counts(app) == {
        "body_routes": counts["body_routes"],
        "str_queries": counts["str_queries"],
    }


def test_only_password_checks_are_exempt() -> None:
    exempt = set()
    pending = list(RequestModel.__subclasses__())

    while pending:
        model = pending.pop()
        pending.extend(model.__subclasses__())

        for name in model.unstorable_text_exempt_fields:
            assert name in model.model_fields, f"{model.__name__}.{name} 는 없는 칸"
            exempt.add((model.__name__, name))

    assert exempt == EXPECTED_EXEMPT_FIELDS


# =========================================================
# 빠뜨리면 실제로 잡히는지
# =========================================================

class _PlainBody(BaseModel):
    text: str


class _PlainItem(BaseModel):
    text: str


class _GuardedWithPlainItem(RequestModel):
    items: List[_PlainItem]


class _GuardedBody(RequestModel):
    text: str


def _probe_app() -> FastAPI:
    inner = APIRouter(prefix="/probe")

    @inner.post("/plain")
    def plain(payload: _PlainBody) -> None:
        return None

    @inner.post("/nested")
    def nested(payload: _GuardedWithPlainItem) -> None:
        return None

    @inner.post("/guarded")
    def guarded(payload: _GuardedBody) -> None:
        return None

    @inner.get("/plain-query")
    def plain_query(search: Annotated[Optional[str], Query(max_length=10)] = None) -> None:
        return None

    @inner.get("/guarded-query")
    def guarded_query(
        search: Annotated[Optional[str], Query(max_length=10), StorableQueryText] = None,
    ) -> None:
        return None

    @inner.get("/wrong-order-query")
    def wrong_order_query(
        search: Annotated[Optional[str], StorableQueryText, Query(max_length=10)] = None,
    ) -> None:
        return None

    outer = APIRouter()
    outer.include_router(inner)

    probe = FastAPI()
    probe.include_router(outer, prefix="/api")

    return probe


def test_guard_reports_missing_inheritance_and_query_type() -> None:
    problems, counts = _collect(_probe_app())

    assert counts["body_routes"] == 3
    assert sorted(problems) == sorted(
        [
            "['POST'] /probe/plain: _PlainBody 가 RequestModel 을 상속하지 않음",
            "['POST'] /probe/nested → _GuardedWithPlainItem.items: _PlainItem 가 RequestModel 을 상속하지 않음",
            "['GET'] /probe/plain-query: 쿼리 search 가 StorableQueryText 를 쓰지 않음",
            "['GET'] /probe/wrong-order-query: 쿼리 search 의 StorableQueryText 가 Annotated 맨 뒤에 있지 않음",
        ]
    )


# =========================================================
# 검사 함수
# =========================================================

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("가상 글 🙂\n\t", False),
        ("퟿", False),  # 서로게이트 범위 바로 밖
        ("가상\x00", True),
        ("가상\ud800", True),
        ("\udfff가상", True),
    ],
)
def test_has_unstorable_character(text: str, expected: bool) -> None:
    assert has_unstorable_character(text) is expected


class _Shapes(RequestModel):
    note: Optional[str] = None
    tags: List[str] = []
    pair: Optional[Tuple[str, str]] = None
    labels: Dict[str, str] = {}


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"note": "가상\x00"}, "note"),
        ({"tags": ["가상", "가상\ud800"]}, "tags"),
        ({"pair": ("가상", "\x00")}, "pair"),
        ({"labels": {"가상\x00": "값"}}, "labels"),  # 키
        ({"labels": {"키": "\udfff"}}, "labels"),  # 값
    ],
)
def test_request_model_checks_text_inside_containers(data: Dict[str, Any], field: str) -> None:
    with pytest.raises(ValidationError) as raised:
        _Shapes.model_validate(data)

    errors = raised.value.errors()

    assert [error["loc"][0] for error in errors] == [field]
    # 사유 문구에 받은 값을 넣지 않는다.
    assert "가상" not in errors[0]["msg"]


def test_request_model_keeps_normal_values() -> None:
    model = _Shapes(note="가상 🙂\n", tags=["가", "나"], pair=("a", "b"), labels={"키": "값"})

    assert model.note == "가상 🙂\n"
    assert model.labels == {"키": "값"}


def _count_python_steps(run: Callable[[], Any]) -> int:
    """run 을 부르는 동안 파이썬이 실행한 단계(함수 호출 · 줄 · 반환) 수를 센다."""

    steps = 0

    def tracer(frame: Any, event: str, arg: Any) -> Any:
        nonlocal steps
        steps += 1
        return tracer

    previous = sys.gettrace()
    sys.settrace(tracer)

    try:
        run()
    finally:
        sys.settrace(previous)

    return steps


def test_request_model_check_does_not_loop_per_character() -> None:
    # 본문 검증은 이벤트 루프에서 돈다. 글자마다 파이썬으로 훑으면 본문 한도(2MB) 안의 긴 글자 하나로
    # 요청이 0.3초쯤 걸리고 그동안 다른 요청이 모두 기다린다.
    # 시간은 기계마다 달라 파이썬 실행 단계 수로 본다. 글자 수가 늘어도 단계 수는 늘지 않아야 한다.
    long_text = "가" * 10_000

    steps = _count_python_steps(
        lambda: _Shapes.model_validate({"note": long_text, "tags": [long_text] * 3})
    )

    assert steps < 300


def test_request_model_check_does_not_loop_per_text_item() -> None:
    # removed_segment_ids · key_points 처럼 항목 수 제한이 없는 글자 목록은 짧은 항목 수십만 개로도
    # 본문 한도 안에서 같은 일이 생긴다. 항목 수가 늘어도 단계 수는 늘지 않아야 한다.
    many_items = ["가"] * 10_000

    steps = _count_python_steps(lambda: _Shapes.model_validate({"tags": many_items}))

    assert steps < 300
