# 서식 4(초기면접지) ② 초기면접 내용의 '아동 특성' · '가정상황' 고르기 항목.
#
# 사례(Case)의 intake_child_traits · intake_family_situations 는 이 목록의 항목만 받는다.
# 상담사 웹의 목록(counselor-web/src/data/screens/intakeItems.ts)과 같아야 한다 — tests/test_case_intake.py 가 비교한다.
# 서식의 선택지라 개인 식별 정보가 아니다. 자유 글('기타' 의 내용 등)은 받지 않는다.

INTAKE_CHILD_TRAITS: tuple[str, ...] = (
    "거짓말",
    "반항 · 충동 · 공격성",
    "도벽",
    "가출",
    "약물",
    "흡연",
    "음주",
    "인터넷(게임)중독",
    "성문제",
    "주의산만",
    "과잉행동",
    "늦은귀가",
    "불건전한 또래관계",
    "대인관계 기피",
    "학교부적응",
    "잦은결석",
    "학교폭력 가해자",
    "학교폭력 피해자",
    "불안",
    "애착문제",
    "무력감",
    "우울",
    "낮은자존감",
    "신체발달지연",
    "언어문제",
    "학습문제",
    "대소변문제",
    "성격 및 기질문제",
    "위생문제",
    "틱",
    "급(만)성질병",
    "영양결핍",
    "탐식 및 결식",
    "특성없음",
    "기타",
)

INTAKE_FAMILY_SITUATIONS: tuple[str, ...] = (
    "성격 및 기질 문제",
    "어릴적 학대경험",
    "알콜남용",
    "약물남용",
    "신체질환 및 장애",
    "정신질환 및 장애",
    "원치않은 아동",
    "부적절한 양육태도",
    "양육지식 및 기술부족",
    "부부 및 가족갈등",
    "성문제",
    "스트레스",
    "사회적 고립",
    "경제적 어려움",
    "배우자폭력",
    "존속학대",
    "전과력",
    "종교문제",
    "도박 · 게임중독",
    "특성없음",
    "기타",
)


def normalize_intake(values: list[str], allowed: tuple[str, ...], label: str) -> list[str]:
    """
    서식 4 항목만 받고 겹친 항목은 처음 것만 남긴다(고른 순서 유지).

    목록에 없는 항목이 있으면 ValueError(스키마 검사에서 422 VALIDATION_ERROR 가 된다).
    보낸 글자를 오류 문구에 되풀이하지 않는다.
    """

    if any(value not in allowed for value in values):
        raise ValueError(f"{label} 은 서식 4 의 항목만 고를 수 있습니다.")

    return list(dict.fromkeys(values))
