"""
LLM 이 한국어 문장 중간에 다른 나라 문자를 섞어 쓴 것 찾기(2026-10-30).

데모에서 확인 메모에 "재발 방지 ব্যবস্থা의 진행 여부"(벵골어 '조치')가 나왔다. 상담사 화면에 그대로 나가면 안 되므로
카드형 AI 결과(확인 메모 · 추가 질문 초안 · 종결 요약)는 이런 문장을 버린다.

허용: 한글 · 로마자(영문 약어 · seg 번호) · 한자(CJK) · 전각/반각 글자. 숫자 · 기호 · 공백은 글자가 아니라 따로 보지 않는다.
그 밖 문자(벵골 · 데바나가리 · 아랍 · 키릴 · 타이 · 가나 등)가 하나라도 있으면 True. 표준 라이브러리만 쓴다(CI 에서 시험).
"""

import unicodedata

_ALLOWED_PREFIXES = ("HANGUL", "LATIN", "CJK", "FULLWIDTH", "HALFWIDTH")


def has_foreign_script(text: str) -> bool:
    """허용 문자가 아닌 글자(유니코드 문자 범주 L*)가 하나라도 있으면 True."""

    for char in text or "":
        if not unicodedata.category(char).startswith("L"):
            continue
        name = unicodedata.name(char, "")
        if not name.startswith(_ALLOWED_PREFIXES):
            return True
    return False
