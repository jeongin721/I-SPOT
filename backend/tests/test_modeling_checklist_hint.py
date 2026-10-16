# 서버 분석 경로가 체크리스트 초안을 '교정 힌트 없이' 만드는지 고정하는 테스트.
#
# ai/modeling/abuse/checklist_llm.generate_checklist_draft 의 use_correction_hint 기본값은 True 다.
# 켜면 build_correction_hint_text() 가 과거 승인 회차(다른 사례 포함)의 원문 인용을 가리지 않은 채
# 시스템 프롬프트에 붙여 외부 LLM 으로 보낸다. 서버 경로(infer_audio_session.analyze_audio_session)는
# False 를 직접 넘겨 이것을 끈다. 새로 부르는 곳이 이 인자를 빠뜨리거나 True 로 바꾸면 여기서 실패한다.
#
# infer_audio_session 은 import 하지 않고 소스를 ast 로 읽는다.
#   - import 하면 pii_masking 이 torch · transformers 를 불러오는데 CI 에는 없다.
#   - case_store 는 import 할 때 DB 파일을 만든다.

import ast
from pathlib import Path
from typing import Set

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

SERVER_PATH_FILE = REPO / "ai" / "modeling" / "abuse" / "infer_audio_session.py"
FUNCTION = "generate_checklist_draft"
HINT = "use_correction_hint"


def _function_names(tree: ast.Module) -> Set[str]:
    """`from ... import generate_checklist_draft as 다른이름` 으로 들여와도 따라간다."""

    names = {FUNCTION}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names if alias.name == FUNCTION)

    return names


def _refers_to_function(node: ast.AST, names: Set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in names

    # checklist_llm.generate_checklist_draft(...) 처럼 모듈을 거쳐 부르는 모양
    return isinstance(node, ast.Attribute) and node.attr == FUNCTION


def test_server_path_builds_checklist_without_correction_hint() -> None:
    tree = ast.parse(SERVER_PATH_FILE.read_text(encoding="utf-8"))
    names = _function_names(tree)
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _refers_to_function(node.func, names)
    ]

    # 하나도 못 찾고 통과하지 않게 한다(함수 이름이 바뀌었거나 찾는 규칙이 틀린 것).
    assert calls, f"{SERVER_PATH_FILE.name} 에서 {FUNCTION} 호출을 찾지 못했다 — 함수 이름이나 찾는 규칙을 고쳐야 한다"

    for call in calls:
        hint = [keyword.value for keyword in call.keywords if keyword.arg == HINT]

        assert len(hint) == 1 and isinstance(hint[0], ast.Constant) and hint[0].value is False, (
            f"{SERVER_PATH_FILE.name}:{call.lineno} 의 {FUNCTION} 호출은 {HINT}=False 를 키워드로 적어야 한다"
        )

    # 부르지 않고 함수만 넘기면(functools.partial · 콜백) 위 검사를 빠져나가므로 그것도 막는다.
    called = {id(call.func) for call in calls}

    for node in ast.walk(tree):
        if _refers_to_function(node, names):
            assert id(node) in called, (
                f"{SERVER_PATH_FILE.name}:{node.lineno} 에서 {FUNCTION} 를 부르지 않고 넘긴다 — "
                f"직접 부르면서 {HINT}=False 를 적어야 한다"
            )
