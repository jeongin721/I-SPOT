"""
v2/v4/v5 모델의 문맥 이해 및 경계 사례 성능을 비교하기 위한 Frozen Context Test v2를 생성한다.
부정·정상돌봄·사고·비유·모호한 아동 발화·복합 학대 신호를 포함하며 학습에는 사용하지 않는다.
"""

from pathlib import Path

import pandas as pd


# ============================================================
# 경로 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "context_test_v2.csv"
)


# ============================================================
# 테스트 데이터
# ============================================================
#
# label 순서:
# [신체학대, 정서학대, 성학대, 방임]
#
# 중요:
# 이 데이터는 모델 선택을 위한 Frozen Test 데이터다.
# 학습/augmentation 데이터에 절대 포함하지 않는다.
# ============================================================

TEST_CASES = [

    # ========================================================
    # 1. 정상 돌봄 / 방임 Hard Negative
    # ========================================================

    {
        "audio_text": "엄마가 늦게 오는 날에는 제가 먼저 집에 있어요. 밥은 냉장고에 해놓고 전화도 해줘요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "normal_care",
    },
    {
        "audio_text": "아빠가 일이 있어서 늦게 왔어요. 저녁은 할머니랑 먹고 아빠가 계속 전화했어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "normal_care",
    },
    {
        "audio_text": "엄마가 병원에 바로 못 데려갔는데 다음 날 아침에 같이 병원 갔어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "medical_care",
    },
    {
        "audio_text": "집에 혼자 있었는데 한 시간 정도였어요. 엄마가 금방 온다고 전화했어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "temporary_alone",
    },
    {
        "audio_text": "엄마가 늦게까지 일해서 저녁에는 할머니가 저를 봐주세요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "alternative_care",
    },

    # ========================================================
    # 2. 사고 / 치료 / 정상적인 신체 접촉
    # ========================================================

    {
        "audio_text": "친구랑 뛰다가 넘어져서 팔에 멍이 생겼어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "accident",
    },
    {
        "audio_text": "축구하다가 공에 맞아서 얼굴이 좀 아팠어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "accident",
    },
    {
        "audio_text": "병원에서 선생님이 아픈 곳을 보려고 배를 눌러봤어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "medical_contact",
    },
    {
        "audio_text": "엄마가 넘어질 것 같아서 제 팔을 꽉 잡았어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "protective_contact",
    },
    {
        "audio_text": "아빠랑 장난치다가 제가 소파에서 떨어져서 등이 조금 아팠어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "accident",
    },

    # ========================================================
    # 3. 위협/부정 표현 - 신체 Hard Negative
    # ========================================================

    {
        "audio_text": "아빠가 때릴 것처럼 손을 들었는데 저를 때리지는 않았어요.",
        "label": [0, 1, 0, 0],
        "scenario_type": "threat_without_hit",
    },
    {
        "audio_text": "엄마가 화는 많이 냈는데 저를 때린 적은 없어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "explicit_negation",
    },
    {
        "audio_text": "아빠가 저를 때린다는 건 아니고 목소리가 커서 무서워요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "explicit_negation",
    },
    {
        "audio_text": "선생님이 혼내기는 했는데 손으로 때리거나 밀지는 않았어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "explicit_negation",
    },
    {
        "audio_text": "엄마가 화나서 손을 들었는데 그냥 내려놓았어요. 저는 좀 무서웠어요.",
        "label": [0, 1, 0, 0],
        "scenario_type": "threat_context",
    },

    # ========================================================
    # 4. 두루뭉술한 신체학대 관련 신호
    # ========================================================

    {
        "audio_text": "아빠가 화나면 저 잡을 때 좀 아파요. 팔에 자국 생긴 적도 있어요.",
        "label": [1, 0, 0, 0],
        "scenario_type": "implicit_physical",
    },
    {
        "audio_text": "제가 말 안 들었을 때 집에서 혼났는데 다음 날 보니까 다리에 멍이 있었어요.",
        "label": [1, 0, 0, 0],
        "scenario_type": "implicit_physical",
    },
    {
        "audio_text": "아빠한테 혼나고 나면 몸이 아플 때가 있어요. 그냥 제가 잘못해서 그런 거예요.",
        "label": [1, 0, 0, 0],
        "scenario_type": "minimized_physical",
    },
    {
        "audio_text": "엄마가 저를 잡아당겼는데 너무 세게 해서 손목이 계속 아팠어요.",
        "label": [1, 0, 0, 0],
        "scenario_type": "physical_force",
    },
    {
        "audio_text": "집에서 잘못하면 가끔 맞아요. 어디를 맞았는지는 말하기 싫어요.",
        "label": [1, 0, 0, 0],
        "scenario_type": "vague_physical",
    },

    # ========================================================
    # 5. 두루뭉술한 정서학대 관련 신호
    # ========================================================

    {
        "audio_text": "엄마가 화나면 제가 없었으면 좋겠다고 해요. 화 풀리면 다시 괜찮아요.",
        "label": [0, 1, 0, 0],
        "scenario_type": "emotional_rejection",
    },
    {
        "audio_text": "아빠 집에 오면 그냥 방에 있어요. 괜히 말했다가 또 뭐라고 할까 봐요.",
        "label": [0, 1, 0, 0],
        "scenario_type": "emotional_fear",
    },
    {
        "audio_text": "엄마가 저 때문에 인생이 힘들어졌다고 자꾸 말해요.",
        "label": [0, 1, 0, 0],
        "scenario_type": "emotional_blame",
    },
    {
        "audio_text": "집에서는 제가 하는 건 다 틀렸다고 해요. 그래서 그냥 말을 안 해요.",
        "label": [0, 1, 0, 0],
        "scenario_type": "emotional_devaluation",
    },
    {
        "audio_text": "아빠가 심한 말을 하고 나중에 미안하다고 했어요. 그래도 그런 말을 자주 해요.",
        "label": [0, 1, 0, 0],
        "scenario_type": "apology_after_emotional",
    },

    # ========================================================
    # 6. 성학대 관련 모호한 표현
    # ========================================================

    {
        "audio_text": "그 사람이 저 만지는 게 싫어요. 어디를 만졌는지는 말하기 싫어요.",
        "label": [0, 0, 1, 0],
        "scenario_type": "implicit_sexual",
    },
    {
        "audio_text": "저한테 이상한 거 보여달라고 했어요. 아무한테도 말하지 말라고 했어요.",
        "label": [0, 0, 1, 0],
        "scenario_type": "sexual_request",
    },
    {
        "audio_text": "둘이 있을 때 자꾸 제 몸을 만져요. 저는 싫은데 그냥 가만히 있었어요.",
        "label": [0, 0, 1, 0],
        "scenario_type": "unwanted_contact",
    },
    {
        "audio_text": "그 사람이 이상한 사진을 보여줬어요. 보기 싫다고 했는데 계속 보여줬어요.",
        "label": [0, 0, 1, 0],
        "scenario_type": "sexual_exposure",
    },
    {
        "audio_text": "우리끼리만 아는 비밀이라고 하면서 제 몸을 보여달라고 했어요.",
        "label": [0, 0, 1, 0],
        "scenario_type": "sexual_secrecy",
    },

    # ========================================================
    # 7. 방임 관련 모호한 표현
    # ========================================================

    {
        "audio_text": "엄마가 며칠 집에 안 왔어요. 배고프면 그냥 라면 먹었어요.",
        "label": [0, 0, 0, 1],
        "scenario_type": "food_neglect",
    },
    {
        "audio_text": "밤에 혼자 있는 날이 많아요. 엄마가 언제 오는지는 잘 몰라요.",
        "label": [0, 0, 0, 1],
        "scenario_type": "supervision_neglect",
    },
    {
        "audio_text": "많이 아팠는데 그냥 참았어요. 병원에는 안 갔어요.",
        "label": [0, 0, 0, 1],
        "scenario_type": "medical_neglect",
    },
    {
        "audio_text": "집에 먹을 게 없을 때가 많아서 학교에서 먹는 게 거의 전부예요.",
        "label": [0, 0, 0, 1],
        "scenario_type": "food_neglect",
    },
    {
        "audio_text": "어른 없이 동생이랑 둘이 자는 날이 자주 있어요.",
        "label": [0, 0, 0, 1],
        "scenario_type": "supervision_neglect",
    },

    # ========================================================
    # 8. 복합 신호
    # ========================================================

    {
        "audio_text": "아빠가 술 마시면 저를 잡고 밀어요. 제가 쓸모없다고 말할 때도 있어요.",
        "label": [1, 1, 0, 0],
        "scenario_type": "physical_emotional",
    },
    {
        "audio_text": "집에서 맞을 때도 있고 밥을 못 먹고 혼자 있는 날도 있어요.",
        "label": [1, 0, 0, 1],
        "scenario_type": "physical_neglect",
    },
    {
        "audio_text": "그 사람이 제 몸을 만지고 말하면 혼내준다고 했어요.",
        "label": [0, 1, 1, 0],
        "scenario_type": "emotional_sexual",
    },
    {
        "audio_text": "엄마가 며칠씩 안 들어오고 전화하면 귀찮게 하지 말라고 해요.",
        "label": [0, 1, 0, 1],
        "scenario_type": "emotional_neglect",
    },
    {
        "audio_text": "아빠가 때리고 욕할 때가 있고 집에 먹을 것도 잘 없어요.",
        "label": [1, 1, 0, 1],
        "scenario_type": "physical_emotional_neglect",
    },

    # ========================================================
    # 9. 키워드 함정 / 비유 / 일반적 갈등
    # ========================================================

    {
        "audio_text": "엄마 잔소리 때문에 귀가 아플 것 같아요. 진짜로 때린 건 아니에요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "figurative",
    },
    {
        "audio_text": "아빠가 게임 그만하라고 해서 짜증났어요. 그래서 오늘은 아빠가 싫어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "normal_conflict",
    },
    {
        "audio_text": "엄마가 시험 점수가 낮다고 혼냈어요. 다음에는 공부하라고 했어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "normal_discipline",
    },
    {
        "audio_text": "친구가 장난으로 제 등을 툭 쳤는데 아프지는 않았어요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "peer_play",
    },
    {
        "audio_text": "아빠가 저를 죽도록 사랑한다고 말해요. 진짜 죽인다는 말은 아니에요.",
        "label": [0, 0, 0, 0],
        "scenario_type": "figurative",
    },
]


# ============================================================
# DataFrame 생성
# ============================================================

def build_dataframe():
    """테스트 사례에 ID와 source 정보를 추가한다."""

    rows = []

    for index, case in enumerate(
        TEST_CASES,
        start=1,
    ):

        rows.append(
            {
                "sample_id": f"CTX{index:03d}",
                "audio_text": case["audio_text"],
                "label": str(case["label"]),
                "scenario_type": case["scenario_type"],
                "source": "frozen_context_test_v2",
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# 데이터 검증
# ============================================================

def validate_dataframe(df):
    """라벨 형식과 중복 문장을 검사한다."""

    if df["audio_text"].duplicated().any():
        duplicates = df[
            df["audio_text"].duplicated(
                keep=False
            )
        ]

        raise ValueError(
            "중복 문장이 발견되었습니다.\n"
            + duplicates.to_string(index=False)
        )

    for label in df["label"]:

        parsed = eval(
            label,
            {"__builtins__": {}},
        )

        if len(parsed) != 4:
            raise ValueError(
                f"잘못된 label 길이: {label}"
            )

        if not all(
            value in (0, 1)
            for value in parsed
        ):
            raise ValueError(
                f"잘못된 label 값: {label}"
            )


# ============================================================
# 저장
# ============================================================

def main():

    df = build_dataframe()

    validate_dataframe(
        df
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("=" * 70)
    print("Frozen Context Test v2 생성 완료")
    print("=" * 70)

    print(
        "저장 위치 :",
        OUTPUT_PATH,
    )

    print(
        "전체 사례 :",
        len(df),
    )

    print()
    print("Scenario 분포")
    print(
        df["scenario_type"]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "주의: 이 CSV는 평가 전용이며 "
        "학습 데이터에 포함하면 안 됩니다."
    )


if __name__ == "__main__":
    main()