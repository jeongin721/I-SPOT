"""
마스킹/Privacy Gateway가 실제로 어떻게 동작하는지 눈으로 확인하는 용도의
개발자용 스크립트. 서비스 코드에서는 쓰지 않는다(마스킹된 텍스트는
외부 LLM 호출 직전/직후에만 잠깐 존재하고 로그에도 남기지 않는 게
설계 의도).

사용법:
    python3 -m ai.modeling.abuse.check_masking "확인할 텍스트"
    python3 -m ai.modeling.abuse.check_masking "확인할 텍스트" --known 김민수,박영희
"""

import argparse

from ai.modeling.abuse.pii_masking import mask_pii
from ai.modeling.abuse.privacy_gateway import review, PrivacyGatewayBlocked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="마스킹을 확인할 텍스트")
    parser.add_argument(
        "--known",
        default="",
        help="등록된 실명(쉼표로 구분) — Privacy Gateway Tier 2 테스트용",
    )
    args = parser.parse_args()

    known_identifiers = [
        name.strip() for name in args.known.split(",") if name.strip()
    ]

    print("=== 원문 ===")
    print(args.text)
    print()

    print("=== 1) mask_pii() — 로컬 Ollama로 갈 때 적용되는 최선형 마스킹 ===")
    masked, entity_map = mask_pii(args.text)
    print("마스킹 결과:", masked)
    print("entity_map(로컬 전용, 외부 전송 안 함):", entity_map)
    print()

    print("=== 2) Privacy Gateway review() — 2차(OpenAI)로 갈 때 적용되는 차단형 검증 ===")
    try:
        result = review({"text": args.text}, known_identifiers=known_identifiers)
        print("통과 — 실제 전송될 텍스트:", result.payload["text"])
        print("entity_map(로컬 전용, 외부 전송 안 함):", result.entity_map)
    except PrivacyGatewayBlocked as exc:
        print("차단됨 — 이 내용은 외부로 전송되지 않습니다.")
        print("차단 사유(필드 경로만, 실제 내용은 포함 안 됨):", exc.reasons)


if __name__ == "__main__":
    main()
