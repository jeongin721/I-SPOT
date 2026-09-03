# Backend ↔ 팀 A STT 연결 지점(glue).
#
# 호출 경로:
#   router → transcript_service → stt_adapter.ModuleSTTAdapter
#          → load_callable("stt.transcribe_service", "transcribe")
#          → 이 module 의 transcribe(audio_path)
#          → stt.ispot_stt.Transcriber
#
# 반환값은 I-SPOT STT Contract(schema_version/segments) dict 이며,
# Backend 는 저장 전에 STTResult 로 다시 검증한다.
# (backend/app/schemas/contracts.py)

import os
from typing import Any, Dict, Optional

from stt.ispot_postprocess import STTPostProcessor
from stt.ispot_stt import Transcriber

# 외부 API Key 없이 오프라인으로 동작하는 provider 를 기본값으로 둔다.
DEFAULT_PROVIDER = "mock"

# 환경변수 이름은 팀 A 코드(ispot_stt.py) 규약을 그대로 따른다.
PROVIDER_ENV = "I_SPOT_STT_PROVIDER"
POSTPROCESS_ENV = "I_SPOT_STT_POSTPROCESS"


def resolve_provider(provider: Optional[str] = None) -> str:
    """사용할 STT provider 이름을 결정한다. (mock/whisper/clova/deepgram)"""

    return (provider or os.getenv(PROVIDER_ENV) or DEFAULT_PROVIDER).strip().lower()


def _postprocess_enabled() -> bool:
    return os.getenv(POSTPROCESS_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def transcribe(audio_path: str) -> Dict[str, Any]:
    """상담 음성 파일 1건을 STT Contract dict 로 변환한다."""

    result = Transcriber(provider=resolve_provider()).transcribe(audio_path)

    # 동일 화자 연속 발화 병합은 실제 provider(deepgram 등) 에서만 의미가 있어
    # 기본값은 off 로 두고 환경변수로 켠다.
    if _postprocess_enabled():
        result = STTPostProcessor().process(result)

    result.setdefault("schema_version", "1.0")

    return result


__all__ = ["DEFAULT_PROVIDER", "resolve_provider", "transcribe"]
