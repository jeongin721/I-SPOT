"""Segment-level CHILD and unresolved-speaker handoff views.

This module is intentionally local to the STT/role-mapping boundary.  It
does not change the shared transcript contract and does not invoke a
classifier.  ``child_analysis_text`` remains the value produced by
``ChildAnalysisTextBuilder``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping


_CANONICAL_ROLES = {"COUNSELOR", "CHILD", "GUARDIAN", "OTHER", "UNKNOWN"}


def _role_for_segment(segment: Mapping[str, Any], role_mapping: Mapping[str, Any]) -> str:
    speaker = str(segment.get("speaker") or "UNKNOWN")
    mapped = role_mapping.get(speaker, {})
    role = mapped.get("role") if isinstance(mapped, Mapping) else None
    if role in _CANONICAL_ROLES:
        return str(role)
    return speaker if speaker in _CANONICAL_ROLES else "UNKNOWN"


def _timed_segment(segment: Mapping[str, Any], index: int) -> Dict[str, Any]:
    segment_id = str(segment.get("segment_id") or "").strip()
    if not segment_id:
        raise ValueError("handoff segment has no segment_id")

    start_ms = int(segment.get("start_ms", 0))
    end_ms = int(segment.get("end_ms", start_ms))
    if start_ms < 0 or end_ms < start_ms:
        raise ValueError("handoff segment has an invalid millisecond time range")

    return {
        "segment_id": segment_id,
        "text": str(segment.get("text") or "").strip(),
        "start_ms": start_ms,
        "end_ms": end_ms,
        "_index": index,
    }


def _timeline_sort_key(item: Mapping[str, Any]) -> tuple[int, int, int]:
    return (int(item["start_ms"]), int(item["end_ms"]), int(item["_index"]))


def _public_segment(item: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "segment_id": item["segment_id"],
        "text": item["text"],
        "start_ms": item["start_ms"],
        "end_ms": item["end_ms"],
    }


def build_stt_child_handoff(
    stt_data: Mapping[str, Any], child_result: Mapping[str, Any]
) -> Dict[str, Any]:
    """Build timestamped CHILD and unresolved-speaker views.

    ``child_result`` must come from the existing ``ChildAnalysisTextBuilder``.
    This helper never infers a role, changes text, or combines UNKNOWN text
    into the classifier-ready CHILD handoff.
    """

    segments = stt_data.get("segments", []) or []
    if not isinstance(segments, list):
        raise ValueError("stt_data.segments must be a list")

    role_mapping = child_result.get("role_mapping", {}) or {}
    if not isinstance(role_mapping, Mapping):
        raise ValueError("child_result.role_mapping must be a mapping")

    status = str(child_result.get("status") or "")
    child_speaker = child_result.get("child_speaker")
    confirmed_children: List[Dict[str, Any]] = []
    review_needed: List[Dict[str, Any]] = []

    for index, raw_segment in enumerate(segments):
        if not isinstance(raw_segment, Mapping):
            raise ValueError("stt_data.segments must contain mappings")

        timed = _timed_segment(raw_segment, index)
        role = _role_for_segment(raw_segment, role_mapping)
        speaker = str(raw_segment.get("speaker") or "UNKNOWN")

        if status == "OK" and child_speaker is not None and speaker == str(child_speaker):
            confirmed_children.append(timed)
        elif role == "UNKNOWN":
            review_needed.append({**timed, "reason": "UNRESOLVED_SPEAKER"})

    confirmed_children.sort(key=_timeline_sort_key)
    review_needed.sort(key=_timeline_sort_key)

    return {
        "child_analysis_text": str(child_result.get("child_analysis_text") or ""),
        "confirmed_child_segments": [_public_segment(item) for item in confirmed_children],
        "review_needed_segments": [
            {**_public_segment(item), "reason": item["reason"]}
            for item in review_needed
        ],
    }


def build_canonical_child_handoff(stt_data: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the handoff from persisted canonical STT roles without re-inferring.

    The backend persists the normalized STT Contract after provider-side runtime
    role mapping.  Re-running a text heuristic at response time could disagree
    with that persisted decision, so this boundary treats only canonical
    ``CHILD`` segments as confirmed and keeps ``UNKNOWN`` segments for review.
    """
    segments = stt_data.get("segments", []) or []
    if not isinstance(segments, list):
        raise ValueError("stt_data.segments must be a list")

    ordered_children = sorted(
        (
            (index, segment)
            for index, segment in enumerate(segments)
            if isinstance(segment, Mapping)
            and str(segment.get("speaker") or "UNKNOWN") == "CHILD"
            and str(segment.get("text") or "").strip()
        ),
        key=lambda item: (
            int(item[1].get("start_ms", 0)),
            int(item[1].get("end_ms", item[1].get("start_ms", 0))),
            item[0],
        ),
    )
    child_text = " ".join(str(segment.get("text") or "").strip() for _, segment in ordered_children)
    child_result: Dict[str, Any]
    if ordered_children:
        child_result = {
            "status": "OK",
            "child_speaker": "CHILD",
            "child_analysis_text": child_text,
            "role_mapping": {},
        }
    else:
        child_result = {
            "status": "UNRESOLVED_CHILD_SPEAKER",
            "child_speaker": None,
            "child_analysis_text": "",
            "role_mapping": {},
        }
    return build_stt_child_handoff(stt_data, child_result)


__all__ = ["build_canonical_child_handoff", "build_stt_child_handoff"]
