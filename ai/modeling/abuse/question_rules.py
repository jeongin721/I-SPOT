"""
화면에 보이는 AI 초안 문장(추가 질문 · 확인 메모 · 확인할 사항)을 거르는 규칙.

[왜 따로 뒀나 — 2026-10-30]

rag/checklist_builder.py 에 있던 판정 · 단정 표현 검사(judgment_reason)와 꼬리 · 부정형 질문 검사를
추가 질문 AI 초안(followup_question_llm.py, #118) · AI 확인 메모(followup_check_llm.py)에도 쓰려고 옮겼다
(팀장님 10/29 결정 ② — #117 의 질문 검증 규칙을 #118 에 붙인다). rag 는 이미 ai.modeling 에 기대고
(rag/privacy.py), ai 쪽은 langchain 이 없어 rag 를 import 할 수 없으므로 의존성 없는 이 모듈에 둔다.
rag/checklist_builder.py 는 여기서 import 해 같은 이름으로 쓴다.

정규식과 낱말 목록만 있다. 외부 호출 · 모델 로딩이 없다.
"""

import re

# 판단 · 법률 용어. 아이에게 할 질문 문장에만 적용한다(질문에는 이 낱말 자체를 쓰지 않는다).
JUDGMENT_TERMS = ("학대", "처벌", "신고", "범죄", "가해", "피해자", "폭행", "위반", "고소", "법적", "법률")

# 화면에 보이는 모든 칸(질문 문장 · 이유, 확인할 사항 · 확인 메모)에서 막는 판정 · 단정 표현.
# 유형 이름(신체학대) · 체크리스트 · 법령을 말하는 것은 상담원용 칸에서 허용하고, 학대 · 위험 · 법 위반을 확정 · 단정하거나
# 사람을 행위자 · 피해자로 못박는 표현만 막는다(05_RULES §1 'AI 가 학대 여부를 최종 확정' 금지,
# API_CONTRACT 표현 주의 — "학대 확정" · "위험 확정" · "AI 판정" · "자동 결정").
JUDGMENT_PHRASES = ("AI 판정", "자동 결정")
_DEFINITIVE_JUDGMENT = re.compile(
    r"(?:학대|위험|범죄|위반|처벌)\s*(?:으로|로|가|이|를|을|은|는)?\s*(?:확정|단정|판정|판단|인정|확실|분명|명백|성립)"
    r"|(?:학대|범죄|위반)(?:이다|입니다|임이|에\s*해당)"
    r"|처벌\s*(?:대상|해야|받아야)"
    r"|가해자|피해자"
)

# 답을 정해 두고 확인받는 꼬리 · 부정형 질문("~했지?", "~맞지?", "~하지 않았어?")
_LEADING_ENDING = re.compile(
    r"(?:[가-힣]지|죠|맞아|맞나요|잖아요?|않았어요?|않았니|않았나요|않니|아니야|아니지)\s*\?*\s*$"
)


def judgment_reason(text: str) -> str | None:
    """판정 · 단정 표현이 있으면 그 사유, 없으면 None."""
    if any(phrase in text for phrase in JUDGMENT_PHRASES) or _DEFINITIVE_JUDGMENT.search(text):
        return "판정 · 단정 표현이 들어 있습니다"
    return None


def question_term_reason(text: str) -> str | None:
    """아이에게 할 질문 문장에 판단 · 법률 용어나 판정 · 단정 표현이 있으면 그 사유, 없으면 None."""
    if any(term in text for term in JUDGMENT_TERMS) or judgment_reason(text):
        return "판단 · 법률 용어가 들어 있습니다"
    return None


def leading_reason(text: str) -> str | None:
    """답을 정해 두고 확인받는 꼬리 · 부정형 질문이면 그 사유, 아니면 None."""
    if _LEADING_ENDING.search(text):
        return "답을 정해 두고 확인받는 질문입니다"
    return None
