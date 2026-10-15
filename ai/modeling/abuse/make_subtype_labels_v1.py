"""
AI-Hub 상담 발화에 공식자료 기반 19개 학대 세부유형 후보 라벨을 생성한다.
명시적인 행위 표현만 자동 라벨링하고, 불확실한 사례는 수동 검토 대상으로 분리한다.
"""

# ============================================================
# 1. Import
# ============================================================

import ast
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd
from tqdm import tqdm

from ai.modeling.abuse.subtype_label_config import (
    ALL_SUBTYPE_LABELS,
)


# ============================================================
# 2. 경로
# ============================================================

BASE_DIR = Path("/data/I-SPOT")

DATASET_DIR = (
    BASE_DIR
    / "ai"
    / "modeling"
    / "abuse"
    / "datasets"
)

TRAIN_INPUT = DATASET_DIR / "subtype_base_train_v1.csv"
VALID_INPUT = DATASET_DIR / "subtype_base_valid_v1.csv"

TRAIN_OUTPUT = DATASET_DIR / "subtype_labeled_train_v1.csv"
VALID_OUTPUT = DATASET_DIR / "subtype_labeled_valid_v1.csv"

TRAIN_REVIEW_OUTPUT = DATASET_DIR / "subtype_review_train_v1.csv"
VALID_REVIEW_OUTPUT = DATASET_DIR / "subtype_review_valid_v1.csv"


# ============================================================
# 3. 대분류 → 관련 답변 컬럼
# ============================================================

MAJOR_CONFIG = {
    "신체학대": {
        "major_column": "label_physical",
        "answer_column": "physical_answers",
    },
    "정서학대": {
        "major_column": "label_emotional",
        "answer_column": "emotional_answers",
    },
    "성학대": {
        "major_column": "label_sexual",
        "answer_column": "sexual_answers",
    },
    "방임": {
        "major_column": "label_neglect",
        "answer_column": "neglect_answers",
    },
}


# ============================================================
# 4. 명시적 행위 패턴
# ============================================================
# 주의:
# 이것은 최종 학대 판정 규칙이 아니다.
#
# AI-Hub에서 이미 해당 4대 유형이 positive인 사례 안에서
# 세부 행위가 명시적으로 드러나는 경우를 찾기 위한
# 초기 라벨링 보조 규칙이다.
#
# 따라서:
#   대분류 positive + 명시적 행위 표현
# 두 조건을 모두 만족해야 자동 라벨을 부여한다.
# ============================================================

SUBTYPE_PATTERNS = {

    # --------------------------------------------------------
    # 신체학대
    # --------------------------------------------------------

    "physical_direct": [
        r"때리",
        r"맞았",
        r"맞아",
        r"맞았어",
        r"꼬집",
        r"물어뜯",
        r"목.{0,3}조르",
        r"비틀",
        r"할퀴",
        r"차였",
        r"발로.{0,5}차",
    ],

    "physical_object": [
        r"막대기",
        r"회초리",
        r"벨트",
        r"몽둥이",
        r"옷걸이",
        r"빗자루",
        r"자.{0,5}때리",
        r"물건.{0,5}때리",
        r"도구.{0,5}때리",
    ],

    "physical_force": [
        r"밀쳤",
        r"밀어.{0,5}넘",
        r"던졌",
        r"잡아.{0,5}끌",
        r"끌고",
        r"묶었",
        r"묶어",
        r"흔들었",
        r"세게.{0,5}잡",
        r"팔.{0,5}잡",
    ],

    "physical_harmful": [
        r"뜨거운.{0,5}(물|것)",
        r"불로",
        r"담뱃불",
        r"화상",
        r"약.{0,5}먹였",
        r"강제로.{0,5}약",
        r"화학",
    ],

    # --------------------------------------------------------
    # 정서학대
    # --------------------------------------------------------

    "emotional_verbal": [
        r"욕했",
        r"욕을",
        r"욕설",
        r"바보",
        r"쓸모없",
        r"싫어",
        r"미워",
        r"죽어",
        r"꺼져",
    ],

    "emotional_threat": [
        r"버리겠",
        r"버린다",
        r"쫓아내",
        r"나가라고",
        r"때리겠",
        r"죽이겠",
        r"가만.{0,3}안.{0,3}두",
        r"협박",
    ],

    "emotional_restriction": [
        r"가둬",
        r"가뒀",
        r"감금",
        r"못.{0,3}나가",
        r"나가지.{0,3}못",
        r"문.{0,5}잠",
        r"강제로.{0,5}시키",
    ],

    "emotional_discrimination": [
        r"동생만",
        r"형만",
        r"누나만",
        r"언니만",
        r"오빠만",
        r"나만.{0,5}(빼|안)",
        r"차별",
        r"편애",
        r"비교하",
    ],

    "emotional_dv_exposure": [
        r"엄마.{0,15}아빠.{0,15}(때리|싸우)",
        r"아빠.{0,15}엄마.{0,15}(때리|싸우)",
        r"부모님.{0,10}싸우",
        r"부부싸움",
        r"가정폭력",
    ],

    "emotional_cruelty": [
        r"잠.{0,5}못.{0,5}자",
        r"재우지.{0,5}않",
        r"밤새.{0,5}(세워|깨워)",
        r"무릎.{0,5}꿇",
    ],

    # --------------------------------------------------------
    # 성학대
    # --------------------------------------------------------

    "sexual_exposure": [
        r"벗은.{0,5}(몸|모습)",
        r"야한.{0,5}(사진|영상|동영상)",
        r"음란물",
        r"성기.{0,5}보여",
        r"몸.{0,5}보여.{0,5}달",
        r"옷.{0,5}벗.{0,5}보여",
    ],

    "sexual_molestation": [
        r"몸을.{0,5}만졌",
        r"몸.{0,5}만져",
        r"가슴.{0,5}만",
        r"엉덩이.{0,5}만",
        r"성기.{0,5}만",
        r"강제로.{0,5}만졌",
    ],

    "sexual_simulated": [
        r"유사성행위",
        r"성기.{0,10}(비비|접촉)",
        r"성적인.{0,5}행동.{0,5}시키",
    ],

    "sexual_intercourse": [
        r"성관계",
        r"성교",
        r"삽입",
        r"강간",
        r"구강성교",
        r"항문성교",
    ],

    "sexual_exploitation": [
        r"성매매",
        r"돈.{0,10}성관계",
        r"돈.{0,10}만지",
        r"사람.{0,5}소개.{0,10}성",
    ],

    # --------------------------------------------------------
    # 방임
    # --------------------------------------------------------

    "neglect_physical": [
        r"밥.{0,5}안.{0,5}(줘|주)",
        r"밥.{0,5}못.{0,5}먹",
        r"먹을.{0,5}것.{0,5}없",
        r"집에.{0,10}혼자",
        r"혼자.{0,10}집",
        r"씻지.{0,5}못",
        r"옷.{0,5}없",
    ],

    "neglect_education": [
        r"학교.{0,5}안.{0,5}(가|보내)",
        r"학교.{0,5}못.{0,5}가",
        r"학교에.{0,5}보내지",
        r"결석.{0,10}방치",
    ],

    "neglect_medical": [
        r"병원.{0,5}안.{0,5}(가|데려)",
        r"병원.{0,5}못.{0,5}가",
        r"아픈데.{0,10}병원",
        r"약.{0,5}안.{0,5}(줘|주)",
        r"치료.{0,5}안",
    ],

    "neglect_abandonment": [
        r"버리고.{0,5}갔",
        r"버려두",
        r"두고.{0,5}갔",
        r"집.{0,5}나가.{0,10}안.{0,5}왔",
        r"돌아오지.{0,5}않",
    ],
}


# ============================================================
# 5. 부정 표현
# ============================================================
# 단순 키워드만으로 false positive가 생기는 것을 일부 방지한다.
# 복잡한 부정/맥락은 자동 처리하지 않고 review 대상으로 남긴다.
# ============================================================

NEGATION_PATTERNS = [
    r"안\s*때렸",
    r"때리지\s*않",
    r"맞은\s*적\s*없",
    r"욕하지\s*않",
    r"욕한\s*적\s*없",
    r"만지지\s*않",
    r"그런\s*적\s*없",
    r"하지\s*않았",
    r"안\s*그랬",
]


# ============================================================
# 6. 문자열 리스트 복원
# ============================================================

def parse_answer_list(value) -> List[str]:
    """
    CSV에 문자열 형태로 저장된 답변 리스트를 Python List로 복원한다.
    """

    if pd.isna(value):
        return []

    if isinstance(value, list):
        return value

    try:
        parsed = ast.literal_eval(str(value))

        if isinstance(parsed, list):
            return [
                str(item).strip()
                for item in parsed
                if str(item).strip()
            ]

    except (ValueError, SyntaxError):
        pass

    text = str(value).strip()

    return [text] if text else []


# ============================================================
# 7. 패턴 탐지
# ============================================================

def contains_pattern(
    text: str,
    patterns: List[str],
) -> bool:

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def contains_negation(text: str) -> bool:
    """
    명시적인 부정 표현이 있는지 확인한다.
    """

    return contains_pattern(
        text,
        NEGATION_PATTERNS,
    )


# ============================================================
# 8. 세부유형 후보 라벨 생성
# ============================================================

def label_row(row: pd.Series) -> Dict:
    """
    AI-Hub 대분류 정답과 해당 유형의 아동 답변을 이용하여
    명시적인 세부유형 후보 라벨을 생성한다.

    자동 규칙으로 근거가 부족한 positive 사례는
    review_required=1로 남긴다.
    """

    labels = {
        f"label_{label}": 0
        for label in ALL_SUBTYPE_LABELS
    }

    evidence = {
        label: []
        for label in ALL_SUBTYPE_LABELS
    }

    positive_major_count = 0
    matched_major_count = 0

    # --------------------------------------------------------
    # 각 대분류별 처리
    # --------------------------------------------------------

    for major_name, config in MAJOR_CONFIG.items():

        major_positive = int(
            row.get(config["major_column"], 0)
        )

        if major_positive != 1:
            continue

        positive_major_count += 1

        answers = parse_answer_list(
            row.get(config["answer_column"], "")
        )

        major_has_match = False

        # ----------------------------------------------------
        # 해당 대분류에 속하는 subtype만 검사
        # ----------------------------------------------------

        for subtype in ALL_SUBTYPE_LABELS:

            # subtype_label_config의 prefix를 이용한 것이 아니라
            # 명시적으로 대분류와 연결한다.
            if major_name == "신체학대" and not subtype.startswith("physical_"):
                continue

            if major_name == "정서학대" and not subtype.startswith("emotional_"):
                continue

            if major_name == "성학대" and not subtype.startswith("sexual_"):
                continue

            if major_name == "방임" and not subtype.startswith("neglect_"):
                continue

            patterns = SUBTYPE_PATTERNS[subtype]

            for answer in answers:

                if contains_negation(answer):
                    continue

                if contains_pattern(
                    answer,
                    patterns,
                ):
                    labels[f"label_{subtype}"] = 1

                    evidence[subtype].append(
                        answer
                    )

                    major_has_match = True

        if major_has_match:
            matched_major_count += 1

    # --------------------------------------------------------
    # 검토 필요 여부
    # --------------------------------------------------------
    # 대분류 positive인데 세부유형을 하나도 확실하게
    # 찾지 못한 대분류가 존재하면 사람이 확인하도록 한다.
    # --------------------------------------------------------

    review_required = int(
        positive_major_count > matched_major_count
    )

    # --------------------------------------------------------
    # 근거 발화 저장
    # --------------------------------------------------------

    evidence_strings = {
        f"evidence_{label}": " || ".join(
            dict.fromkeys(evidence[label])
        )
        for label in ALL_SUBTYPE_LABELS
    }

    return {
        **labels,
        **evidence_strings,
        "review_required": review_required,
        "positive_major_count": positive_major_count,
        "matched_major_count": matched_major_count,
    }


# ============================================================
# 9. Split 전체 처리
# ============================================================

def process_dataset(
    input_path: Path,
    output_path: Path,
    review_output_path: Path,
    split: str,
):
    """
    AI-Hub 기반 기초 CSV 전체에 세부유형 후보 라벨을 부여한다.
    """

    print()
    print("=" * 70)
    print(f"{split.upper()} 세부유형 후보 라벨 생성")
    print(f"입력: {input_path}")
    print("=" * 70)

    dataframe = pd.read_csv(input_path)

    generated_rows = []

    for _, row in tqdm(
        dataframe.iterrows(),
        total=len(dataframe),
        desc=f"{split} subtype labeling",
    ):
        generated_rows.append(
            label_row(row)
        )

    generated = pd.DataFrame(
        generated_rows
    )

    result = pd.concat(
        [
            dataframe.reset_index(drop=True),
            generated.reset_index(drop=True),
        ],
        axis=1,
    )

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    result.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    review_dataframe = result[
        result["review_required"] == 1
    ].copy()

    review_dataframe.to_csv(
        review_output_path,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 결과 출력
    # --------------------------------------------------------

    print()
    print(f"전체 사례: {len(result)}")
    print(
        f"검토 필요: "
        f"{int(result['review_required'].sum())}"
    )

    print()
    print("[세부유형 Positive 수]")

    for subtype in ALL_SUBTYPE_LABELS:

        count = int(
            result[f"label_{subtype}"].sum()
        )

        print(
            f"{subtype:32s}: {count}"
        )

    print()
    print(f"전체 저장: {output_path}")
    print(f"검토 대상: {review_output_path}")


# ============================================================
# 10. Main
# ============================================================

def main():

    process_dataset(
        TRAIN_INPUT,
        TRAIN_OUTPUT,
        TRAIN_REVIEW_OUTPUT,
        "train",
    )

    process_dataset(
        VALID_INPUT,
        VALID_OUTPUT,
        VALID_REVIEW_OUTPUT,
        "valid",
    )


if __name__ == "__main__":
    main()