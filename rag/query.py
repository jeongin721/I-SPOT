from __future__ import annotations

import argparse

from dotenv import load_dotenv

from .retriever import search_evidence


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="I-SPOT RAG 검색 테스트")
    parser.add_argument("query", help="검색할 문장")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--source-type", default=None)
    parser.add_argument("--abuse-type", default=None)
    args = parser.parse_args()

    results = search_evidence(
        args.query,
        top_k=args.top_k,
        source_type=args.source_type,
        abuse_type=args.abuse_type,
    )

    if not results:
        print("검색 결과가 없습니다.")
        return

    for i, item in enumerate(results, start=1):
        metadata = item["metadata"]
        print("=" * 80)
        print(f"[{i}] {metadata.get('source', '')} p.{metadata.get('page', '')}")
        print(f"source_type={metadata.get('source_type')} / abuse_type={metadata.get('abuse_type')}")
        print(f"chunk_id={metadata.get('chunk_id')}")
        print("-" * 80)
        print(item["content"])


if __name__ == "__main__":
    main()
