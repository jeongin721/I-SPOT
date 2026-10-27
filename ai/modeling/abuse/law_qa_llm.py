"""
법령·매뉴얼 AI 질의 — 현직자 인터뷰(2026-10-24, "I-SPOT 현직자 인터뷰
정리.pdf")에서 가장 구체적으로 요청받은 기능. 상담사가 자연어로 법령을
물어보면(아동복지법·아동학대범죄의 처벌 등에 관한 특례법), AI가 조문을
인용하며 답한다.

[law/ 쪽 기존 모듈과 이 모듈의 역할 차이]

law/mapper.py의 rank_law_articles는 "상담 회차의 학대유형 + 발화"에 맞춰
법조문을 자동으로 골라 인용하는 용도다(legal_reference_adapter.py 같은
기존 파이프라인이 씀) — 특정 상담 회차의 분석 결과에 붙는 보조 정보다.

이 모듈은 다른 용도다. 상담사가 직접 자유 질문을 타이핑하면 답하는 독립
Q&A고, 특정 상담 회차·학대유형이랑 묶여 있지 않다. "회의록 녹음 요약"처럼
이 PDF가 요청한 다른 기능들과 마찬가지로 상담 분석 파이프라인 바깥에서
단독으로 쓰인다.

[왜 벡터 검색(RAG) 없이 하나]

law_cache의 두 대상 법령 전체 조문 텍스트를 합쳐도 약 9.8만 자(아동복지법
123개 조문 + 아동학대범죄의 처벌 등에 관한 특례법 78개 조문, 2026-10-26
실측)라, LLM 컨텍스트 창에 전체를 그대로 넣어도 충분히 들어간다. 벡터
임베딩·청크·유사도 검색 파이프라인을 새로 만들 필요가 없다 — jeongin의
feature/rag(판례 유사사례 검색, 아직 main에 안 들어왔고 계속 바뀌는 중)와는
완전히 별개로 간다. 법령이 더 늘어나 컨텍스트가 부족해지면 그때 청크+검색
방식으로 바꾸면 된다.

[개인정보]

질문 텍스트는 법령 내용이 아니라 상담사가 직접 입력하는 것이라, 실제 사례
맥락(아동 이름 등)이 섞여 들어올 수 있다. 다른 모든 외부 LLM 호출과 똑같이
mask_for_outbound를 거쳐서 보낸다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry
from law import LawApiClient, extract_articles
from law.config import LAW_TARGET_LAWS
from law.portal import attach_portal_urls

DEFAULT_MODEL = "gpt-5.6-luna"


SYSTEM_PROMPT_TEMPLATE = """너는 아동보호전문기관 상담사의 법령 질문에 답하는 도우미다.

[절대 원칙]
1. 아래 [법령 전문]에 실제로 있는 조문 내용만 근거로 답한다. 법령에 없는
   내용을 추측하거나 지어내지 않는다.
2. 답할 때 반드시 관련 조문 번호를 "제17조"처럼 본문에 그대로 적어 밝힌다.
   "같은 법 제17조"처럼 줄여 쓰지 말고, 법령이 둘 이상이면 매번 법령명을
   같이 적는다 — 두 법령에 번호가 같은 조문(예: 두 법 모두 "제10조")이
   있을 수 있어 헷갈리면 안 된다.
3. 질문이 법률 자문(판단·전망)을 요구하면, 조문 내용을 그대로 알려주되
   "실제 적용은 기관 내부 절차·법률 자문을 따라야 한다"는 점을 짧게
   덧붙인다 — 판정을 대신 내리지 않는다.
4. 법령에서 답을 찾을 수 없으면 "제공된 법령({law_names}) 안에서는
   확인되지 않습니다"라고 명확히 말한다 — 모르는 걸 아는 척하지 않는다.
5. 2~5문장으로 간결하게 답한다.
6. cited_articles에는 답변에서 실제로 근거로 쓴 조문만 (법령명, 조문번호)
   쌍으로 적는다. 조문번호는 "제10조"처럼 적고, 법령명은 [법령 전문]의
   "===" 구분선에 있는 이름 그대로 적는다.

[법령 전문]
{law_corpus}

반드시 아래 JSON 형식으로만 답한다:
{{"answer": "...", "cited_articles": [{{"law_name": "...", "article": "제10조"}}]}}
"""


def _build_law_corpus(
    law_names: Optional[List[str]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """law_cache에서 대상 법령 전체 조문을 모아 LLM 컨텍스트용 텍스트로 만든다.

    반환값: (컨텍스트 텍스트, 조문 메타데이터 목록 — 답변에 실제로 인용된
    조문을 찾아 포털 링크를 붙이는 데 쓴다).
    """

    names = law_names or list(LAW_TARGET_LAWS)
    client = LawApiClient()

    blocks: List[str] = []
    all_articles: List[Dict[str, Any]] = []

    for law_name in names:
        cached = client.get_law_by_name(law_name)
        articles = extract_articles(
            cached.get("body", {}), fallback_law_name=law_name
        )
        articles = attach_portal_urls(articles, cached.get("search_item", {}))
        all_articles.extend(articles)

        lines = [f"=== {law_name} ==="]
        for article in articles:
            title = f" {article['title']}" if article.get("title") else ""
            lines.append(f"{article['article']}{title}\n{article['content']}")
        blocks.append("\n\n".join(lines))

    return "\n\n".join(blocks), all_articles


def _verify_cited_articles(
    claimed: Any, articles: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """LLM이 JSON으로 주장한 (법령명, 조문번호) 인용을 실제 조문 목록과 대조한다.

    두 법령에 같은 조문 번호가 둘 다 있을 수 있어(예: 둘 다 "제10조"),
    조문 번호만으로는 어느 법인지 구분이 안 된다 — 법령명까지 같이
    맞아야 통과시킨다. 존재하지 않는 조문을 지어내 인용했으면(법령명이
    틀렸거나 조문 번호 자체가 없으면) 조용히 빠진다 — LLM 주장을
    그대로 믿지 않고 여기서 검증한다.
    """

    by_key = {
        (article.get("law_name", ""), article.get("article", "")): article
        for article in articles
    }

    if not isinstance(claimed, list):
        return []

    verified = []
    seen = set()

    for item in claimed:
        if not isinstance(item, dict):
            continue

        key = (str(item.get("law_name", "")).strip(), str(item.get("article", "")).strip())

        if key in by_key and key not in seen:
            verified.append(by_key[key])
            seen.add(key)

    return verified


class LawQAOutputError(ValueError):
    """LLM 응답에 답변(answer)이 없다. 문구는 고정이다(질문 원문 · 인증값을 싣지 않는다).

    2026-10-27 §6-1(PROPOSAL_law_guide_api.md): 예전에는 실패를 answer 에 "질의에
    실패했습니다" 로 넣어 성공처럼 돌려줘서 Backend 가 실패를 구분할 수 없었다. 이제 실패는
    예외로 올라간다 — LLM 호출 실패는 _call_llm_with_retry 의 예외 그대로(마감을 넘기면
    TimeoutError), 법령 데이터 실패는 LawApiError, 빈 답변은 이 예외. Backend 는
    map_ai_error 처럼 예외 종류로 오류 코드를 정하고 문구는 화면에 내지 않는다.
    """


class LawQALLMError(RuntimeError):
    """LLM 호출이 실패했다. 문구는 고정이고 원인 예외의 종류 이름만 싣는다.

    2026-10-27 민규 교차검증: _call_llm_with_retry 는 실패를 RuntimeError("2차 LLM 호출 실패:
    {SDK 원문}")로 감싸 올리는데, 그 원문에 OpenAI SDK 메시지(요청 URL 등)가 실린다. 예전에는
    answer_* 가 잡아 종류 이름만 남겼지만 §6-1 로 실패를 예외로 올리면서 원문이 str(error) ·
    traceback · 부르는 쪽 로그로 나가게 됐다. second_stage_llm 은 분석 파이프라인이 같이 써서
    건드리지 않고 여기(_call_llm_safely)에서 고정 문구로 바꾸고 체인을 끊는다(from None).
    """


EMPTY_ANSWER_MESSAGE = "법령 질의 답변을 만들지 못했습니다."
LLM_TIMEOUT_MESSAGE = "법령 질의가 제한 시간 안에 끝나지 않았습니다."


def _call_llm_safely(call: Any, **kwargs: Any) -> Any:
    """call(_call_llm_with_retry)을 부르고, 실패는 문구가 고정된 예외로 바꿔 던진다.

    - TimeoutError(마감 초과)는 종류를 그대로 두고 문구만 고정한다 — 제안서 §3 표에서 AI_TIMEOUT.
      _call_llm_with_retry 의 TimeoutError 문구에도 SDK 원문이 실린다.
    - 그 밖은 LawQALLMError("…(종류 이름)"). _call_llm_with_retry 가 감싸 올리면 종류는 RuntimeError 다.
    두 경우 모두 from None 으로 원인 예외(SDK 원문)를 체인에 남기지 않는다.
    call 을 인자로 받는 것은 두 모듈이 각자 가져온 _call_llm_with_retry 를 쓰게 하려는 것이다(시험의 바꿔치기).
    """

    try:
        return call(**kwargs)
    except TimeoutError:
        raise TimeoutError(LLM_TIMEOUT_MESSAGE) from None
    except Exception as error:  # noqa: BLE001 — 종류 이름만 남기고 고정 문구로 바꾼다
        raise LawQALLMError(f"법령 질의 LLM 호출 실패({type(error).__name__})") from None

#: 모든 답변 끝에 코드가 붙이는 고정 안내. LLM 프롬프트 준수에 기대지 않는다
#: (2026-10-26 매뉴얼 질의에 먼저 넣었고, 2026-10-27 민규 교차검증 R3 으로 법령 전용 답변에도).
REFERENCE_NOTICE = (
    "※ 이 답변은 참고용입니다. 실제 적용 전 원본 자료를 "
    "직접 확인하고, 최종 판단은 상담사가 내려야 합니다."
)


def with_reference_notice(answer_text: str) -> str:
    return f"{answer_text}\n\n{REFERENCE_NOTICE}"


def answer_law_question(
    client: OpenAI,
    model: str,
    question: str,
    *,
    law_names: Optional[List[str]] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """법령 질문에 조문 근거를 달아 답한다.

    반환: {"answer": str, "law_names": [...], "cited_articles": [...]}. answer 는 늘 비어 있지 않다.
    실패하면 예외를 던진다 — TimeoutError · LawQALLMError · LawQAOutputError · LawApiError
    (_call_llm_safely · LawQAOutputError 참고). 실패를 answer 에 넣어 돌려주지 않는다.
    """

    # 2026-10-26 민규 리뷰: restore_pii(pii_masking.py)와
    # mask_for_outbound(privacy_gateway.py, 이쪽도 내부에서 pii_masking을
    # 가져옴)가 모듈 맨 위에 있으면 그걸 가져오는 순간 torch·transformers
    # 까지 딸려 들어와서, torch 없는 환경(Backend 가상환경)에서는 이
    # 파일을 가져오기만 해도 실패한다 — 순수 함수 테스트
    # (tests/test_law_qa_llm.py)까지 같이 막힌다. 실제로 쓰는 시점(여기)
    # 에만 가져오도록 늦춘다.
    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound

    names = law_names or list(LAW_TARGET_LAWS)

    masked_question, entity_map = mask_for_outbound(question)

    law_corpus, articles = _build_law_corpus(names)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        law_names="·".join(names),
        law_corpus=law_corpus,
    )

    # 실패는 예외로 올린다(LawQAOutputError docstring, §6-1). 예외 문구에는 OpenAI 인증 실패 메시지 ·
    # 요청 URL 같은 민감한 내용이 섞일 수 있어(2026-10-26 민규 교차검증) 부르는 쪽이 문구를 화면에 내지 않는다.
    parsed = _call_llm_safely(
        _call_llm_with_retry,
        client=client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=masked_question,
        max_retries=2,
        timeout_seconds=180.0,
        deadline=deadline,
    )

    answer_text = (
        str(parsed.get("answer") or "").strip() if isinstance(parsed, dict) else ""
    )

    if not answer_text:
        raise LawQAOutputError(EMPTY_ANSWER_MESSAGE)

    answer_text = with_reference_notice(restore_pii(answer_text, entity_map))

    return {
        "answer": answer_text,
        "law_names": names,
        "cited_articles": _verify_cited_articles(
            parsed.get("cited_articles"), articles
        ),
    }


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    import json

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model

    client, model = build_openai_client_and_model(DEFAULT_MODEL)
    result = answer_law_question(
        client=client,
        model=model,
        question="아동학대 신고의무자가 신고하지 않으면 어떻게 되나요?",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
