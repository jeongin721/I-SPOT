# 음성 Paralinguistic Feature 저장 구조 테스트.
#
# 팀 A 의 추출 모듈(extract_audio_features)이 반환하는 화자별 특징 벡터를
# Backend 가 손실 없이 보관하고, Contract 로 다시 읽어낼 수 있는지 확인한다.

import uuid
from typing import Dict

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.enums import Speaker
from app.models.audio import AudioFile
from app.models.audio_feature import AudioFeature
from app.schemas.audio_feature import (
    AUDIO_FEATURE_SCHEMA_VERSION,
    AudioFeatureResult,
    SpeakerAudioFeature,
)
from tests.conftest import upload_audio


# 팀 A extract_audio_features() 출력 형태 그대로.
SAMPLE_FEATURES: Dict[str, Dict[str, float]] = {
    "COUNSELOR": {
        "turn_count": 12,
        "word_count": 240,
        "pause_count": 8,
        "mean_pause_ms": 320.5,
        "max_pause_ms": 1500,
        "total_pause_ms": 2564,
        "response_count": 11,
        "mean_response_latency_ms": 480.2,
        "min_response_latency_ms": 120,
        "max_response_latency_ms": 1100,
        "char_count": 980,
        "speaking_duration_ms": 62000,
        "words_per_second": 3.87,
        "chars_per_second": 15.8,
        "pitch_mean_hz": 182.4,
        "pitch_median_hz": 180.1,
        "pitch_std_hz": 22.7,
        "pitch_min_hz": 120.0,
        "pitch_max_hz": 260.3,
        "pitch_voiced_frame_count": 4200,
        "energy_mean": 0.042,
        "energy_median": 0.038,
        "energy_std": 0.011,
        "energy_min": 0.001,
        "energy_max": 0.19,
        "energy_frame_count": 5800,
    },
    "CHILD": {
        "turn_count": 9,
        "word_count": 85,
        "pause_count": 14,
        "mean_pause_ms": 890.3,
        "max_pause_ms": 4200,
        "total_pause_ms": 12464,
        "response_count": 9,
        "mean_response_latency_ms": 1850.7,
        "min_response_latency_ms": 400,
        "max_response_latency_ms": 5200,
        "char_count": 310,
        "speaking_duration_ms": 28000,
        "words_per_second": 3.04,
        "chars_per_second": 11.1,
        "pitch_mean_hz": 265.8,
        "pitch_median_hz": 262.0,
        "pitch_std_hz": 48.9,
        "pitch_min_hz": 150.0,
        "pitch_max_hz": 410.5,
        "pitch_voiced_frame_count": 1900,
        "energy_mean": 0.018,
        "energy_median": 0.015,
        "energy_std": 0.009,
        "energy_min": 0.0,
        "energy_max": 0.11,
        "energy_frame_count": 2600,
    },
}


@pytest.fixture
def audio_file_id(
    client: TestClient, counselor_headers, case: dict, session: dict, db
) -> uuid.UUID:
    """업로드된 음성 1건을 만들고 그 id 를 돌려준다."""

    status_code, body = upload_audio(client, counselor_headers, session["id"])

    assert status_code == 201, body

    return uuid.UUID(body["data"]["audio"]["id"])


def _make_feature(db, session_id: str, audio_file_id: uuid.UUID) -> AudioFeature:
    feature = AudioFeature(
        session_id=uuid.UUID(session_id),
        audio_file_id=audio_file_id,
        transcript_version=1,
        schema_version=AUDIO_FEATURE_SCHEMA_VERSION,
        extractor="ispot_audio_features",
        features=SAMPLE_FEATURES,
    )

    db.add(feature)
    db.commit()
    db.refresh(feature)

    return feature


# =========================================================
# 저장 / 조회
# =========================================================

def test_features_round_trip_without_loss(
    db, session: dict, audio_file_id: uuid.UUID
) -> None:
    """26개 지표가 화자별로 그대로 보존되어야 한다."""

    feature = _make_feature(db, session["id"], audio_file_id)

    stored = db.get(AudioFeature, feature.id)

    assert stored is not None
    assert stored.features == SAMPLE_FEATURES
    assert set(stored.features.keys()) == {"COUNSELOR", "CHILD"}
    assert len(stored.features["CHILD"]) == 26
    # 부동소수점 값이 문자열로 뭉개지지 않아야 한다.
    assert stored.features["CHILD"]["pitch_mean_hz"] == 265.8


def test_provenance_is_tracked(db, session: dict, audio_file_id: uuid.UUID) -> None:
    """어떤 음성/전사본 version 기준으로 뽑았는지 남아야 한다."""

    feature = _make_feature(db, session["id"], audio_file_id)

    assert feature.audio_file_id == audio_file_id
    assert feature.transcript_version == 1
    assert feature.extractor == "ispot_audio_features"
    assert feature.schema_version == AUDIO_FEATURE_SCHEMA_VERSION


def test_reachable_from_session_and_audio_file(
    db, session: dict, audio_file_id: uuid.UUID
) -> None:
    _make_feature(db, session["id"], audio_file_id)

    audio = db.get(AudioFile, audio_file_id)

    assert audio is not None
    assert len(audio.features) == 1
    assert audio.features[0].session_id == uuid.UUID(session["id"])


def test_multiple_versions_are_kept(
    db, session: dict, audio_file_id: uuid.UUID
) -> None:
    """전사본이 수정되면 같은 음성에 대해 특징을 다시 뽑을 수 있어야 한다."""

    _make_feature(db, session["id"], audio_file_id)

    second = AudioFeature(
        session_id=uuid.UUID(session["id"]),
        audio_file_id=audio_file_id,
        transcript_version=2,
        schema_version=AUDIO_FEATURE_SCHEMA_VERSION,
        extractor="ispot_audio_features",
        features=SAMPLE_FEATURES,
    )

    db.add(second)
    db.commit()

    audio = db.get(AudioFile, audio_file_id)

    assert {f.transcript_version for f in audio.features} == {1, 2}


def test_deleting_audio_file_removes_features(
    db, session: dict, audio_file_id: uuid.UUID
) -> None:
    """음성이 삭제되면 파생 특징도 남지 않아야 한다."""

    feature = _make_feature(db, session["id"], audio_file_id)
    feature_id = feature.id

    db.delete(db.get(AudioFile, audio_file_id))
    db.commit()

    # DB 의 ON DELETE CASCADE 로 지워지므로(passive_deletes), 세션 캐시를 비우고
    # 다시 조회해야 실제 상태를 본다.
    db.expire_all()

    assert db.get(AudioFeature, feature_id) is None


# =========================================================
# Contract
# =========================================================

def test_contract_parses_extractor_output() -> None:
    """팀 A 모듈 출력이 Contract 로 그대로 파싱되어야 한다."""

    result = AudioFeatureResult(speakers=SAMPLE_FEATURES)

    assert result.schema_version == AUDIO_FEATURE_SCHEMA_VERSION
    assert result.speakers[Speaker.CHILD].mean_response_latency_ms == 1850.7
    assert result.speakers[Speaker.COUNSELOR].turn_count == 12


def test_contract_fills_missing_metrics_with_zero() -> None:
    """추출 모듈이 일부 지표를 생략해도 0 으로 채워 깨지지 않아야 한다."""

    partial = SpeakerAudioFeature(turn_count=3)

    assert partial.pitch_mean_hz == 0
    assert partial.energy_frame_count == 0


def test_contract_allows_new_metrics() -> None:
    """지표가 추가되어도 Backend 가 거부하지 않아야 한다."""

    extended = SpeakerAudioFeature(turn_count=1, jitter_percent=1.4)

    assert extended.turn_count == 1
    assert extended.model_dump()["jitter_percent"] == 1.4


def test_contract_rejects_unknown_speaker() -> None:
    """STT Contract 밖의 화자 라벨은 거부해야 한다."""

    with pytest.raises(ValidationError):
        AudioFeatureResult(speakers={"TEACHER": {"turn_count": 1}})


def test_contract_rejects_negative_duration() -> None:
    with pytest.raises(ValidationError):
        SpeakerAudioFeature(speaking_duration_ms=-1)
