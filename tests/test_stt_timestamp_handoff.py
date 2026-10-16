"""Synthetic regression tests for timestamped STT CHILD handoff views."""

from child_analysis_text import ChildAnalysisTextBuilder
from stt.child_handoff import build_stt_child_handoff


def _segment(segment_id, speaker, start_ms, end_ms, text):
    return {
        "segment_id": segment_id,
        "speaker": speaker,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "text": text,
        "confidence": 0.0,
    }


def _build(segments):
    stt_data = {"schema_version": "1.0", "segments": segments}
    child_result = ChildAnalysisTextBuilder().build(stt_data)
    return stt_data, child_result, build_stt_child_handoff(stt_data, child_result)


def test_confirmed_child_handoff_keeps_each_millisecond_range_and_text():
    stt_data, child_result, handoff = _build(
        [
            _segment("q1", "SPEAKER_0", 0, 500, "Question one?"),
            _segment("a1", "SPEAKER_1", 1000, 1800, "CHILD_FIRST"),
            _segment("q2", "SPEAKER_0", 2000, 2500, "Question two?"),
            _segment("a2", "SPEAKER_1", 3000, 3900, "CHILD_SECOND"),
        ]
    )

    assert child_result["status"] == "OK"
    assert handoff["child_analysis_text"] == child_result["child_analysis_text"]
    assert handoff["confirmed_child_segments"] == [
        {"segment_id": "a1", "text": "CHILD_FIRST", "start_ms": 1000, "end_ms": 1800},
        {"segment_id": "a2", "text": "CHILD_SECOND", "start_ms": 3000, "end_ms": 3900},
    ]
    assert handoff["review_needed_segments"] == []
    assert stt_data["segments"][1]["start_ms"] == 1000


def test_child_handoff_is_time_ordered_even_if_provider_segments_are_not():
    _, child_result, handoff = _build(
        [
            _segment("a2", "SPEAKER_1", 3000, 3900, "CHILD_SECOND"),
            _segment("q1", "SPEAKER_0", 0, 500, "Question one?"),
            _segment("q2", "SPEAKER_0", 2000, 2500, "Question two?"),
            _segment("a1", "SPEAKER_1", 1000, 1800, "CHILD_FIRST"),
        ]
    )

    assert child_result["child_analysis_text"] == "CHILD_FIRST CHILD_SECOND"
    assert [item["start_ms"] for item in handoff["confirmed_child_segments"]] == [1000, 3000]
    assert [item["end_ms"] for item in handoff["confirmed_child_segments"]] == [1800, 3900]
    assert [item["segment_id"] for item in handoff["confirmed_child_segments"]] == ["a1", "a2"]


def test_unknown_segments_are_reviewable_but_never_added_to_child_text():
    stt_data = {
        "segments": [
            _segment("u1", "UNKNOWN", 197000, 204000, "UNKNOWN_REVIEW_TEXT"),
            _segment("c1", "COUNSELOR", 0, 400, "COUNSELOR_TEXT"),
        ]
    }
    child_result = {
        "status": "UNRESOLVED_CHILD_SPEAKER",
        "child_speaker": None,
        "child_analysis_text": "",
        "role_mapping": {"UNKNOWN": {"role": "UNKNOWN"}, "COUNSELOR": {"role": "COUNSELOR"}},
    }
    handoff = build_stt_child_handoff(stt_data, child_result)

    assert handoff["confirmed_child_segments"] == []
    assert handoff["child_analysis_text"] == ""
    assert handoff["review_needed_segments"] == [
        {
            "segment_id": "u1",
            "text": "UNKNOWN_REVIEW_TEXT",
            "start_ms": 197000,
            "end_ms": 204000,
            "reason": "UNRESOLVED_SPEAKER",
        }
    ]


def test_ambiguous_and_single_speaker_results_keep_review_timestamps():
    for segments in (
        [
            _segment("a", "SPEAKER_0", 0, 500, "Question from first?"),
            _segment("b", "SPEAKER_1", 1000, 1600, "Question from second?"),
        ],
        [
            _segment("s1", "SPEAKER_0", 82000, 95000, "SINGLE_SPEAKER_TEXT"),
        ],
    ):
        _, child_result, handoff = _build(segments)

        assert child_result["status"] == "UNRESOLVED_CHILD_SPEAKER"
        assert handoff["confirmed_child_segments"] == []
        assert handoff["child_analysis_text"] == ""
        assert handoff["review_needed_segments"]
        assert all(item["segment_id"] for item in handoff["review_needed_segments"])
        assert all(item["start_ms"] >= 0 for item in handoff["review_needed_segments"])
        assert all(item["end_ms"] >= item["start_ms"] for item in handoff["review_needed_segments"])


def test_guardian_and_other_are_not_child_or_review_segments():
    handoff = build_stt_child_handoff(
        {
            "segments": [
                _segment("g", "GUARDIAN", 0, 100, "GUARDIAN_TEXT"),
                _segment("o", "OTHER", 100, 200, "OTHER_TEXT"),
                _segment("c", "CHILD", 200, 300, "CHILD_TEXT"),
            ]
        },
        {
            "status": "OK",
            "child_speaker": "CHILD",
            "child_analysis_text": "CHILD_TEXT",
            "role_mapping": {
                "GUARDIAN": {"role": "GUARDIAN"},
                "OTHER": {"role": "OTHER"},
                "CHILD": {"role": "CHILD"},
            },
        },
    )

    assert handoff["confirmed_child_segments"] == [
        {"segment_id": "c", "text": "CHILD_TEXT", "start_ms": 200, "end_ms": 300}
    ]
    assert handoff["review_needed_segments"] == []
