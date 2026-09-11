# 팀 A(STT) / 팀 B(AI) 산출물을 동적으로 import 한다.
#
# 각 파트가 별도 branch 로 작업하기 때문에, 해당 package 가 없을 때도
# Backend 는 mock provider 로 단독 실행되어야 한다.

import importlib
import sys
from typing import Any

from app.core.config import REPO_ROOT


class ModuleLoadError(Exception):
    """대상 module/function 을 찾을 수 없는 경우."""


def ensure_repo_root_on_path() -> None:
    """repo root 를 sys.path 에 추가해 ai/, stt/ package 를 import 가능하게 한다."""

    root = str(REPO_ROOT)

    if root not in sys.path:
        sys.path.insert(0, root)


def load_callable(module_path: str, function_name: str) -> Any:
    ensure_repo_root_on_path()

    try:
        module = importlib.import_module(module_path)
    except ImportError as error:
        raise ModuleLoadError(
            f"module '{module_path}' 를 import 할 수 없습니다: {error}"
        ) from error

    target = getattr(module, function_name, None)

    if target is None or not callable(target):
        raise ModuleLoadError(
            f"module '{module_path}' 에 호출 가능한 '{function_name}' 이 없습니다."
        )

    return target
