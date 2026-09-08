"""
2차 세부유형 후보 라벨링 v4.
v3의 보수적 라벨링을 유지하면서 같은 대분류 내 후속 Q+A 문맥을 이용해 명확한 세부유형만 복구한다.
"""

# ============================================================
# 1. Import
# ============================================================

from pathlib import Path
import re
from typing import Dict, List, Set, Tuple

import pandas as pd
from tqdm import tqdm

from ai.modeling.abuse.subtype_label_config import ALL_SUBTYPE_LABELS


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

TRAIN_V3 = DATASET_DIR / "subtype_labeled_train_v3.csv"
VALID_V3 = DATASET_DIR / "subtype_labeled_valid_v3.csv"

TRAIN_OUT = DATASET_DIR / "subtype_labeled_train_v4.csv"
VALID_OUT = DATASET_DIR / "subtype_labeled_valid_v4.csv"

TRAIN_REVIEW_OUT = DATASET_DIR / "subtype_review_train_v4.csv"
VALID_REVIEW_OUT = DATASET_DIR / "subtype_review_valid_v4.csv"


# ============================================================
# 3. 대분류 → 허용 subtype
# ============================================================

MAJOR_TO_SUBTYPES: Dict[str, List[str]] = {
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
# 4. 텍스트 유틸
# ============================================================

def clean_text(value) -> str:
    """NaN을 제거하고 문자열을 정리한다."""

    if pd.isna(value):
        return ""

    return str(value).strip()


def normalize_binary(value) -> int:
    """CSV 값을 0/1 정수로 변환한다."""

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def normalize_text(text: str) -> str:
    """패턴 비교용으로 공백을 단순화한다."""

    text = clean_text(text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# 5. Q+A 분리
# ============================================================

ROLE_PATTERN = re.compile(
    r"\[(COUNSELOR|CHILD)\]\s*(.*?)(?="
    r"\[(?:COUNSELOR|CHILD)\]|\Z)",
    re.DOTALL,
)


def extract_qa_pairs(qa_text: str) -> List[Tuple[str, str]]:
    """
    하나의 qa_text 안에서 COUNSELOR → CHILD 쌍을 추출한다.

    v4의 핵심:
    첫 번째 답변만 보지 않고 같은 major_section에 포함된
    후속 질문/답변까지 모두 검사한다.
    """

    matches = ROLE_PATTERN.findall(
        clean_text(qa_text)
    )

    pairs: List[Tuple[str, str]] = []

    current_question = ""

    for role, text in matches:

        text = normalize_text(text)

        if role == "COUNSELOR":
            current_question = text

        elif role == "CHILD":

            if current_question:
                pairs.append(
                    (
                        current_question,
                        text,
                    )
                )

            current_question = ""

    return pairs


# ============================================================
# 6. 명확한 부정
# ============================================================

STRONG_NEGATIVE_PATTERNS = [
    r"^(아니요|아니오)[\.\s]*$",
    r"^(없어요|없습니다|없어|없었어요)[\.\s]*$",
    r"^(그런\s*적\s*(은\s*)?없어요)[\.\s]*$",
    r"^(그런\s*적\s*(은\s*)?없습니다)[\.\s]*$",
    r"^(한\s*적\s*없어요)[\.\s]*$",
    r"^(안\s*그래요)[\.\s]*$",
]


def is_strong_negative(answer: str) -> bool:
    """답변 전체가 명백한 부정인 경우만 True."""

    answer = normalize_text(answer)

    for pattern in STRONG_NEGATIVE_PATTERNS:

        if re.search(
            pattern,
            answer,
            flags=re.IGNORECASE,
        ):
            return True

    return False


# ============================================================
# 7. v4 문맥 복구 패턴
# ============================================================
#
# 중요한 원칙:
#
# 1. 질문 단독으로 positive를 만들지 않는다.
# 2. CHILD 답변에 구체적 행위가 있으면 사용한다.
# 3. 단순 "네"인 경우에는 질문이 단일 subtype을
#    명확하게 묻는 경우에만 복구한다.
# 4. 성학대 복합질문 "만지거나 보여달라" + "네"는
#    여전히 subtype을 확정하지 않는다.
# ============================================================


# ------------------------------------------------------------
# 7-1. 신체학대
# ------------------------------------------------------------

CONTEXT_PATTERNS_PHYSICAL = {
    "physical_object": [
        r"(막대기|몽둥이|회초리|벨트|빗자루|옷걸이|"
        r"야구방망이|골프채|자|신발|병|도구).{0,15}"
        r"(때리|맞|휘두르|내리치)",
    ],

    "physical_force": [
        r"(목을?\s*조르|목\s*졸|붙잡|제압|"
        r"움직이지\s*못하게|못\s*움직이게|"
        r"눌렀|누르고|밀쳤|끌고\s*갔)",
    ],

    "physical_harmful": [
        r"(뜨거운|불|담뱃불|라이터|끓는|화상).{0,15}"
        r"(지졌|댔|부었|데였|화상)",
        r"(약물|세제|락스|술|유해).{0,15}"
        r"(먹였|마시게|부었)",
    ],

    "physical_direct": [
        r"(때렸|때려|맞았|맞고|맞았어요|"
        r"발로\s*찼|걷어찼|주먹으로|"
        r"뺨을?\s*때|머리를?\s*때)",
    ],
}


# ------------------------------------------------------------
# 7-2. 정서학대
# ------------------------------------------------------------

CONTEXT_PATTERNS_EMOTIONAL = {
    "emotional_verbal": [
        r"(욕했|욕을\s*했|욕해|욕설|"
        r"바보|쓸모없|병신|새끼|꺼져|"
        r"죽어|미친놈|미친년)",
    ],

    "emotional_threat": [
        r"(죽인다고|죽여버린다고|"
        r"버린다고|쫓아낸다고|"
        r"나가라고|집에서\s*나가|"
        r"협박|겁을\s*줬)",
    ],

    "emotional_restriction": [
        r"(가둬|가뒀|감금|문을\s*잠그|"
        r"못\s*나가게|나가지\s*못하게|"
        r"움직이지\s*못하게)",
    ],

    "emotional_discrimination": [
        r"(동생만|형만|누나만|언니만|오빠만).{0,20}"
        r"(좋아|챙겨|예뻐|사줘)",
        r"(차별|편애|저만\s*빼|나만\s*빼)",
    ],

    "emotional_dv_exposure": [
        r"(엄마|아빠|부모).{0,20}"
        r"(때렸|때리고|맞았|싸웠|폭행)",
    ],

    "emotional_cruelty": [
        r"(괴롭혔|괴롭혀|겁주|공포|"
        r"일부러\s*무섭게|가학)",
    ],
}


# ------------------------------------------------------------
# 7-3. 성학대
# ------------------------------------------------------------

CONTEXT_PATTERNS_SEXUAL = {
    "sexual_exposure": [
        r"(옷을?\s*벗기|팬티를?\s*벗기|"
        r"속옷을?\s*벗기)",
        r"(몸|가슴|성기|소중한\s*부위|밑에).{0,15}"
        r"(보여\s*달라|보여달라|보라고)",
        r"(자기|아빠|아저씨|남자).{0,15}"
        r"(옷을?\s*벗|알몸|나체)",
    ],

    "sexual_molestation": [
        # 일반적인 "몸 만졌다" 하나만으로는 넣지 않는다.
        # 구체적인 성적 신체 부위 또는 옷 안 접촉을 요구한다.
        r"(가슴|엉덩이|성기|소중이|"
        r"소중한\s*부위|밑에).{0,15}"
        r"(만졌|만지고|주물|잡았|건드렸)",

        r"(만졌|만지고|주물|잡았|건드렸).{0,15}"
        r"(가슴|엉덩이|성기|소중이|"
        r"소중한\s*부위|밑에)",

        r"(옷|팬티|속옷)\s*안.{0,15}"
        r"(손을?\s*넣|만졌)",
    ],

    "sexual_simulated": [
        r"(자위\s*흉내|자위하는\s*척|"
        r"성행위\s*흉내|성행위하는\s*척|"
        r"성관계\s*흉내)",
    ],

    "sexual_intercourse": [
        r"(성기|손가락).{0,12}"
        r"(넣었|넣고|삽입)",
        r"(밑에|질|항문).{0,12}"
        r"(넣었|삽입)",
        r"(성관계|성교).{0,10}"
        r"(했|시켰)",
    ],

    "sexual_exploitation": [
        r"(돈|용돈|선물|대가).{0,20}"
        r"(사진|영상|성관계|성행위)",
        r"(사진|영상|성관계|성행위).{0,20}"
        r"(돈|용돈|대가|받았)",
        r"(성매매|조건만남)",
    ],
}


# ------------------------------------------------------------
# 7-4. 방임
# ------------------------------------------------------------

CONTEXT_PATTERNS_NEGLECT = {
    "neglect_physical": [
        r"(굶었|굶은\s*적|먹을\s*게\s*없|"
        r"밥을?\s*안\s*(줘|챙겨)|"
        r"밥을?\s*주지\s*않)",
        r"(혼자\s*두고|혼자\s*있|"
        r"아무도\s*없|돌봐주는\s*사람.{0,10}없)",
        r"(더러운|냄새나는).{0,12}"
        r"(옷|옷을\s*입)",
        r"(작은|맞지\s*않는|안\s*맞는).{0,12}"
        r"(옷|신발)",
    ],

    "neglect_education": [
        r"(학교|수업).{0,15}"
        r"(안\s*보내|못\s*가게|가지\s*말라)",
        r"(결석).{0,15}"
        r"(방치|내버려)",
    ],

    "neglect_medical": [
        r"(병원).{0,20}"
        r"(안\s*데려|못\s*갔|안\s*보내|"
        r"가지\s*말|못\s*가게)",
        r"(아픈|다쳤|상처|멍).{0,20}"
        r"(병원).{0,15}"
        r"(안|못)",
        r"(병원을?\s*불신|민간요법)",
    ],

    "neglect_abandonment": [
        r"(버리고\s*갔|버려졌|유기|"
        r"집을?\s*나가.{0,15}안\s*들어|"
        r"며칠씩.{0,15}혼자)",
    ],
}


CONTEXT_PATTERNS = {
    **CONTEXT_PATTERNS_PHYSICAL,
    **CONTEXT_PATTERNS_EMOTIONAL,
    **CONTEXT_PATTERNS_SEXUAL,
    **CONTEXT_PATTERNS_NEGLECT,
}


# ============================================================
# 8. 단일 질문 + 긍정 답변 복구
# ============================================================
#
# 여기 패턴은 "네", "있어요" 같은 짧은 답변일 때만 사용한다.
#
# 성학대의
#   "만지거나 보여달라고 했나요?"
# 같은 복합 질문은 일부러 넣지 않는다.
# ============================================================

AFFIRMATIVE_PATTERNS = [
    r"^네[\.\s]*$",
    r"^예[\.\s]*$",
    r"^응[\.\s]*$",
    r"^맞아요[\.\s]*$",
    r"^있어요[\.\s]*$",
    r"^있었어요[\.\s]*$",
    r"^그랬어요[\.\s]*$",
]


SINGLE_QUESTION_PATTERNS = {
    "physical_direct": [
        r"(때린\s*적|맞은\s*적)",
    ],

    "physical_object": [
        r"(도구|물건).{0,10}"
        r"(때렸|맞았)",
    ],

    "physical_force": [
        r"(못\s*움직이게|붙잡|목을?\s*조르)",
    ],

    "emotional_verbal": [
        r"(욕을?\s*했|욕설|모욕)",
    ],

    "emotional_threat": [
        r"(협박|죽인다고|쫓아낸다고)",
    ],

    "emotional_restriction": [
        r"(가둔|감금|못\s*나가게)",
    ],

    # --------------------------------------------------------
    # 성학대
    # --------------------------------------------------------

    "sexual_molestation": [
        # 반드시 특정 접촉 행위만 묻는 질문
        r"(가슴|엉덩이|성기|소중한\s*부위).{0,15}"
        r"(만졌|만진)",
    ],

    "sexual_intercourse": [
        r"(성관계|성교|삽입).{0,15}"
        r"(한\s*적|했)",
    ],

    "sexual_simulated": [
        r"(자위|성행위).{0,15}"
        r"(흉내|따라\s*하)",
    ],

    # --------------------------------------------------------
    # 방임
    # --------------------------------------------------------

    "neglect_physical": [
        r"(먹을\s*게\s*없어서|밥이\s*없어서).{0,10}"
        r"(굶은\s*적|굶었)",
        r"(집에\s*혼자\s*두고|혼자\s*있게)",
        r"(더럽고|냄새나는).{0,10}옷",
        r"(작은|맞지\s*않는).{0,10}(옷|신발)",
    ],

    "neglect_medical": [
        r"(아픈|다친).{0,15}"
        r"병원.{0,10}"
        r"(안\s*데려|못\s*간)",
    ],

    "neglect_education": [
        r"학교.{0,15}"
        r"(안\s*보내|못\s*가게)",
    ],
}


def is_simple_affirmative(answer: str) -> bool:
    """답변이 '네/있어요' 수준의 짧은 긍정인지 확인한다."""

    answer = normalize_text(answer)

    return any(
        re.search(
            pattern,
            answer,
            flags=re.IGNORECASE,
        )
        for pattern in AFFIRMATIVE_PATTERNS
    )


# ============================================================
# 9. 한 Q+A에서 subtype 탐지
# ============================================================

def find_context_subtypes(
    question: str,
    answer: str,
    allowed_subtypes: List[str],
) -> Dict[str, str]:
    """
    후속 Q+A 한 쌍에서 고신뢰 subtype을 찾는다.

    반환:
        {
            subtype: evidence_text
        }
    """

    question = normalize_text(question)
    answer = normalize_text(answer)

    results: Dict[str, str] = {}

    if not answer:
        return results

    # 명확한 부정은 절대 질문 문맥으로 positive 처리하지 않는다.
    if is_strong_negative(answer):
        return results

    # --------------------------------------------------------
    # 1) CHILD 답변 자체에 구체적인 행위가 있는 경우
    # --------------------------------------------------------

    for subtype in allowed_subtypes:

        patterns = CONTEXT_PATTERNS.get(
            subtype,
            [],
        )

        for pattern in patterns:

            if re.search(
                pattern,
                answer,
                flags=re.IGNORECASE,
            ):

                results[subtype] = (
                    f"[COUNSELOR] {question}\n"
                    f"[CHILD] {answer}"
                )

                break

    # --------------------------------------------------------
    # 2) 단순 긍정 답변이면 단일 subtype 질문만 상속
    # --------------------------------------------------------

    if is_simple_affirmative(answer):

        matched_question_subtypes: Set[str] = set()

        for subtype in allowed_subtypes:

            patterns = SINGLE_QUESTION_PATTERNS.get(
                subtype,
                [],
            )

            if any(
                re.search(
                    pattern,
                    question,
                    flags=re.IGNORECASE,
                )
                for pattern in patterns
            ):
                matched_question_subtypes.add(
                    subtype
                )

        # 질문 하나가 정확히 한 subtype만 가리킬 때만 허용
        if len(matched_question_subtypes) == 1:

            subtype = next(
                iter(
                    matched_question_subtypes
                )
            )

            results.setdefault(
                subtype,
                (
                    f"[COUNSELOR] {question}\n"
                    f"[CHILD] {answer}"
                ),
            )

    return results


# ============================================================
# 10. 성학대 subtype 후처리
# ============================================================

def refine_sexual_labels(
    detected: Dict[str, str],
) -> Dict[str, str]:
    """
    성학대 subtype 간 의미 중복을 최소화한다.

    예:
    손가락 삽입이 명시되면 intercourse를 유지하되,
    같은 표현 때문에 molestation까지 기계적으로 중복되는 것을 줄인다.

    서로 다른 발화에서 별개의 행위가 명확하면 둘 다 유지될 수 있다.
    """

    result = dict(detected)

    if (
        "sexual_intercourse" in result
        and "sexual_molestation" in result
    ):

        intercourse_evidence = result[
            "sexual_intercourse"
        ]

        molestation_evidence = result[
            "sexual_molestation"
        ]

        if (
            intercourse_evidence
            == molestation_evidence
        ):
            result.pop(
                "sexual_molestation",
                None,
            )

    return result


# ============================================================
# 11. 한 행 처리
# ============================================================

def process_row(row: pd.Series) -> pd.Series:
    """
    v3 결과를 기반으로 후속 Q+A 문맥에서 명확한 subtype을 추가한다.

    v3에서 이미 잡은 고신뢰 라벨은 유지한다.
    """

    result = row.copy()

    major_section = clean_text(
        row.get(
            "major_section",
            "",
        )
    )

    major_positive = normalize_binary(
        row.get(
            "major_positive",
            0,
        )
    )

    # --------------------------------------------------------
    # 대분류 Negative면 subtype 복구 금지
    # --------------------------------------------------------

    if major_positive != 1:
        return result

    allowed_subtypes = MAJOR_TO_SUBTYPES.get(
        major_section,
        [],
    )

    if not allowed_subtypes:
        return result

    qa_text = clean_text(
        row.get(
            "qa_text",
            "",
        )
    )

    qa_pairs = extract_qa_pairs(
        qa_text
    )

    # --------------------------------------------------------
    # 후속 Q+A 전체 탐색
    # --------------------------------------------------------

    recovered: Dict[str, str] = {}

    for question, answer in qa_pairs:

        pair_results = find_context_subtypes(
            question=question,
            answer=answer,
            allowed_subtypes=allowed_subtypes,
        )

        for subtype, evidence in pair_results.items():

            # 최초의 명확한 근거를 보존
            recovered.setdefault(
                subtype,
                evidence,
            )

    # 성학대 중복 후처리
    if major_section == "성학대":
        recovered = refine_sexual_labels(
            recovered
        )

    # --------------------------------------------------------
    # v3에 없는 subtype만 추가
    # --------------------------------------------------------

    for subtype, evidence in recovered.items():

        label_column = f"label_{subtype}"
        evidence_column = f"evidence_{subtype}"

        current_label = normalize_binary(
            result.get(
                label_column,
                0,
            )
        )

        if current_label == 0:

            result[label_column] = 1
            result[evidence_column] = evidence

    # --------------------------------------------------------
    # matched_subtype_count 다시 계산
    # --------------------------------------------------------

    matched_count = 0

    for subtype in ALL_SUBTYPE_LABELS:

        label_column = f"label_{subtype}"

        matched_count += normalize_binary(
            result.get(
                label_column,
                0,
            )
        )

    result["matched_subtype_count"] = matched_count

    # --------------------------------------------------------
    # Review 재계산
    # --------------------------------------------------------

    old_reason = clean_text(
        result.get(
            "review_reason",
            "",
        )
    )

    reasons = [
        reason
        for reason in old_reason.split("|")
        if reason
    ]

    # subtype이 생겼으면
    # positive_major_without_subtype는 제거
    if matched_count > 0:

        reasons = [
            reason
            for reason in reasons
            if reason
            != "positive_major_without_subtype"
        ]

    # subtype이 여전히 하나도 없으면 유지/추가
    else:

        if (
            "positive_major_without_subtype"
            not in reasons
        ):
            reasons.append(
                "positive_major_without_subtype"
            )

    # 중복 제거
    reasons = list(
        dict.fromkeys(
            reasons
        )
    )

    result["review_reason"] = "|".join(
        reasons
    )

    result["review_required"] = (
        1 if reasons else 0
    )

    return result


# ============================================================
# 12. 통계 출력
# ============================================================

def print_statistics(
    df: pd.DataFrame,
    split: str,
):
    """v4 결과 통계를 출력한다."""

    print()
    print("=" * 80)
    print(f"{split.upper()} SUBTYPE V4")
    print("=" * 80)

    total_rows = len(df)

    positive_major = int(
        (df["major_positive"] == 1).sum()
    )

    matched_positive = int(
        (
            (df["major_positive"] == 1)
            & (
                df["matched_subtype_count"]
                > 0
            )
        ).sum()
    )

    unmatched_positive = (
        positive_major
        - matched_positive
    )

    review_count = int(
        (
            df["review_required"] == 1
        ).sum()
    )

    coverage = (
        matched_positive
        / positive_major
        * 100
        if positive_major
        else 0.0
    )

    print("[전체 통계]")
    print(
        f"전체 Q+A 행           : {total_rows}"
    )
    print(
        f"대분류 Positive 행    : {positive_major}"
    )
    print(
        f"Subtype 매칭 Positive : {matched_positive}"
    )
    print(
        f"미매칭 Positive        : {unmatched_positive}"
    )
    print(
        f"Review 필요 행         : {review_count}"
    )
    print(
        f"Positive subtype coverage: "
        f"{coverage:.2f}%"
    )

    # --------------------------------------------------------
    # subtype 분포
    # --------------------------------------------------------

    print()
    print("[Subtype 후보 분포]")

    for subtype in ALL_SUBTYPE_LABELS:

        column = f"label_{subtype}"

        count = int(
            df[column].fillna(0).sum()
        )

        print(
            f"{subtype:30s} : {count}"
        )

    # --------------------------------------------------------
    # 대분류별 미매칭
    # --------------------------------------------------------

    print()
    print("[대분류별 미매칭]")

    for major in MAJOR_TO_SUBTYPES:

        subset = df[
            (df["major_section"] == major)
            & (df["major_positive"] == 1)
        ]

        unmatched = int(
            (
                subset[
                    "matched_subtype_count"
                ]
                == 0
            ).sum()
        )

        print(
            f"{major:10s} : "
            f"{unmatched} / {len(subset)}"
        )

    # --------------------------------------------------------
    # Review reason
    # --------------------------------------------------------

    print()
    print("[Review reason 통계]")

    reason_counts: Dict[str, int] = {}

    for value in df[
        "review_reason"
    ].fillna(""):

        for reason in str(value).split("|"):

            if not reason:
                continue

            reason_counts[reason] = (
                reason_counts.get(
                    reason,
                    0,
                )
                + 1
            )

    for reason, count in sorted(
        reason_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):

        print(
            f"{reason:45s}: {count}"
        )


# ============================================================
# 13. Split 처리
# ============================================================

def process_split(
    input_path: Path,
    output_path: Path,
    review_path: Path,
    split: str,
):
    """v3 CSV 하나를 읽어 v4 문맥 보정 결과를 생성한다."""

    print()
    print("=" * 80)
    print(
        f"{split.upper()} v3 → v4 문맥 보정"
    )
    print("=" * 80)

    df = pd.read_csv(
        input_path
    )

    rows = []

    for _, row in tqdm(
        df.iterrows(),
        total=len(df),
        desc=f"{split} subtype v4",
    ):

        rows.append(
            process_row(row)
        )

    result_df = pd.DataFrame(
        rows
    )

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    review_df = result_df[
        result_df["review_required"] == 1
    ].copy()

    review_df.to_csv(
        review_path,
        index=False,
        encoding="utf-8-sig",
    )

    print_statistics(
        result_df,
        split,
    )

    print()
    print(
        f"전체 저장 : {output_path}"
    )
    print(
        f"검수 저장 : {review_path}"
    )


# ============================================================
# 14. Main
# ============================================================

def main():

    process_split(
        input_path=TRAIN_V3,
        output_path=TRAIN_OUT,
        review_path=TRAIN_REVIEW_OUT,
        split="train",
    )

    process_split(
        input_path=VALID_V3,
        output_path=VALID_OUT,
        review_path=VALID_REVIEW_OUT,
        split="valid",
    )


if __name__ == "__main__":
    main()