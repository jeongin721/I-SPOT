# 음성 Paralinguistic Feature Contract.
#
# 팀 A 의 stt/ 음성 특징 추출 모듈이 화자별로 반환하는 값을 그대로 옮긴 구조이다.
#   extract_audio_features(audio_path, stt_segments) -> {speaker: {...}}
#
# STT/AI Contract(schemas/contracts.py)와는 별개의 신규 산출물이므로 그 파일을
# 수정하지 않고 여기에 둔다. 필드를 바꿀 때는 팀 A 모듈과 함께 변경한다.

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Speaker

AUDIO_FEATURE_SCHEMA_VERSION = "1.0"


class SpeakerAudioFeature(BaseModel):
    """한 화자의 음성 특징 벡터."""

    # 발화 중 휴지(within-turn pause)
    turn_count: int = Field(0, ge=0)
    word_count: int = Field(0, ge=0)
    pause_count: int = Field(0, ge=0)
    mean_pause_ms: float = Field(0, ge=0)
    max_pause_ms: float = Field(0, ge=0)
    total_pause_ms: float = Field(0, ge=0)

    # 상대 발화 후 응답까지의 지연(response latency)
    response_count: int = Field(0, ge=0)
    mean_response_latency_ms: float = 0
    min_response_latency_ms: float = 0
    max_response_latency_ms: float = 0

    # 발화 속도
    char_count: int = Field(0, ge=0)
    speaking_duration_ms: float = Field(0, ge=0)
    words_per_second: float = Field(0, ge=0)
    chars_per_second: float = Field(0, ge=0)

    # 피치(F0)
    pitch_mean_hz: float = Field(0, ge=0)
    pitch_median_hz: float = Field(0, ge=0)
    pitch_std_hz: float = Field(0, ge=0)
    pitch_min_hz: float = Field(0, ge=0)
    pitch_max_hz: float = Field(0, ge=0)
    pitch_voiced_frame_count: int = Field(0, ge=0)

    # RMS 에너지
    energy_mean: float = 0
    energy_median: float = 0
    energy_std: float = Field(0, ge=0)
    energy_min: float = 0
    energy_max: float = 0
    energy_frame_count: int = Field(0, ge=0)

    # 추출 모듈이 지표를 추가해도 Backend 가 깨지지 않도록 허용한다.
    # (제거/의미 변경은 Contract 변경이므로 팀 A 와 함께 처리한다.)
    model_config = ConfigDict(extra="allow")


class AudioFeatureResult(BaseModel):
    """추출 모듈이 반환하는 최상위 구조."""

    schema_version: str = AUDIO_FEATURE_SCHEMA_VERSION
    speakers: Dict[Speaker, SpeakerAudioFeature] = Field(default_factory=dict)


class AudioFeatureResponse(BaseModel):
    """조회 API 응답."""

    id: str
    session_id: str
    audio_file_id: str
    transcript_version: int | None = None
    schema_version: str
    extractor: str | None = None
    speakers: Dict[Speaker, SpeakerAudioFeature] = Field(default_factory=dict)
