# 서버 분석 경로가 체크리스트 초안을 '교정 힌트 없이' 만드는지 고정하는 테스트.
#
# ai/modeling/abuse/checklist_llm.generate_checklist_draft 의 use_correction_hint 기본값은 True 다.
# 켜면 build_correction_hint_text() 가 과거 승인 회차(다른 사례 포함)의 원문 인용을 가리지 않은 채
# 시스템 프롬프트에 붙여 외부 LLM 으로 보낸다. 서버 경로(infer_audio_session.analyze_audio_session)는
# False 를 직접 넘겨 이것을 끈다. 새로 부르는 곳이 이 인자를 빠뜨리거나 True 로 바꾸면 여기서 실패한다.
#
# 인정하는 모양은 두 가지다. 어느 쪽이든 그 호출에 use_correction_hint=False 키워드가 정확히 하나 있어야 한다.
#   1) 직접 부르기:        generate_checklist_draft(..., use_correction_hint=False)
#   2) 스레드 풀에 맡기기: 무엇.submit(generate_checklist_draft, ..., use_correction_hint=False)
#      submit 은 첫 위치 인자 뒤의 인자를 그대로 함수에 넘긴다(PR #57 이 네 호출을 동시에 돌리며 쓰는 모양).
# 그 밖에 함수를 값으로 쓰는 모양(functools.partial · executor.map · 다른 이름에 담기 · submit 의 둘째 인자 ·
# getattr 에 넘기는 이름 문자열)은 이 시험이 인자를 따라가지 못하므로 실패시킨다. 하나도 찾지 못해도 실패한다.
#
# infer_audio_session 은 import 하지 않고 소스를 ast 로 읽는다.
#   - import 하면 pii_masking 이 torch · transformers 를 불러오는데 CI 에는 없다.
#   - case_store 는 import 할 때 DB 파일을 만든다.

import ast
from pathlib import Path
from typing import Dict, Optional, Set

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

SERVER_PATH_FILE = REPO / "ai" / "modeling" / "abuse" / "infer_audio_session.py"
FUNCTION = "generate_checklist_draft"
HINT = "use_correction_hint"
SUBMIT = "submit"


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

    # checklist_llm.generate_checklist_draft 처럼 모듈을 거쳐 쓰는 모양
    if isinstance(node, ast.Attribute):
        return node.attr == FUNCTION

    # getattr(checklist_llm, "generate_checklist_draft") 처럼 이름 문자열로 꺼내는 모양(늘 실패시킨다)
    return isinstance(node, ast.Constant) and node.value == FUNCTION


def _parents(tree: ast.Module) -> Dict[int, ast.AST]:
    return {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _call_that_must_carry_hint(use: ast.AST, parent: Optional[ast.AST]) -> Optional[ast.Call]:
    """use 가 인정하는 두 모양 중 하나면 use_correction_hint 를 적어야 하는 호출을, 아니면 None 을 돌려준다."""

    if isinstance(use, ast.Constant) or not isinstance(parent, ast.Call):
        return None

    # 1) 직접 부르기
    if parent.func is use:
        return parent

    # 2) 무엇.submit(함수, ...) — 함수가 첫 위치 인자일 때만(submit 의 fn 은 위치 전용이다)
    if (
        isinstance(parent.func, ast.Attribute)
        and parent.func.attr == SUBMIT
        and parent.args
        and parent.args[0] is use
    ):
        return parent

    return None


def test_server_path_builds_checklist_without_correction_hint() -> None:
    tree = ast.parse(SERVER_PATH_FILE.read_text(encoding="utf-8"))
    names = _function_names(tree)
    parents = _parents(tree)
    uses = [node for node in ast.walk(tree) if _refers_to_function(node, names)]

    # 하나도 못 찾고 통과하지 않게 한다(함수 이름이 바뀌었거나 찾는 규칙이 틀린 것).
    # 아래에서 찾은 것이 모두 인정하는 모양이어야 통과하므로, 통과하면 그런 호출이 하나 이상 있다.
    assert uses, f"{SERVER_PATH_FILE.name} 에서 {FUNCTION} 를 찾지 못했다 — 함수 이름이나 찾는 규칙을 고쳐야 한다"

    for use in uses:
        call = _call_that_must_carry_hint(use, parents.get(id(use)))

        assert call is not None, (
            f"{SERVER_PATH_FILE.name}:{use.lineno} 에서 {FUNCTION} 를 직접 부르지도, 무엇.submit 의 "
            f"첫 위치 인자로 넘기지도 않는다 — 두 모양 중 하나로 쓰고 {HINT}=False 를 적어야 한다"
        )

        # 같은 키워드를 두 번 적어도 ast.parse 는 통과하므로(컴파일할 때에야 오류) 개수까지 본다.
        hint = [keyword.value for keyword in call.keywords if keyword.arg == HINT]

        assert len(hint) == 1 and isinstance(hint[0], ast.Constant) and hint[0].value is False, (
            f"{SERVER_PATH_FILE.name}:{call.lineno} 의 {FUNCTION} 호출은 {HINT}=False 를 키워드로 한 번만 적어야 한다"
        )
