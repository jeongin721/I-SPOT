"""
I-SPOT 2차 모델에서 사용하는 공식자료 기반 학대 세부유형 라벨을 정의한다.
4대 학대유형 아래 19개 세부 신호를 Multi-label 방식으로 분류하기 위한 설정 파일이다.
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
# 2. 세부유형 Multi-label
# ============================================================
# 하나의 상담 발화/사례에서 여러 세부유형이 동시에
# 나타날 수 있으므로 상호배타적인 클래스가 아니다.
# ============================================================

SUBTYPE_LABELS = {
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
# 3. 사용자 화면용 한국어 표시명
# ============================================================

SUBTYPE_DISPLAY_NAMES = {
    # --------------------------------------------------------
    # 신체학대
    # --------------------------------------------------------
    "physical_direct": "직접 신체 가해",
    "physical_object": "도구 사용 가해",
    "physical_force": "완력·신체적 강압",
    "physical_harmful": "유해물질·화상 등 가해",

    # --------------------------------------------------------
    # 정서학대
    # --------------------------------------------------------
    "emotional_verbal": "언어적 모욕·적대",
    "emotional_threat": "위협·쫓아냄",
    "emotional_restriction": "감금·억제·강압",
    "emotional_discrimination": "차별·편애·가족 내 고립",
    "emotional_dv_exposure": "가정폭력 노출",
    "emotional_cruelty": "기타 가학적 행위",

    # --------------------------------------------------------
    # 성학대
    # --------------------------------------------------------
    "sexual_exposure": "성적 노출·관찰",
    "sexual_molestation": "성적 추행",
    "sexual_simulated": "유사성행위",
    "sexual_intercourse": "성교",
    "sexual_exploitation": "성매매·매개",

    # --------------------------------------------------------
    # 방임
    # --------------------------------------------------------
    "neglect_physical": "물리적 방임",
    "neglect_education": "교육적 방임",
    "neglect_medical": "의료적 방임",
    "neglect_abandonment": "유기",
}


# ============================================================
# 4. 전체 세부유형 라벨
# ============================================================

ALL_SUBTYPE_LABELS = [
    subtype
    for subtype_list in SUBTYPE_LABELS.values()
    for subtype in subtype_list
]


# ============================================================
# 5. 세부유형 → 대분류 매핑
# ============================================================
# 추론 결과를 다시 4대 유형과 연결하거나
# 데이터 검증 시 사용한다.
# ============================================================

SUBTYPE_TO_MAJOR = {
    subtype: major
    for major, subtype_list in SUBTYPE_LABELS.items()
    for subtype in subtype_list
}


# ============================================================
# 6. 기본 검증
# ============================================================

assert len(ALL_SUBTYPE_LABELS) == 19
assert len(set(ALL_SUBTYPE_LABELS)) == 19