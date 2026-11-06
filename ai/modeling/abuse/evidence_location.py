"""
근거(evidence) 인용 → STT 줄(segment) · 원본 음성 시각 연결(2026-11-02, infer_audio_session 에서 옮김).

[왜 옮겼나 — 근거가 엉뚱한 줄에 붙던 문제]
2차 세부유형 분석(second_stage_llm.analyze_subtypes)은 **이름을 가린 글**(mask_for_outbound)을 받아 인용문의 글자 위치
(evidence_start / evidence_end)를 계산한다. 줄 위치(line_spans)는 **원래 글**로 계산한다. '하준이' 가 '[이름1]' 같은 표지로
바뀌면 글자 수가 달라져서, 이름이 처음 나온 뒤의 근거는 몇 줄씩 밀린 줄에 연결됐다(데모 11/02: 03:19~03:24 "손바닥으로 /
아동: 머리 한대" 인용이 03:31 상담원 · 03:33 아동 줄에 붙고, 관련 조문도 03:33 에 붙음).
그래서 연결 전에 이름을 되돌린 인용문을 **원래 글에서 다시 찾아** 위치를 고친다(relocate_evidence). 같은 글이 여러 번
나오면 가린 글 위치에 가장 가까운 것을 고른다. 못 찾으면 시각을 붙이지 않는다(엉뚱한 줄보다 없는 편이 낫다).

표준 라이브러리만 쓴다(backend/tests 에서 시험).
"""

import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

_SPACE = re.compile(r"\s+")


def build_line_char_spans(lines: List[Tuple[str, str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """build_full_transcript_text 와 같은 규칙("화자: 텍스트" 를 "\\n" 으로 join)으로 줄마다 글자 구간을 계산한다."""

    spans: List[Dict[str, Any]] = []
    cursor = 0

    for speaker, text, segment in lines:
        line_text = f"{speaker}: {text}"
        start_char = cursor
        end_char = cursor + len(line_text)
        spans.append(
            {
                "start_char": start_char,
                "end_char": end_char,
                "segment_id": segment["segment_id"],
                "start_ms": segment["start_ms"],
                "end_ms": segment["end_ms"],
            }
        )
        # 줄 사이에 "\n" 하나가 들어가므로 다음 줄은 그만큼 뒤에서 시작한다.
        cursor = end_char + 1

    return spans


def find_spans_for_char_range(start_char: int, end_char: int, line_spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [span for span in line_spans if span["start_char"] < end_char and span["end_char"] > start_char]


def _occurrences(source: str, needle: str) -> Iterator[Tuple[int, int]]:
    """needle 이 나오는 모든 (시작, 끝). 그대로 못 찾으면 공백을 하나로 줄여 찾고 원래 글 위치로 되돌린다."""

    if not needle:
        return
    found = False
    start = source.find(needle)
    while start != -1:
        found = True
        yield start, start + len(needle)
        start = source.find(needle, start + 1)
    if found:
        return

    pattern = r"\s+".join(re.escape(part) for part in _SPACE.split(needle.strip()) if part)
    if not pattern:
        return
    for match in re.finditer(pattern, source):
        yield match.start(), match.end()


def relocate_evidence(evidence: Dict[str, Any], source_text: str) -> Optional[Tuple[int, int]]:
    """이름을 되돌린 인용문(matched_evidence, 없으면 evidence)을 원래 글에서 찾는다. 여러 번 나오면 가린 글의 위치
    (evidence_start)에 가장 가까운 것. 못 찾으면 None."""

    hint = evidence.get("evidence_start")
    for key in ("matched_evidence", "evidence"):
        text = evidence.get(key)
        if not isinstance(text, str) or not text.strip():
            continue
        candidates = list(_occurrences(source_text, text))
        if candidates:
            if isinstance(hint, int):
                return min(candidates, key=lambda pair: abs(pair[0] - hint))
            return candidates[0]
    return None


def link_evidence_timestamps(
    subtype_analysis: Dict[str, Any],
    line_spans: List[Dict[str, Any]],
    source_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    subtype_analysis 안의 evidence 마다 원본 음성 시각(start_ms / end_ms / segment_ids)을 timestamps 로 붙인다.

    source_text(line_spans 를 만든 원래 글)를 주면 인용문 위치를 그 글에서 다시 찾는다(모듈 docstring). 주지 않으면
    evidence_start / evidence_end 를 그대로 믿는다(가리지 않은 글로 분석한 경우).
    evidence_verified 가 False 이거나 위치가 없으면 timestamps 는 None(불확실한 근거에 잘못된 구간을 잇지 않는다).
    """

    for major_result in subtype_analysis.get("results", []):
        for subtype in major_result.get("subtypes", []):
            for evidence in subtype.get("evidences", []):
                if not evidence.get("evidence_verified"):
                    evidence["timestamps"] = None
                    continue

                if source_text is not None:
                    located = relocate_evidence(evidence, source_text)
                    if located is None:
                        evidence["timestamps"] = None
                        continue
                    evidence["evidence_start"], evidence["evidence_end"] = located

                start_char = evidence.get("evidence_start")
                end_char = evidence.get("evidence_end")
                if start_char is None or end_char is None:
                    evidence["timestamps"] = None
                    continue

                matches = find_spans_for_char_range(start_char, end_char, line_spans)
                if not matches:
                    evidence["timestamps"] = None
                    continue

                evidence["timestamps"] = {
                    "start_ms": min(span["start_ms"] for span in matches),
                    "end_ms": max(span["end_ms"] for span in matches),
                    "segment_ids": [span["segment_id"] for span in matches],
                }

    return subtype_analysis
