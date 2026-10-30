"""
'추가 확인 · 질문' 화면 '추가 질문' 카드의 AI 초안을 만드는 LLM 모듈(2026-10-29,
I-SPOT_DOCS/docs/PROPOSAL_ai_suggestions_case_context.md §4 C-1).

[followup_check_llm 과 무엇이 다른가]

followup_check_llm 은 질문 문장을 만들지 않고 "무엇이 확인이 안 됐는지" 메모만 쓴다. 이 모듈은
아동에게 건넬 **열린 질문 초안**을 만든다. 아동 면담에서 유도 질문은 가장 큰 위험이라 세 겹으로 막는다.

1. 프롬프트 금지 — 예/아니오로 답하는 질문, 가해자 · 행위를 먼저 꺼내는 질문, 원문에 없는 사실 ·
   감정 가정, 한 번에 여러 질문.
2. 코드 검사(_clean_questions) — 아래 하나라도 걸리면 그 질문을 버린다.
   - 근거 segment_ids 가 없거나 실제 발화 목록에 없다.
   - 열린 질문 표지(무엇 · 어떻게 · 어디 · 언제 · 누구 · 어땠 · 이야기해 줄래 …)가 없다 —
     "~했어?" · "~니?" · "~지?" 처럼 닫힌 꼴만 있는 질문이 여기서 빠진다.
   - 물음표가 둘 이상(한 번에 여러 질문).
   - 인물(아빠 · 엄마 · 선생님 …) · 행위(때리 · 만지 · 굶 …) 낱말이 질문에 있는데 근거 발화에는 없다 —
     아이가 꺼내지 않은 사람 · 행위를 질문이 먼저 꺼내는 것.
3. 상담사 승인 — 초안은 분석 결과에만 남고, 상담사가 [승인] 해야 질문 목록(API_CONTRACT 18절)에 들어간다.

질문 은행(검증된 문항)이 생기면 RAG 로 섞을 수 있게 Contract 의 kind 에 "BANK" · bank_code 를
예약해 두었다(민규 #100 §7 답 5). 이 모듈은 늘 kind "OPEN" 만 만든다.

[입력 — 새로 분석하지 않는다]

followup_check_llm.format_inputs_for_masking 이 만든 글(마스킹 뒤)을 그대로 받는다. 같은 글을 한 번만
마스킹해 확인 메모와 이 모듈, 두 LLM 호출을 **병렬로** 부른다(infer_audio_session). 질문 쪽은 마감 전까지만
기다리고(wait_for_questions) 늦으면 [] 로 두어, 선택 필드 때문에 분석 전체가 마감을 넘기지 않게 한다.
- 첫 칸(아동 진술 요지 · 위험 신호 요지)만 질문 재료로 쓴다.
- 사례 정보 칸에서는 아동 나이대만 꺼내 말투 · 어휘 수준에 쓴다. 초기면접 항목 · 지난 회차 요약은
  넣지 않는다 — 질문이 이번 회차에서 아이가 하지 않은 말을 먼저 꺼내지 않게.

openai 는 CI 에 없다. 검사 함수를 backend/tests 에서 시험할 수 있게 LLM 호출 쪽 import 는 함수 안에 둔다.
"""

import re
import time
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ai.modeling.abuse.case_context import AGE_BANDS
from ai.modeling.abuse.text_script import has_foreign_script

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

DEFAULT_MODEL = "gpt-5.6-luna"

#: 질문 초안 최대 개수(PROPOSAL §4).
MAX_QUESTIONS = 5
#: Backend 저장 API 의 질문 길이 한도(followup_question 스키마)와 같다.
MAX_TEXT_CHARS = 300
#: followup_check_llm.SPLIT_MARKER 와 같은 값. 그 모듈을 import 하면 openai 를 불러와 여기 다시 적는다.
SPLIT_MARKER = "\n===I-SPOT-FOLLOWUP-SPLIT===\n"


SYSTEM_PROMPT = """너는 아동보호전문기관 상담사가 다음 상담에서 아동에게 건넬 **열린 질문 초안**을
만드는 도우미다. 초안은 상담사가 검토 · 수정 · 승인한 뒤에만 쓰인다.

[절대 원칙 — 유도 질문 금지]
1. 예/아니오로 답할 수 있는 질문을 만들지 않는다("~했어?", "~맞지?", "~였니?" 금지).
   "무엇 · 어떻게 · 어디 · 언제 · 누구 · 어땠어 · 이야기해 줄래" 처럼 아이가 자기 말로 답하는 질문만 만든다.
   "왜 ~했어?" 는 아이에게 탓을 묻는 것처럼 들리니 쓰지 않는다.
2. 아이가 이번 상담에서 직접 말하지 않은 사람이나 행위를 질문에서 먼저 꺼내지 않는다
   (예: 아이가 "아빠"를 말하지 않았는데 "아빠가 때렸어?" 금지).
3. 입력에 없는 사실 · 감정을 가정하지 않는다("무서웠지?" 금지).
4. 질문 하나에 물음 하나만. 물음표는 한 번만 쓴다.
5. 아이가 실제로 한 말을 이어받아 묻는다. 예: 아이가 "등이랑 팔이요"라고 했으면
   "등이랑 팔이 아팠던 건 지금은 어때?".
6. 아이의 나이대에 맞는 쉬운 반말로 짧게 쓴다(나이대: {age_band}).
7. 언급은 됐지만 그 뒤가 안 나온 것(치료 여부, 지금의 안전 등)을 우선으로 고른다.
   입력이 비어 있거나 물을 만한 것이 없으면 빈 리스트를 돌려준다. 최대 {max_questions}개.
8. 질문마다 근거가 된 입력 줄의 segment_id 를 정확히 인용한다. 줄 앞에 [seg_001] 처럼 적혀 있다.
   질문에 쓴 사람 · 행위 낱말이 나온 줄은 모두 인용한다. 인용할 줄이 없으면 그 질문은 만들지 않는다.
9. reason 에는 왜 이 질문이 필요한지 상담사에게 한 문장으로 적는다(예: "통증 이후 치료 여부가 안 나옴").

[입력 — 이번 상담에서 확인된 아동 진술 · 위험 신호 요지]
{session_content_input}

문장은 한국어로만 쓴다(다른 나라 글자를 섞지 않는다).
반드시 아래 JSON 형식으로만 답한다:
{{
  "questions": [
    {{"text": "...", "segment_ids": ["seg_001"], "reason": "..."}}
  ]
}}
"""


# ------------------------------------------------------------
# 코드 검사
# ------------------------------------------------------------

#: 열린 질문 표지. 하나도 없으면 닫힌 질문(예/아니오)으로 보고 버린다.
#: "왜" 는 넣지 않는다 — 아동 면담에서 "왜" 질문은 아이에게 탓을 묻는 것처럼 들려 피한다(프롬프트 1번).
_OPEN_MARKERS = (
    "무엇", "뭐", "뭘", "무슨", "어떻게", "어떤", "어때", "어땠", "어떨", "어디", "언제", "누구", "누가",
    "얼마나", "몇",
    # 이야기를 청하는 꼴. "선생님한테 이야기했어?" 같은 닫힌 질문이 지나가지 않게 '해 줄' 까지 본다.
    "이야기해 줄", "이야기 해 줄", "이야기를 해 줄", "이야기해줄", "얘기해 줄", "얘기 해 줄", "얘기를 해 줄",
    "얘기해줄", "말해 줄", "말해줄", "들려줄", "들려 줄", "설명해 줄",
)

#: 아이가 먼저 꺼내지 않았으면 질문에 쓰면 안 되는 인물 낱말. 근거 발화에도 있으면 괜찮다.
_PERSON_WORDS = (
    "아빠", "엄마", "아버지", "어머니", "새아빠", "새엄마", "계부", "계모", "할머니", "할아버지",
    "삼촌", "이모", "고모", "외삼촌", "오빠", "언니", "형", "누나", "동생", "선생님", "친구",
)

#: 같은 이유로 막는 행위 낱말. 활용꼴(때려요 · 때린다고)이 달라도 같은 행위로 보도록 줄기를 묶는다 —
#: 질문에 한 묶음의 줄기가 있으면 근거 발화에도 그 묶음의 줄기가 하나는 있어야 한다.
_ACT_FAMILIES = (
    ("때리", "때렸", "때려", "때린", "때릴"),
    ("맞았", "맞아", "맞은", "맞고", "맞을"),
    ("만지", "만졌", "만져", "만진", "만질"),
    ("굶",),
    ("욕",),
    ("꼬집",),
    ("던지", "던졌", "던져", "던진"),
    ("밀쳤", "밀쳐", "밀친", "밀었", "밀어"),
    ("가두", "가뒀", "가둬", "가둔"),
    ("벗기", "벗겼", "벗겨", "벗긴"),
    ("혼내", "혼냈", "혼난", "혼났"),
    ("발로", "찼", "차였"),
)

#: "형" 처럼 짧은 낱말은 다른 낱말 안에 끼어 있을 수 있다(형편 · 형태). 이것들은 앞뒤가 한글이 아닐 때 또는
#: 조사 · 복수 '들' 이 붙은 꼴만 인물로 본다.
_SHORT_PERSON_WORDS = {"형", "동생", "친구"}
_PARTICLES = "이가은는을를도랑과와한테에게께의야아"


def _mentions(text: str, word: str) -> bool:
    if word not in _SHORT_PERSON_WORDS:
        return word in text

    # 복수형 '들'(형들 · 동생들 · 친구들)도 인물로 본다(민규 #118 R3).
    pattern = rf"(?<![가-힣]){re.escape(word)}(?:들)?(?:[{_PARTICLES}]|(?![가-힣]))"
    return re.search(pattern, text) is not None


def _is_open_question(text: str) -> bool:
    return any(marker in text for marker in _OPEN_MARKERS)


def _introduces_new_word(question: str, evidence_text: str) -> bool:
    """질문에 있는 인물 · 행위 낱말이 근거 발화에 하나라도 없으면 True."""

    for word in _PERSON_WORDS:
        if _mentions(question, word) and not _mentions(evidence_text, word):
            return True

    for family in _ACT_FAMILIES:
        if any(stem in question for stem in family) and not any(stem in evidence_text for stem in family):
            return True

    return False


def _clean_questions(
    raw_questions: Any,
    segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """LLM 이 낸 질문을 모듈 docstring 의 코드 검사로 거른다. 걸린 질문만 빠지고 나머지는 남는다.

    segments: 원본(마스킹 전) 발화 목록. segment_id 확인과 근거 발화 글에 쓴다.
    질문 글은 마스킹된 채로 온다(이름이 [이름1] 같은 표지). 검사 낱말은 이름이 아니라 가족 · 행위 낱말이라
    마스킹과 상관없다.
    """

    if not isinstance(raw_questions, list):
        return []

    texts_by_id = {
        str(segment.get("segment_id", "")): str(segment.get("text") or "")
        for segment in segments
        if isinstance(segment, dict)
    }

    cleaned: List[Dict[str, Any]] = []
    seen_texts = set()

    for item in raw_questions:
        if len(cleaned) >= MAX_QUESTIONS:
            break

        if not isinstance(item, dict):
            continue

        text = item.get("text")

        if not isinstance(text, str):
            continue

        text = " ".join(text.split())

        if not text or len(text) > MAX_TEXT_CHARS or text in seen_texts:
            continue

        # 다른 나라 문자가 섞인 초안은 버린다(2026-10-30 데모 확인 메모 사례, text_script).
        if has_foreign_script(text):
            continue

        raw_segment_ids = item.get("segment_ids")

        if not isinstance(raw_segment_ids, list):
            continue

        segment_ids: List[str] = []

        for sid in raw_segment_ids:
            if isinstance(sid, str) and sid in texts_by_id and sid not in segment_ids:
                segment_ids.append(sid)

        if not segment_ids:
            continue

        if text.count("?") + text.count("？") > 1:
            continue

        if not _is_open_question(text):
            continue

        evidence_text = " ".join(texts_by_id[sid] for sid in segment_ids)

        if _introduces_new_word(text, evidence_text):
            continue

        reason = item.get("reason")
        reason = " ".join(reason.split())[:MAX_TEXT_CHARS] if isinstance(reason, str) else ""

        seen_texts.add(text)
        cleaned.append(
            {"text": text, "kind": "OPEN", "segment_ids": segment_ids, "reason": reason}
        )

    return cleaned


# ------------------------------------------------------------
# LLM 호출
# ------------------------------------------------------------


def child_age_band(case_context: Any) -> str:
    """사례 정보의 나이대(허용 5구간 중 하나). 없으면 "알 수 없음"."""

    band = case_context.get("child_age_band") if isinstance(case_context, dict) else None
    return band if band in AGE_BANDS else "알 수 없음"


def generate_followup_questions_from_masked_text(
    client: "OpenAI",
    model: str,
    masked_combined_text: str,
    segments: List[Dict[str, Any]],
    age_band: str = "알 수 없음",
    deadline: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """masked_combined_text: followup_check_llm.format_inputs_for_masking → mask_for_outbound 결과.
    첫 칸만 쓴다. segments: 원본 발화 목록(검사용). 실패하면 빈 목록 — 분석 전체를 멈추지 않는다.
    """

    session_content_input = masked_combined_text.split(SPLIT_MARKER)[0]

    if not session_content_input.strip() or session_content_input.strip() == "없음":
        return []

    system_prompt = SYSTEM_PROMPT.format(
        age_band=age_band if age_band in AGE_BANDS else "알 수 없음",
        max_questions=MAX_QUESTIONS,
        session_content_input=session_content_input,
    )

    # import 도 try 안 — 불러오기가 실패해도 [] 로 분석을 계속한다(민규 #118).
    try:
        from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt="위 입력을 바탕으로 열린 질문 초안을 만들어.",
            max_retries=2,
            timeout_seconds=180.0,
            deadline=deadline,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        return []

    try:
        return _clean_questions(parsed.get("questions"), segments)
    except Exception:
        return []


#: 마감 직전 이만큼은 남겨 두고 질문을 포기한다 — 뒤의 PII 복원 · 결과 조립이 마감을 넘기지 않게.
DEADLINE_MARGIN_SECONDS = 1.0


def wait_for_questions(future: "Future", deadline: Optional[float]) -> List[Dict[str, Any]]:
    """확인 메모와 동시에 띄운 질문 생성을 기다린다. 마감 전까지만 기다리고, 늦거나 실패하면 [] (민규 #118).

    질문 초안은 선택 필드라, 질문 LLM 이 느리다고 분석 전체가 마감을 넘겨 AI_TIMEOUT 이 되면 안 된다.
    늦은 호출은 뒤에서 끝나고 버려진다(_call_llm_with_retry 도 마감 + 5초 안에 스스로 멈춘다).
    """

    timeout = None if deadline is None else max(0.0, deadline - time.monotonic() - DEADLINE_MARGIN_SECONDS)

    try:
        result = future.result(timeout=timeout)
    except Exception:
        future.cancel()
        return []

    return result if isinstance(result, list) else []
