"""
I-SPOT 2차 LLM 설명 Validator를 Mock 데이터로 테스트한다.
정상 출력은 통과하고 subtype·XAI 근거·원문 변조는 차단되는지 확인한다.
"""

# ============================================================
# 1. Import
# ============================================================

from ai.schemas.subtype_explanation import (
    SubtypeExplanationItem,
    SubtypeExplanationOutput,
)

from ai.services.subtype_explanation_validator import (
    SubtypeExplanationValidationError,
    validate_subtype_explanation,
)


# ============================================================
# 2. Mock LLM Input
# ============================================================

MOCK_INPUT = {
    "original_text": (
        "아빠가 화가 나서 막대기로 "
        "제 팔을 여러 번 때렸어요."
    ),
    "detected_subtypes": [
        {
            "subtype": "physical_direct",
            "subtype_name": "직접 신체 가해",
            "evidence_candidates": [
                "때렸어요.",
                "팔을",
                "막대기로",
            ],
        },
        {
            "subtype": "physical_object",
            "subtype_name": "도구 사용 가해",
            "evidence_candidates": [
                "막대기로",
                "팔을",
                "때렸어요.",
            ],
        },
    ],
}


# ============================================================
# 3. 공통 테스트 실행 함수
# ============================================================

def run_test(
    test_name: str,
    output: SubtypeExplanationOutput,
    should_pass: bool,
) -> bool:
    """
    하나의 Mock LLM 출력을 Validator에 넣어 테스트한다.

    should_pass=True:
        Validation 성공이 정상

    should_pass=False:
        Validation 실패가 정상
    """

    print()
    print("=" * 70)
    print(f"TEST: {test_name}")
    print("=" * 70)

    try:
        validate_subtype_explanation(
            llm_input=MOCK_INPUT,
            llm_output=output,
        )

        if should_pass:
            print("[PASS] 정상적으로 Validation을 통과했습니다.")
            return True

        print(
            "[FAIL] 차단되어야 하는 출력이 "
            "Validation을 통과했습니다."
        )
        return False

    except SubtypeExplanationValidationError as error:

        if not should_pass:
            print("[PASS] 잘못된 출력을 정상적으로 차단했습니다.")
            print()
            print(error)
            return True

        print(
            "[FAIL] 정상 출력이 Validation에서 차단되었습니다."
        )
        print()
        print(error)
        return False


# ============================================================
# 4. TEST 1
# 정상 출력
# ============================================================

def test_valid_output() -> bool:
    """
    XAI 후보 중 핵심 표현만 선택하고
    원문을 그대로 유지한 정상적인 LLM 출력이다.
    """

    output = SubtypeExplanationOutput(
        schema_version="1.0",
        explanations=[
            SubtypeExplanationItem(
                subtype="physical_direct",
                subtype_name="직접 신체 가해",
                evidence_text=[
                    "때렸어요.",
                ],
                source_text=MOCK_INPUT[
                    "original_text"
                ],
                explanation=(
                    "'때렸어요.'라는 표현은 "
                    "직접적인 신체 가격 행위와 관련된 표현으로, "
                    "직접 신체 가해 관련 신호 탐지에 "
                    "기여한 것으로 볼 수 있습니다."
                ),
            ),
            SubtypeExplanationItem(
                subtype="physical_object",
                subtype_name="도구 사용 가해",
                evidence_text=[
                    "막대기로",
                ],
                source_text=MOCK_INPUT[
                    "original_text"
                ],
                explanation=(
                    "'막대기로'라는 표현은 "
                    "도구를 사용한 신체 가격과 관련된 표현으로, "
                    "도구 사용 가해 관련 신호 탐지에 "
                    "기여한 것으로 볼 수 있습니다."
                ),
            ),
        ],
        warnings=[],
    )

    return run_test(
        test_name="정상 출력",
        output=output,
        should_pass=True,
    )


# ============================================================
# 5. TEST 2
# XAI에 없는 근거 생성
# ============================================================

def test_fake_evidence() -> bool:
    """
    LLM이 XAI가 제시하지 않은 표현을
    evidence_text로 새롭게 생성한 경우다.
    """

    output = SubtypeExplanationOutput(
        schema_version="1.0",
        explanations=[
            SubtypeExplanationItem(
                subtype="physical_direct",
                subtype_name="직접 신체 가해",
                evidence_text=[
                    "여러 번 폭행했어요.",
                ],
                source_text=MOCK_INPUT[
                    "original_text"
                ],
                explanation="잘못된 Mock 설명",
            ),
            SubtypeExplanationItem(
                subtype="physical_object",
                subtype_name="도구 사용 가해",
                evidence_text=[
                    "막대기로",
                ],
                source_text=MOCK_INPUT[
                    "original_text"
                ],
                explanation="Mock 설명",
            ),
        ],
        warnings=[],
    )

    return run_test(
        test_name="XAI에 없는 근거 생성",
        output=output,
        should_pass=False,
    )


# ============================================================
# 6. TEST 3
# Subtype 변경
# ============================================================

def test_changed_subtype() -> bool:
    """
    LLM이 모델이 탐지하지 않은 subtype을
    새롭게 추가한 경우다.
    """

    output = SubtypeExplanationOutput(
        schema_version="1.0",
        explanations=[
            SubtypeExplanationItem(
                subtype="physical_direct",
                subtype_name="직접 신체 가해",
                evidence_text=[
                    "때렸어요.",
                ],
                source_text=MOCK_INPUT[
                    "original_text"
                ],
                explanation="Mock 설명",
            ),
            SubtypeExplanationItem(
                subtype="emotional_threat",
                subtype_name="위협·쫓아냄",
                evidence_text=[
                    "막대기로",
                ],
                source_text=MOCK_INPUT[
                    "original_text"
                ],
                explanation="잘못된 Mock 설명",
            ),
        ],
        warnings=[],
    )

    return run_test(
        test_name="Subtype 임의 변경",
        output=output,
        should_pass=False,
    )


# ============================================================
# 7. TEST 4
# Source Text 변경
# ============================================================

def test_changed_source_text() -> bool:
    """
    LLM이 원본 상담 발화를 수정하거나
    재작성한 경우다.
    """

    output = SubtypeExplanationOutput(
        schema_version="1.0",
        explanations=[
            SubtypeExplanationItem(
                subtype="physical_direct",
                subtype_name="직접 신체 가해",
                evidence_text=[
                    "때렸어요.",
                ],
                source_text=(
                    "아버지가 막대기로 "
                    "아동의 팔을 폭행했습니다."
                ),
                explanation="잘못된 Mock 설명",
            ),
            SubtypeExplanationItem(
                subtype="physical_object",
                subtype_name="도구 사용 가해",
                evidence_text=[
                    "막대기로",
                ],
                source_text=MOCK_INPUT[
                    "original_text"
                ],
                explanation="Mock 설명",
            ),
        ],
        warnings=[],
    )

    return run_test(
        test_name="Source Text 임의 변경",
        output=output,
        should_pass=False,
    )


# ============================================================
# 8. TEST 5
# Subtype 누락
# ============================================================

def test_missing_subtype() -> bool:
    """
    LLM이 모델이 탐지한 subtype 중 하나를
    출력에서 임의로 누락한 경우다.
    """

    output = SubtypeExplanationOutput(
        schema_version="1.0",
        explanations=[
            SubtypeExplanationItem(
                subtype="physical_direct",
                subtype_name="직접 신체 가해",
                evidence_text=[
                    "때렸어요.",
                ],
                source_text=MOCK_INPUT[
                    "original_text"
                ],
                explanation="Mock 설명",
            ),
        ],
        warnings=[],
    )

    return run_test(
        test_name="탐지 Subtype 누락",
        output=output,
        should_pass=False,
    )


# ============================================================
# 9. 전체 테스트
# ============================================================

def main() -> None:
    """모든 Validator Mock 테스트를 실행한다."""

    print()
    print("=" * 70)
    print("I-SPOT 2차 LLM 설명 Validator Mock Test")
    print("=" * 70)

    results = [
        test_valid_output(),
        test_fake_evidence(),
        test_changed_subtype(),
        test_changed_source_text(),
        test_missing_subtype(),
    ]

    passed = sum(results)
    total = len(results)

    print()
    print("=" * 70)
    print("최종 결과")
    print("=" * 70)
    print(f"PASS: {passed}/{total}")

    if passed == total:
        print(
            "모든 Validator 테스트가 정상적으로 통과했습니다."
        )
    else:
        print(
            "일부 Validator 테스트를 확인해야 합니다."
        )


# ============================================================
# 10. Entry Point
# ============================================================

if __name__ == "__main__":
    main()