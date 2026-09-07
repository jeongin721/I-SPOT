"""
A-only 멀티라벨 모델의 예측에 기여한 주요 표현을 Logit 기반 Phrase Occlusion으로 추출한다.

문장의 1~3개 연속 어절을 가렸을 때 각 학대 유형의 logit 변화량을 계산해
사람이 읽기 쉬운 형태의 주요 근거 표현을 반환한다.
"""

# ============================================================
# 1. Import
# ============================================================

import re
from typing import Dict, List, Tuple

import torch

from ai.modeling.abuse.infer_abuse import (
    LABEL_NAMES,
    MAX_LEN,
    clean_text,
    device,
    model,
    tokenizer,
)


# ============================================================
# 2. 설정
# ============================================================

# 최대 몇 개 어절을 하나의 Phrase로 묶을지
MAX_NGRAM = 3

# 라벨별 최대 근거 표현 수
TOP_K = 5

# 너무 작은 logit 변화는 근거에서 제외
MIN_LOGIT_IMPORTANCE = 0.05

# 여러 Phrase 가림 문장을 한 번에 추론
BATCH_SIZE = 32


# ============================================================
# 3. 모델 출력 계산
# ============================================================

def _predict_batch(
    texts: List[str],
) -> Dict[str, torch.Tensor]:
    """
    여러 문장을 한 번에 추론한다.

    반환:
        {
            "logits": [batch_size, 4],
            "probabilities": [batch_size, 4]
        }
    """

    encoded = tokenizer(
        texts,
        max_length=MAX_LEN,
        padding=True,
        truncation=True,
        return_tensors="pt",
    )

    encoded = {
        key: value.to(device)
        for key, value in encoded.items()
    }

    with torch.no_grad():

        outputs = model(
            **encoded
        )

        logits = outputs.logits

        probabilities = torch.sigmoid(
            logits
        )

    return {
        "logits": logits.cpu(),
        "probabilities": probabilities.cpu(),
    }


# ============================================================
# 4. 문장의 어절 위치 추출
# ============================================================

def _extract_words(
    text: str,
) -> List[Tuple[str, int, int]]:
    """
    공백 기준으로 어절과 원문 내 문자 위치를 추출한다.

    예:
        "아빠가 저를 때렸어요."

    반환:
        [
            ("아빠가", 0, 3),
            ("저를", 4, 6),
            ("때렸어요.", 7, 12),
        ]
    """

    words = []

    for match in re.finditer(
        r"\S+",
        text,
    ):

        words.append(
            (
                match.group(),
                match.start(),
                match.end(),
            )
        )

    return words


# ============================================================
# 5. Phrase 후보 생성
# ============================================================

def _make_phrase_candidates(
    text: str,
    max_ngram: int = MAX_NGRAM,
) -> List[dict]:
    """
    1~max_ngram개의 연속 어절을 Phrase 후보로 만든다.

    예:
        "때려서"
        "때려서 팔에"
        "팔에 멍이 들었어요"
    """

    words = _extract_words(
        text
    )

    candidates = []

    for start_index in range(
        len(words)
    ):

        for ngram_size in range(
            1,
            max_ngram + 1,
        ):

            end_index = (
                start_index
                + ngram_size
            )

            if end_index > len(words):
                break

            start_char = words[
                start_index
            ][1]

            end_char = words[
                end_index - 1
            ][2]

            phrase = text[
                start_char:end_char
            ]

            candidates.append(
                {
                    "phrase": phrase,
                    "start": start_char,
                    "end": end_char,
                    "word_count": ngram_size,
                }
            )

    return candidates


# ============================================================
# 6. Phrase 가리기
# ============================================================

def _mask_phrase(
    text: str,
    start: int,
    end: int,
) -> str:
    """
    지정된 표현을 tokenizer의 MASK token으로 교체한다.

    원문에서 완전히 삭제하지 않고 MASK를 사용해
    문장 구조 변화 영향을 줄인다.
    """

    mask_token = tokenizer.mask_token

    if mask_token is None:
        raise ValueError(
            "현재 tokenizer에 MASK token이 없습니다."
        )

    return (
        text[:start]
        + mask_token
        + text[end:]
    )


# ============================================================
# 7. 겹치는 근거 표현 정리
# ============================================================

def _select_evidence(
    items: List[dict],
    top_k: int,
) -> List[dict]:
    """
    logit 기여도가 높은 표현부터 선택한다.

    이미 선택한 표현과 문자 범위가 겹치는 후보는 제외해
    유사한 표현이 반복 출력되는 것을 줄인다.
    """

    sorted_items = sorted(
        items,
        key=lambda item: item[
            "importance"
        ],
        reverse=True,
    )

    selected = []

    for item in sorted_items:

        if (
            item["importance"]
            < MIN_LOGIT_IMPORTANCE
        ):
            continue

        overlap = False

        for existing in selected:

            if (
                item["start"]
                < existing["end"]
                and item["end"]
                > existing["start"]
            ):
                overlap = True
                break

        if overlap:
            continue

        selected.append(
            item
        )

        if len(selected) >= top_k:
            break

    return selected


# ============================================================
# 8. Logit 기반 Phrase Occlusion
# ============================================================

def explain_abuse(
    text: str,
    top_k: int = TOP_K,
    max_ngram: int = MAX_NGRAM,
) -> Dict[str, List[dict]]:
    """
    Phrase를 가리기 전/후의 logit 차이를 계산한다.

    importance:
        원본 logit - Phrase 가림 후 logit

    값이 클수록 해당 Phrase가 그 라벨의 예측 점수를
    높이는 방향으로 기여했다고 해석한다.
    """

    text = clean_text(
        text
    )

    if not text:
        raise ValueError(
            "근거를 분석할 상담 텍스트가 없습니다."
        )

    # ========================================================
    # 원본 문장 예측
    # ========================================================

    original_output = _predict_batch(
        [text]
    )

    original_logits = (
        original_output[
            "logits"
        ][0]
    )

    original_probabilities = (
        original_output[
            "probabilities"
        ][0]
    )

    # ========================================================
    # Phrase 후보 생성
    # ========================================================

    candidates = _make_phrase_candidates(
        text=text,
        max_ngram=max_ngram,
    )

    if not candidates:

        return {
            label: []
            for label in LABEL_NAMES
        }

    # ========================================================
    # Phrase 가림 문장 생성
    # ========================================================

    masked_texts = []

    for candidate in candidates:

        masked_text = _mask_phrase(
            text=text,
            start=candidate[
                "start"
            ],
            end=candidate[
                "end"
            ],
        )

        masked_texts.append(
            masked_text
        )

    # ========================================================
    # Batch 추론
    # ========================================================

    masked_logits_list = []
    masked_probabilities_list = []

    for batch_start in range(
        0,
        len(masked_texts),
        BATCH_SIZE,
    ):

        batch_texts = masked_texts[
            batch_start:
            batch_start + BATCH_SIZE
        ]

        batch_output = _predict_batch(
            batch_texts
        )

        masked_logits_list.append(
            batch_output[
                "logits"
            ]
        )

        masked_probabilities_list.append(
            batch_output[
                "probabilities"
            ]
        )

    masked_logits = torch.cat(
        masked_logits_list,
        dim=0,
    )

    masked_probabilities = torch.cat(
        masked_probabilities_list,
        dim=0,
    )

    # ========================================================
    # 라벨별 logit 기여도 계산
    # ========================================================

    explanations = {
        label: []
        for label in LABEL_NAMES
    }

    for candidate_index, candidate in enumerate(
        candidates
    ):

        candidate_logits = (
            masked_logits[
                candidate_index
            ]
        )

        candidate_probabilities = (
            masked_probabilities[
                candidate_index
            ]
        )

        importance_scores = (
            original_logits
            - candidate_logits
        )

        for label_index, label in enumerate(
            LABEL_NAMES
        ):

            importance = float(
                importance_scores[
                    label_index
                ].item()
            )

            # 해당 라벨 점수를 높인 표현만 근거 후보로 사용
            if importance <= 0:
                continue

            explanations[
                label
            ].append(
                {
                    "phrase": candidate[
                        "phrase"
                    ],
                    "importance": importance,

                    # 디버깅용 logit 정보
                    "original_logit": float(
                        original_logits[
                            label_index
                        ].item()
                    ),
                    "masked_logit": float(
                        candidate_logits[
                            label_index
                        ].item()
                    ),

                    # 사람이 보기 쉬운 확률도 함께 보관
                    "original_probability": float(
                        original_probabilities[
                            label_index
                        ].item()
                    ),
                    "masked_probability": float(
                        candidate_probabilities[
                            label_index
                        ].item()
                    ),

                    "start": candidate[
                        "start"
                    ],
                    "end": candidate[
                        "end"
                    ],
                    "word_count": candidate[
                        "word_count"
                    ],
                }
            )

    # ========================================================
    # 겹치는 후보 제거 + TOP K
    # ========================================================

    for label in LABEL_NAMES:

        explanations[
            label
        ] = _select_evidence(
            items=explanations[
                label
            ],
            top_k=top_k,
        )

    return explanations


# ============================================================
# 9. 터미널 테스트
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print(
        "A-only 모델 Logit 기반 Phrase Occlusion 근거 표현 테스트"
    )
    print("=" * 70)

    test_text = input(
        "\n상담 텍스트 입력: "
    )

    result = explain_abuse(
        test_text
    )

    print()
    print(
        "===== 모델 예측의 주요 근거 표현 ====="
    )

    for label in LABEL_NAMES:

        print()
        print(
            f"[{label}]"
        )

        evidence_items = (
            result[
                label
            ]
        )

        if not evidence_items:

            print(
                "근거 표현 없음"
            )

            continue

        for item in evidence_items:

            print(
                f"- {item['phrase']:<30} "
                f"logit 기여도={item['importance']:.4f} "
                f"| 확률 "
                f"{item['original_probability']:.4f}"
                f" → "
                f"{item['masked_probability']:.4f}"
            )