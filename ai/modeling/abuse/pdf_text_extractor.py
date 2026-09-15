"""
PDF 상담일지에서 텍스트를 추출한다.

현재는 텍스트 레이어가 있는 PDF만 지원한다.
스캔 이미지로만 이루어진 페이지는 텍스트가 비어 있는 채로
has_text_layer=False로 표시만 하고, OCR은 하지 않는다.
"""

import argparse
from pathlib import Path
from typing import Any, Dict, List

import fitz


# ============================================================
# 1. 페이지별 텍스트 추출
# ============================================================

def extract_pages(
    pdf_path,
) -> List[Dict[str, Any]]:
    """
    PDF의 각 페이지에서 텍스트를 추출한다.

    text가 비어 있는 페이지는 텍스트 레이어가 없는(스캔 이미지 등)
    페이지로 보고 has_text_layer=False로 표시한다.
    """

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF 파일을 찾을 수 없습니다: {pdf_path}"
        )

    pages: List[Dict[str, Any]] = []

    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            text = page.get_text(
                "text"
            ).strip()

            pages.append(
                {
                    "page_number": page_index + 1,
                    "text": text,
                    "has_text_layer": bool(text),
                }
            )

    return pages


# ============================================================
# 2. 전체 텍스트 합치기
# ============================================================

def extract_text_from_pdf(
    pdf_path,
) -> Dict[str, Any]:
    """
    PDF 전체 텍스트와 페이지별 추출 상태를 함께 반환한다.
    """

    pages = extract_pages(
        pdf_path
    )

    full_text = "\n\n".join(
        page["text"]
        for page in pages
        if page["text"]
    )

    pages_without_text_layer = [
        page["page_number"]
        for page in pages
        if not page["has_text_layer"]
    ]

    return {
        "page_count": len(pages),
        "text": full_text,
        "pages": pages,
        "pages_without_text_layer": pages_without_text_layer,
    }


# ============================================================
# 3. CLI 데모
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PDF 상담일지 텍스트 추출"
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="PDF 파일 경로",
    )

    args = parser.parse_args()

    result = extract_text_from_pdf(
        args.pdf
    )

    print(
        f"총 {result['page_count']}페이지"
    )

    if result["pages_without_text_layer"]:
        pages_str = ", ".join(
            str(n)
            for n in result["pages_without_text_layer"]
        )

        print(
            "텍스트 레이어가 없는 페이지 "
            f"(스캔 이미지일 가능성): {pages_str}"
        )

    print()
    print(
        result["text"]
    )


if __name__ == "__main__":
    main()
