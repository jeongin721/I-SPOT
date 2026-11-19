"""
아이 앱(콩콩) 답을 보고 상담사용 '확인해 볼 점'과 추가 질문 초안을 만드는 LLM 모듈(2026-11-09).

입력은 확인이 필요한 답과 그 질문의 지난 답, 아이가 쓴 글이다. privacy_gateway 로 가린 뒤 보내고, 답은 restore_pii 로 되돌린다.
나가는 글은 세 겹으로 막는다.
 1. 판정 · 단정 표현(judgment_reason)이 있는 메모는 버린다.
 2. 아이에게 할 질문은 판단 · 법률 용어(question_term_reason) · 답을 정해 둔 꼬리 질문(leading_reason)이 있으면 버린다.
 3. 가린 이름 토큰이 남은 질문은 버린다(이름이 들어간 질문은 아이 기기로 보내지 않는다).
초안은 상담사가 승인해야 앱으로 간다(Backend child_app_ai_service).
"""

import json
import re
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_MODEL = "gpt-5.6-luna"

MAX_NOTE_CHARS = 300
MAX_QUESTION_CHARS = 120
MAX_OPTION_CHARS = 20
MAX_OPTIONS = 6
HARD_TO_SAY = "말하기 어려워요"
_MASK_TOKEN = re.compile(r"\[[A-Z]+_\d+\]")

SYSTEM_PROMPT = """너는 아동보호전문기관 상담사를 돕는 보조 도구다. 아이가 앱에서 고른 답을 보고, 상담사가 참고할 초안을 쓴다.
최종 판단과 연락 여부는 상담사가 한다.

[항목마다 쓸 것]
- note: 상담사가 확인해 볼 점 1~2문장. 답이 어떻게 달라졌는지와, 다음 상담에서 살펴볼 만한 것을 쓴다.
- question: 아이에게 앱으로 물어볼 짧은 추가 질문 1개. 필요 없으면 null.
- options: question 의 답 보기 2~4개.

[절대 원칙]
1. 입력에 없는 사실을 지어내지 않는다. 원인을 추측하지 않는다.
2. 학대 여부 · 위험을 확정하거나 단정하지 않는다. 누구를 행위자 · 피해자로 못박지 않는다.
3. 아이에게 할 질문은 아이에게 직접 말하듯 쓴다("아이는", "아동은"처럼 3인칭으로 부르지 않는다). 초등학생도 이해할 쉬운 존댓말로, 한 번에 하나만 묻는다.
4. 질문에 '학대 · 처벌 · 신고 · 범죄 · 가해 · 피해자 · 폭행 · 위반 · 고소 · 법적 · 법률' 같은 말을 쓰지 않는다.
5. 답을 정해 두고 확인받는 질문("~했지?", "~않았어요?")을 쓰지 않는다. 특정 사람이 무엇을 했다고 전제하지 않는다.
6. 질문에 사람 이름이나 [PERSON_01] 같은 표시를 넣지 않는다.
7. 답 보기는 치우치지 않게 쓰고, 아이의 답을 한쪽으로 몰지 않는다.
8. 문장은 한국어로만 쓴다.

반드시 아래 JSON 형식으로만 답한다. no 는 입력의 번호다.
{"items": [{"no": 1, "note": "...", "question": "..." , "options": ["...", "..."]}]}
"""


def format_input(items: List[Dict[str, Any]], written: Optional[str]) -> str:
    lines = []

    for number, item in enumerate(items, start=1):
        previous = " → ".join(item.get("previous") or []) or "없음"
        lines.append(f"{number}. 질문: {item['question']} / 지난 답(오래된 순): {previous} / 이번 답: {item['answer']}")

    lines.append(f"아이가 쓴 글: {written.strip() if written and written.strip() else '없음'}")

    return "\n".join(lines)


def _clean_question(raw_question: Any, raw_options: Any) -> Optional[Dict[str, Any]]:
    from ai.modeling.abuse.question_rules import leading_reason, question_term_reason
    from ai.modeling.abuse.text_script import has_foreign_script

    if not isinstance(raw_question, str) or not isinstance(raw_options, list):
        return None

    text = raw_question.strip()

    if (
        not text
        or len(text) > MAX_QUESTION_CHARS
        or _MASK_TOKEN.search(text)
        or has_foreign_script(text)
        or question_term_reason(text)
        or leading_reason(text)
    ):
        return None

    options: List[str] = []

    for raw in raw_options:
        if not isinstance(raw, str):
            continue

        option = raw.strip()

        if (
            not option
            or len(option) > MAX_OPTION_CHARS
            or option in options
            or _MASK_TOKEN.search(option)
            or has_foreign_script(option)
            or question_term_reason(option)
        ):
            continue

        options.append(option)

    options = [option for option in options if option != HARD_TO_SAY][: MAX_OPTIONS - 1]

    if len(options) < 2:
        return None

    # 아이가 답하지 않을 길을 늘 둔다.
    return {"text": text, "options": [*options, HARD_TO_SAY]}


def clean_output(raw: Any, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """번호가 맞는 항목만 남긴다. 메모를 쓸 수 없는 항목은 질문까지 함께 버린다."""

    from ai.modeling.abuse.question_rules import judgment_reason
    from ai.modeling.abuse.text_script import has_foreign_script

    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        return []

    cleaned: Dict[int, Dict[str, Any]] = {}

    for entry in raw["items"]:
        if not isinstance(entry, dict):
            continue

        number = entry.get("no")

        if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= len(items) or number in cleaned:
            continue

        note = entry.get("note")

        if not isinstance(note, str):
            continue

        note = note.strip()

        if not note or len(note) > MAX_NOTE_CHARS or has_foreign_script(note) or judgment_reason(note):
            continue

        question = _clean_question(entry.get("question"), entry.get("options"))
        cleaned[number] = {
            "question_id": items[number - 1]["question_id"],
            "note": note,
            "questions": [question] if question else [],
        }

    return [cleaned[number] for number in sorted(cleaned)]


def generate_child_answer_drafts(
    items: List[Dict[str, Any]],
    written: Optional[str] = None,
    known_identifiers: Iterable[str] = (),
    deadline: Optional[float] = None,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """items: [{question_id, question, answer, previous: [오래된 순]}]. 가리기가 막히거나 LLM 이 실패하면 예외가 그대로 올라간다."""

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model
    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound
    from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

    if not items:
        return []

    masked, entity_map = mask_for_outbound(format_input(items, written), known_identifiers=list(known_identifiers))
    client, model_name = build_openai_client_and_model(model or DEFAULT_MODEL)
    parsed = _call_llm_with_retry(
        client=client,
        model=model_name,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"[입력]\n{masked}",
        max_retries=2,
        timeout_seconds=60.0,
        deadline=deadline,
    )
    cleaned = clean_output(parsed, items)

    # 메모만 되돌린다. 질문에는 토큰이 없다(_clean_question).
    for entry in cleaned:
        entry["note"] = restore_pii(entry["note"], entity_map)

    return cleaned


if __name__ == "__main__":
    sample = [{"question_id": "safe", "question": "지금 지내는 곳이 안전하다고 느끼나요?", "answer": "안전하지 않아요", "previous": ["안전해요"]}]
    print(json.dumps(generate_child_answer_drafts(sample), ensure_ascii=False, indent=2))
