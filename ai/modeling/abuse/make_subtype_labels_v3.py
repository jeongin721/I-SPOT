"""
AI-Hub 상담 Q+A를 기반으로 19개 학대 세부유형의 고신뢰 후보 라벨을 생성한다.
v2 검수 결과를 반영해 아동 표현을 확장하고, 복합 질문·단순 긍정 응답은 자동 확정하지 않고 검수 대상으로 보낸다.
"""

# ============================================================
# 1. Import
# ============================================================

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

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

TRAIN_INPUT = DATASET_DIR / "subtype_qa_train_v1.csv"
VALID_INPUT = DATASET_DIR / "subtype_qa_valid_v1.csv"

TRAIN_OUTPUT = DATASET_DIR / "subtype_labeled_train_v3.csv"
VALID_OUTPUT = DATASET_DIR / "subtype_labeled_valid_v3.csv"

TRAIN_REVIEW_OUTPUT = DATASET_DIR / "subtype_review_train_v3.csv"
VALID_REVIEW_OUTPUT = DATASET_DIR / "subtype_review_valid_v3.csv"


# ============================================================
# 3. 대분류 → 허용 subtype
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
# 4. 명확한 부정 / 단순 긍정
# ============================================================

STRONG_NEGATIVE_PATTERNS = [
    r"^\s*아니요[\s.!?]*$",
    r"^\s*아뇨[\s.!?]*$",
    r"^\s*아니[\s.!?]*$",
    r"^\s*없어요[\s.!?]*$",
    r"^\s*없었어요[\s.!?]*$",
    r"^\s*없는데요[\s.!?]*$",
    r"^\s*전혀\s*없어요[\s.!?]*$",
    r"^\s*그런\s*적(?:은)?\s*없어요[\s.!?]*$",
    r"^\s*그런\s*적(?:은)?\s*없었어요[\s.!?]*$",
    r"^\s*그런\s*일(?:은)?\s*없어요[\s.!?]*$",
    r"^\s*그런\s*일(?:은)?\s*없었어요[\s.!?]*$",
]

SIMPLE_AFFIRMATIVE_PATTERNS = [
    r"^\s*네[\s.!?]*$",
    r"^\s*예[\s.!?]*$",
    r"^\s*응[\s.!?]*$",
    r"^\s*맞아요[\s.!?]*$",
    r"^\s*있어요[\s.!?]*$",
    r"^\s*있었어요[\s.!?]*$",
]


# ============================================================
# 5. A 중심 subtype 패턴
#
# v3 원칙:
# - 질문에 학대 단어가 있다는 이유로 라벨 생성 X
# - 실제 CHILD 답변에 나타난 행위를 우선
# - AI-Hub 실제 아동 표현을 추가
# ============================================================

ANSWER_PATTERNS: Dict[str, List[str]] = {

    # ========================================================
    # 신체학대
    # ========================================================

    "physical_direct": [
        r"때렸",
        r"때려",
        r"때린",
        r"맞았",
        r"맞아요",
        r"맞은",
        r"맞고",
        r"두들겨",
        r"뺨",
        r"싸대기",
        r"주먹",
        r"손으로.*때",
        r"발로.*차",
        r"걷어차",
        r"머리채",
        r"꼬집",
        r"할퀴",
        r"물어뜯",
        r"목(?:을)?\s*조르",
        r"머리.*부딪",
        r"밟았",
        r"밟아",
        r"밟고",
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
        r"파리채",
        r"리모컨",
        r"책으로.*때",
        r"자(?:로|를).*때",
        r"물건.*(?:던지|던졌|때리|맞)",
        r"(?:던져서|던진|던졌).*맞",
        r"(?:병|컵|의자).*던",
    ],

    "physical_force": [
        r"밀쳤",
        r"밀치",
        r"밀었",
        r"세게\s*밀",
        r"꽉\s*잡",
        r"세게\s*잡",
        r"붙잡",
        r"끌고\s*가",
        r"끌려",
        r"묶었",
        r"묶어",
        r"흔들었",
        r"흔들어",
        r"눌렀",
        r"누르고",
        r"몸으로\s*누르",
        r"몸으로\s*눌",
        r"못\s*움직이게",
        r"움직이지\s*못하게",
        r"억지로.*(?:잡|끌)",
    ],

    "physical_harmful": [
        r"뜨거운\s*물",
        r"끓는\s*물",
        r"불로",
        r"불에",
        r"화상",
        r"담뱃불",
        r"담배.*지",
        r"약을?\s*억지로",
        r"약물.*억지",
        r"세제.*먹",
        r"유해.*물질",
    ],

    # ========================================================
    # 정서학대
    # ========================================================

    "emotional_verbal": [
        r"욕(?:을|설|하|했|해)",
        r"욕먹",
        r"돼지",
        r"한심",
        r"멍청",
        r"바보",
        r"병신",
        r"미친",
        r"쓸모없",
        r"필요\s*없",
        r"너\s*같은\s*(?:건|애)",
        r"저\s*같은\s*(?:건|애)",
        r"없어졌으면\s*좋",
        r"사라졌으면\s*좋",
        r"태어나지\s*말",
        r"태어나지\s*않",
        r"왜\s*태어났",
        r"낳지\s*말",
        r"싫어한다고\s*말",
        r"비난",
        r"무시하",
        r"윽박",
    ],

    "emotional_threat": [
        r"죽여\s*버",
        r"죽여버",
        r"죽인다",
        r"죽인다고",
        r"죽일\s*수",
        r"죽이겠",
        r"죽여\s*버리겠",
        r"버린다고",
        r"버리겠",
        r"버려버",
        r"쫓아낸",
        r"쫓아내",
        r"쫓아내겠",
        r"집에서\s*나가",
        r"집에서\s*내쫓",
        r"다시는\s*보지\s*말",
        r"가만\s*안\s*둔",
        r"가만두지\s*않",
    ],

    "emotional_restriction": [
        r"감금",
        r"문(?:을)?\s*잠",
        r"못\s*나오게",
        r"못\s*나가게",
        r"나가면\s*안\s*돼",
        r"나가면\s*안돼",
        r"방에서.*나가.*안",
        r"방에.*(?:가두|가둬)",
        r"어디.*가두",
        r"밖에.*세워",
        r"계속\s*세워",
        r"무릎(?:을)?\s*꿇",
        r"강제로.*(?:눕|앉|서|하)",
        r"억지로.*(?:눕|앉|서|하)",
        r"못\s*움직이게",
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
        r"누구는.*누구는",
        r"너보다.*(?:잘|낫)",
        r"동생.*(?:더\s*좋|더\s*잘)",
        r"형제.*비교",
    ],

    "emotional_dv_exposure": [
        r"엄마.*아빠.*싸우",
        r"아빠.*엄마.*싸우",
        r"부모님.*싸우",
        r"엄마(?:를)?\s*때리",
        r"아빠(?:를)?\s*때리",
        r"엄마.*맞",
        r"아빠.*맞",
        r"서로.*때리",
        r"가정폭력",
    ],

    "emotional_cruelty": [
        r"괴롭히",
        r"일부러.*겁",
        r"겁을?\s*주",
        r"무섭게.*하",
        r"잠(?:을)?\s*못\s*자게",
        r"잠(?:을)?\s*안\s*재",
        r"일부러.*울",
        r"창피.*주",
        r"망신.*주",
        r"투명\s*인간",
    ],

    # ========================================================
    # 성학대
    # ========================================================

    "sexual_exposure": [
        r"야동",
        r"음란",
        r"벗은\s*몸",
        r"알몸",
        r"나체",
        r"옷도\s*안\s*입",
        r"옷을?\s*벗으라고",
        r"벗으라고",
        r"벗기",
        r"몸(?:을)?\s*보여\s*달",
        r"(?:소중한|민감한|성기).*보여",
        r"사진.*(?:보내|찍)",
        r"몸.*사진.*찍",
        r"신체.*사진.*찍",
    ],

    "sexual_molestation": [
        r"몸\s*만졌",
        r"몸을?\s*만졌",
        r"제\s*몸\s*만졌",
        r"몸을?\s*만지",
        r"만지고.*아프",
        r"밑에(?:를)?\s*만지",
        r"밑에(?:를)?\s*아프",
        r"아래(?:를)?\s*만지",
        r"소중이(?:를)?\s*만지",
        r"소중한\s*부위.*만지",
        r"민감한\s*부위.*만지",
        r"성기.*만지",
        r"가슴.*만지",
        r"엉덩이.*만지",
        r"몸을?\s*더듬",
        r"주물럭",
        r"억지로.*만지",
        r"강제로.*만지",
        r"강제로.*키스",
        r"억지로.*키스",
        r"입(?:을)?\s*맞추",
    ],

    "sexual_simulated": [
        r"성행위.*흉내",
        r"성관계.*흉내",
        r"유사\s*성행위",
        r"성적인\s*행동.*시키",
        r"성행위.*시키",
        r"자위.*시키",
    ],

    "sexual_intercourse": [
        r"성관계",
        r"강간",
        r"삽입",
        r"(?:성기|아빠\s*거|남자\s*거).*넣",
        r"몸\s*안에.*넣",
        r"안으로.*넣",
        r"입으로.*(?:해|하라고)",
    ],

    "sexual_exploitation": [
        r"성매매",
        r"조건\s*만남",
        r"조건만남",
        r"돈.*(?:성관계|성행위)",
        r"(?:성관계|성행위).*돈",
        r"몸.*사진.*돈",
        r"사진.*돈.*준",
        r"사진.*팔",
        r"성매매.*시키",
        r"성매매.*소개",
        r"성매매.*알선",
    ],

    # ========================================================
    # 방임
    # ========================================================

    "neglect_physical": [
        r"밥(?:을)?\s*안\s*(?:주|차려)",
        r"밥(?:을)?\s*못\s*먹",
        r"밥.*없",
        r"굶었",
        r"굶어",
        r"굶는",
        r"먹을\s*(?:게|것이)\s*없",
        r"혼자.*집",
        r"집.*혼자",
        r"혼자.*있",
        r"아무도.*돌봐",
        r"돌봐주는\s*사람.*없",
        r"냄새나는\s*옷",
        r"더러운\s*옷",
        r"옷.*더럽",
        r"빨래.*안",
        r"세탁.*안",
        r"씻지\s*못",
        r"씻겨주지\s*않",
        r"옷.*작",
        r"신발.*작",
    ],

    "neglect_education": [
        r"학교(?:를)?\s*안\s*보내",
        r"학교(?:에)?\s*못\s*가",
        r"학교(?:를)?\s*계속\s*빠",
        r"학교.*결석",
        r"결석.*많",
        r"등교.*안",
        r"학교.*안\s*가",
        r"교육.*시키지\s*않",
    ],

    "neglect_medical": [
        r"병원.*안\s*(?:가|보내|데려)",
        r"병원.*못\s*(?:가|갔)",
        r"병원\s*갈\s*자격\s*없",
        r"아픈데.*병원.*안",
        r"다쳤는데.*병원.*안",
        r"치료.*안\s*받",
        r"치료.*못\s*받",
        r"치료.*안\s*해",
        r"약.*안\s*사",
        r"병원.*불신",
        r"병원.*믿지\s*않",
        r"민간요법",
    ],

    "neglect_abandonment": [
        r"버리고\s*갔",
        r"버려두",
        r"내버려두",
        r"두고\s*사라",
        r"집(?:을)?\s*나가.*안\s*들어",
        r"며칠.*혼자",
        r"오랫동안.*혼자",
        r"며칠씩.*집.*없",
    ],
}


# ============================================================
# 6. 복합 질문 탐지
#
# 예:
# "몸을 만지거나 보여달라고 한 적 있어?"
# "네."
#
# → molestation인지 exposure인지 알 수 없으므로 자동 확정 X
# ============================================================

COMPOUND_QUESTION_RULES: List[Tuple[str, Set[str]]] = [
    (
        r"만지.*(?:거나|또는).*보여",
        {
            "sexual_molestation",
            "sexual_exposure",
        },
    ),
    (
        r"보여.*(?:거나|또는).*만지",
        {
            "sexual_molestation",
            "sexual_exposure",
        },
    ),
    (
        r"쫓아내.*(?:거나|또는).*버리",
        {
            "emotional_threat",
        },
    ),
    (
        r"버리.*(?:거나|또는).*가두",
        {
            "emotional_threat",
            "emotional_restriction",
        },
    ),
]


# ============================================================
# 7. 질문 문맥으로 허용 가능한 단일 subtype
#
# 단순 "네"를 쓸 수 있는 건 질문이 한 subtype만 명확하게
# 가리킬 때뿐이다.
# ============================================================

QUESTION_PATTERNS: Dict[str, List[str]] = {

    "physical_direct": [
        r"때린\s*적",
        r"맞은\s*적",
        r"발로.*찬\s*적",
    ],

    "physical_object": [
        r"도구로.*때",
        r"물건으로.*때",
    ],

    "physical_force": [
        r"밀친\s*적",
        r"묶은\s*적",
        r"붙잡은\s*적",
    ],

    "physical_harmful": [
        r"뜨거운.*(?:붓|물)",
        r"불.*지진",
    ],

    "emotional_verbal": [
        r"욕(?:을)?.*한\s*적",
        r"모욕.*한\s*적",
    ],

    "emotional_threat": [
        r"죽이겠.*말",
        r"버리겠.*말",
        r"쫓아내겠.*말",
    ],

    "emotional_restriction": [
        r"가둔\s*적",
        r"못\s*나오게.*한\s*적",
    ],

    "emotional_discrimination": [
        r"차별.*한\s*적",
        r"편애.*한\s*적",
    ],

    "emotional_dv_exposure": [
        r"부모님.*싸우",
        r"엄마.*때리는.*보",
        r"아빠.*때리는.*보",
    ],

    "emotional_cruelty": [
        r"일부러.*괴롭",
    ],

    # 성학대는 복합 질문이 많아서 매우 보수적으로 설정
    "sexual_exposure": [
        r"벗은\s*몸.*보여.*한\s*적",
        r"옷을?\s*벗으라고.*한\s*적",
    ],

    "sexual_molestation": [
        r"소중한\s*부위만.*만진",
        r"성기.*만진\s*적",
    ],

    "sexual_simulated": [
        r"성행위.*흉내.*시키",
    ],

    "sexual_intercourse": [
        r"성관계.*한\s*적",
        r"삽입.*한\s*적",
    ],

    "sexual_exploitation": [
        r"성매매.*시키",
    ],

    "neglect_physical": [
        r"먹을\s*게\s*없어서\s*굶",
        r"며칠.*혼자.*있",
    ],

    "neglect_education": [
        r"학교.*안\s*보내",
    ],

    "neglect_medical": [
        r"아픈데.*병원.*데려가지\s*않",
    ],

    "neglect_abandonment": [
        r"버리고\s*간\s*적",
    ],
}


# ============================================================
# 8. 문자열 리스트 복원
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
# 9. Regex helper
# ============================================================

def regex_match(
    text: str,
    patterns: List[str],
) -> bool:

    return any(
        re.search(
            pattern,
            text,
            re.IGNORECASE,
        )
        for pattern in patterns
    )


def is_strong_negative(answer: str) -> bool:

    return regex_match(
        answer.strip(),
        STRONG_NEGATIVE_PATTERNS,
    )


def is_simple_affirmative(answer: str) -> bool:

    return regex_match(
        answer.strip(),
        SIMPLE_AFFIRMATIVE_PATTERNS,
    )


# ============================================================
# 10. 답변 절 분리
# ============================================================

def split_clauses(text: str) -> List[str]:
    """
    한 답변 안의 여러 사실을 절 단위로 나눈다.
    부분 부정 때문에 전체 답변을 버리는 문제를 줄인다.
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
# 11. 복합 질문 확인
# ============================================================

def get_compound_subtypes(
    question: str,
) -> Set[str]:

    matched: Set[str] = set()

    for pattern, subtypes in COMPOUND_QUESTION_RULES:

        if re.search(
            pattern,
            question,
            re.IGNORECASE,
        ):
            matched.update(subtypes)

    return matched


# ============================================================
# 12. Q+A 하나에서 subtype 탐색
# ============================================================

def find_subtypes_from_pair(
    question: str,
    answer: str,
    allowed_subtypes: List[str],
) -> Tuple[Dict[str, List[str]], List[str]]:
    """
    하나의 Q+A에서 고신뢰 subtype 후보를 찾는다.

    반환:
    - matches: 자동 후보 subtype + 근거
    - review_reasons: 자동 확정하지 않은 이유
    """

    matches: Dict[str, List[str]] = {}
    review_reasons: List[str] = []

    question = question.strip()
    answer = answer.strip()

    if not answer:
        return matches, review_reasons

    # --------------------------------------------------------
    # 명확한 전체 부정
    # --------------------------------------------------------

    if is_strong_negative(answer):
        return matches, review_reasons

    clauses = split_clauses(answer)

    # --------------------------------------------------------
    # 1. CHILD 답변 자체에서 구체적인 행위 탐지
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
    # 답변에서 이미 구체적 근거를 찾았으면
    # Q의 단순 긍정 추론은 추가하지 않음
    # --------------------------------------------------------

    if matches:
        return matches, review_reasons

    # --------------------------------------------------------
    # 2. "네" 같은 단순 긍정
    # --------------------------------------------------------

    if is_simple_affirmative(answer):

        compound_subtypes = get_compound_subtypes(
            question
        )

        # ----------------------------------------------------
        # 복합 질문이면 subtype을 결정할 수 없음
        # ----------------------------------------------------

        if len(compound_subtypes) >= 2:

            review_reasons.append(
                "ambiguous_compound_question_affirmative"
            )

            return matches, review_reasons

        question_candidates = []

        for subtype in allowed_subtypes:

            patterns = QUESTION_PATTERNS.get(
                subtype,
                [],
            )

            if regex_match(
                question,
                patterns,
            ):
                question_candidates.append(
                    subtype
                )

        # ----------------------------------------------------
        # 질문이 정확히 하나의 subtype만 가리키는 경우
        # ----------------------------------------------------

        if len(question_candidates) == 1:

            subtype = question_candidates[0]

            evidence = (
                f"[COUNSELOR] {question}\n"
                f"[CHILD] {answer}"
            )

            matches.setdefault(
                subtype,
                [],
            ).append(evidence)

        elif len(question_candidates) > 1:

            review_reasons.append(
                "multiple_question_subtype_candidates"
            )

        else:

            review_reasons.append(
                "affirmative_without_specific_subtype"
            )

    return matches, review_reasons


# ============================================================
# 13. 신체학대 generic/specific 중복 제거
# ============================================================

def apply_physical_specificity(
    matches: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """
    같은 근거가 object와 direct에 동시에 잡히면
    더 구체적인 physical_object를 우선한다.

    서로 다른 발화에서 각각 나온 경우에는 둘 다 유지한다.
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

        filtered = [
            evidence
            for evidence in direct_evidence
            if evidence not in object_evidence
        ]

        if filtered:
            matches["physical_direct"] = filtered
        else:
            matches.pop(
                "physical_direct",
                None,
            )

    return matches


# ============================================================
# 14. 한 Q+A section 행 처리
# ============================================================

def process_row(
    row: pd.Series,
) -> dict:

    output = row.to_dict()

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

    # --------------------------------------------------------
    # 출력 컬럼 초기화
    # --------------------------------------------------------

    for subtype in ALL_SUBTYPE_LABELS:

        output[f"label_{subtype}"] = 0
        output[f"evidence_{subtype}"] = ""

    output["matched_subtype_count"] = 0
    output["review_required"] = 0
    output["review_reason"] = ""

    # --------------------------------------------------------
    # 대분류 음성은 subtype positive 생성하지 않음
    # --------------------------------------------------------

    if major_positive != 1:
        return output

    allowed_subtypes = MAJOR_TO_SUBTYPES.get(
        major_section,
        [],
    )

    if not allowed_subtypes:

        output["review_required"] = 1
        output["review_reason"] = (
            "unknown_major_section"
        )

        return output

    review_reasons: List[str] = []

    # --------------------------------------------------------
    # Q/A 길이 불일치
    # --------------------------------------------------------

    if len(questions) != len(answers):

        review_reasons.append(
            "qa_length_mismatch"
        )

    # --------------------------------------------------------
    # 모든 Q+A pair 분석
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

        pair_matches, pair_reviews = (
            find_subtypes_from_pair(
                question=question,
                answer=answer,
                allowed_subtypes=allowed_subtypes,
            )
        )

        for subtype, evidences in pair_matches.items():

            all_matches.setdefault(
                subtype,
                [],
            ).extend(evidences)

        review_reasons.extend(
            pair_reviews
        )

    # --------------------------------------------------------
    # 신체 subtype 중복 정리
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
    # 대분류 positive인데 subtype을 하나도 못 찾음
    # --------------------------------------------------------

    if len(all_matches) == 0:

        review_reasons.append(
            "positive_major_without_subtype"
        )

    # --------------------------------------------------------
    # Review reason 중복 제거
    # --------------------------------------------------------

    review_reasons = list(
        dict.fromkeys(
            review_reasons
        )
    )

    if review_reasons:

        output["review_required"] = 1

        output["review_reason"] = "|".join(
            review_reasons
        )

    return output


# ============================================================
# 15. 데이터셋 처리
# ============================================================

def process_dataset(
    input_path: Path,
    output_path: Path,
    review_output_path: Path,
    split: str,
):

    print()
    print("=" * 80)
    print(
        f"{split.upper()} subtype candidate labeling v3"
    )
    print(f"입력: {input_path}")
    print("=" * 80)

    dataframe = pd.read_csv(
        input_path
    )

    results = []

    for _, row in tqdm(
        dataframe.iterrows(),
        total=len(dataframe),
        desc=f"{split} subtype v3",
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
    # Review 저장
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
    # 기본 통계
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

    coverage = (
        matched_positive_rows
        / positive_major_rows
        * 100
        if positive_major_rows
        else 0.0
    )

    print()
    print("[전체 통계]")
    print(
        f"전체 Q+A 행           : {len(result)}"
    )
    print(
        f"대분류 Positive 행    : {positive_major_rows}"
    )
    print(
        f"Subtype 매칭 Positive : {matched_positive_rows}"
    )
    print(
        f"미매칭 Positive        : {unmatched_positive_rows}"
    )
    print(
        f"Review 필요 행         : {len(review)}"
    )
    print(
        f"Positive subtype coverage: {coverage:.2f}%"
    )

    # --------------------------------------------------------
    # subtype 분포
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 대분류별 미매칭
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Review reason 통계
    # --------------------------------------------------------

    print()
    print("[Review reason 통계]")

    reason_counts: Dict[str, int] = {}

    for reasons in review["review_reason"].fillna(""):

        for reason in str(reasons).split("|"):

            reason = reason.strip()

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

    print()
    print(f"전체 저장 : {output_path}")
    print(f"검수 저장 : {review_output_path}")


# ============================================================
# 16. Main
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