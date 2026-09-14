from __future__ import annotations

import argparse
import json
from typing import Any

from law.client import LawApiClient, LawApiError
from law.mapper import rank_law_articles
from law.parser import extract_articles

from .checklist_builder import build_next_session_checklist
from .config import LAW_TARGET_LAWS
from .evidence_analyzer import analyze_checklist_candidates
from .resource_ranker import build_reference_materials
from .retriever import search_evidence


DISCLAIMER = (
    "본 결과는 상담사의 판단을 지원하기 위한 참고정보이며 "
    "학대 여부를 확정하거나 법적 판단을 대신하지 않습니다."
)

ABUSE_TYPE_KO = {
    "physical": "신체학대",
    "emotional": "정서학대",
    "sexual": "성학대",
    "neglect": "방임",
    "multiple": "복합 학대",
}


def _empty_result(consultation_text: str, abuse_type: str) -> dict[str, Any]:
    return {
        "analysis_type": abuse_type,
        "consultation_text": consultation_text,
        "evidence_sentences": [],
        "checklist_results": [],
        "additional_questions": [],
        "related_laws": [],
        "next_session_checklist": {"items": []},
        "reference_materials": [],
        "disclaimer": DISCLAIMER,
    }


def _merge_results(
    consultation_text: str,
    abuse_type: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    result = _empty_result(consultation_text, abuse_type)
    if not candidates:
        return result

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

    result["checklist_results"] = checklist_results
    result["evidence_sentences"] = evidence_sentences
    result["additional_questions"] = analysis.additional_questions
    return result


def _load_law_articles(
    consultation_text: str,
    abuse_type: str,
    *,
    refresh: bool = False,
    limit: int = 3,
) -> tuple[list[dict[str, Any]], str | None]:
    client = LawApiClient()
    if not client.configured:
        return [], "LAW_API_OC가 설정되지 않아 법령 API 조회를 건너뛰었습니다."

    ranked_all: list[dict[str, Any]] = []
    warnings: list[str] = []

    for law_name in LAW_TARGET_LAWS:
        try:
            cached = client.get_law_by_name(law_name, refresh=refresh)
            articles = extract_articles(
                cached.get("body", {}),
                fallback_law_name=law_name,
            )
            ranked_all.extend(
                rank_law_articles(
                    articles,
                    abuse_type=abuse_type,
                    consultation_text=consultation_text,
                    limit=3,
                )
            )
        except (LawApiError, OSError, ValueError) as exc:
            warnings.append(f"{law_name}: {exc}")

    ranked_all.sort(
        key=lambda item: float(item.get("relevance_score", 0)),
        reverse=True,
    )

    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in ranked_all:
        key = (str(item.get("law_name", "")), str(item.get("article", "")))
        if key in seen:
            continue
        unique.append(item)
        seen.add(key)
        if len(unique) >= limit:
            break

    return unique, "; ".join(warnings) if warnings else None


def _load_supplementary_rag(
    consultation_text: str,
    abuse_type: str,
) -> list[dict[str, Any]]:
    query = (
        f"{consultation_text} "
        f"{ABUSE_TYPE_KO.get(abuse_type, '아동학대')} 상담 확인 대응"
    )

    results: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()

    for source_type in ("manual", "guideline"):
        try:
            found = search_evidence(
                query,
                top_k=2,
                source_type=source_type,
            )
        except Exception:
            continue

        for item in found:
            chunk_id = str(item.get("metadata", {}).get("chunk_id", ""))
            if chunk_id and chunk_id in seen_chunks:
                continue
            results.append(item)
            if chunk_id:
                seen_chunks.add(chunk_id)

    return results


def analyze_consultation_evidence(
    text: str,
    abuse_type: str,
    *,
    top_k: int = 5,
    source_type: str = "checklist",
    use_law: bool = True,
    refresh_law: bool = False,
    reference_limit: int = 3,
) -> dict[str, Any]:
    consultation_text = text.strip()
    if not consultation_text:
        raise ValueError("상담 문장이 비어 있습니다.")

    rag_abuse_filter = None if abuse_type == "multiple" else abuse_type
    candidates = search_evidence(
        consultation_text,
        top_k=top_k,
        source_type=source_type,
        abuse_type=rag_abuse_filter,
    )

    result = _merge_results(
        consultation_text=consultation_text,
        abuse_type=abuse_type,
        candidates=candidates,
    )

    law_articles: list[dict[str, Any]] = []
    law_warning: str | None = None
    if use_law:
        law_articles, law_warning = _load_law_articles(
            consultation_text,
            abuse_type,
            refresh=refresh_law,
            limit=3,
        )

    supplementary_results = _load_supplementary_rag(
        consultation_text,
        abuse_type,
    )

    next_session_checklist = build_next_session_checklist(
        consultation_text,
        result["checklist_results"],
        law_articles,
        fallback_questions=result["additional_questions"],
    )

    reference_materials = build_reference_materials(
        result["checklist_results"],
        law_articles,
        supplementary_results,
        limit=reference_limit,
    )

    result["related_laws"] = law_articles
    result["next_session_checklist"] = next_session_checklist
    result["reference_materials"] = reference_materials
    if law_warning:
        result["law_warning"] = law_warning

    if not candidates:
        result["message"] = "조건에 맞는 체크리스트 검색 결과가 없습니다."

    return result


def _print_human_readable(
    result: dict[str, Any],
    *,
    show_excluded: bool = False,
) -> None:
    print("=" * 80)
    print(f"분석 유형: {result['analysis_type']}")
    print("=" * 80)

    print("\n[1. 상담 내용에서 확인된 근거 문장]")
    evidence_sentences = result.get("evidence_sentences", [])
    if evidence_sentences:
        for item in evidence_sentences:
            print(f"- {item['text']}")
            print(f"  이유: {item['reason']}")
    else:
        print("- 직접 확인된 근거 문장이 없습니다.")

    checklist_results = result.get("checklist_results", [])
    matched = [item for item in checklist_results if item.get("status") == "matched"]
    needs_confirmation = [
        item for item in checklist_results if item.get("status") == "needs_confirmation"
    ]
    excluded = [item for item in checklist_results if item.get("status") == "excluded"]

    print("\n[2. 상담 내용과 일치하는 체크리스트 항목]")
    if matched:
        for item in matched:
            print(f"✓ {item['item']}")
            print(f"  근거: {item['evidence']}")
            print(f"  출처: {item['source']} p.{item['page']} ({item['organization']})")
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

    print("\n[4. 관련 현행 법령]")
    laws = result.get("related_laws", [])
    if laws:
        for article in laws:
            print(
                f"- {article.get('law_name', '')} {article.get('article', '')} "
                f"{article.get('title', '')}"
            )
            print(f"  관련 키워드: {', '.join(article.get('matched_keywords', []))}")
    else:
        print("- 조회된 관련 법령이 없습니다.")
    if result.get("law_warning"):
        print(f"  참고: {result['law_warning']}")

    print("\n[5. 다음 상담용 확인 체크리스트]")
    items = result.get("next_session_checklist", {}).get("items", [])
    if items:
        for item in items:
            mark = "!" if item.get("priority") == "high" else "-"
            print(f"{mark} {item.get('question', '')}")
            print(f"  이유: {item.get('rationale', '')}")
            print(f"  근거: {', '.join(item.get('basis_refs', []))}")
    else:
        print("- 생성된 후속 확인 질문이 없습니다.")

    print("\n[6. 상담사 참고자료]")
    materials = result.get("reference_materials", [])
    if materials:
        for index, material in enumerate(materials, start=1):
            title = material.get("title", "")
            article = material.get("article", "")
            page = material.get("page")
            suffix = f" {article}" if article else (f" p.{page}" if page else "")
            print(f"{index}. [{material.get('type', '')}] {title}{suffix}")
            print(f"   {material.get('summary', '')}")
    else:
        print("- 제공할 참고자료가 없습니다.")

    print("\n[참고]")
    print(result.get("disclaimer", DISCLAIMER))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "상담 문장, RAG 체크리스트, 현행 법령을 결합하여 근거 문장, "
            "다음 상담 체크리스트, 참고자료를 생성합니다."
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
    parser.add_argument("--source-type", default="checklist")
    parser.add_argument("--references", type=int, default=3, choices=[2, 3])
    parser.add_argument("--skip-law", action="store_true", help="법령 API 조회를 생략")
    parser.add_argument(
        "--refresh-law",
        action="store_true",
        help="법령 캐시를 무시하고 국가법령정보센터에서 다시 조회",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--show-excluded", action="store_true")
    args = parser.parse_args()

    result = analyze_consultation_evidence(
        text=args.text,
        abuse_type=args.abuse_type,
        top_k=args.top_k,
        source_type=args.source_type,
        use_law=not args.skip_law,
        refresh_law=args.refresh_law,
        reference_limit=args.references,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    _print_human_readable(result, show_excluded=args.show_excluded)


if __name__ == "__main__":
    main()
