"""
고령자 '다음 상담 준비' 화면 '추가 질문' 카드의 초안(2026-11-17, 아동 followup_question_llm 을 대상만 바꿔 옮김).

[아동 템플릿과 같은 것]
- 질문은 늘 초안이다. 담당자가 승인해야 질문 목록(API_CONTRACT 18절 PUT /sessions/{id}/followup-questions)에 들어간다.
- 결과 모양도 같다 — AIAnalysisResult.followup_questions = [{"text", "kind", "segment_ids", "reason", "bank_code"}].
- 유도 질문을 막는 세 겹: 프롬프트 금지 · 코드 검사(_clean_questions) · 담당자 승인.
  코드 검사는 열린 질문 표지가 없거나, 물음이 둘 이상이거나, 어르신이 이번에 말하지 않은 사람 · 행위 낱말을 먼저 꺼내거나,
  판단 · 법률 용어(question_rules)나 진단 · 판정 말(senior_brief_llm.FORBIDDEN)이 있거나, 답을 정해 둔 꼬리 질문이면 버린다.

[아동과 다른 것]
- 대상: 어르신. 쉬운 존댓말, 짧게. 아이 나이대 대신 어르신 말씀을 이어받아 생활 · 건강 · 관계를 여쭙는다.
- 재료: 이번 녹취 전체(가린 뒤)와 이번에 이야기가 나오지 않은 생활 · 정서 영역.
- 질문 은행(BANK) 초안: 이번 방문에 이야기가 없던 영역(식사 · 수면 · 외출 · 사회활동 · 정서)은 정해 둔 문장
  (DOMAIN_BANK)으로 '다음에 여쭤 볼 것' 을 낸다. LLM 없이(SENIOR_AI_PROVIDER=rule)도 나온다. 근거 발화는 없다(segment_ids []).
- 우울 · 치매 등 진단으로 이어지는 선별 질문(검사 문항)을 만들지 않는다 — 의료법 27조 · 멘토 기준 'AI 는 진단하지 않음'.

openai 는 CI 에 없다. 검사 함수를 backend/tests 에서 시험할 수 있게 LLM 호출 쪽 import 는 함수 안에 둔다.
"""

import re
from typing import Any, Dict, Iterable, List, Optional

from ai.modeling.abuse.question_rules import judgment_reason, leading_reason, question_term_reason
from ai.modeling.abuse.text_script import has_foreign_script
from ai.modeling.senior.care_domains import DOMAINS, DOMAIN_LABELS
from ai.modeling.senior.senior_brief_llm import is_forbidden

#: 질문 초안 최대 개수(아동과 같다).
MAX_QUESTIONS = 5
#: Backend 저장 API 의 질문 길이 한도(followup_question 스키마)와 같다.
MAX_TEXT_CHARS = 300
#: 은행 질문은 LLM 질문 뒤에 붙이고, 이만큼까지만.
MAX_BANK_QUESTIONS = 3

#: 이번에 이야기가 없던 영역을 다음에 여쭤 볼 정해 둔 문장. 판정 · 유도 없이 어르신이 자기 말로 답하게.
DOMAIN_BANK = {
    "MEAL": "요즘 식사는 어떻게 챙겨 드세요?",
    "SLEEP": "요즘 밤에 주무시는 건 어떠세요?",
    "OUTING": "요즘 바깥에는 얼마나 나가세요?",
    "SOCIAL": "요즘 자주 만나거나 연락하는 분은 누구세요?",
    "MOOD": "요즘 하루하루 지내시는 마음은 어떠세요?",
}
BANK_REASON = "이번 방문에 {label} 이야기가 나오지 않음"


SYSTEM_PROMPT = """너는 고령자 돌봄 담당자(생활지원사 · 사회복지사)가 다음 방문에서 어르신께 여쭐 **열린 질문 초안**을
만드는 도우미다. 초안은 담당자가 검토 · 수정 · 승인한 뒤에만 쓰인다. 판단은 담당자가 한다.

[절대 원칙]
1. 예/아니오로 답할 수 있는 질문을 만들지 않는다("~하셨어요?", "~맞으시죠?", "~지 않으셨어요?" 금지).
   "무엇 · 어떻게 · 어디 · 언제 · 누구 · 얼마나 · 어떠세요 · 말씀해 주시겠어요" 처럼 어르신이 자기 말로 답하는 질문만 만든다.
2. 어르신이 이번 상담에서 직접 말하지 않은 사람이나 행위를 질문에서 먼저 꺼내지 않는다
   (예: 어르신이 아드님 이야기를 하지 않았는데 "아드님이 화를 내세요?" 금지).
3. 입력에 없는 사실 · 감정을 가정하지 않는다("많이 외로우시죠?" 금지).
4. 질문 하나에 물음 하나만. 물음표는 한 번만 쓴다.
5. 질병 이름 · 진단 · 판정 말을 쓰지 않는다("우울", "치매", "고혈압", "의심" 금지). 기억력 · 우울을 재는 검사 문항을 만들지 않는다.
   치료 · 약 조절 · 병원 진료를 권하는 질문도 만들지 않는다.
6. 어르신이 실제로 한 말을 이어받아 묻는다. 예: 어르신이 "요새 밥맛이 없어"라고 했으면 "밥맛이 없으신 건 언제부터 그러셨어요?".
7. 쉬운 존댓말로 짧게 쓴다. 어르신께 직접 소리 내어 여쭐 수 있는 말로.
8. 말씀은 나왔지만 그 뒤가 안 나온 것(언제부터 · 얼마나 · 지금은 어떤지 · 누가 돕는지)을 우선으로 고른다.
   물을 만한 것이 없으면 빈 리스트를 돌려준다. 최대 {max_questions}개.
9. 질문마다 근거가 된 발화 번호를 정확히 인용한다. 줄 앞에 [s3] 처럼 적혀 있다. 인용할 줄이 없으면 그 질문은 만들지 않는다.
10. reason 에는 왜 이 질문이 필요한지 담당자에게 한 문장으로 적는다(예: "식사를 거른다는 말씀 뒤로 얼마나 그런지 안 나옴").

[이번 녹취]
{transcript}

문장은 한국어로만 쓴다(다른 나라 글자를 섞지 않는다). 이름 토큰은 그대로 둔다.
반드시 아래 JSON 형식으로만 답한다:
{{
  "questions": [
    {{"text": "...", "refs": ["s3"], "reason": "..."}}
  ]
}}
"""


# ------------------------------------------------------------
# 코드 검사
# ------------------------------------------------------------

#: 열린 질문 표지(존댓말 꼴 포함). 하나도 없으면 닫힌 질문으로 보고 버린다.
_OPEN_MARKERS = (
    "무엇", "뭐", "뭘", "무슨", "어떻게", "어떤", "어떠", "어땠", "어떨", "어디", "언제", "누구", "누가",
    "얼마나", "몇",
    "말씀해 주", "말씀 해 주", "말씀해주", "이야기해 주", "이야기 해 주", "이야기해주", "얘기해 주", "얘기해주",
    "들려주", "들려 주", "설명해 주",
)

#: 어르신이 먼저 꺼내지 않았으면 질문에 쓰면 안 되는 인물 낱말. 근거 발화에도 있으면 괜찮다.
_PERSON_WORDS = (
    "아들", "아드님", "딸", "따님", "며느리", "사위", "손주", "손자", "손녀", "남편", "아내", "부인", "영감", "할멈",
    "할아버지", "할머니", "자식", "자녀", "형제", "누님", "언니", "오빠", "동생", "조카", "이웃", "친구", "요양보호사",
)

#: 같은 이유로 막는 행위 낱말 묶음(아동 템플릿과 같은 줄기 + 돈 · 방치 관련). 질문에 한 묶음의 줄기가 있으면 근거에도 있어야 한다.
_ACT_FAMILIES = (
    ("때리", "때렸", "때려", "때린", "때릴"),
    ("맞았", "맞으셨", "맞은", "맞고"),
    ("밀쳤", "밀쳐", "밀친", "밀었"),
    ("던지", "던졌", "던져", "던진"),
    ("가두", "가뒀", "가둬", "가둔"),
    ("굶",),
    ("욕",),
    ("소리 지르", "소리를 지르", "소리치"),
    ("돈을 가져", "돈 가져", "통장", "연금을 가져"),
    ("혼자 두", "내버려", "방치"),
)

_SHORT_PERSON_WORDS = {"딸", "동생", "친구", "아내", "부인"}
_PARTICLES = "이가은는을를도랑과와한테에게께의"


def _mentions(text: str, word: str) -> bool:
    if word not in _SHORT_PERSON_WORDS:
        return word in text
    pattern = rf"(?<![가-힣]){re.escape(word)}(?:들)?(?:[{_PARTICLES}]|(?![가-힣]))"
    return re.search(pattern, text) is not None


def _is_open_question(text: str) -> bool:
    return any(marker in text for marker in _OPEN_MARKERS)


#: 높임말로 부른 사람은 근거 발화의 보통말과 같은 사람으로 본다("아드님" ↔ 어르신이 말한 "아들").
_HONORIFIC = {"아드님": "아들", "따님": "딸", "손주분": "손주", "남편분": "남편", "부인분": "부인"}


def _plain(text: str) -> str:
    for honorific, plain in _HONORIFIC.items():
        text = text.replace(honorific, plain)
    return text


def _introduces_new_word(question: str, evidence_text: str) -> bool:
    """질문에 있는 인물 · 행위 낱말이 근거 발화에 하나라도 없으면 True."""

    question, evidence_text = _plain(question), _plain(evidence_text)
    for word in _PERSON_WORDS:
        if _mentions(question, word) and not _mentions(evidence_text, word):
            return True
    for family in _ACT_FAMILIES:
        if any(stem in question for stem in family) and not any(stem in evidence_text for stem in family):
            return True
    return False


def question_problem(text: str, evidence_text: str) -> Optional[str]:
    """질문 하나를 버릴 사유. 괜찮으면 None. 은행 문장 시험에도 쓴다."""

    if not text or len(text) > MAX_TEXT_CHARS:
        return "길이"
    if has_foreign_script(text):
        return "다른 나라 글자"
    if text.count("?") + text.count("？") > 1:
        return "물음 둘 이상"
    if not _is_open_question(text):
        return "닫힌 질문"
    if _introduces_new_word(text, evidence_text):
        return "말하지 않은 사람 · 행위"
    if question_term_reason(text) or leading_reason(text):
        return "판단 용어 · 꼬리 질문"
    if is_forbidden(text):
        return "진단 · 판정 말"
    return None


def _clean_questions(raw_questions: Any, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """LLM 이 낸 질문을 거른다. 걸린 질문만 빠진다. segments: 원본(가리기 전) 발화 — 번호 확인 · 근거 글."""

    if not isinstance(raw_questions, list):
        return []

    texts_by_id = {
        str(segment.get("segment_id", "")): str(segment.get("text") or "")
        for segment in segments
        if isinstance(segment, dict)
    }
    cleaned: List[Dict[str, Any]] = []
    seen = set()

    for item in raw_questions:
        if len(cleaned) >= MAX_QUESTIONS:
            break
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        text = " ".join(item["text"].split())
        if text in seen:
            continue
        refs = item.get("refs") if isinstance(item.get("refs"), list) else item.get("segment_ids")
        segment_ids: List[str] = []
        for sid in refs if isinstance(refs, list) else []:
            sid = str(sid).strip()
            if sid in texts_by_id and sid not in segment_ids:
                segment_ids.append(sid)
        if not segment_ids:
            continue
        evidence_text = " ".join(texts_by_id[sid] for sid in segment_ids)
        if question_problem(text, evidence_text):
            continue

        reason = item.get("reason")
        reason = " ".join(reason.split())[:MAX_TEXT_CHARS] if isinstance(reason, str) else ""
        if reason and (judgment_reason(reason) or is_forbidden(reason)):
            continue

        seen.add(text)
        cleaned.append({"text": text, "kind": "OPEN", "segment_ids": segment_ids, "reason": reason, "bank_code": None})

    return cleaned


def bank_questions(domains: Iterable[Dict[str, Any]], already: Iterable[str] = ()) -> List[Dict[str, Any]]:
    """이번에 이야기가 없던 영역(change NOT_MENTIONED)의 정해 둔 질문. 영역 순서대로 MAX_BANK_QUESTIONS 개까지."""

    missing = {item.get("domain") for item in domains if isinstance(item, dict) and item.get("change") == "NOT_MENTIONED"}
    taken = set(already)
    result = []
    for domain in DOMAINS:
        if domain not in missing or DOMAIN_BANK[domain] in taken:
            continue
        result.append(
            {
                "text": DOMAIN_BANK[domain],
                "kind": "BANK",
                "segment_ids": [],
                "reason": BANK_REASON.format(label=DOMAIN_LABELS[domain]),
                "bank_code": f"SENIOR_{domain}",
            }
        )
        if len(result) >= MAX_BANK_QUESTIONS:
            break
    return result


def merge_questions(llm: List[Dict[str, Any]], domains: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """LLM 질문 뒤에 은행 질문을 붙인다(합쳐 MAX_QUESTIONS 개까지)."""

    room = MAX_QUESTIONS - len(llm)
    if room <= 0:
        return llm[:MAX_QUESTIONS]
    return llm + bank_questions(domains, [q["text"] for q in llm])[:room]


# ------------------------------------------------------------
# LLM 호출
# ------------------------------------------------------------


def generate_questions_from_masked_lines(
    client: Any,
    model: str,
    masked_lines: List[str],
    segments: List[Dict[str, Any]],
    deadline: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """masked_lines: senior_session_llm.format_transcript 줄을 가린 것. 실패하면 [] — 요약 전체를 멈추지 않는다."""

    transcript = "\n".join(masked_lines).strip()
    if not transcript:
        return []
    prompt = SYSTEM_PROMPT.format(max_questions=MAX_QUESTIONS, transcript=transcript)
    try:
        from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=prompt,
            user_prompt="위 녹취를 바탕으로 다음 방문에 여쭐 열린 질문 초안을 만들어.",
            max_retries=2,
            timeout_seconds=120.0,
            deadline=deadline,
        )
    except Exception:
        return []
    if not isinstance(parsed, dict):
        return []
    try:
        return _clean_questions(parsed.get("questions"), segments)
    except Exception:
        return []
