from __future__ import annotations

import argparse
import json

from .client import LawApiClient
from .mapper import rank_law_articles
from .parser import extract_articles


def main() -> None:
    parser = argparse.ArgumentParser(description="국가법령정보센터 API 연동 테스트")
    parser.add_argument("law_name", help="조회할 법령명 (예: 아동복지법)")
    parser.add_argument(
        "--abuse-type",
        default="emotional",
        choices=["physical", "emotional", "sexual", "neglect", "multiple"],
    )
    parser.add_argument("--text", default="", help="관련 상담 문장")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    client = LawApiClient()
    cached = client.get_law_by_name(args.law_name, refresh=args.refresh)
    articles = extract_articles(
        cached.get("body", {}),
        fallback_law_name=args.law_name,
    )
    ranked = rank_law_articles(
        articles,
        abuse_type=args.abuse_type,
        consultation_text=args.text,
        limit=args.top_k,
    )

    if args.json:
        print(json.dumps(ranked, ensure_ascii=False, indent=2))
        return

    print(f"법령: {args.law_name}")
    print(f"추출 조문 수: {len(articles)}")
    print("=" * 80)
    for index, article in enumerate(ranked, start=1):
        print(
            f"[{index}] {article.get('law_name', '')} "
            f"{article.get('article', '')} {article.get('title', '')}"
        )
        print(f"관련 키워드: {', '.join(article.get('matched_keywords', []))}")
        print(article.get("content", "")[:1200])
        print("=" * 80)


if __name__ == "__main__":
    main()
