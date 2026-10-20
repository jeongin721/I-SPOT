"""
rag/, law/ 모듈(feature/rag 브랜치, jeongin 담당, 2026-10-19 포팅)을 이
파이프라인에 연결하는 어댑터. 탐지된 학대유형마다 관련 법령 조문을
찾아 호(clause) 단위로 쪼개 붙인다.

[코드 소유 — law/·rag/는 손대지 않는다]

law/·rag/는 jeongin님이 만드는 feature/rag 브랜치의 코드를 그대로
복사해 온 것이다(2026-10-19 Mingyu 리뷰에서 지적) — 여기서 그 파일들을
고치면 나중에 feature/rag가 main에 들어올 때 각자 고친 게 충돌한다
(요약 변환기 때와 같은 문제). 그래서 호 단위 파싱 같은 새 로직은 전부
이 어댑터(내 소유 파일) 안에서, law/·rag/가 돌려주는 값을 가공하는
방식으로만 구현한다.

[Contract 모양 — 2026-10-19 Mingyu 제안]

유형별로 묶은 dict가 아니라 평평한 목록 하나로 돌려준다. 각 항목은
{major_type, law_name, article, clause, title, content, url}. relevance_score·
matched_keywords는 정렬/호 선택에만 쓰고 바깥으로 내보내지 않는다.
law_warning은 따로 두지 않고 warnings 목록에 합친다. manual_references·
precedents는 rag.pipeline이 내부적으로 계산은 하지만(원본 자료 색인 전이라
항상 빈 값), Mingyu가 "나중에 Contract에 추가" 한다고 해서 지금은 이
어댑터 바깥으로 안 내보낸다.

[왜 마스킹을 거치는가]

rag.pipeline.analyze_consultation_evidence()는 자체적으로 PII 마스킹을
하지 않는다 — consultation_text를 그대로 OpenAI 임베딩(검색 질의)과
분석 LLM(rag/evidence_analyzer.py, rag/checklist_builder.py)에 보낸다.
이 프로젝트의 다른 모든 외부 LLM 호출과 같은 규칙을 적용하기 위해,
여기서 mask_for_outbound()를 거친 텍스트만 analyze_consultation_evidence()
에 넘기고, 돌아온 결과에는 restore_pii()를 적용한다.

law.go.kr 자체(law/client.py)에는 상담 원문이 전혀 나가지 않는다 —
LawApiClient.get_law_by_name()은 LAW_TARGET_LAWS의 고정된 법령명
("아동복지법" 등)과 내부 법령ID/일련번호만 보낸다(2026-10-19 Mingyu
질문 답변). consultation_text는 로컬 키워드 매칭(law.mapper, 네트워크
없음)과 OpenAI 임베딩(위에서 마스킹 거침)에만 쓰인다.

[지금 비어 있는 것]

- related_laws: LAW_API_OC(국가법령정보센터 Open API 키)가 .env에
  없으면 건너뛴다(law.client.LawApiClient.configured가 False) — 키를
  등록하면 바로 동작한다. 예외 없이 빈 결과로 돌아온다(rag/pipeline.py
  설계).

[세그먼트 단위가 아니라 유형 단위로 호출하는 이유]

risk_signal_point(발화)마다 호출하면 호출 수가 발화 개수만큼 늘어난다.
대신 탐지된 major_type마다 그 유형의 근거 발화를 모아 한 번만
호출한다 — law.mapper.rank_law_articles()도 원래 "학대유형 + 상담
표현 전체"를 받아 랭킹하도록 설계돼 있어 이 쪽이 자연스럽다.

[처리시간 · deadline]

유형 하나당 실측 9~15초(법령 캐시 여부에 따라, 2026-10-19 측정) —
analyze_consultation_evidence() 자체는 deadline을 모른다(ported 코드라
손 안 댐). 그래서 유형별 반복 "사이"에서만 deadline을 확인해 남은
유형은 건너뛴다 — 이미 시작된 한 번의 호출 중간에 끊지는 못한다.
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from law.mapper import build_law_keywords
from rag.pipeline import analyze_consultation_evidence

from ai.modeling.abuse.pii_masking import restore_pii
from ai.modeling.abuse.privacy_gateway import mask_for_outbound

MAJOR_TYPE_TO_RAG_ABUSE_TYPE = {
    "신체학대": "physical",
    "정서학대": "emotional",
    "성학대": "sexual",
    "방임": "neglect",
}

# 조문 content 끝에 붙는 "제17조(금지행위) 누구든지 ... <개정 ...>" 같은
# 머리말/개정이력 줄 — 호가 아니라서 버린다.
_ARTICLE_HEADING_RE = re.compile(r"^제\d+조")
# 항(①②③...) 경계 — 항마다 호 번호가 1부터 다시 시작돼서, 이 경계를
# 모르면 서로 다른 항의 "4호"끼리 내용이 섞인다. 항 단위 텍스트 자체는
# (지금은) 호로 만들지 않고 버린다 — Mingyu가 요청한 건 호 단위라서.
_PARAGRAPH_MARK_RE = re.compile(r"^[①-⑩]")
_CLAUSE_START_RE = re.compile(r"^(\d+)\.\s*(.*)")


def _split_into_clauses(content: str) -> List[Dict[str, str]]:
    """
    조문 content를 호 단위로 쪼갠다. "1. ...", "2. ..."처럼 줄 앞의
    숫자+마침표를 호 경계로 본다. 삭제된 호("4. 삭제<2014.1.28>")도
    그대로 호 하나로 남긴다 — 화면에서 걸러낼지는 상담사 판단.
    """

    clauses: List[Dict[str, str]] = []
    current_num: Optional[str] = None
    current_lines: List[str] = []

    def flush() -> None:
        if current_num is not None and current_lines:
            text = " ".join(
                line for line in current_lines if line
            ).strip()
            if text:
                clauses.append(
                    {"clause": f"{current_num}호", "content": text}
                )

    for raw_line in content.split("\n"):
        line = raw_line.strip()
        clause_match = _CLAUSE_START_RE.match(line)

        if clause_match:
            flush()
            current_num = clause_match.group(1)
            current_lines = [clause_match.group(2)]
        elif _ARTICLE_HEADING_RE.match(line) or _PARAGRAPH_MARK_RE.match(
            line
        ):
            # 조문 머리말/개정이력, 또는 새 항(①②③...) 시작 — 호가
            # 아니므로 지금까지 모은 호만 저장하고 더 안 붙인다. 새 항의
            # 호 번호는 1부터 다시 시작되므로, 여기서 안 끊으면 이전
            # 항의 같은 번호 호와 내용이 섞인다.
            flush()
            current_num = None
            current_lines = []
        elif current_num is not None:
            current_lines.append(line)

    flush()

    return clauses


def _matching_clauses(
    law: Dict[str, Any],
    keywords: List[str],
) -> List[Dict[str, str]]:
    """
    조문을 호 단위로 쪼갠 뒤, 학대유형 키워드가 들어간 호만 남긴다.
    호 단위로 하나도 안 걸리면(파싱이 이 조문 형식과 안 맞는 경우 등)
    조문 전체를 "호 없음"으로 돌려줘 근거 자체는 잃지 않는다.
    """

    content = law.get("content", "")
    clauses = _split_into_clauses(content)
    matched = [
        clause
        for clause in clauses
        if any(keyword in clause["content"] for keyword in keywords)
    ]

    if matched:
        return matched

    if clauses:
        # 호는 쪼개졌는데 키워드가 하나도 안 걸림 — 조문 자체가
        # rank_law_articles()에서 이미 관련 있다고 랭킹된 것이므로,
        # 안전하게 전체를 "호 없음" 한 건으로 남긴다.
        return [{"clause": "", "content": content}]

    return [{"clause": "", "content": content}]


def _evidence_text_for_major_type(
    risk_signal_points: List[Dict[str, Any]],
    major_type: str,
) -> str:
    texts = [
        point.get("text", "")
        for point in risk_signal_points
        if point.get("major_type") == major_type and point.get("text")
    ]

    return "\n".join(texts)


def build_legal_references(
    detected_major_types: List[str],
    risk_signal_points: List[Dict[str, Any]],
    known_identifiers: Optional[List[str]] = None,
    deadline: Optional[float] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    탐지된 학대유형마다 관련 법령 조문을 찾아 호 단위로 쪼갠 평평한
    목록으로 돌려준다(모듈 docstring의 Contract 모양 참고).

    반환값은 (items, warnings) 튜플이다. items의 각 항목은
    {major_type, law_name, article, clause, title, content, url}.
    """

    items: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for major_type in detected_major_types:
        if deadline is not None and time.monotonic() >= deadline:
            warnings.append(
                "시간 제한으로 일부 학대유형의 관련 법령 조회를 건너뛰었습니다."
            )
            break

        rag_abuse_type = MAJOR_TYPE_TO_RAG_ABUSE_TYPE.get(major_type)

        if not rag_abuse_type:
            continue

        evidence_text = _evidence_text_for_major_type(
            risk_signal_points, major_type
        )

        if not evidence_text.strip():
            continue

        masked_text, entity_map = mask_for_outbound(
            evidence_text, known_identifiers=known_identifiers
        )

        try:
            result = analyze_consultation_evidence(
                text=masked_text,
                abuse_type=rag_abuse_type,
            )
        except Exception as error:
            warnings.append(
                f"{major_type} 관련 법령/참고자료 조회 실패: {error}"
            )
            continue

        result = restore_pii(result, entity_map)

        if result.get("law_warning"):
            warnings.append(result["law_warning"])

        keywords = build_law_keywords(rag_abuse_type, evidence_text)

        for law in result.get("related_laws", []):
            for clause in _matching_clauses(law, keywords):
                items.append(
                    {
                        "major_type": major_type,
                        "law_name": law.get("law_name", ""),
                        "article": law.get("article", ""),
                        "clause": clause["clause"],
                        "title": law.get("title", ""),
                        "content": clause["content"],
                        "url": law.get("portal_url", ""),
                    }
                )

    return items, warnings
