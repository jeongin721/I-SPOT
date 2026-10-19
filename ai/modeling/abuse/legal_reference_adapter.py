"""
rag/, law/ 모듈(feature/rag 브랜치에서 2026-10-19 포팅)을 이 파이프라인에
연결하는 어댑터. 탐지된 학대유형별로 관련 법령 조문(related_laws)·
매뉴얼 참고자료(manual_references)·판례(precedents)를 찾아 붙인다.

[왜 마스킹을 거치는가]

rag.pipeline.analyze_consultation_evidence()는 자체적으로 PII 마스킹을
하지 않는다 — consultation_text를 그대로 OpenAI 임베딩(검색 질의)과
분석 LLM(rag/evidence_analyzer.py, rag/checklist_builder.py)에 보낸다.
이 프로젝트의 다른 모든 외부 LLM 호출과 같은 규칙을 적용하기 위해,
여기서 mask_for_outbound()를 거친 텍스트만 analyze_consultation_evidence()
에 넘기고, 돌아온 결과(상담 원문을 그대로 반사할 수 있는 evidence_sentences
등)에는 restore_pii()를 적용한다.

[지금 비어 있는 것]

- manual_references/precedents: rag_data/(원본 매뉴얼·판례 PDF)가
  gitignore돼 있어 저장소에 없다 — 색인 전까지는 항상 빈 배열.
- related_laws: LAW_API_OC(국가법령정보센터 Open API 키)가 .env에
  없으면 건너뛴다(law.client.LawApiClient.configured가 False) — 키를
  등록하면 바로 동작한다. 둘 다 없어도 예외 없이 빈 결과로 돌아온다
  (rag/pipeline.py가 이미 이렇게 설계돼 있다).

[세그먼트 단위가 아니라 유형 단위로 호출하는 이유]

risk_signal_point(발화)마다 호출하면 호출 수가 발화 개수만큼 늘어나
처리시간 예산(deadline 기반 타임아웃, infer_audio_session.py 참고)에
부담을 준다. 대신 탐지된 major_type마다 그 유형의 근거 발화를 모아
한 번만 호출한다 — law.mapper.rank_law_articles()도 원래 "학대유형 +
상담 표현 전체"를 받아 랭킹하도록 설계돼 있어 이 쪽이 자연스럽다.
"""

from typing import Any, Dict, List, Optional

from rag.pipeline import analyze_consultation_evidence

from ai.modeling.abuse.pii_masking import restore_pii
from ai.modeling.abuse.privacy_gateway import mask_for_outbound

MAJOR_TYPE_TO_RAG_ABUSE_TYPE = {
    "신체학대": "physical",
    "정서학대": "emotional",
    "성학대": "sexual",
    "방임": "neglect",
}


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
) -> Dict[str, Dict[str, Any]]:
    """
    탐지된 학대유형마다 관련 법령/매뉴얼/판례를 찾는다.

    반환값은 {major_type(한글): {related_laws, manual_references,
    precedents, law_warning}} 모양이다. 근거 발화가 없거나 매핑 안 되는
    유형(현재는 4종 모두 매핑됨)은 결과에서 빠진다.
    """

    references: Dict[str, Dict[str, Any]] = {}

    for major_type in detected_major_types:
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
            references[major_type] = {
                "related_laws": [],
                "manual_references": [],
                "precedents": [],
                "law_warning": f"법령/참고자료 조회 실패: {error}",
            }
            continue

        result = restore_pii(result, entity_map)

        references[major_type] = {
            "related_laws": result.get("related_laws", []),
            "manual_references": result.get("manual_references", []),
            "precedents": result.get("precedents", []),
            "law_warning": result.get("law_warning"),
        }

    return references
