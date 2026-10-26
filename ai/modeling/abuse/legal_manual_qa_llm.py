"""법령·매뉴얼 AI 질의 — law_qa_llm.py(법령 전용)에 "2026년 아동학대
대응 업무 매뉴얼" 6장(서식·참고자료) 내용을 결합한 버전.

현직자 인터뷰(2026-10-24, "I-SPOT 현직자 인터뷰 정리.pdf" §6-2
"법령·매뉴얼 AI 질의")가 법령과 매뉴얼을 한 번에 물어보고 싶다고 요청한
것을 그대로 따른다.

[왜 매뉴얼은 텍스트가 아니라 이미지로 넣나]

매뉴얼 원본은 PDF가 아니라 실물 책자를 촬영한 사진(2026-10-26,
`사례관리_업무/`)이라 텍스트 레이어가 없다. 손으로 옮겨 적으면 위험사정
척도 같은 숫자·문항이 하나라도 틀렸을 때 상담 판단에 영향을 줄 수 있어,
OCR·수동 전사 대신 이미지를 그대로 멀티모달 LLM에 보여주는 방식을
택했다(2026-10-26 판단). `_call_llm_with_retry`의 user_prompt는 문자열뿐
아니라 OpenAI 메시지 content 배열([{"type": "text", ...},
{"type": "image_url", ...}])도 그대로 받아들여서, 이 모듈 쪽만 고치면
되고 second_stage_llm.py는 손대지 않는다.

[법령 인용과 매뉴얼 인용의 신뢰도 차이]

법령 인용(cited_articles)은 law_qa_llm._verify_cited_articles로 실제
조문 목록과 대조해 검증한다. 매뉴얼 인용(manual_references)은 원본이
텍스트가 아니라 이미지라 그런 자동 대조가 불가능하다 — LLM이 실제로
이번 호출에 첨부받은 페이지 목록에 있는 것만 답하도록 검증하지만
("이 페이지에 실제로 이 내용이 있다"는 보장이 아니라 "존재하는 페이지를
가리키긴 했다"는 보장만 됨), 문장 단위 사실 검증은 못 한다는 한계가
있다. 상담사가 참고용으로만 쓰고 최종 판단은 원본을 봐야 한다는 점을
답변에도 명시한다(SYSTEM_PROMPT_TEMPLATE 참고).

[1차 범위: 6장(서식·참고자료)만]

5장(신변안전매뉴얼, 상담원 본인 안전)은 아직 포함하지 않는다 —
I-SPOT_DOCS/docs/LAW_MANUAL_QA.md 참고. manual/manifest.py에 ManualPage를
추가하면 같은 구조로 확장된다.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from ai.modeling.abuse.law_qa_llm import _build_law_corpus, _verify_cited_articles
from ai.modeling.abuse.pii_masking import restore_pii
from ai.modeling.abuse.privacy_gateway import mask_for_outbound
from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry
from law.config import LAW_TARGET_LAWS
from manual.config import MANUAL_IMAGE_DIR
from manual.manifest import ManualPage, CHAPTER6_PAGES

DEFAULT_MODEL = "gpt-5.6-luna"

# 질문 하나당 첨부할 매뉴얼 이미지 수 상한 — 이미지가 많아질수록 토큰
# 비용과 지연이 커지고, LLM이 여러 장 중 엉뚱한 장을 근거로 댈 위험도
# 늘어난다. 6장 10장 중 보통 1~2장이면 충분하다고 보고 넉넉히 3으로 둠.
MAX_MANUAL_IMAGES = 3


SYSTEM_PROMPT_TEMPLATE = """너는 아동보호전문기관 상담사의 법령·매뉴얼 질문에 답하는 도우미다.

[절대 원칙]
1. 아래 [법령 전문]과 (있다면) 첨부된 매뉴얼 이미지에 실제로 있는
   내용만 근거로 답한다. 없는 내용을 추측하거나 지어내지 않는다.
2. 법령을 근거로 답할 때는 반드시 "제17조"처럼 조문 번호를 본문에 그대로
   적고, 법령이 둘 이상이면 매번 법령명을 같이 적는다 — 두 법령에 번호가
   같은 조문이 있을 수 있어 헷갈리면 안 된다.
3. 매뉴얼 이미지를 근거로 답할 때는 [첨부된 매뉴얼 자료] 목록에 적힌
   제목 그대로("서식4 초기면접지(아동용)" 등) 어느 자료를 봤는지 밝힌다.
   목록에 없는 매뉴얼 내용을 지어내지 않는다.
4. 질문이 법률 자문(판단·전망)을 요구하면, 내용을 그대로 알려주되
   "실제 적용은 기관 내부 절차·법률 자문을 따라야 한다"는 점을 짧게
   덧붙인다 — 판정을 대신 내리지 않는다.
5. 서식·척도 내용은 사진으로 옮긴 참고 자료라 글자가 흐릿하거나 일부
   가려졌을 수 있다. 확신이 서지 않는 부분은 "원본을 직접 확인하라"고
   안내한다.
6. 법령·매뉴얼 어느 쪽에서도 답을 찾을 수 없으면 "제공된 자료 안에서는
   확인되지 않습니다"라고 명확히 말한다 — 모르는 걸 아는 척하지 않는다.
7. 2~5문장으로 간결하게 답한다.
8. cited_articles에는 답변에서 실제로 근거로 쓴 법조문만 (법령명,
   조문번호) 쌍으로 적는다. manual_references에는 실제로 근거로 쓴
   매뉴얼 자료 제목만 [첨부된 매뉴얼 자료] 목록에 있는 그대로 적는다.
   둘 다 안 썼으면 빈 배열로 둔다.

[법령 전문]
{law_corpus}

{manual_section}
반드시 아래 JSON 형식으로만 답한다:
{{"answer": "...", "cited_articles": [{{"law_name": "...", "article": "제10조"}}], "manual_references": ["서식4 초기면접지(아동용) 1/2 — ..."]}}
"""


def _select_manual_pages(
    question: str,
    pages: Tuple[ManualPage, ...] = CHAPTER6_PAGES,
    limit: int = MAX_MANUAL_IMAGES,
) -> List[ManualPage]:
    """질문 문자열에 포함된 키워드로 관련 매뉴얼 페이지를 고른다.

    law/mapper.py의 키워드 매칭과 같은 수준의 단순 방식이다 — 10장
    전부를 매번 보낼 필요 없이, 겹치는 키워드가 많은 순으로 상위
    `limit`개만 고른다. 매칭이 하나도 없으면 빈 리스트(이번 질문엔
    매뉴얼을 첨부하지 않는다 — 법령만으로 답함).
    """

    scored: List[Tuple[int, ManualPage]] = []

    for page in pages:
        score = sum(1 for keyword in page.keywords if keyword in question)
        if score > 0:
            scored.append((score, page))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [page for _, page in scored[:limit]]


def _encode_image_b64(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _build_manual_section(pages: List[ManualPage]) -> str:
    if not pages:
        return "[첨부된 매뉴얼 자료]\n(이번 질문엔 첨부된 매뉴얼 자료가 없음 — 법령 전문만 근거로 답할 것)\n"

    lines = ["[첨부된 매뉴얼 자료]"]
    for index, page in enumerate(pages, start=1):
        lines.append(f"{index}. {page.title} (p.{page.page})")
    lines.append(
        "※ 아래 이미지는 위 목록과 같은 순서로 첨부되어 있다."
    )
    return "\n".join(lines) + "\n"


def _build_user_content(question: str, pages: List[ManualPage]) -> Any:
    """user_prompt로 넘길 content. 이미지가 없으면 순수 문자열,
    있으면 OpenAI 멀티모달 content 배열([text, image_url, ...])을 만든다.
    """

    if not pages:
        return question

    content: List[Dict[str, Any]] = [{"type": "text", "text": question}]

    for page in pages:
        image_path = MANUAL_IMAGE_DIR / page.filename
        b64 = _encode_image_b64(image_path)
        if b64 is None:
            continue
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            }
        )

    # 선택된 페이지의 이미지 파일을 하나도 못 읽었으면(경로 문제 등)
    # 텍스트만 보낸다 — 매뉴얼 자료 없이도 법령만으로는 답할 수 있다.
    if len(content) == 1:
        return question

    return content


def _verify_manual_references(claimed: Any, attached_pages: List[ManualPage]) -> List[str]:
    """LLM이 주장한 매뉴얼 인용을, 이번 호출에 실제로 첨부한 페이지
    제목 목록과 대조한다. 첨부하지 않은 자료를 인용했다고 하면(지어낸
    것이므로) 조용히 뺀다. law_qa_llm._verify_cited_articles와 같은
    목적이지만, 매뉴얼 쪽은 원본이 이미지라 내용 자체의 사실 검증은
    못 하고 "존재하는 첨부 자료를 가리켰는지"만 확인한다.
    """

    if not isinstance(claimed, list):
        return []

    # 2026-10-26 실제 LLM 테스트로 발견: 프롬프트 목록에 "제목 (p.350)"
    # 형식으로 보여주면, LLM이 페이지 표시까지 그대로 베껴서
    # "제목 (p.350)"을 통째로 반환할 때가 있다 — 제목 완전일치만
    # 허용하면 이런 정상적인 인용까지 전부 걸러진다. 그래서 완전일치
    # 외에 "claimed가 title로 시작하는 경우"(뒤에 페이지 등 접미사가
    # 붙은 경우)도 같은 자료로 인정한다. law_qa_llm의 같은 법령 내
    # 동일 조문번호 버그와 같은 종류 — 실제 호출해보기 전엔 안 보였다.
    attached_titles = [page.title for page in attached_pages]
    verified: List[str] = []
    seen = set()

    for item in claimed:
        text = str(item).strip() if not isinstance(item, dict) else str(
            item.get("title", "")
        ).strip()

        if not text:
            continue

        matched_title = next(
            (
                title
                for title in attached_titles
                if text == title or text.startswith(title)
            ),
            None,
        )

        if matched_title is not None and matched_title not in seen:
            verified.append(matched_title)
            seen.add(matched_title)

    return verified


def answer_legal_manual_question(
    client: OpenAI,
    model: str,
    question: str,
    *,
    law_names: Optional[List[str]] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """법령·매뉴얼 질문에 조문·자료 근거를 달아 답한다.

    반환: {"answer": str, "law_names": [...], "cited_articles": [...],
    "manual_references": [...]}
    """

    names = law_names or list(LAW_TARGET_LAWS)

    masked_question, entity_map = mask_for_outbound(question)

    law_corpus, articles = _build_law_corpus(names)
    manual_pages = _select_manual_pages(masked_question)
    manual_section = _build_manual_section(manual_pages)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        law_corpus=law_corpus,
        manual_section=manual_section,
    )

    user_content = _build_user_content(masked_question, manual_pages)

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_content,
            max_retries=2,
            timeout_seconds=180.0,
            deadline=deadline,
        )
    except Exception as error:
        return {
            "answer": f"법령·매뉴얼 질의에 실패했습니다: {error}",
            "law_names": names,
            "cited_articles": [],
            "manual_references": [],
        }

    if not isinstance(parsed, dict):
        parsed = {}

    answer_text = str(parsed.get("answer") or "").strip()
    answer_text = restore_pii(answer_text, entity_map)

    return {
        "answer": answer_text,
        "law_names": names,
        "cited_articles": _verify_cited_articles(
            parsed.get("cited_articles"), articles
        ),
        "manual_references": _verify_manual_references(
            parsed.get("manual_references"), manual_pages
        ),
    }


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    import json

    from ai.modeling.abuse.llm_backend import build_openai_client_and_model

    client, model = build_openai_client_and_model(DEFAULT_MODEL)
    result = answer_legal_manual_question(
        client=client,
        model=model,
        question="아동학대 위험수준별 개입 사정 척도에서 위험요인 문항은 몇 개고 어떻게 채점해?",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
