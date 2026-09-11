# STT Adapter.
#
# 호출 경로(03_BACKEND_PROMPT.md §8):
#     router → service → stt_adapter
#
# Adapter 는 Provider 가 바뀌어도 STT Contract(schema_version/segments)를 유지한다.
# 팀 A 의 transcribe(audio_path) 를 그대로 호출할 수 있도록 설계했다.

from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from pydantic import ValidationError

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.config import settings
from app.core.enums import Speaker
from app.schemas.contracts import STTResult


class STTError(Exception):
    """STT 처리 실패."""


class STTOutputError(STTError):
    """STT 결과가 STT Contract 를 만족하지 않는 경우."""


class STTAdapter(Protocol):
    name: str
    model: Optional[str]

    def transcribe(self, audio_path: Path) -> STTResult:
        ...


# =========================================================
# Mock Adapter
# =========================================================

class MockSTTAdapter:
    """
    팀 A 산출물 없이 Backend/Frontend 통합을 진행하기 위한 Mock.

    반환 텍스트는 전부 합성 데이터이며 실제 상담 내용이 아니다.
    (docs/05_RULES.md: 실제 아동 개인정보를 테스트에 사용하지 않는다.)
    """

    name = "mock"
    model = "mock-stt-1.0"

    _SCRIPT = [
        (Speaker.COUNSELOR, "안녕하세요. 오늘 상담을 시작하겠습니다.", 0.95),
        (Speaker.CHILD, "네, 안녕하세요.", 0.92),
        (Speaker.COUNSELOR, "요즘 학교 생활은 어떤지 이야기해 줄 수 있을까요?", 0.94),
        (Speaker.CHILD, "그냥 그래요. 조금 힘든 날도 있어요.", 0.78),
        (Speaker.COUNSELOR, "힘든 날에는 어떤 일이 있었는지 말해 줄 수 있어요?", 0.93),
        (Speaker.CHILD, "잘 기억이 안 나요.", 0.61),
        (Speaker.GUARDIAN, "집에서는 조용한 편입니다.", 0.88),
        (Speaker.UNKNOWN, "잡음이 섞여 확인이 어려운 구간입니다.", 0.42),
    ]

    def transcribe(self, audio_path: Path) -> STTResult:
        if not audio_path.exists():
            raise STTError(f"음성 파일을 찾을 수 없습니다: {audio_path.name}")

        if audio_path.stat().st_size == 0:
            raise STTError("빈 음성 파일은 전사할 수 없습니다.")

        segments = []
        cursor_ms = 0

        for index, (speaker, text, confidence) in enumerate(self._SCRIPT, start=1):
            duration_ms = 2000 + (index % 3) * 500

            segments.append(
                {
                    "segment_id": f"seg_{index:03d}",
                    "speaker": speaker.value,
                    "start_ms": cursor_ms,
                    "end_ms": cursor_ms + duration_ms,
                    "text": text,
                    "confidence": confidence,
                }
            )

            cursor_ms += duration_ms + 300

        return STTResult.model_validate({"schema_version": "1.0", "segments": segments})


# =========================================================
# Module Adapter (팀 A 실제 STT)
# =========================================================

class ModuleSTTAdapter:
    """
    설정된 module 의 transcribe(audio_path) 를 호출한다.

    반환값은 dict 또는 STT Contract 를 만족하는 객체여야 하며,
    Backend 는 저장 전에 항상 Contract 검증을 수행한다.
    """

    def __init__(self, module_path: str, function_name: str) -> None:
        self.name = f"{module_path}.{function_name}"
        self.model = None
        self._module_path = module_path
        self._function_name = function_name

    def transcribe(self, audio_path: Path) -> STTResult:
        try:
            transcribe_fn = load_callable(self._module_path, self._function_name)
        except ModuleLoadError as error:
            raise STTError(str(error)) from error

        raw: Any = transcribe_fn(str(audio_path))

        return validate_stt_output(raw)


def validate_stt_output(raw: Any) -> STTResult:
    """STT Provider 출력이 공통 Contract 를 만족하는지 검증한다."""

    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()

    if not isinstance(raw, dict):
        raise STTOutputError("STT 결과가 JSON 객체 형태가 아닙니다.")

    payload: Dict[str, Any] = dict(raw)
    payload.setdefault("schema_version", "1.0")

    try:
        return STTResult.model_validate(payload)
    except ValidationError as error:
        raise STTOutputError(
            f"STT 결과가 STT Contract 를 만족하지 않습니다: {error.error_count()}건"
        ) from error


# =========================================================
# Factory
# =========================================================

_override: Optional[STTAdapter] = None


def set_stt_adapter_override(adapter: Optional[STTAdapter]) -> None:
    """테스트에서 STT 성공/실패/Timeout 을 주입하기 위한 hook."""

    global _override
    _override = adapter


def get_stt_adapter() -> STTAdapter:
    if _override is not None:
        return _override

    if settings.STT_PROVIDER == "module":
        return ModuleSTTAdapter(settings.STT_MODULE, settings.STT_FUNCTION)

    return MockSTTAdapter()
