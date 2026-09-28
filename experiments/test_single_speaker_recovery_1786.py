import re


QUESTION_ENDINGS = (
    "나요?",
    "가요?",
    "까요?",
    "어요?",
    "아요?",
    "해요?",
    "인가요?",
    "건가요?",
    "있나요?",
    "없나요?",
    "어때요?",
    "어떤가요?",
    "왜요?",
    "뭐예요?",
    "뭔가요?",
)


SHORT_ANSWER_PREFIXES = (
    "네",
    "아니요",
    "응",
    "아니",
    "맞아요",
    "몰라요",
    "모르겠어요",
    "괜찮아요",
    "없어요",
    "있어요",
)


QUESTION_START_PATTERNS = (
    "최근에",
    "무엇",
    "어디",
    "언제",
    "왜",
    "어떻게",
    "어떤",
    "몇 시",
    "평소에",
    "평상시에",
    "그렇게",
    "그럼",
    "혹시",
    "누가",
    "누구",
)


def is_question(text: str) -> bool:
    text = text.strip()

    if not text:
        return False

    if text.endswith("?"):
        return True

    return any(
        text.endswith(ending)
        for ending in QUESTION_ENDINGS
    )


def split_by_punctuation(text: str) -> list[str]:
    if not text:
        return []

    chunks = re.findall(
        r"[^.!?]+[.!?]?",
        text,
    )

    return [
        chunk.strip()
        for chunk in chunks
        if chunk.strip()
    ]


def split_short_answer_plus_question(
    text: str,
) -> list[str]:

    text = text.strip()

    if not text:
        return []

    if not is_question(text):
        return [text]

    for prefix in SHORT_ANSWER_PREFIXES:

        pattern = rf"^{re.escape(prefix)}[\s,]+(.+)$"

        match = re.match(
            pattern,
            text,
        )

        if match:
            remainder = match.group(1).strip()

            if is_question(remainder):
                return [
                    prefix,
                    remainder,
                ]

    return [text]


def split_answer_plus_question(
    text: str,
) -> list[str]:
    """
    예:
    '가끔이요 한 달에 한 번 정도 있어요
     그렇게 짜증이나 화가 날 때 어떻게 하면 풀려요?'

    →
    CHILD:
    '가끔이요 한 달에 한 번 정도 있어요'

    COUNSELOR:
    '그렇게 짜증이나 화가 날 때 어떻게 하면 풀려요?'
    """

    text = text.strip()

    if not text:
        return []

    if not is_question(text):
        return [text]

    candidates = []

    for pattern in QUESTION_START_PATTERNS:

        for match in re.finditer(
            rf"\s({re.escape(pattern)}\s+)",
            text,
        ):
            split_index = match.start(1)

            before = text[:split_index].strip()
            after = text[split_index:].strip()

            if (
                before
                and after
                and not is_question(before)
                and is_question(after)
            ):
                candidates.append(
                    (
                        split_index,
                        before,
                        after,
                    )
                )

    if not candidates:
        return [text]

    candidates.sort(
        key=lambda x: x[0]
    )

    _, before, after = candidates[0]
    
    return [
        before,
        after,
    ]


def recover_chunks(text: str) -> list[dict]:

    results = []

    punctuation_chunks = split_by_punctuation(
        text
    )

    for chunk in punctuation_chunks:

        step1_chunks = (
            split_short_answer_plus_question(
                chunk
            )
        )

        for step1_chunk in step1_chunks:

            step2_chunks = (
                split_answer_plus_question(
                    step1_chunk
                )
            )

            for final_chunk in step2_chunks:

                if is_question(final_chunk):

                    results.append(
                        {
                            "role": "COUNSELOR",
                            "text": final_chunk,
                        }
                    )

                else:

                    results.append(
                        {
                            "role": "CHILD_CANDIDATE",
                            "text": final_chunk,
                        }
                    )

    return results


TEST_SEGMENTS = [
    "최근에 건강한가요?",
    "네 최근에 다친 곳이 있나요?",
    "네",
    "어디를 얼마나 다쳤나요?",
    "손을 다쳤는데 멍이 들었어요",
    "언제 어떻게 하다가 다쳤나요?",
    "어제 창문 닫다가 조심하지 않아서",
    "다쳤어요. 무엇을 할 때 즐겁나요?",
    "친구 집에 가서 놀대요. 어떤 점이 즐거운가요?",
    "친구 집 구경하고 맛있는 것도 먹다 보면 더 친해져서요.",
    "최근 일주일 동안 짜증이나 화가 난 적이 있나요?",
    "네, 화 난 적 있어요.",
    "무엇 때문에 짜증이나 화가 났나요?",
    "피아노 학원 선생님이 제가 피아노 연습을 안 했다고 의심해서요.",
    (
        "친구의 기분을 상하게 하는 일이 자주 있나요? "
        "가끔이요 한 달에 한 번 정도 있어요 "
        "그렇게 짜증이나 화가 날 때 어떻게 하면 풀려요?"
    ),
    "친구들이랑 같이 마라탕 사 먹으면서 떠들어요.",
    "몇 시에 자고 몇 시에 일어나요?",
    "열 한 시에 다섯 일곱 시에 일어나요.",
    "자고 일어나면 몸 상태는 어떤가요?",
    "괜찮아요. 평소에 잠들기 힘들거나 잠자는 중간에 자주 깨나요?",
]


def main():

    print("=" * 100)
    print("SINGLE SPEAKER RECOVERY v3 - 1786")
    print("=" * 100)

    child_candidates = []

    for index, segment_text in enumerate(
        TEST_SEGMENTS,
        start=1,
    ):

        print()
        print(
            f"[SEGMENT {index:02d}] "
            f"{segment_text}"
        )

        recovered = recover_chunks(
            segment_text
        )

        for item in recovered:

            role = item["role"]
            text = item["text"]

            print(
                f"    {role:16} | {text}"
            )

            if role == "CHILD_CANDIDATE":
                child_candidates.append(
                    text
                )

    print()
    print("=" * 100)
    print("CHILD CANDIDATE TEXT")
    print("=" * 100)

    print(
        " ".join(child_candidates)
    )


if __name__ == "__main__":
    main()