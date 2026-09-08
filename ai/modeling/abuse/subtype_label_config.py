"""
I-SPOT 2차 학대 세부유형 모델의 라벨 체계와 5단계 신호 수준을 정의한다.
 Multi-label 분류에 사용하며, 신호 수준은 별도 ordinal target으로 관리한다.
"""

# ============================================================
# 1. 4대 학대유형
# ============================================================

MAJOR_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 2. 세부유형 라벨
# ============================================================

SUBTYPE_LABELS = {
    "신체학대": [
        "physical_direct_hit",
        "physical_force",
        "physical_object",
        "physical_punishment",
        "physical_harmful_substance",
    ],

    "정서학대": [
        "emotional_verbal",
        "emotional_threat",
        "emotional_humiliation",
        "emotional_isolation",
        "emotional_dv_exposure",
        "emotional_excessive_demand",
    ],

    "성학대": [
        "sexual_contact",
        "sexual_harassment",
        "sexual_request",
        "sexual_exposure_request",
        "sexual_content_exposure",
        "sexual_exploitation",
    ],

    "방임": [
        "neglect_physical",
        "neglect_medical",
        "neglect_education",
        "neglect_supervision",
        "neglect_abandonment",
    ],
}


# ============================================================
# 3. 한국어 표시명
# ============================================================

SUBTYPE_DISPLAY_NAMES = {
    "physical_direct_hit": "직접 타격",
    "physical_force": "완력 사용",
    "physical_object": "도구 사용",
    "physical_punishment": "체벌",
    "physical_harmful_substance": "유해물질",

    "emotional_verbal": "언어폭력·모욕",
    "emotional_threat": "위협·협박",
    "emotional_humiliation": "공개적 수치심",
    "emotional_isolation": "감금·고립",
    "emotional_dv_exposure": "가정폭력 노출",
    "emotional_excessive_demand": "과도한 강요",

    "sexual_contact": "성적 신체접촉",
    "sexual_harassment": "성적 언행·성희롱",
    "sexual_request": "성적 행위 요구",
    "sexual_exposure_request": "신체 노출 요구",
    "sexual_content_exposure": "성적 장면 노출",
    "sexual_exploitation": "성매매·매개",

    "neglect_physical": "물리적 방임",
    "neglect_medical": "의료적 방임",
    "neglect_education": "교육적 방임",
    "neglect_supervision": "보호·감독 방임",
    "neglect_abandonment": "유기",
}


# ============================================================
# 4. 5단계 신호 수준
# ============================================================

SIGNAL_LEVELS = {
    1: "매우 낮음",
    2: "낮음",
    3: "중간",
    4: "높음",
    5: "매우 높음",
}


# ============================================================
# 5. 전체 세부유형 라벨 평탄화
# ============================================================

ALL_SUBTYPE_LABELS = [
    subtype
    for subtype_list in SUBTYPE_LABELS.values()
    for subtype in subtype_list
]
