from __future__ import annotations

import argparse
import json
from typing import Any

from .evidence_analyzer import analyze_checklist_candidates
from .retriever import search_evidence


DISCLAIMER = (
    "본 결과는 상담사의 판단을 지원하기 위한 참고정보이며 "
    "학대 여부를 확정하거나 법적 판단을 대신하지 않습니다."
)


def _merge_results(
    consultation_text: str,
    abuse_type: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    analysis = analyze_checklist_candidates(
        consultation_text=consultation_text,
        candidates=candidates,
    )

    checklist_results: list[dict[str, Any]] = []
    evidence_sentences: list[dict[str, str]] = []
    seen_evidence: set[str] = set()

    for judgement in analysis.judgements:
        candidate = candidates[judgement.candidate_id - 1]
        metadata = candidate.get("metadata", {})

        item = {
            "status": judgement.status,
            "item": candidate.get("content", ""),
            "evidence": judgement.evidence,
            "reason": judgement.reason,
            "source": metadata.get("source", ""),
            "organization": metadata.get("organization", ""),
            "page": metadata.get("page"),
            "chunk_id": metadata.get("chunk_id", ""),
            "source_type": metadata.get("source_type", ""),
            "abuse_type": metadata.get("abuse_type", ""),
            "category": metadata.get("category", ""),
        }
        checklist_results.append(item)

        if judgement.status == "matched" and judgement.evidence:
            if judgement.evidence not in seen_evidence:
                evidence_sentences.append(
                    {
                        "text": judgement.evidence,
                        "reason": judgement.reason,
                    }
                )
                seen_evidence.add(judgement.evidence)

    return {
        "analysis_type": abuse_type,
        "consultation_text": consultation_text,
        "evidence_sentences": evidence_sentences,
        "checklist_results": checklist_results,
        "additional_questions": analysis.additional_questions,
        "disclaimer": DISCLAIMER,
    }


def analyze_consultation_evidence(
    text: str,
    abuse_type: str,
    *,
    top_k: int = 5,
    source_type: str = "checklist",
) -> dict[str, Any]:
    consultation_text = text.strip()
    if not consultation_text:
        raise ValueError("상담 문장이 비어 있습니다.")

    candidates = search_evidence(
        consultation_text,
        top_k=top_k,
        source_type=source_type,
        abuse_type=abuse_type,
    )

    if not candidates:
        return {
            "analysis_type": abuse_type,
            "consultation_text": consultation_text,
            "evidence_sentences": [],
            "checklist_results": [],
            "additional_questions": [],
            "disclaimer": DISCLAIMER,
            "message": "조건에 맞는 체크리스트 검색 결과가 없습니다.",
        }

    return _merge_results(
        consultation_text=consultation_text,
        abuse_type=abuse_type,
        candidates=candidates,
    )


def _print_human_readable(
    result: dict[str, Any],
    *,
    show_excluded: bool = False,
) -> None:
    print("=" * 80)
    print(f"분석 유형: {result['analysis_type']}")
    print("=" * 80)

    evidence_sentences = result.get("evidence_sentences", [])
    print("\n[1. 상담 내용에서 확인된 근거 문장]")
    if evidence_sentences:
        for item in evidence_sentences:
            print(f"- {item['text']}")
            print(f"  이유: {item['reason']}")
    else:
        print("- 직접 확인된 근거 문장이 없습니다.")

    checklist_results = result.get("checklist_results", [])

    matched = [
        item for item in checklist_results if item.get("status") == "matched"
    ]
    needs_confirmation = [
        item
        for item in checklist_results
        if item.get("status") == "needs_confirmation"
    ]
    excluded = [
        item for item in checklist_results if item.get("status") == "excluded"
    ]

    print("\n[2. 상담 내용과 일치하는 체크리스트 항목]")
    if matched:
        for item in matched:
            print(f"✓ {item['item']}")
            print(f"  근거: {item['evidence']}")
            print(
                f"  출처: {item['source']} p.{item['page']} "
                f"({item['organization']})"
            )
    else:
        print("- 직접 일치가 확인된 항목이 없습니다.")

    print("\n[3. 추가 확인이 필요한 체크리스트 항목]")
    if needs_confirmation:
        for item in needs_confirmation:
            print(f"△ {item['item']}")
            print(f"  이유: {item['reason']}")
            print(f"  출처: {item['source']} p.{item['page']}")
    else:
        print("- 추가 확인 대상으로 분류된 항목이 없습니다.")

    if show_excluded:
        print("\n[검색되었지만 현재 상담과 직접 관련성이 낮은 항목]")
        if excluded:
            for item in excluded:
                print(f"- {item['item']}")
                print(f"  이유: {item['reason']}")
        else:
            print("- 없음")

    print("\n[4. 추가 확인 권장 질문]")
    questions = result.get("additional_questions", [])
    if questions:
        for question in questions:
            print(f"- {question}")
    else:
        print("- 생성된 추가 질문이 없습니다.")

    print("\n[참고]")
    print(result.get("disclaimer", DISCLAIMER))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "상담 문장과 RAG 체크리스트를 비교하여 근거 문장, "
            "확인 항목, 추가 질문을 생성합니다."
        )
    )
    parser.add_argument("text", help="분석할 상담 문장")
    parser.add_argument(
        "--abuse-type",
        required=True,
        choices=["physical", "emotional", "sexual", "neglect", "multiple"],
        help="상위 멀티라벨 모델이 판단한 학대 유형",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--source-type",
        default="checklist",
        help="검색할 RAG source_type (기본값: checklist)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="백엔드 연동용 JSON 형식으로 출력",
    )
    parser.add_argument(
        "--show-excluded",
        action="store_true",
        help="현재 상담과 관련성이 낮아 제외된 검색 항목도 표시",
    )
    args = parser.parse_args()

    result = analyze_consultation_evidence(
        text=args.text,
        abuse_type=args.abuse_type,
        top_k=args.top_k,
        source_type=args.source_type,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    _print_human_readable(
        result,
        show_excluded=args.show_excluded,
    )


if __name__ == "__main__":
    main()
