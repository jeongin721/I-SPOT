from __future__ import annotations

from typing import Any


class RagPrivacyBlocked(RuntimeError):
    """비식별 검증을 통과하지 못해 외부 전송(임베딩·LLM)을 막았다.

    reasons 에는 원문이 아니라 막힌 사유만 담긴다(privacy_gateway 규약).
    """

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("비식별 검증을 통과하지 못해 RAG 분석을 하지 않았습니다: " + "; ".join(reasons))


def mask_text(
    text: str,
    known_identifiers: list[str] | None = None,
) -> tuple[str, dict[str, str]]:
    """외부(OpenAI 임베딩·LLM)로 보내기 전에 상담 문장의 개인 식별 정보를 가린다.

    9/18 회의 결정(외부 LLM 에는 비식별한 텍스트만)에 따라 팀 공용 관문
    ai.modeling.abuse.privacy_gateway.mask_for_outbound 를 그대로 쓴다.
    가린 뒤 다시 검사해 남은 식별 정보가 있으면 전송을 막는다(RagPrivacyBlocked).

    반환하는 entity_map(토큰 → 원문)은 로컬 전용이다. 외부로 보내거나 로그에 남기지 않는다.
    NER 모델을 올리는 데 시간이 걸려 처음 부를 때 import 한다.
    """
    if not text or not text.strip():
        return text, {}

    from ai.modeling.abuse.privacy_gateway import PrivacyGatewayBlocked, mask_for_outbound

    try:
        return mask_for_outbound(text, known_identifiers=known_identifiers)
    except PrivacyGatewayBlocked as error:
        raise RagPrivacyBlocked(list(error.reasons)) from None


def restore(value: Any, entity_map: dict[str, str]) -> Any:
    """결과(str/dict/list)에 남은 비식별 토큰을 원문으로 되돌린다. 상담사 화면에는 원문이 보여야 한다."""
    if not entity_map:
        return value

    from ai.modeling.abuse.pii_masking import restore_pii

    return restore_pii(value, entity_map)
