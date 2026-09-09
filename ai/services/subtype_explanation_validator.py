"""
I-SPOT 2차 세부유형 LLM 설명 결과를 검증하는 Validator다.
LLM이 subtype·XAI 근거·원문을 변경하거나 새로운 근거를 생성했는지 검사한다.
"""

# ============================================================
# 1. Import
# ============================================================

from typing import Dict, List, Set

from ai.schemas.subtype_explanation import (
    SubtypeExplanationOutput,
)


# ============================================================
# 2. Validation Error
# ============================================================

class SubtypeExplanationValidationError(ValueError):
    """2차 세부유형 LLM 설명 검증 실패 시 발생하는 오류다."""

    pass


# ============================================================
# 3. 입력 Subtype Map 생성
# ============================================================

def _build_input_subtype_map(
    llm_input: Dict,
) -> Dict[str, Dict]:
    """
    LLM 입력의 detected_subtypes를 subtype 기준 Dictionary로 변환한다.
    """

    subtype_map = {}

    for item in llm_input.get(
        "detected_subtypes",
        [],
    ):

        subtype = item.get(
            "subtype"
        )

        if not subtype:
            continue

        subtype_map[subtype] = item

    return subtype_map


# ============================================================
# 4. evidence_text 검증
# ============================================================

def _validate_evidence(
    subtype: str,
    evidence_text: List[str],
    evidence_candidates: List[str],
    original_text: str,
) -> List[str]:
    """
    LLM이 선택한 evidence_text를 검증한다.

    모든 evidence_text는:
    1. XAI evidence_candidates에 존재해야 하고
    2. original_text에도 실제 존재해야 한다.
    """

    errors = []

    candidate_set: Set[str] = set(
        evidence_candidates
    )

    for evidence in evidence_text:

        # ----------------------------------------------------
        # 빈 근거 방지
        # ----------------------------------------------------

        if not evidence.strip():

            errors.append(
                f"{subtype}: 빈 evidence_text가 포함되어 있습니다."
            )

            continue

        # ----------------------------------------------------
        # XAI 후보에 실제 존재하는지 확인
        # ----------------------------------------------------

        if evidence not in candidate_set:

            errors.append(
                f"{subtype}: evidence_text '{evidence}'가 "
                f"XAI evidence_candidates에 존재하지 않습니다."
            )

        # ----------------------------------------------------
        # 원문에 실제 존재하는지 확인
        # ----------------------------------------------------

        if evidence not in original_text:

            errors.append(
                f"{subtype}: evidence_text '{evidence}'가 "
                f"original_text에 존재하지 않습니다."
            )

    return errors


# ============================================================
# 5. 전체 LLM 출력 검증
# ============================================================

def validate_subtype_explanation(
    llm_input: Dict,
    llm_output: SubtypeExplanationOutput,
) -> None:
    """
    2차 세부유형 LLM 출력 전체를 검증한다.

    검증 항목:
    - 입력에 없는 subtype 추가 여부
    - subtype 누락 여부
    - subtype_name 변경 여부
    - subtype 중복 여부
    - evidence_text의 XAI 후보 포함 여부
    - evidence_text의 원문 포함 여부
    - source_text 원문 동일 여부

    문제가 있으면 SubtypeExplanationValidationError를 발생시킨다.
    """

    errors = []

    original_text = llm_input.get(
        "original_text",
        "",
    )

    input_subtype_map = (
        _build_input_subtype_map(
            llm_input
        )
    )

    input_subtypes = set(
        input_subtype_map.keys()
    )

    # --------------------------------------------------------
    # LLM 출력 subtype 수집
    # --------------------------------------------------------

    output_subtypes = []

    for explanation in llm_output.explanations:

        output_subtypes.append(
            explanation.subtype
        )

    output_subtype_set = set(
        output_subtypes
    )

    # --------------------------------------------------------
    # 중복 subtype 검사
    # --------------------------------------------------------

    if len(output_subtypes) != len(
        output_subtype_set
    ):

        errors.append(
            "LLM 출력에 중복된 subtype이 존재합니다."
        )

    # --------------------------------------------------------
    # 새 subtype 생성 검사
    # --------------------------------------------------------

    added_subtypes = (
        output_subtype_set
        - input_subtypes
    )

    if added_subtypes:

        errors.append(
            "LLM이 입력에 없는 subtype을 추가했습니다: "
            + ", ".join(
                sorted(
                    added_subtypes
                )
            )
        )

    # --------------------------------------------------------
    # 기존 subtype 삭제 검사
    # --------------------------------------------------------

    missing_subtypes = (
        input_subtypes
        - output_subtype_set
    )

    if missing_subtypes:

        errors.append(
            "LLM이 입력 subtype을 누락했습니다: "
            + ", ".join(
                sorted(
                    missing_subtypes
                )
            )
        )

    # --------------------------------------------------------
    # 개별 explanation 검사
    # --------------------------------------------------------

    for explanation in llm_output.explanations:

        subtype = explanation.subtype

        # 입력에 없는 subtype은 위에서 이미 오류 처리
        if subtype not in input_subtype_map:
            continue

        input_item = (
            input_subtype_map[
                subtype
            ]
        )

        expected_name = (
            input_item.get(
                "subtype_name",
                "",
            )
        )

        evidence_candidates = (
            input_item.get(
                "evidence_candidates",
                [],
            )
        )

        # ----------------------------------------------------
        # subtype_name 변경 검사
        # ----------------------------------------------------

        if (
            explanation.subtype_name
            != expected_name
        ):

            errors.append(
                f"{subtype}: subtype_name이 변경되었습니다. "
                f"expected='{expected_name}', "
                f"actual='{explanation.subtype_name}'"
            )

        # ----------------------------------------------------
        # source_text 변경 검사
        # ----------------------------------------------------

        if (
            explanation.source_text
            != original_text
        ):

            errors.append(
                f"{subtype}: source_text가 "
                f"original_text와 일치하지 않습니다."
            )

        # ----------------------------------------------------
        # XAI 근거 검사
        # ----------------------------------------------------

        evidence_errors = (
            _validate_evidence(
                subtype=subtype,
                evidence_text=(
                    explanation.evidence_text
                ),
                evidence_candidates=(
                    evidence_candidates
                ),
                original_text=(
                    original_text
                ),
            )
        )

        errors.extend(
            evidence_errors
        )

    # --------------------------------------------------------
    # 최종 Validation
    # --------------------------------------------------------

    if errors:

        error_message = (
            "2차 세부유형 LLM 설명 검증 실패:\n- "
            + "\n- ".join(
                errors
            )
        )

        raise (
            SubtypeExplanationValidationError(
                error_message
            )
        )


# ============================================================
# 6. Boolean Validation Helper
# ============================================================

def is_valid_subtype_explanation(
    llm_input: Dict,
    llm_output: SubtypeExplanationOutput,
) -> bool:
    """
    예외 대신 True/False가 필요한 경우 사용하는 Helper다.
    """

    try:

        validate_subtype_explanation(
            llm_input=llm_input,
            llm_output=llm_output,
        )

        return True

    except SubtypeExplanationValidationError:

        return False