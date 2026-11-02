# 근거 인용 → STT 줄 연결(ai/modeling/abuse/evidence_location.py, 2026-11-02).
#
# 데모 11/02: 2차 분석은 이름을 가린 글로 인용 위치를 계산하는데 줄 위치는 원래 글로 계산해서, 이름('하준이' → '[이름1]')
# 뒤의 근거가 두 줄 밀린 줄(상담원 되묻기 · 다음 아동 대답)에 붙었다. 원래 글에서 다시 찾아 바른 줄에 붙는지 본다. 가상 데이터.

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.abuse.evidence_location import (  # noqa: E402
    build_line_char_spans,
    link_evidence_timestamps,
    relocate_evidence,
)

LINES = [
    ("상담사", "맞을 때 하준이는", {"segment_id": "seg_001", "start_ms": 114000, "end_ms": 115500}),
    ("상담사", "있으면 말해주고 없으면 없다고 해줘. 손바닥으로", {"segment_id": "seg_002", "start_ms": 199000, "end_ms": 203000}),
    ("아동", "머리 한대", {"segment_id": "seg_003", "start_ms": 204000, "end_ms": 205500}),
    ("상담사", "머리를 맞은 적도 있구나", {"segment_id": "seg_004", "start_ms": 209000, "end_ms": 211000}),
    ("상담사", "그건 언제쯤이야?", {"segment_id": "seg_005", "start_ms": 211000, "end_ms": 212500}),
    ("아동", "여름방학 때요, 한번이요.", {"segment_id": "seg_006", "start_ms": 213000, "end_ms": 215000}),
]


def _full(lines):
    return "\n".join(f"{speaker}: {text}" for speaker, text, _ in lines)


def _analysis(evidence):
    return {"results": [{"major_type": "신체학대", "subtypes": [{"type": "직접 신체 가해", "evidences": [evidence]}]}]}


def test_masked_offsets_are_relocated_to_original_lines():
    original = _full(LINES)
    masked = original.replace("하준이", "[이름1]")  # 글자 수가 1 늘어난다
    quote = "손바닥으로\n아동: 머리 한대"
    start = masked.index(quote) + 40  # 가린 글 기준 위치가 원래 글과 어긋난 상황(이름이 길면 몇 줄씩 밀린다)
    evidence = {"evidence": quote, "matched_evidence": quote, "evidence_verified": True,
                "evidence_start": start, "evidence_end": start + len(quote)}

    result = link_evidence_timestamps(_analysis(evidence), build_line_char_spans(LINES), source_text=original)

    timestamps = result["results"][0]["subtypes"][0]["evidences"][0]["timestamps"]
    assert timestamps["segment_ids"] == ["seg_002", "seg_003"]
    assert timestamps["start_ms"] == 199000 and timestamps["end_ms"] == 205500


def test_without_source_text_offsets_are_trusted_as_before():
    original = _full(LINES)
    quote = "아동: 여름방학 때요"
    start = original.index(quote)
    evidence = {"evidence": quote, "evidence_verified": True, "evidence_start": start, "evidence_end": start + len(quote)}

    result = link_evidence_timestamps(_analysis(evidence), build_line_char_spans(LINES))

    assert result["results"][0]["subtypes"][0]["evidences"][0]["timestamps"]["segment_ids"] == ["seg_006"]


def test_repeated_text_picks_occurrence_nearest_to_hint():
    source = "상담사: 손바닥으로\n아동: 네\n상담사: 손바닥으로"
    second = source.rindex("손바닥으로")

    assert relocate_evidence({"evidence": "손바닥으로", "evidence_start": second - 2}, source) == (second, second + 5)
    assert relocate_evidence({"evidence": "손바닥으로", "evidence_start": 0}, source) == (5, 10)


def test_whitespace_differences_and_missing_quotes():
    source = "아동: 머리   한대\n상담사: 그랬구나"

    assert relocate_evidence({"evidence": "머리 한대"}, source) == (4, 11)
    assert relocate_evidence({"evidence": "발로 찼어요"}, source) is None


def test_unfound_quote_gets_no_timestamps_instead_of_wrong_lines():
    evidence = {"evidence": "지어낸 문장", "evidence_verified": True, "evidence_start": 10, "evidence_end": 20}

    result = link_evidence_timestamps(_analysis(evidence), build_line_char_spans(LINES), source_text=_full(LINES))

    assert result["results"][0]["subtypes"][0]["evidences"][0]["timestamps"] is None


def test_unverified_evidence_is_not_linked():
    evidence = {"evidence": "머리 한대", "evidence_verified": False, "evidence_start": 0, "evidence_end": 5}

    result = link_evidence_timestamps(_analysis(evidence), build_line_char_spans(LINES), source_text=_full(LINES))

    assert result["results"][0]["subtypes"][0]["evidences"][0]["timestamps"] is None
