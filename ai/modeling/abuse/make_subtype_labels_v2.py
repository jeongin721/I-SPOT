"""
AI-Hub Q+A 문맥을 이용해 19개 학대 세부유형의 후보 라벨을 생성한다.
질문은 문맥으로만 사용하고 아동 답변의 긍정·부정 및 구체적 행위를 중심으로 후보 라벨을 생성한다.
"""

# ============================================================
# 1. Import
# ============================================================

import ast
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from tqdm import tqdm

from ai.modeling.abuse.subtype_label_config import (
    ALL_SUBTYPE_LABELS,
    SUBTYPE_TO_MAJOR,
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

TRAIN_INPUT = DATASET_DIR / "subtype_qa_train_v1.csv"
VALID_INPUT = DATASET_DIR / "subtype_qa_valid_v1.csv"

TRAIN_OUTPUT = DATASET_DIR / "subtype_labeled_train_v2.csv"
VALID_OUTPUT = DATASET_DIR / "subtype_labeled_valid_v2.csv"

TRAIN_REVIEW_OUTPUT = DATASET_DIR / "subtype_review_train_v2.csv"
VALID_REVIEW_OUTPUT = DATASET_DIR / "subtype_review_valid_v2.csv"


# ============================================================
# 3. 대분류 → subtype
# ============================================================

MAJOR_TO_SUBTYPES = {
    "신체학대": [
        "physical_direct",
        "physical_object",
        "physical_force",
        "physical_harmful",
    ],
    "정서학대": [
        "emotional_verbal",
        "emotional_threat",
        "emotional_restriction",
        "emotional_discrimination",
        "emotional_dv_exposure",
        "emotional_cruelty",
    ],
    "성학대": [
        "sexual_exposure",
        "sexual_molestation",
        "sexual_simulated",
        "sexual_intercourse",
        "sexual_exploitation",
    ],
    "방임": [
        "neglect_physical",
        "neglect_education",
        "neglect_medical",
        "neglect_abandonment",
    ],
}


# ============================================================
# 4. 명확한 단답형 응답
# ============================================================

STRONG_NEGATIVE_PATTERNS = [
    r"^\s*아니요[\.\!\?]?\s*$",
    r"^\s*아뇨[\.\!\?]?\s*$",
    r"^\s*아니[\.\!\?]?\s*$",
    r"^\s*없어요[\.\!\?]?\s*$",
    r"^\s*없었어요[\.\!\?]?\s*$",
    r"^\s*그런\s*적\s*없어요[\.\!\?]?\s*$",
    r"^\s*그런\s*적은\s*없었어요[\.\!\?]?\s*$",
    r"^\s*그런\s*일\s*없어요[\.\!\?]?\s*$",
    r"^\s*전혀\s*없어요[\.\!\?]?\s*$",
]

AFFIRMATIVE_PATTERNS = [
    r"^\s*네(?:[\.\!\?]|$)",
    r"^\s*예(?:[\.\!\?]|$)",
    r"^\s*응(?:[\.\!\?]|$)",
    r"^\s*맞아요(?:[\.\!\?]|$)",
    r"^\s*있어요(?:[\.\!\?]|$)",
    r"^\s*있었어요(?:[\.\!\?]|$)",
]


# ============================================================
# 5. subtype 패턴
#
# 중요한 원칙:
# - 질문에 단어가 있다고 바로 라벨링하지 않는다.
# - 답변에 구체적 행위가 있으면 답변을 우선한다.
# - "네" 같은 문맥 의존 응답에서만 질문을 제한적으로 사용한다.
# ============================================================

ANSWER_PATTERNS: Dict[str, List[str]] = {

    # --------------------------------------------------------
    # 신체학대
    # --------------------------------------------------------

    "physical_direct": [
        r"때리",
        r"맞았",
        r"맞아요",
        r"맞은",
        r"맞고",
        r"뺨",
        r"싸대기",
        r"주먹",
        r"발로\s*차",
        r"걷어차",
        r"머리채",
        r"꼬집",
        r"물어뜯",
        r"할퀴",
        r"목을?\s*조르",
        r"머리.*부딪",
    ],

    "physical_object": [
        r"방망이",
        r"야구방망이",
        r"막대기",
        r"회초리",
        r"벨트",
        r"옷걸이",
        r"빗자루",
        r"스테이플러",
        r"자(?:로|를)",
        r"나무칼",
        r"철봉",
        r"물건.*(?:던지|때리|맞)",
        r"(?:던진|던져서|던졌).*맞",
    ],

    "physical_force": [
        r"밀치",
        r"밀었",
        r"밀어",
        r"세게\s*밀",
        r"꽉\s*잡",
        r"세게\s*잡",
        r"붙잡",
        r"끌고\s*가",
        r"끌려",
        r"묶",
        r"흔들",
        r"눌렀",
        r"누르",
        r"못\s*움직이",
        r"억지로.*물",
    ],

    "physical_harmful": [
        r"뜨거운\s*물",
        r"불로",
        r"불에",
        r"화상",
        r"담뱃불",
        r"약을\s*억지로",
        r"약물",
        r"유해.*물질",
        r"세제.*먹",
    ],

    # --------------------------------------------------------
    # 정서학대
    # --------------------------------------------------------

    "emotional_verbal": [
        r"욕(?:을|하|했|해)",
        r"욕설",
        r"돼지",
        r"한심",
        r"멍청",
        r"바보",
        r"쓸모없",
        r"정신\s*상태.*글러",
        r"태어나지\s*말",
        r"태어났으면\s*안",
        r"싫어한다고\s*말",
        r"비난",
        r"무시하",
        r"윽박",
    ],

    "emotional_threat": [
        r"죽여버",
        r"죽인다",
        r"죽이겠",
        r"버린다",
        r"버리겠",
        r"쫓아낸",
        r"쫓아내겠",
        r"집에서\s*나가",
        r"집에서\s*내쫓",
        r"다시는\s*보지\s*말",
        r"헤어질.*협박",
    ],

    "emotional_restriction": [
        r"감금",
        r"문을?\s*잠",
        r"못\s*나오",
        r"방에.*(?:가두|넣어)",
        r"밖에.*세워",
        r"계속\s*세워",
        r"강제로.*(?:눕|앉|서)",
        r"억지로.*(?:눕|앉|서)",
    ],

    "emotional_discrimination": [
        r"동생만",
        r"형만",
        r"누나만",
        r"언니만",
        r"오빠만",
        r"아들만",
        r"딸만",
        r"차별",
        r"편애",
        r"비교하",
        r"너보다.*(?:잘|낫)",
    ],

    "emotional_dv_exposure": [
        r"엄마.*아빠.*(?:싸우|때리)",
        r"아빠.*엄마.*(?:싸우|때리)",
        r"부모님.*싸우",
        r"엄마를?\s*때리",
        r"아빠를?\s*때리",
        r"서로.*때리",
        r"가정폭력",
    ],

    "emotional_cruelty": [
        r"괴롭히",
        r"일부러.*겁",
        r"무섭게.*하",
        r"잠을?\s*못\s*자게",
        r"잠을?\s*안\s*재",
        r"일부러.*울",
        r"창피.*주",
    ],

    # --------------------------------------------------------
    # 성학대
    # --------------------------------------------------------

    "sexual_exposure": [
        r"야동",
        r"음란",
        r"벗은\s*몸",
        r"알몸",
        r"나체",
        r"몸을?\s*보여\s*달",
        r"사진.*(?:보내|찍)",
        r"(?:소중한|민감한|성기).*보여",
        r"벗으라고",
        r"옷을?\s*벗으라고",
    ],

    "sexual_molestation": [
        r"(?:소중한|민감한|성기|가슴|엉덩이|쉬\s*하는\s*곳).*만지",
        r"만졌.*(?:소중한|민감한|성기|가슴|엉덩이)",
        r"몸을?\s*더듬",
        r"강제로.*키스",
        r"억지로.*키스",
        r"입을?\s*맞추",
    ],

    "sexual_simulated": [
        r"성행위.*흉내",
        r"성관계.*흉내",
        r"유사\s*성행위",
        r"성적인\s*행동.*시키",
    ],

    "sexual_intercourse": [
        r"성관계",
        r"강간",
        r"삽입",
        r"(?:성기|아빠\s*거|이상한\s*거).*넣",
        r"몸\s*안에.*넣",
        r"입으로.*(?:해|하라고)",
    ],

    "sexual_exploitation": [
        r"성매매",
        r"조건만남",
        r"돈.*(?:성관계|성행위)",
        r"(?:성관계|성행위).*돈",
        r"성매매.*시키",
        r"성매매.*소개",
        r"성매매.*알선",
    ],

    # --------------------------------------------------------
    # 방임
    # --------------------------------------------------------

    "neglect_physical": [
        r"밥을?\s*안\s*주",
        r"밥을?\s*못\s*먹",
        r"굶",
        r"먹을\s*게\s*없",
        r"혼자.*(?:집|있)",
        r"아무도.*돌봐",
        r"돌봐주는\s*사람.*없",
        r"옷.*(?:더럽|안\s*빨)",
        r"씻지\s*못",
        r"씻겨주지\s*않",
        r"신발.*작",
        r"옷.*작",
    ],

    "neglect_education": [
        r"학교를?\s*안\s*보내",
        r"학교에?\s*못\s*가",
        r"학교를?\s*계속\s*빠",
        r"학교.*결석",
        r"등교.*안",
        r"교육.*시키지\s*않",
    ],

    "neglect_medical": [
        r"병원.*안\s*(?:가|데려)",
        r"병원.*못\s*(?:가|갔)",
        r"아픈데.*병원.*안",
        r"다쳤는데.*병원.*안",
        r"치료.*안\s*받",
        r"치료.*못\s*받",
        r"약.*안\s*사",
    ],

    "neglect_abandonment": [
        r"버리고\s*갔",
        r"버려두",
        r"두고\s*사라",
        r"집을?\s*나가.*안\s*들어",
        r"며칠.*혼자",
        r"오랫동안.*혼자",
    ],
}


# ============================================================
# 6. 질문 패턴
#
# "네", "맞아요"처럼 A만으로 의미를 알 수 없는 경우에만 사용한다.
# 질문 단독으로는 절대 subtype 후보를 만들지 않는다.
# ============================================================

QUESTION_PATTERNS: Dict[str, List[str]] = {

    "physical_direct": [
        r"때린",
        r"때려",
        r"맞은",
        r"맞았",
        r"발로\s*찬",
        r"꼬집",
        r"목.*조른",
    ],

    "physical_object": [
        r"무엇으로.*맞",
        r"뭘로.*맞",
        r"도구.*때",
        r"물건.*던",
    ],

    "physical_force": [
        r"밀친",
        r"붙잡",
        r"묶",
        r"흔든",
        r"끌고",
    ],

    "physical_harmful": [
        r"뜨거운",
        r"불",
        r"화상",
        r"약물",
        r"유해",
    ],

    "emotional_verbal": [
        r"욕",
        r"심한\s*말",
        r"어떤\s*말",
        r"모욕",
    ],

    "emotional_threat": [
        r"협박",
        r"죽인",
        r"버린",
        r"쫓아",
    ],

    "emotional_restriction": [
        r"가둔",
        r"감금",
        r"못\s*나오",
    ],

    "emotional_discrimination": [
        r"차별",
        r"편애",
        r"비교",
    ],

    "emotional_dv_exposure": [
        r"부모님.*싸",
        r"엄마.*아빠.*싸",
        r"아빠.*엄마.*싸",
    ],

    "emotional_cruelty": [
        r"괴롭",
        r"잠.*못",
    ],

    "sexual_exposure": [
        r"보여달라고",
        r"벗은\s*몸",
        r"야동",
        r"사진.*보내",
    ],

    "sexual_molestation": [
        r"몸을?\s*만지",
        r"소중한.*만지",
        r"키스",
    ],

    "sexual_simulated": [
        r"성행위.*흉내",
        r"성적인\s*행동",
    ],

    "sexual_intercourse": [
        r"성관계",
        r"삽입",
        r"몸.*넣",
    ],

    "sexual_exploitation": [
        r"성매매",
        r"돈.*성",
    ],

    "neglect_physical": [
        r"밥.*안\s*주",
        r"굶",
        r"잘\s*챙겨",
        r"돌봐",
    ],

    "neglect_education": [
        r"학교.*안\s*보내",
        r"결석",
        r"학교.*빠",
    ],

    "neglect_medical": [
        r"병원.*안",
        r"치료.*안",
    ],

    "neglect_abandonment": [
        r"버리고",
        r"혼자.*두",
        r"사라",
    ],
}


# ============================================================
# 7. 문자열 리스트 복원
# ============================================================

def parse_list(value) -> List[str]:

    if pd.isna(value):
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

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
# 8. 텍스트 유틸
# ============================================================

def regex_match(text: str, patterns: List[str]) -> bool:

    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in patterns
    )


def is_strong_negative(answer: str) -> bool:
    """
    답변 전체가 명확한 부정 응답인지 확인한다.

    이전 v1처럼 문장 어딘가에 '없어요'가 있다는 이유로
    전체 Q+A를 버리지 않는다.
    """

    text = answer.strip()

    return regex_match(
        text,
        STRONG_NEGATIVE_PATTERNS,
    )


def is_affirmative(answer: str) -> bool:
    """
    '네', '예', '있어요' 등 질문 문맥에 의존하는
    명시적 긍정 응답인지 확인한다.
    """

    return regex_match(
        answer.strip(),
        AFFIRMATIVE_PATTERNS,
    )


def split_clauses(text: str) -> List[str]:
    """
    답변을 문장/절 단위로 나눈다.

    서로 다른 사실이 한 답변에 들어 있을 때
    부정 표현이 다른 긍정 사실까지 제거하는 문제를 줄인다.
    """

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?])\s+|"
        r"\s*(?:그리고|그런데|하지만|근데)\s*",
        text,
    )

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


# ============================================================
# 9. 하나의 Q+A에서 subtype 후보 찾기
# ============================================================

def find_subtypes_from_pair(
    question: str,
    answer: str,
    allowed_subtypes: List[str],
) -> Dict[str, List[str]]:
    """
    하나의 상담사 질문 + 아동 답변에서 subtype 후보를 찾는다.

    반환:
    {
        "physical_direct": [
            "[COUNSELOR] ...\\n[CHILD] ..."
        ]
    }
    """

    matches: Dict[str, List[str]] = {}

    question = question.strip()
    answer = answer.strip()

    if not answer:
        return matches

    # --------------------------------------------------------
    # 명확한 부정 단답은 질문에 키워드가 있어도 라벨링 금지
    # --------------------------------------------------------

    if is_strong_negative(answer):
        return matches

    clauses = split_clauses(answer)

    # --------------------------------------------------------
    # 1. A 자체에 구체적인 subtype 표현이 있는지 확인
    # --------------------------------------------------------

    for subtype in allowed_subtypes:

        patterns = ANSWER_PATTERNS.get(
            subtype,
            [],
        )

        for clause in clauses:

            if regex_match(
                clause,
                patterns,
            ):

                evidence = (
                    f"[COUNSELOR] {question}\n"
                    f"[CHILD] {clause}"
                )

                matches.setdefault(
                    subtype,
                    [],
                ).append(evidence)

    # --------------------------------------------------------
    # 2. A가 단순 긍정형이면 Q 문맥을 제한적으로 사용
    # --------------------------------------------------------

    if is_affirmative(answer):

        for subtype in allowed_subtypes:

            # 이미 A 자체에서 잡힌 subtype이면 중복 불필요
            if subtype in matches:
                continue

            question_patterns = QUESTION_PATTERNS.get(
                subtype,
                [],
            )

            if regex_match(
                question,
                question_patterns,
            ):

                evidence = (
                    f"[COUNSELOR] {question}\n"
                    f"[CHILD] {answer}"
                )

                matches.setdefault(
                    subtype,
                    [],
                ).append(evidence)

    return matches


# ============================================================
# 10. 신체학대 subtype 중복 후처리
# ============================================================

def apply_physical_specificity(
    matches: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """
    같은 근거에서 '도구 사용'과 '직접 신체 가해'가 동시에
    잡힌 경우 generic physical_direct 중복을 줄인다.

    단, 서로 다른 발화에서 각각 탐지된 경우에는 둘 다 유지한다.
    """

    object_evidence = set(
        matches.get(
            "physical_object",
            [],
        )
    )

    direct_evidence = matches.get(
        "physical_direct",
        [],
    )

    if object_evidence and direct_evidence:

        filtered_direct = [
            evidence
            for evidence in direct_evidence
            if evidence not in object_evidence
        ]

        if filtered_direct:
            matches["physical_direct"] = filtered_direct
        else:
            matches.pop(
                "physical_direct",
                None,
            )

    return matches


# ============================================================
# 11. 한 행 처리
# ============================================================

def process_row(row: pd.Series) -> dict:

    major_section = str(
        row.get(
            "major_section",
            "",
        )
    ).strip()

    major_positive = int(
        row.get(
            "major_positive",
            0,
        )
    )

    questions = parse_list(
        row.get(
            "questions",
            "",
        )
    )

    answers = parse_list(
        row.get(
            "answers",
            "",
        )
    )

    # 기본 출력
    output = row.to_dict()

    for subtype in ALL_SUBTYPE_LABELS:

        output[f"label_{subtype}"] = 0
        output[f"evidence_{subtype}"] = ""

    output["matched_subtype_count"] = 0
    output["review_required"] = 0
    output["review_reason"] = ""

    # --------------------------------------------------------
    # AI-Hub 대분류 GT가 음성이면 subtype 자동 양성 생성 금지
    # --------------------------------------------------------

    if major_positive != 1:
        return output

    allowed_subtypes = MAJOR_TO_SUBTYPES.get(
        major_section,
        [],
    )

    if not allowed_subtypes:

        output["review_required"] = 1
        output["review_reason"] = "unknown_major_section"
        return output

    # --------------------------------------------------------
    # 질문/답변 개수 차이는 검수 대상으로 남김
    # --------------------------------------------------------

    qa_length_mismatch = (
        len(questions)
        != len(answers)
    )

    # --------------------------------------------------------
    # Q+A pair 단위 후보 탐색
    # --------------------------------------------------------

    all_matches: Dict[str, List[str]] = {}

    max_length = max(
        len(questions),
        len(answers),
    )

    for index in range(max_length):

        question = (
            questions[index]
            if index < len(questions)
            else ""
        )

        answer = (
            answers[index]
            if index < len(answers)
            else ""
        )

        pair_matches = find_subtypes_from_pair(
            question=question,
            answer=answer,
            allowed_subtypes=allowed_subtypes,
        )

        for subtype, evidences in pair_matches.items():

            all_matches.setdefault(
                subtype,
                [],
            ).extend(evidences)

    # --------------------------------------------------------
    # subtype 특이도 후처리
    # --------------------------------------------------------

    if major_section == "신체학대":

        all_matches = apply_physical_specificity(
            all_matches
        )

    # --------------------------------------------------------
    # 결과 저장
    # --------------------------------------------------------

    for subtype, evidences in all_matches.items():

        unique_evidences = list(
            dict.fromkeys(
                evidences
            )
        )

        output[f"label_{subtype}"] = 1

        output[f"evidence_{subtype}"] = (
            " || ".join(
                unique_evidences
            )
        )

    output["matched_subtype_count"] = len(
        all_matches
    )

    # --------------------------------------------------------
    # 검수 필요 여부
    # --------------------------------------------------------

    review_reasons = []

    if len(all_matches) == 0:
        review_reasons.append(
            "positive_major_without_subtype"
        )

    if qa_length_mismatch:
        review_reasons.append(
            "qa_length_mismatch"
        )

    if review_reasons:

        output["review_required"] = 1
        output["review_reason"] = "|".join(
            review_reasons
        )

    return output


# ============================================================
# 12. 전체 데이터 처리
# ============================================================

def process_dataset(
    input_path: Path,
    output_path: Path,
    review_output_path: Path,
    split: str,
):

    print()
    print("=" * 75)
    print(f"{split.upper()} subtype candidate labeling v2")
    print(f"입력: {input_path}")
    print("=" * 75)

    dataframe = pd.read_csv(
        input_path
    )

    results = []

    for _, row in tqdm(
        dataframe.iterrows(),
        total=len(dataframe),
        desc=f"{split} subtype v2",
    ):

        results.append(
            process_row(row)
        )

    result = pd.DataFrame(
        results
    )

    # --------------------------------------------------------
    # 전체 결과 저장
    # --------------------------------------------------------

    result.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 검수 대상만 별도 저장
    # --------------------------------------------------------

    review = result[
        result["review_required"] == 1
    ].copy()

    review.to_csv(
        review_output_path,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 통계 출력
    # --------------------------------------------------------

    positive_major_rows = int(
        result["major_positive"].sum()
    )

    matched_positive_rows = int(
        (
            (result["major_positive"] == 1)
            &
            (result["matched_subtype_count"] > 0)
        ).sum()
    )

    unmatched_positive_rows = (
        positive_major_rows
        - matched_positive_rows
    )

    print()
    print("[전체 통계]")
    print(f"전체 Q+A 행           : {len(result)}")
    print(f"대분류 Positive 행    : {positive_major_rows}")
    print(f"Subtype 매칭 Positive : {matched_positive_rows}")
    print(f"미매칭 Positive        : {unmatched_positive_rows}")
    print(f"Review 필요 행         : {len(review)}")

    if positive_major_rows > 0:

        coverage = (
            matched_positive_rows
            / positive_major_rows
            * 100
        )

        print(
            f"Positive subtype coverage: "
            f"{coverage:.2f}%"
        )

    print()
    print("[Subtype 후보 분포]")

    for subtype in ALL_SUBTYPE_LABELS:

        column = f"label_{subtype}"

        count = int(
            result[column].sum()
        )

        print(
            f"{subtype:30s}: {count}"
        )

    print()
    print("[대분류별 미매칭]")

    for major_name in MAJOR_TO_SUBTYPES:

        subset = result[
            (result["major_section"] == major_name)
            &
            (result["major_positive"] == 1)
        ]

        unmatched = subset[
            subset["matched_subtype_count"] == 0
        ]

        print(
            f"{major_name:10s}: "
            f"{len(unmatched)} / {len(subset)}"
        )

    print()
    print(f"전체 저장 : {output_path}")
    print(f"검수 저장 : {review_output_path}")


# ============================================================
# 13. Main
# ============================================================

def main():

    process_dataset(
        input_path=TRAIN_INPUT,
        output_path=TRAIN_OUTPUT,
        review_output_path=TRAIN_REVIEW_OUTPUT,
        split="train",
    )

    process_dataset(
        input_path=VALID_INPUT,
        output_path=VALID_OUTPUT,
        review_output_path=VALID_REVIEW_OUTPUT,
        split="valid",
    )


if __name__ == "__main__":
    main()