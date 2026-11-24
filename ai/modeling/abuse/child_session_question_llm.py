"""
아이 앱(콩콩)으로 보낼 '이번 회차 맞춤 질문' 초안을 만드는 LLM 모듈(2026-11-24).

고정 8문항만 있어 한 아이의 1~3회차 질문이 늘 같았다(현장 문제 제기). 가장 최근 분석 회차의 '확인할 사항' ·
상담원용 추가 질문 · 요약과 초기면접지의 단어 칸(나이대 · 아동 특성 · 가정 상황)을 보고, 아이에게 앱으로 물어볼 질문 3~5개를 쓴다.
privacy_gateway 로 가린 뒤 보내고, 상담사에게만 보이는 이유(reason)는 restore_pii 로 되돌린다.

아이 폰은 다른 가족이 볼 수 있다. 그래서 질문은 회차에서 나온 사건 · 사람을 드러내지 않고, 아이의 생활 · 마음 · 안전을
일반적인 말로 묻는다. 나가는 질문은 네 겹으로 막는다.
 1. 판단 · 법률 용어(question_term_reason) · 답을 정해 둔 꼬리 질문(leading_reason)이 있으면 버린다.
 2. 가족 · 친척 · 어른을 가리키는 말(아빠 · 엄마 · 형 · 가족 · 어른 · 사촌 …)이 있으면 버린다(누가 무엇을 했는지 폰에 남지 않게).
 3. 가린 이름 토큰 · 그 사례의 등록 이름(known_identifiers, 가족 이름 포함)이 있거나 한국어가 아닌 글자가 있으면 버린다.
 4. 이미 보낸 질문 · 고정 문항과 글이 같으면 버린다.
 5. 자해 · 자살 · 죽음을 묻는 질문은 버린다(11/24 데모 실측 · 민규 #195 리뷰). 아이가 밤에 앱으로 "지금도 있어요" 를 골라도
    그 자리에서 대응할 사람이 없다 — 이 주제는 상담에서 직접 묻는다.
 6. 사건 단서가 되는 몇 낱말(술 · 허리띠 · 때리 · 맞은 · 만지 …)이 있으면 버린다. 낱말로 다 막을 수는 없어 화면에
    "아이 폰은 가족이 볼 수 있어요" 안내를 두고 상담사가 고른다.
살펴볼 답은 AI 가 정하지 않는다 — 맞춤 질문은 건너뛰지 않은 답이면 모두 살펴볼 답(AMBER)이다(Backend, 민규 #195 리뷰).
'말하기 어려워요' 같은 보기도 넣지 않는다 — 아이 앱에 '답하기 어려워요'(건너뛰기)가 있다.
초안은 상담사가 골라야 앱으로 간다(Backend child_session_question_service).
"""

import json
import re
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_MODEL = "gpt-5.6-luna"

MAX_QUESTIONS = 5
MAX_QUESTION_CHARS = 80
MAX_OPTION_CHARS = 20
MAX_OPTIONS = 4
MAX_REASON_CHARS = 200
# 아이 앱의 건너뛰기와 겹치는 보기. 보기에서 뺀다.
SKIP_LIKE = {"말하기 어려워요", "답하기 어려워요", "말하고 싶지 않아요"}
CATEGORIES = ("생활", "집", "안전", "학교", "마음")
TYPES = ("choice", "text")
_MASK_TOKEN = re.compile(r"\[[A-Z]+_\d+\]")
# 폰에 남으면 누가 무엇을 했는지 드러날 수 있는 말. '상담 선생님' 은 앱이 늘 쓰는 말이라 뺀다.
_PEOPLE = re.compile(
    r"아빠|아버지|아버님|엄마|어머니|어머님|부모|할머니|할아버지|할매|할배|외할|친할|삼촌|이모|고모|숙모|외숙|오빠|언니|누나|동생|"
    # 형 · 큰형 · 우리형 · 의붓형(인형 · 형태 · 형편은 남긴다)
    r"(?:(?<![가-힣])|(?<=우리)|(?<=저희)|(?<=의붓)|(?<=친)|(?<=내))(?:큰|작은|둘째|첫째|막내)?형(?![태식편광성])|"
    r"의붓|사촌|아저씨|아줌마|계부|계모|새아빠|새엄마|양부|양모|보호자|가족|식구|친척|어른|이웃|"
    r"(?<!상담 )선생님|쌤|담임|원장|관장|코치"  # '상담 선생님' 은 앱이 늘 쓰는 말
)
# 앱으로 묻지 않는 주제. 상담에서 직접 묻는다(민규 #195 리뷰에서 지어낸 17문장이 모두 걸리게 더함).
_SELF_HARM = re.compile(
    r"자해|자살|죽|다치게 하|해치|목숨|극단|사라지|사라져|사라졌|없어지|없어졌|없었으면|살고 싶지|살기 싫|그만 살|"
    r"상처를 내|상처를 낸|(?:나|스스로|자신|자기|몸|내 몸)(?:를|을)? ?아프게|아프게\s*(?:하|했|한|할|만들|만든)|끝내고 싶|긋|뛰어내|태어나지|약을 한꺼번에|약을 많이"
)
# 회차의 사건이 드러나는 낱말 몇 개. 낱말로 다 막을 수는 없다(화면 안내로 상담사가 본다).
# '미술 · 술래' · '맞은편' 같은 평범한 말은 남긴다(민규 #195 머지 뒤 리뷰 3).
_INCIDENT = re.compile(
    r"(?<![가-힣])술(?!래)|허리띠|때리|때린|때렸|맞은(?!편)|맞았|맞을|만지|만져|만졌|매를|벗겨|벗으|"
    r"꼬집|발로 차|발로 찬|발로 찼|걷어차|밀쳤|밀친|밀쳐|던졌|던진"
)

SYSTEM_PROMPT = """너는 아동보호전문기관 상담사를 돕는 보조 도구다. 상담사가 다음 상담 전에 아이 앱으로 먼저 물어볼 질문 초안을 쓴다.
상담사가 고르고 고친 뒤에만 아이에게 간다. 최종 판단은 상담사가 한다.

[입력]
- 아이 정보: 나이대 · 성별 · 초기면접에서 고른 아동 특성 · 가정 상황(단어)
- 이번 회차: 다음 상담 전 확인할 사항, 상담원이 다음 상담에서 물어볼 질문, 회차 요약
- 이미 보낸 질문: 고정 문항과 지난번에 보낸 질문(겹치지 않게)

[쓸 것] 질문 3~5개. 질문마다
- category: 생활 · 집 · 안전 · 학교 · 마음 중 하나
- type: "choice"(보기에서 고름) 또는 "text"(짧게 씀). text 는 많아야 1개.
- text: 아이에게 할 질문 한 문장
- options: choice 일 때 보기 2~4개(text 면 빈 목록)
- reason: 상담사에게만 보이는 한 문장. 이번 회차의 어떤 확인 사항 · 내용과 이어지는지.

[절대 원칙]
1. 아이 폰은 다른 가족이 볼 수 있다. 질문 · 보기에 회차에서 나온 구체적인 사건 · 장소 · 사람을 쓰지 않는다.
   아빠 · 엄마 · 할머니 · 형 · 가족 · 어른 · 선생님처럼 사람을 가리키는 말을 쓰지 않는다. 술 · 때림 같은 사건 낱말도 쓰지 않는다. 대신 그 주제를 아이의 생활 · 기분 · 잠 · 식사 ·
   학교 · 안전감 · 도움받을 곳 같은 일반적인 말로 묻는다. (예: 집에서 큰 소리가 났던 일 → "요즘 집에 있을 때 마음이 편한가요?")
2. 입력에 없는 사실을 지어내지 않는다. 원인을 추측하지 않는다.
3. 학대 여부 · 위험을 확정하거나 단정하지 않는다. 누구를 행위자 · 피해자로 못박지 않는다.
4. 아이에게 직접 말하듯, 나이대에 맞는 쉬운 존댓말로, 한 번에 하나만 묻는다.
5. '학대 · 처벌 · 신고 · 범죄 · 가해 · 피해자 · 폭행 · 위반 · 고소 · 법적 · 법률' 같은 말을 쓰지 않는다.
6. 답을 정해 두고 확인받는 질문("~했지?", "~않았어요?")을 쓰지 않는다.
7. 사람 이름이나 [PERSON_01] 같은 표시를 넣지 않는다.
8. 보기는 치우치지 않게 쓴다. '말하기 어려워요' 같은 건너뛰기 보기는 넣지 않는다(앱에 건너뛰기가 따로 있다).
9. 이미 보낸 질문과 같은 질문을 다시 쓰지 않는다.
10. 문장은 한국어로만 쓴다.
11. 자해 · 자살 · 죽음 · 스스로를 다치게 하는 생각은 앱으로 묻지 않는다. 아이가 혼자 있을 때 답하면 바로 도울 사람이 없다.
    확인할 사항에 이런 내용이 있으면 그 항목은 건너뛴다(상담사가 상담에서 직접 묻는다).

반드시 아래 JSON 형식으로만 답한다.
{"questions": [{"category": "마음", "type": "choice", "text": "...", "options": ["...", "..."], "reason": "..."}]}
"""


def _bullets(values: Any) -> List[str]:
    lines = [f"- {text}" for text in values or []]

    return lines or ["- 없음"]


def format_input(context: Dict[str, Any]) -> str:
    """context: {child: {age_band, gender, traits, family}, checks: [..], counselor_questions: [..], summary, sent: [..]}"""

    child = context.get("child") or {}
    lines = [
        "[아이 정보]",
        f"나이대: {child.get('age_band') or '모름'} / 성별: {child.get('gender') or '모름'}",
        f"아동 특성: {', '.join(child.get('traits') or []) or '없음'}",
        f"가정 상황: {', '.join(child.get('family') or []) or '없음'}",
        f"[이번 회차: {context.get('session_label') or '최근 회차'}]",
        "확인할 사항:",
        *_bullets(context.get("checks")),
        "상담원이 다음 상담에서 물어볼 질문:",
        *_bullets(context.get("counselor_questions")),
        f"회차 요약: {context.get('summary') or '없음'}",
        "[이미 보낸 질문]",
        *_bullets(context.get("sent")),
    ]

    return "\n".join(lines)


# 상담사가 고친 문장에 쓰는 좁은 목록(민규 #198 리뷰). 위 _SELF_HARM 은 AI 초안을 넉넉히 버리려고 '죽 · 긋 · 없어지' 처럼
# 넓어서, 고치기에 쓰면 '아침에 죽을 먹었나요?' · '선을 긋는 걸 좋아하나요?' · '입맛이 없어졌나요?' 같은 평범한 문장도 막는다.
# 여기에는 뜻이 분명한 말만 둔다.
_SELF_HARM_STRICT = re.compile(
    r"자해|자살|극단적|목숨|죽음|죽고\s*싶|죽었으면|죽어\s*버리|죽는\s*게\s*나|죽을까|"
    r"사라지고\s*싶|사라져\s*버리|사라졌으면|없어지고\s*싶|없어졌으면|없었으면\s*좋|태어나지\s*말|"
    r"살기\s*싫|살고\s*싶지|그만\s*살|삶을\s*끝|모든\s*걸\s*끝내|다\s*끝내고\s*싶|"
    r"상처를\s*(?:내|낸|냈)|손목|뛰어내리|약을\s*한꺼번에|약을\s*많이\s*먹|"
    r"(?:나|스스로|자신|자기|몸|내\s*몸)(?:를|을)?\s*(?:일부러\s*)?(?:다치게|아프게)\s*(?:하|했|한|할|만들|만든)"
)


def has_self_harm(text: str) -> bool:
    """상담사가 아이 앱 질문을 고칠 때 막을 자해 · 자살 · 죽음 말이 있는지(경진 11/24, 좁은 목록 — 민규 #198 리뷰).
    Backend child_session_question_service.ensure_no_self_harm 이 쓴다."""

    return bool(_SELF_HARM_STRICT.search(text))


def _bad_text(text: str, names: Iterable[str] = ()) -> bool:
    from ai.modeling.abuse.question_rules import question_term_reason
    from ai.modeling.abuse.text_script import has_foreign_script

    return bool(
        _MASK_TOKEN.search(text)
        or has_foreign_script(text)
        or question_term_reason(text)
        or _PEOPLE.search(text)
        or _SELF_HARM.search(text)
        or _INCIDENT.search(text)
        or any(name in text for name in names)
    )


def _norm(text: str) -> str:
    return re.sub(r"[\s?.!·]", "", text)


def clean_output(raw: Any, sent: Iterable[str] = (), names: Iterable[str] = ()) -> List[Dict[str, Any]]:
    """규칙에 맞는 질문만 남긴다. reason 을 쓸 수 없는 질문도 버린다(상담사가 왜 나왔는지 알아야 고른다).

    names: 그 사례의 등록 이름(두 글자 이상만 쓴다). 질문 · 보기에 들어 있으면 버린다.
    """

    from ai.modeling.abuse.question_rules import judgment_reason, leading_reason
    from ai.modeling.abuse.text_script import has_foreign_script

    if not isinstance(raw, dict) or not isinstance(raw.get("questions"), list):
        return []

    names = [name.strip() for name in names if name and len(name.strip()) >= 2]
    seen = {_norm(text) for text in sent}
    cleaned: List[Dict[str, Any]] = []
    has_text = False

    for entry in raw["questions"]:
        if len(cleaned) >= MAX_QUESTIONS:
            break

        if not isinstance(entry, dict):
            continue

        category, kind, text, reason = entry.get("category"), entry.get("type"), entry.get("text"), entry.get("reason")

        if category not in CATEGORIES or kind not in TYPES or not isinstance(text, str) or not isinstance(reason, str):
            continue

        text, reason = text.strip(), reason.strip()

        if (
            not text
            or len(text) > MAX_QUESTION_CHARS
            or _bad_text(text, names)
            or leading_reason(text)
            or _norm(text) in seen
            or not reason
            or len(reason) > MAX_REASON_CHARS
            or has_foreign_script(reason)
            or judgment_reason(reason)
        ):
            continue

        options: List[str] = []

        if kind == "choice":
            raw_options = entry.get("options")

            for option in raw_options if isinstance(raw_options, list) else []:
                if not isinstance(option, str):
                    continue

                option = option.strip()

                if (
                    not option
                    or len(option) > MAX_OPTION_CHARS
                    or option in options
                    or option in SKIP_LIKE
                    or _bad_text(option, names)
                ):
                    continue

                options.append(option)

            options = options[:MAX_OPTIONS]

            if len(options) < 2:
                continue
        elif has_text:
            continue
        else:
            has_text = True

        seen.add(_norm(text))
        cleaned.append({"category": category, "type": kind, "text": text, "options": options, "reason": reason})

    return cleaned


def generate_child_session_questions(
    context: Dict[str, Any],
    known_identifiers: Iterable[str] = (),
    deadline: Optional[float] = None,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """가리기가 막히거나 LLM 이 실패하면 예외가 그대로 올라간다."""

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model
    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound
    from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

    masked, entity_map = mask_for_outbound(format_input(context), known_identifiers=list(known_identifiers))

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
    names = list(known_identifiers)
    cleaned = clean_output(parsed, context.get("sent") or [], names)

    # 이유만 되돌린다. 질문 · 보기에는 토큰이 없다(_bad_text).
    for entry in cleaned:
        entry["reason"] = restore_pii(entry["reason"], entity_map)

    return cleaned


if __name__ == "__main__":
    sample = {
        "child": {"age_band": "만 10~13세", "gender": "F", "traits": [], "family": ["한부모"]},
        "session_label": "2회차",
        "checks": ["밤에 큰 소리가 나면 잠을 못 잔다고 함 — 수면 상태 확인"],
        "counselor_questions": ["요즘 잠은 몇 시쯤 자나요?"],
        "summary": "",
        "sent": [],
    }
    print(json.dumps(generate_child_session_questions(sample), ensure_ascii=False, indent=2))
