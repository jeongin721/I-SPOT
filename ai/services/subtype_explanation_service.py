"""
2차 세부유형 모델의 XAI 근거를 OpenAI LLM에 전달해 설명을 생성한다.
LLM은 subtype을 변경하지 않고 XAI 후보 선별과 설명만 수행한다.
"""

# ============================================================
# 1. Import
# ============================================================

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

from ai.schemas.subtype_explanation import (
    SubtypeExplanationOutput,
)
from dotenv import load_dotenv

# ============================================================
# 환경변수 로드
# ============================================================

load_dotenv()


# ============================================================
# 2. 기본 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROMPT_PATH = (
    PROJECT_ROOT
    / "ai"
    / "prompts"
    / "subtype_explanation.txt"
)

MODEL_NAME = os.getenv(
    "I_SPOT_LLM_MODEL",
    "gpt-5.6-luna",
)


# ============================================================
# 3. Prompt 로드
# ============================================================

def _load_prompt() -> str:
    """
    세부유형 XAI 설명용 System Prompt를 읽는다.
    """

    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Prompt 파일을 찾을 수 없습니다: {PROMPT_PATH}"
        )

    return PROMPT_PATH.read_text(
        encoding="utf-8"
    ).strip()


# ============================================================
# 4. 문자열 중복 제거
# ============================================================

def _is_duplicate_candidate(
    candidates: List[Dict[str, str]],
    evidence_text: str,
    source_text: str,
) -> bool:
    """
    동일한 XAI 표현 + 동일한 원문 조합이
    이미 후보에 존재하는지 확인한다.
    """

    for candidate in candidates:

        if (
            candidate["evidence_text"] == evidence_text
            and candidate["source_text"] == source_text
        ):
            return True

    return False


# ============================================================
# 5. XAI 결과 → LLM 입력 변환
# ============================================================

def build_subtype_explanation_input(
    subtype_signals: Dict[
        str,
        Dict[str, Any],
    ],
) -> Dict[str, Any]:
    """
    infer_session.py의 subtype_signals에서
    탐지된 세부유형과 XAI 근거만 추출한다.

    최종 구조:

    {
        "detected_subtypes": [
            {
                "subtype": "...",
                "subtype_name": "...",
                "evidence_candidates": [
                    {
                        "evidence_text": "...",
                        "source_text": "..."
                    }
                ]
            }
        ]
    }
    """

    detected_subtypes: List[
        Dict[str, Any]
    ] = []

    # --------------------------------------------------------
    # 탐지된 subtype 순회
    # --------------------------------------------------------

    for (
        subtype,
        result,
    ) in subtype_signals.items():

        if not result.get(
            "detected",
            False,
        ):
            continue

        evidence_candidates: List[
            Dict[str, str]
        ] = []

        # ----------------------------------------------------
        # Phrase Occlusion → Segment 연결 결과 읽기
        # ----------------------------------------------------

        for evidence in result.get(
            "evidence",
            [],
        ):

            # 현재 infer_session.py에서 사용하는 이름을 우선 사용하고,
            # 기존 코드 호환을 위해 몇 가지 이름도 같이 허용한다.
            evidence_text = (
                evidence.get("phrase")
                or evidence.get("evidence_text")
                or ""
            )

            source_text = (
                evidence.get("text")
                or evidence.get("source_text")
                or ""
            )

            evidence_text = (
                str(evidence_text).strip()
            )

            source_text = (
                str(source_text).strip()
            )

            # ------------------------------------------------
            # 빈 XAI 후보는 LLM에 보내지 않음
            # ------------------------------------------------

            if not evidence_text:
                continue

            if not source_text:
                continue

            # ------------------------------------------------
            # XAI 표현이 실제 원문에 없는 경우 제외
            #
            # LLM이 잘못된 근거를 설명하는 것을
            # 입력 단계에서 한 번 더 방지한다.
            # ------------------------------------------------

            if evidence_text not in source_text:
                continue

            # ------------------------------------------------
            # 동일 후보 중복 방지
            # ------------------------------------------------

            if _is_duplicate_candidate(
                candidates=evidence_candidates,
                evidence_text=evidence_text,
                source_text=source_text,
            ):
                continue

            evidence_candidates.append(
                {
                    "evidence_text": (
                        evidence_text
                    ),
                    "source_text": (
                        source_text
                    ),
                }
            )

        # ----------------------------------------------------
        # subtype 자체는 삭제하지 않음
        #
        # XAI 후보가 없어도 LLM에 subtype을 넘겨서
        # evidence=[] + warning을 생성할 수 있게 한다.
        # ----------------------------------------------------

        detected_subtypes.append(
            {
                "subtype": subtype,
                "subtype_name": (
                    result.get(
                        "display_name",
                        subtype,
                    )
                ),
                "evidence_candidates": (
                    evidence_candidates
                ),
            }
        )

    return {
        "detected_subtypes": (
            detected_subtypes
        )
    }


# ============================================================
# 6. LLM 호출
# ============================================================

def generate_subtype_explanations(
    subtype_signals: Dict[
        str,
        Dict[str, Any],
    ],
) -> SubtypeExplanationOutput:
    """
    2차 모델 + XAI 결과를 입력받아
    상담사용 근거 설명 Structured Output을 생성한다.
    """

    # --------------------------------------------------------
    # LLM 입력 생성
    # --------------------------------------------------------

    input_data = (
        build_subtype_explanation_input(
            subtype_signals
        )
    )

    # --------------------------------------------------------
    # 탐지된 subtype 자체가 없으면 API 호출하지 않음
    # --------------------------------------------------------

    if not input_data[
        "detected_subtypes"
    ]:
        return SubtypeExplanationOutput()

    # --------------------------------------------------------
    # API Key 확인
    # --------------------------------------------------------

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 설정되지 않았습니다."
        )

    # --------------------------------------------------------
    # OpenAI Client
    # --------------------------------------------------------

    client = OpenAI(
        api_key=api_key
    )

    system_prompt = _load_prompt()

    # --------------------------------------------------------
    # Structured Output 호출
    # --------------------------------------------------------

    try:

        response = (
            client.beta.chat.completions.parse(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            system_prompt
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            json.dumps(
                                input_data,
                                ensure_ascii=False,
                                indent=2,
                            )
                        ),
                    },
                ],
                response_format=(
                    SubtypeExplanationOutput
                ),
            )
        )

    except Exception as exc:

        raise RuntimeError(
            "세부유형 LLM 설명 생성 중 "
            f"OpenAI API 오류가 발생했습니다: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Parsed Structured Output
    # --------------------------------------------------------

    parsed = (
        response
        .choices[0]
        .message
        .parsed
    )

    if parsed is None:
        raise RuntimeError(
            "세부유형 LLM Structured Output "
            "파싱에 실패했습니다."
        )

    return parsed