# 실제 STT 연결 경로(ModuleSTTAdapter) 테스트.
#
# 다른 테스트는 conftest.py 가 STT_PROVIDER=mock 으로 고정해서, 운영에서 쓰는
# "설정값(STT_MODULE / STT_FUNCTION)으로 실제 모듈을 불러 호출" 하는 경로가 실행되지 않았다.
# 외부 STT 대신 가짜 모듈을 넣고, 불러오기 · 호출 · Contract 검증을 실제 코드로 확인한다.

import sys
import types
from pathlib import Path

import pytest

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.adapters.stt_adapter import (
    ModuleSTTAdapter,
    STTError,
    STTOutputError,
    get_stt_adapter,
)
from app.core.config import settings
from app.schemas.contracts import STTResult

FAKE_MODULE = "ispot_test_fake_stt"

VALID_OUTPUT = {
    "schema_version": "1.0",
    "segments": [
        {
            "segment_id": "seg_001",
            "speaker": "CHILD",
            "start_ms": 0,
            "end_ms": 1200,
            "text": "합성 발화입니다.",
            "confidence": 0.9,
        }
    ],
}


@pytest.fixture
def fake_stt(monkeypatch: pytest.MonkeyPatch) -> dict:
    """transcribe(audio_path) 를 가진 가짜 STT 모듈. 반환값과 호출 기록을 조절한다."""

    state = {"output": VALID_OUTPUT, "calls": []}

    def transcribe(audio_path):
        state["calls"].append(audio_path)
        return state["output"]

    module = types.ModuleType(FAKE_MODULE)
    module.transcribe = transcribe
    module.NOT_CALLABLE = "문자열"
    monkeypatch.setitem(sys.modules, FAKE_MODULE, module)

    return state


def test_module_adapter_calls_configured_function_and_validates_output(fake_stt, tmp_path) -> None:
    audio_path = tmp_path / "consultation.wav"

    result = ModuleSTTAdapter(FAKE_MODULE, "transcribe").transcribe(audio_path)

    assert isinstance(result, STTResult)
    assert result.segments[0].segment_id == "seg_001"
    # 팀 A 함수 규약대로 문자열 경로를 넘긴다.
    assert fake_stt["calls"] == [str(audio_path)]


def test_module_adapter_accepts_pydantic_like_output(fake_stt, tmp_path) -> None:
    fake_stt["output"] = STTResult.model_validate(VALID_OUTPUT)

    result = ModuleSTTAdapter(FAKE_MODULE, "transcribe").transcribe(tmp_path / "a.wav")

    assert result.segments[0].text == "합성 발화입니다."


def test_missing_schema_version_defaults_to_current(fake_stt, tmp_path) -> None:
    fake_stt["output"] = {"segments": VALID_OUTPUT["segments"]}

    result = ModuleSTTAdapter(FAKE_MODULE, "transcribe").transcribe(tmp_path / "a.wav")

    assert result.schema_version == "1.0"


@pytest.mark.parametrize(
    "output",
    [
        "문자열 결과",
        {"schema_version": "1.0", "segments": [{"segment_id": "seg_001"}]},
    ],
)
def test_output_breaking_stt_contract_is_rejected(fake_stt, tmp_path, output) -> None:
    fake_stt["output"] = output

    with pytest.raises(STTOutputError):
        ModuleSTTAdapter(FAKE_MODULE, "transcribe").transcribe(tmp_path / "a.wav")


@pytest.mark.parametrize(
    "module_path, function_name",
    [
        ("ispot_module_that_does_not_exist", "transcribe"),
        (FAKE_MODULE, "missing_function"),
        (FAKE_MODULE, "NOT_CALLABLE"),
    ],
)
def test_wrong_stt_setting_becomes_stt_error(fake_stt, tmp_path, module_path, function_name) -> None:
    """설정 오타·함수 이름 변경은 조용히 넘어가지 않고 STT 실패로 드러난다."""

    with pytest.raises(STTError) as raised:
        ModuleSTTAdapter(module_path, function_name).transcribe(tmp_path / "a.wav")

    assert not isinstance(raised.value, STTOutputError)


def test_load_callable_reports_what_is_missing(fake_stt) -> None:
    with pytest.raises(ModuleLoadError, match="missing_function"):
        load_callable(FAKE_MODULE, "missing_function")


def test_module_provider_setting_selects_module_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STT_PROVIDER", "module")
    monkeypatch.setattr(settings, "STT_MODULE", FAKE_MODULE)
    monkeypatch.setattr(settings, "STT_FUNCTION", "transcribe")

    adapter = get_stt_adapter()

    assert isinstance(adapter, ModuleSTTAdapter)
    assert adapter.name == f"{FAKE_MODULE}.transcribe"


def test_default_stt_module_setting_points_to_real_function() -> None:
    """기본 설정값(stt.transcribe_service.transcribe)이 실제로 존재하는지 확인한다.

    외부 STT 호출은 하지 않고, 설정 문자열이 가리키는 파일·함수 이름만 대조한다.
    """

    module_file = Path(__file__).resolve().parents[2] / (settings.model_fields["STT_MODULE"].default.replace(".", "/") + ".py")

    assert module_file.is_file(), f"STT_MODULE 기본값이 가리키는 파일이 없다: {module_file}"
    assert f"def {settings.model_fields['STT_FUNCTION'].default}(" in module_file.read_text(encoding="utf-8")
