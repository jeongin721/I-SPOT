"""Regression tests for STT confidence-unavailable handling."""

from app.adapters.ai_adapter import MockAIAdapter


def _payload(segment):
    return {"schema_version": "1.0", "segments": [segment]}


def _segment(confidence, **extra):
    return {
        "segment_id": "seg_001",
        "speaker": "CHILD",
        "start_ms": 0,
        "end_ms": 1000,
        "text": "예시 발화",
        "confidence": confidence,
        **extra,
    }


def test_confidence_unavailable_does_not_create_low_confidence_warning():
    result = MockAIAdapter().analyze(_payload(_segment(0.0))).result

    assert not any("저신뢰" in warning for warning in result.warnings)


def test_positive_low_confidence_still_creates_warning():
    result = MockAIAdapter().analyze(_payload(_segment(0.42))).result

    assert any("저신뢰" in warning for warning in result.warnings)


def test_explicit_internal_low_confidence_metadata_still_creates_warning():
    result = MockAIAdapter().analyze(
        _payload(_segment(0.0, is_low_confidence=True))
    ).result

    assert any("저신뢰" in warning for warning in result.warnings)
