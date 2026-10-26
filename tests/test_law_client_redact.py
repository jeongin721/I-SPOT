# law/client.py의 OC(국가법령정보센터 인증값) 가리기 로직을 테스트한다.
#
# 2026-10-26 민규 교차검증으로 발견: requests.RequestException을 그대로
# str()로 찍으면 실패한 요청의 전체 URL이 메시지에 들어가는데, 그 URL에
# OC=<실제 인증값>이 그대로 박혀 있다. 이 메시지가 law_qa_llm.py의 답변
# 텍스트로 그대로 나가거나 로그에 남으면 인증값이 유출된다 — 이 테스트가
# 그 가리기 로직을 고정한다.

from law.client import _redact_oc


def test_redact_oc_masks_query_param_value():
    url = "https://www.law.go.kr/DRF/lawSearch.do?OC=realsecretvalue123&target=law"

    redacted = _redact_oc(url)

    assert "realsecretvalue123" not in redacted
    assert "OC=***" in redacted


def test_redact_oc_handles_oc_as_first_param():
    url = "https://www.law.go.kr/DRF/lawSearch.do?OC=realsecretvalue123"

    redacted = _redact_oc(url)

    assert "realsecretvalue123" not in redacted


def test_redact_oc_is_case_insensitive():
    # requests 예외 메시지나 서버가 쿼리 문자열을 그대로 돌려줄 때
    # 대소문자가 달라질 수 있어 둘 다 가린다.
    url = "https://www.law.go.kr/DRF/lawSearch.do?oc=realsecretvalue123&target=law"

    redacted = _redact_oc(url)

    assert "realsecretvalue123" not in redacted


def test_redact_oc_leaves_text_without_oc_param_unchanged():
    text = "ConnectionError: Max retries exceeded with no OC in it"

    assert _redact_oc(text) == text


def test_redact_oc_only_masks_oc_not_other_params():
    url = "https://www.law.go.kr/DRF/lawSearch.do?target=law&OC=secret&type=JSON"

    redacted = _redact_oc(url)

    assert "secret" not in redacted
    assert "target=law" in redacted
    assert "type=JSON" in redacted
