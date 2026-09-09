# 상담 텍스트
# → infer_subtype.py
# → 탐지된 세부유형
# → explain_subtype.py
# → 세부유형별 근거 표현 1~3개

"""
I-SPOT 2차 세부유형 모델의 Phrase Occlusion 기반 XAI 모듈이다.
모델은 전체 Q+A 문맥을 유지하고, XAI 근거 탐색은 CHILD 발화 내부에서만 수행한다.
"""

# ============================================================
# 1. Import
# ============================================================

from typing import Dict, List, Tuple

import torch
from tqdm import tqdm

from ai.modeling.abuse import infer_subtype as subtype_infer


# ============================================================
# 2. XAI 설정
# ============================================================

# 한 번에 가릴 최대 연속 어절 수
MAX_NGRAM = 4

# 세부유형별 최대 근거 표현 개수
TOP_K = 3

# 최소 logit 감소량
MIN_LOGIT_IMPORTANCE = 0.10

# 해당 라벨의 최대 중요도 대비 최소 비율
RELATIVE_IMPORTANCE_RATIO = 0.15

# GPU batch 추론 크기
BATCH_SIZE = 32


# ============================================================
# 3. 의미가 약한 단독 표현 제외
# ============================================================

LOW_VALUE_WORDS = {
    "나서",
    "해서",
    "근데",
    "그리고",
    "그래서",
    "그냥",
    "제가",
    "저를",
    "저랑",
    "나는",
    "저는",
    "아빠가",
    "엄마가",
}


# ============================================================
# 4. 화자 태그 설정
# ============================================================

SPEAKER_TAGS = [
    "[COUNSELOR]",
    "[CHILD]",
    "[GUARDIAN]",
    "[OTHER]",
    "[UNKNOWN]",
]


# ============================================================
# 5. CHILD 발화 위치 추출
# ============================================================

def extract_child_span(
    text: str,
) -> Tuple[str, int, int]:
    """
    전체 Q+A 텍스트에서 첫 번째 [CHILD] 발화 구간을 추출한다.

    반환:
        child_text:
            실제 CHILD 발화

        child_start:
            전체 원문에서 CHILD 발화가 시작되는 문자 위치

        child_end:
            전체 원문에서 CHILD 발화가 끝나는 문자 위치

    [CHILD] 태그가 없는 일반 텍스트는
    전체 문장을 XAI 탐색 범위로 사용한다.
    """

    child_tag = "[CHILD]"

    # --------------------------------------------------------
    # 화자 태그가 없는 일반 문장
    # --------------------------------------------------------

    if child_tag not in text:

        stripped_text = text.strip()

        if not stripped_text:
            return "", 0, 0

        start = text.find(
            stripped_text
        )

        end = (
            start
            + len(stripped_text)
        )

        return (
            stripped_text,
            start,
            end,
        )

    # --------------------------------------------------------
    # [CHILD] 태그 이후 위치
    # --------------------------------------------------------

    tag_end = (
        text.find(child_tag)
        + len(child_tag)
    )

    child_start = tag_end

    # [CHILD] 뒤 공백 제거
    while (
        child_start < len(text)
        and text[child_start].isspace()
    ):
        child_start += 1

    # --------------------------------------------------------
    # 다음 화자 태그가 있으면 CHILD 발화를 거기까지만 사용
    # --------------------------------------------------------

    child_end = len(text)

    for speaker_tag in SPEAKER_TAGS:

        next_position = text.find(
            speaker_tag,
            child_start,
        )

        if (
            next_position != -1
            and next_position < child_end
        ):
            child_end = next_position

    # --------------------------------------------------------
    # CHILD 발화 추출
    # --------------------------------------------------------

    child_text = text[
        child_start:
        child_end
    ].strip()

    if not child_text:
        return "", child_start, child_start

    # strip()으로 앞쪽 공백이 제거된 경우 위치 재보정
    actual_start = text.find(
        child_text,
        child_start,
        child_end,
    )

    if actual_start != -1:
        child_start = actual_start

    child_end = (
        child_start
        + len(child_text)
    )

    return (
        child_text,
        child_start,
        child_end,
    )


# ============================================================
# 6. 모델 준비
# ============================================================

def _prepare_model():
    """
    infer_subtype.py와 동일한 tokenizer/model을 사용한다.

    별도 모델을 로드하지 않아
    추론 모델과 XAI 모델이 달라지는 문제를 방지한다.
    """

    subtype_infer.load_subtype_model()

    return (
        subtype_infer.tokenizer,
        subtype_infer.model,
        subtype_infer.DEVICE,
    )


# ============================================================
# 7. Logit 계산
# ============================================================

@torch.no_grad()
def _get_logits(
    texts: List[str],
) -> torch.Tensor:
    """
    여러 문장의 raw logits를 batch로 계산한다.

    확률이 아니라 특정 표현 제거 전후의
    logit 감소량을 XAI 중요도로 사용한다.
    """

    tokenizer, model, device = (
        _prepare_model()
    )

    all_logits = []

    for start_index in range(
        0,
        len(texts),
        BATCH_SIZE,
    ):

        batch_texts = texts[
            start_index:
            start_index + BATCH_SIZE
        ]

        encoded = tokenizer(
            batch_texts,
            truncation=True,
            padding=True,
            max_length=(
                subtype_infer.MAX_LENGTH
            ),
            return_tensors="pt",
        )

        input_ids = encoded[
            "input_ids"
        ].to(device)

        attention_mask = encoded[
            "attention_mask"
        ].to(device)

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        all_logits.append(
            outputs.logits
            .detach()
            .cpu()
        )

    return torch.cat(
        all_logits,
        dim=0,
    )


# ============================================================
# 8. N-gram 후보 생성
# ============================================================

def _generate_ngram_candidates(
    child_text: str,
) -> List[Tuple[int, int, str]]:
    """
    CHILD 발화만 공백 단위로 분리한 뒤
    1~MAX_NGRAM 길이의 연속 표현 후보를 생성한다.

    COUNSELOR 질문과 [CHILD] 태그는
    후보 생성 대상에 포함되지 않는다.

    반환:
        [
            (
                start_index,
                end_index,
                phrase,
            ),
            ...
        ]
    """

    words = child_text.split()

    candidates = []

    for ngram_size in range(
        1,
        MAX_NGRAM + 1,
    ):

        if ngram_size > len(words):
            break

        for start_index in range(
            0,
            len(words)
            - ngram_size
            + 1,
        ):

            end_index = (
                start_index
                + ngram_size
            )

            phrase = " ".join(
                words[
                    start_index:
                    end_index
                ]
            )

            candidates.append(
                (
                    start_index,
                    end_index,
                    phrase,
                )
            )

    return candidates


# ============================================================
# 9. CHILD 발화 Occlusion
# ============================================================

def _make_occluded_child_text(
    words: List[str],
    start_index: int,
    end_index: int,
) -> str:
    """
    CHILD 발화 안에서 특정 표현만 제거한다.

    전체 Q+A를 삭제하거나 다시 구성하지 않고,
    CHILD 발화 중 XAI 후보 표현만 제거하기 위한 함수다.
    """

    remaining_words = (
        words[:start_index]
        + words[end_index:]
    )

    # CHILD 발화 전체가 제거되는 극단적 경우
    if not remaining_words:
        return "[MASK]"

    return " ".join(
        remaining_words
    )


# ============================================================
# 10. 전체 Q+A 문맥 복원
# ============================================================

def _rebuild_full_text(
    original_text: str,
    child_start: int,
    child_end: int,
    occluded_child_text: str,
) -> str:
    """
    전체 상담 Q+A 문맥을 유지하면서
    CHILD 발화 내부에서 선택한 표현만 제거한다.

    예:
        원본
        [COUNSELOR] 질문 [CHILD] 막대기로 때렸어요.

        '막대기로' Occlusion
        [COUNSELOR] 질문 [CHILD] 때렸어요.
    """

    prefix = original_text[
        :child_start
    ]

    suffix = original_text[
        child_end:
    ]

    return (
        prefix
        + occluded_child_text
        + suffix
    )


# ============================================================
# 11. Label별 Phrase Importance 계산
# ============================================================

def _calculate_phrase_importance(
    text: str,
    label: str,
) -> List[Dict]:
    """
    특정 세부유형 label에 대해
    CHILD 발화의 각 phrase를 제거했을 때
    해당 label의 logit이 얼마나 감소하는지 계산한다.

    중요:
        모델의 원본 입력은 전체 Q+A다.

        XAI 후보 생성 및 제거 범위만
        CHILD 발화 내부로 제한한다.
    """

    if label not in subtype_infer.LABEL_NAMES:

        raise ValueError(
            f"알 수 없는 subtype label: {label}"
        )

    # --------------------------------------------------------
    # CHILD 발화 추출
    # --------------------------------------------------------

    (
        child_text,
        child_start,
        child_end,
    ) = extract_child_span(
        text
    )

    if not child_text:
        return []

    child_words = (
        child_text.split()
    )

    if not child_words:
        return []

    # --------------------------------------------------------
    # Label Index
    # --------------------------------------------------------

    label_index = (
        subtype_infer
        .LABEL_NAMES
        .index(label)
    )

    # --------------------------------------------------------
    # 원본 전체 Q+A Logit
    # --------------------------------------------------------

    base_logits = _get_logits(
        [text]
    )

    base_logit = float(
        base_logits[
            0,
            label_index,
        ].item()
    )

    # --------------------------------------------------------
    # CHILD 발화에서만 N-gram 후보 생성
    # --------------------------------------------------------

    candidates = (
        _generate_ngram_candidates(
            child_text
        )
    )

    if not candidates:
        return []

    # --------------------------------------------------------
    # CHILD 표현만 제거한 전체 Q+A 문장 생성
    # --------------------------------------------------------

    occluded_texts = []

    for (
        start_index,
        end_index,
        _,
    ) in candidates:

        occluded_child_text = (
            _make_occluded_child_text(
                words=child_words,
                start_index=start_index,
                end_index=end_index,
            )
        )

        full_occluded_text = (
            _rebuild_full_text(
                original_text=text,
                child_start=child_start,
                child_end=child_end,
                occluded_child_text=(
                    occluded_child_text
                ),
            )
        )

        occluded_texts.append(
            full_occluded_text
        )

    # --------------------------------------------------------
    # 모든 Occlusion 문장 Batch 추론
    # --------------------------------------------------------

    occluded_logits = _get_logits(
        occluded_texts
    )

    results = []

    for candidate_index, (
        start_index,
        end_index,
        phrase,
    ) in enumerate(
        candidates
    ):

        removed_logit = float(
            occluded_logits[
                candidate_index,
                label_index,
            ].item()
        )

        importance = (
            base_logit
            - removed_logit
        )

        results.append(
            {
                "phrase": phrase,
                "importance": float(
                    importance
                ),
                "start_index": (
                    start_index
                ),
                "end_index": (
                    end_index
                ),
                "length": (
                    end_index
                    - start_index
                ),
            }
        )

    return results


# ============================================================
# 12. 겹치는 Phrase 판정
# ============================================================

def _is_overlap(
    first: Dict,
    second: Dict,
) -> bool:
    """
    CHILD 발화 내부에서 두 phrase의
    어절 위치가 겹치는지 확인한다.
    """

    return not (
        first["end_index"]
        <= second["start_index"]
        or
        second["end_index"]
        <= first["start_index"]
    )


# ============================================================
# 13. 최종 근거 Phrase 선택
# ============================================================

def _select_evidence_phrases(
    candidates: List[Dict],
    top_k: int = TOP_K,
) -> List[str]:
    """
    의미 있는 CHILD 발화 기반 XAI 표현을 선택한다.

    기준:
    - importance가 양수인 표현
    - 최소 중요도 기준 통과
    - 의미가 약한 단독 어절 제외
    - 지나치게 긴 표현이 유리하지 않도록 정규화
    - 서로 겹치는 후보 중복 제거
    """

    if not candidates:
        return []

    # --------------------------------------------------------
    # 양의 Importance만 사용
    # --------------------------------------------------------

    positive_candidates = [
        candidate
        for candidate in candidates
        if candidate[
            "importance"
        ] > 0
    ]

    if not positive_candidates:
        return []

    # --------------------------------------------------------
    # 상대 Importance Threshold
    # --------------------------------------------------------

    max_importance = max(
        candidate[
            "importance"
        ]
        for candidate
        in positive_candidates
    )

    minimum_threshold = max(
        MIN_LOGIT_IMPORTANCE,
        (
            max_importance
            * RELATIVE_IMPORTANCE_RATIO
        ),
    )

    filtered_candidates = []

    # --------------------------------------------------------
    # 후보 정제
    # --------------------------------------------------------

    for candidate in positive_candidates:

        phrase = (
            candidate[
                "phrase"
            ]
            .strip()
        )

        words = phrase.split()

        # 최소 importance 미달
        if (
            candidate[
                "importance"
            ]
            < minimum_threshold
        ):
            continue

        # 빈 표현
        if not phrase:
            continue

        # 화자 태그가 포함된 표현 차단
        if any(
            tag in phrase
            for tag in SPEAKER_TAGS
        ):
            continue

        # 의미가 약한 단독 어절
        if (
            len(words) == 1
            and phrase
            in LOW_VALUE_WORDS
        ):
            continue

        # 한 글자 단독 표현
        if (
            len(words) == 1
            and len(phrase) <= 1
        ):
            continue

        # ----------------------------------------------------
        # 긴 phrase가 무조건 유리하지 않도록 정규화
        # ----------------------------------------------------

        normalized_score = (
            candidate[
                "importance"
            ]
            / (
                candidate[
                    "length"
                ]
                ** 0.5
            )
        )

        candidate = (
            candidate.copy()
        )

        candidate[
            "normalized_score"
        ] = normalized_score

        filtered_candidates.append(
            candidate
        )

    if not filtered_candidates:
        return []

    # --------------------------------------------------------
    # 중요도 순 정렬
    # --------------------------------------------------------

    filtered_candidates.sort(
        key=lambda item: (
            item[
                "normalized_score"
            ],
            item[
                "importance"
            ],
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # 겹치는 Phrase 제거
    # --------------------------------------------------------

    selected = []

    for candidate in filtered_candidates:

        overlap = False

        for selected_candidate in selected:

            if _is_overlap(
                candidate,
                selected_candidate,
            ):
                overlap = True
                break

        if overlap:
            continue

        selected.append(
            candidate
        )

        if len(selected) >= top_k:
            break

    return [
        item[
            "phrase"
        ]
        for item in selected
    ]


# ============================================================
# 14. 단일 Subtype XAI
# ============================================================

def explain_single_subtype(
    text: str,
    label: str,
) -> List[str]:
    """
    특정 세부유형에 대해
    CHILD 발화 내부에서 추출된 주요 XAI 표현을 반환한다.

    반환되는 표현은 인과적·법적 판단 근거가 아니라
    '모델 예측에 기여한 주요 표현'이다.
    """

    candidates = (
        _calculate_phrase_importance(
            text=text,
            label=label,
        )
    )

    evidence_phrases = (
        _select_evidence_phrases(
            candidates
        )
    )

    return evidence_phrases


# ============================================================
# 15. 탐지된 전체 Subtype XAI
# ============================================================

def explain_subtype(
    text: str,
) -> Dict[str, Dict]:
    """
    infer_subtype.py에서 detected=True인
    세부유형에 대해서만 XAI를 수행한다.

    Subtype 예측:
        전체 Q+A 사용

    XAI 근거 탐색:
        CHILD 발화만 사용

    확률과 threshold는 외부 결과에 포함하지 않는다.
    """

    if not text or not text.strip():

        raise ValueError(
            "XAI를 수행할 상담 텍스트가 비어 있습니다."
        )

    # --------------------------------------------------------
    # 2차 모델 예측은 전체 Q+A
    # --------------------------------------------------------

    predictions = (
        subtype_infer.predict_subtype(
            text
        )
    )

    detected_labels = [
        label
        for label
        in subtype_infer.LABEL_NAMES
        if predictions[
            label
        ][
            "detected"
        ]
    ]

    explanations = {}

    # --------------------------------------------------------
    # 탐지된 Subtype만 XAI
    # --------------------------------------------------------

    for label in tqdm(
        detected_labels,
        desc="Subtype XAI",
    ):

        evidence_phrases = (
            explain_single_subtype(
                text=text,
                label=label,
            )
        )

        explanations[
            label
        ] = {
            "display_name": (
                subtype_infer
                .LABEL_DISPLAY_NAMES[
                    label
                ]
            ),
            "evidence_phrases": (
                evidence_phrases
            ),
        }

    return explanations


# ============================================================
# 16. CLI 테스트
# ============================================================

def main() -> None:
    """
    터미널에서 2차 세부유형 XAI를 테스트한다.
    """

    print()

    print(
        "=" * 70
    )

    print(
        "I-SPOT 2차 세부유형 XAI"
    )

    print(
        "=" * 70
    )

    print(
        f"Device : "
        f"{subtype_infer.DEVICE}"
    )

    if torch.cuda.is_available():

        print(
            f"GPU    : "
            f"{torch.cuda.get_device_name(0)}"
        )

    print()

    text = input(
        "상담 텍스트 입력: "
    ).strip()

    result = explain_subtype(
        text
    )

    print()

    print(
        "=" * 70
    )

    print(
        "세부유형 XAI 결과"
    )

    print(
        "=" * 70
    )

    if not result:

        print(
            "탐지된 세부유형 관련 신호가 없습니다."
        )

    else:

        for (
            label,
            explanation,
        ) in result.items():

            print()

            print(
                f"[{explanation['display_name']}]"
            )

            evidence_phrases = (
                explanation[
                    "evidence_phrases"
                ]
            )

            if evidence_phrases:

                for (
                    index,
                    phrase,
                ) in enumerate(
                    evidence_phrases,
                    start=1,
                ):

                    print(
                        f"  근거 {index}: "
                        f"{phrase}"
                    )

            else:

                print(
                    "  유의미한 근거 표현을 "
                    "추출하지 못했습니다."
                )

    print()

    print(
        "※ 표시된 표현은 해당 세부유형의 최종 판단 근거가 아니라 "
        "모델 예측에 기여한 주요 표현입니다."
    )

    print(
        "※ 최종 판단은 상담사가 수행합니다."
    )


# ============================================================
# 17. Entry Point
# ============================================================

if __name__ == "__main__":
    main()