# 검수된 Transcript 에서 RAG 입력을 만드는 규칙과 가이드북 판례 추출을 테스트한다.
# 외부 호출(OpenAI · 국가법령정보센터)은 하지 않는다.

from langchain_core.documents import Document

import rag.session as session
from rag.precedents import extract_precedent_cases
from rag.privacy import RagPrivacyBlocked


def make_transcript():
    return {
        "schema_version": "1.0",
        "segments": [
            {"segment_id": "seg_003", "speaker": "CHILD", "start_ms": 9000, "text": "등이랑 팔이 아파요."},
            {"segment_id": "seg_001", "speaker": "COUNSELOR", "start_ms": 0, "text": "집에서는 어때?"},
            {"segment_id": "seg_002", "speaker": "CHILD", "start_ms": 3000, "text": "아빠가 때렸어요."},
            {"segment_id": "seg_004", "speaker": "GUARDIAN", "start_ms": 12000, "text": "애가 거짓말하는 거예요."},
            {"segment_id": "seg_005", "speaker": "UNKNOWN", "start_ms": 15000, "text": "밥도 안 줄 때가 있어요."},
        ],
    }


def test_child_text_uses_only_child_segments_in_time_order():
    child = session.child_text_from_transcript(make_transcript())

    assert child["text"] == "아빠가 때렸어요. 등이랑 팔이 아파요."
    assert child["child_segment_ids"] == ["seg_002", "seg_003"]
    assert child["excluded_speakers"] == {"COUNSELOR": 1, "GUARDIAN": 1, "UNKNOWN": 1}


def test_no_child_speech_skips_analysis(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("아동 발화가 없으면 분석을 부르지 않는다")

    monkeypatch.setattr(session, "analyze_consultation_evidence", fail)
    monkeypatch.setattr(session, "build_screen_references", fail)

    transcript = {"segments": [{"segment_id": "s1", "speaker": "GUARDIAN", "text": "괜찮아요."}]}
    result = session.analyze_reviewed_transcript(transcript, "physical")

    assert result["rag_analysis"] is None
    assert result["manual_screen_references"] is None
    assert result["excluded_speakers"] == {"GUARDIAN": 1}


def test_privacy_block_is_reported_without_content(monkeypatch):
    def blocked(*args, **kwargs):
        raise RagPrivacyBlocked(["text: NER 개체 잔존(PS)"])

    monkeypatch.setattr(session, "analyze_consultation_evidence", blocked)
    monkeypatch.setattr(session, "build_screen_references", blocked)

    result = session.analyze_reviewed_transcript(make_transcript(), "physical")

    for key in ("rag_analysis", "manual_screen_references"):
        assert result[key]["privacy_blocked"] is True
        assert result[key]["reasons"] == ["text: NER 개체 잔존(PS)"]
        assert "아빠" not in result[key]["error"]


def test_other_errors_keep_only_exception_type(monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("아빠가 때렸어요 원문이 섞인 문구")

    monkeypatch.setattr(session, "analyze_consultation_evidence", broken)
    monkeypatch.setattr(session, "build_screen_references", lambda *a, **k: {"references": {}, "errors": {}})

    result = session.analyze_reviewed_transcript(make_transcript(), "physical")

    assert result["rag_analysis"] == {"error": "RAG 근거자료 분석 중 오류가 발생했습니다: ValueError"}


def make_page(page, text):
    return Document(page_content=text, metadata={"page": page, "source": "guide.pdf"})


def test_extract_precedent_cases_across_pages():
    pages = [
        make_page(
            21,
            "021\n"
            " ❖ 판례로 보는 신체학대 사례 – 학대행위자가 부모 등인 경우\n"
            "친부가 자녀를 때림\n"
            "피고인은 피해아동의 친부이다. 피고인은 손바닥으로 피해아동의 얼굴을  \n"
            "3회 때렸다. (인천지방법원 \n"
            "2022고정1131)\n"
            "교사가 학생을 때림\n"
            "피고인은 교사이다. 피고인은 피해 아동을 때렸다. (수원지방법원 2021고\n",
        ),
        make_page(
            22,
            "022\n"
            "정650)\n"
            " ❖ 학대(의심)행위의 예시 \n"
            "• 판례가 아닌 목록\n",
        ),
    ]

    cases = extract_precedent_cases(pages)

    assert [case["title"] for case in cases] == ["친부가 자녀를 때림", "교사가 학생을 때림"]
    first, second = cases
    assert first["facts"] == "피고인은 피해아동의 친부이다. 피고인은 손바닥으로 피해아동의 얼굴을 3회 때렸다."
    assert first["citation"] == "인천지방법원 2022고정1131"
    assert first["abuse_type"] == "physical"
    assert first["perpetrator"] == "부모 등"
    assert first["page"] == 21
    assert second["case_number"] == "2021고정650"
    assert second["court"] == "수원지방법원"


def test_harvest_record_reads_facts_and_abuse_types():
    from rag.precedent_harvest import build_record

    detail = {
        "사건명": "아동복지법위반(아동학대)",
        "법원명": "춘천지법",
        "사건번호": "2015고단651",
        "선고일자": "20160122",
        "판시사항": "",
        "판결요지": "",
        "판례내용": (
            "【피 고 인】 피고인 【주 문】 피고인을 벌금에 처한다. 【이 유】 "
            "공소사실의 요지 가. 피고인은 어린이집에서 피해아동이 밥을 먹기 싫다고 하자 식판을 치웠다. "
            "이로써 피고인은 아동의 정신건강 및 발달에 해를 끼치는 정서적 학대행위를 하였다."
        ),
    }

    record = build_record("1", {}, detail)

    assert record["abuse_types"] == ["emotional"]
    assert record["title"] == "피고인은 어린이집에서 피해아동이 밥을 먹기 싫다고 하자 식판을 치웠다."
    assert record["facts"].startswith("공소사실의 요지 가. 피고인은 어린이집에서")
    assert record["citation"] == "춘천지법 2016. 1. 22. 2015고단651"
    assert record["url"] == "https://www.law.go.kr/LSW/precInfoP.do?precSeq=1"


def test_harvest_skips_cases_without_child_abuse_context():
    from rag.precedent_harvest import build_record

    detail = {"사건명": "노인복지법위반", "판례내용": "공소사실의 요지 피고인은 노인을 방임행위 하였다."}

    assert build_record("2", {}, detail) is None
