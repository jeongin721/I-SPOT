"""
PDF 상담일지에서 텍스트를 추출한다.

현재는 텍스트 레이어가 있는 PDF만 지원한다.
스캔 이미지로만 이루어진 페이지는 텍스트가 비어 있는 채로
has_text_layer=False로 표시만 하고, OCR은 하지 않는다.
"""

import argparse
import re
from collections import Counter
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
# 2. 행정 잡음 제거
# ============================================================
# 상담일지 양식은 기관마다 달라서, "이 내용은 필요하다"고 항목명을
# 짚어서 골라내는 방식(whitelist)은 양식이 다르면 아예 못 찾고
# 넘어갈 위험이 있다. 대신 "이건 확실히 행정 정보다"라고 판단되는
# 줄만 제거하는 방식(blacklist)을 쓴다 — 확신이 없으면 그대로
# 둔다. 최악의 경우에도 지금처럼 전체 텍스트가 나오는 것뿐이라,
# 실수로 실제 상담 내용을 지우는 방향으로는 가지 않는다.

_ADMIN_LINE_PATTERNS = [
    re.compile(r"^\s*[-–]?\s*\d{1,4}\s*[-–]?\s*$"),  # 페이지 번호 단독
    re.compile(r"^\s*(page|쪽|페이지)\s*[:\.]?\s*\d+"),
    re.compile(r"^\s*(문서\s*번호|접수\s*번호|관리\s*번호)\s*[:：]"),
    re.compile(r"^\s*(결\s*재|기안|검토|승인)\s*[:：]?\s*$"),
    re.compile(r"^\s*(작성\s*(일자|일)|접수\s*일자?)\s*[:：]"),
    re.compile(r"^\s*(담당\s*자?|작성\s*자|기관\s*명|시설\s*명)\s*[:：]"),
    re.compile(r"^\s*(슈\s*퍼\s*바\s*이\s*저|지도\s*감독\s*자)\s*[:：]?"),
]

_ADMIN_LINE_MAX_LEN = 40

# 아래 라벨들("상담자", "이름" 등)은 실제 상담내용 문장 첫머리에도
# 흔히 나오는 단어라("상담자는 ~라고 하였음") 콜론 없이 라벨만 덜렁
# 있거나 라벨+짧은 값만 있는 줄로 범위를 좁게 잡는다 — 그래서 일반
# 행정 패턴보다 더 짧은 길이 기준(_AMBIGUOUS_LABEL_MAX_LEN)을 쓴다.
_AMBIGUOUS_LABEL_PATTERNS = [
    re.compile(r"^\s*이\s*름\s*[:：]?\s*"),
    re.compile(r"^\s*성\s*별\s*[:：]?\s*"),
    re.compile(r"^\s*생\s*년\s*월\s*일\s*[:：]?\s*"),
    re.compile(r"^\s*입\s*소\s*일\s*자\s*[:：]?\s*"),
    re.compile(r"^\s*상\s*담\s*자\s*[:：]?\s*$"),
    re.compile(r"^\s*상\s*담\s*일\s*시\s*[:：]?\s*"),
    re.compile(r"^\s*상\s*담\s*장\s*소\s*[:：]?\s*"),
]

_AMBIGUOUS_LABEL_MAX_LEN = 25

# 라벨 줄 바로 다음에 따로 떨어져 나온 짧은 "값"까지 정리할 때,
# 실수로 내용 항목 제목까지 지우지 않도록 지켜야 하는 키워드.
_CONTENT_HEADER_KEYWORDS = [
    "상담목적",
    "상담사유",
    "상담내용",
    "조치내용",
    "슈퍼비전",
    "상담주제",
    "상담결과",
    "종합의견",
    "상담소견",
]

_ORPHAN_VALUE_MAX_LEN = 15


def _looks_like_content_header(
    line: str,
) -> bool:
    compact = re.sub(
        r"\s+",
        "",
        line.strip(),
    )

    return any(
        keyword in compact
        for keyword in _CONTENT_HEADER_KEYWORDS
    )


def _is_ambiguous_label_line(
    line: str,
) -> bool:
    stripped = line.strip()

    if not stripped or len(stripped) > _AMBIGUOUS_LABEL_MAX_LEN:
        return False

    return any(
        pattern.search(stripped)
        for pattern in _AMBIGUOUS_LABEL_PATTERNS
    )


def _is_admin_line(
    line: str,
) -> bool:
    stripped = line.strip()

    if not stripped:
        return False

    if len(stripped) <= _AMBIGUOUS_LABEL_MAX_LEN and any(
        pattern.search(stripped)
        for pattern in _AMBIGUOUS_LABEL_PATTERNS
    ):
        return True

    if len(stripped) > _ADMIN_LINE_MAX_LEN:
        # 긴 줄(실제 서술 내용)은 우연히 키워드를 포함해도 건드리지 않는다.
        return False

    return any(
        pattern.search(stripped)
        for pattern in _ADMIN_LINE_PATTERNS
    )


def strip_administrative_noise(
    pages: List[Dict[str, Any]],
) -> str:
    """
    페이지별 텍스트에서 확실한 행정 잡음(페이지 번호, 문서번호,
    결재란, 반복되는 머리글/바닥글 등)만 제거하고 나머지는 그대로
    이어붙인다.
    """

    page_line_lists = [
        [
            line
            for line in page["text"].split("\n")
        ]
        for page in pages
        if page["text"]
    ]

    # 페이지 2개 이상에서 토씨 하나 안 틀리고 반복되는 짧은 줄은
    # 머리글/바닥글일 가능성이 높다.
    line_counts = Counter(
        line.strip()
        for lines in page_line_lists
        for line in lines
        if line.strip()
        and len(line.strip()) <= _ADMIN_LINE_MAX_LEN
    )

    repeated_lines = {
        line
        for line, count in line_counts.items()
        if count >= 2
        and len(page_line_lists) >= 2
    }

    cleaned_pages = []

    for lines in page_line_lists:
        removed = [
            line.strip() in repeated_lines
            or _is_admin_line(line)
            for line in lines
        ]

        # 라벨만 덜렁 있던 줄(예: "이름") 바로 다음에 따로 떨어져
        # 나온 짧은 값(예: "000", 날짜)도 같이 정리한다. 내용 항목
        # 제목처럼 보이면 절대 건드리지 않는다.
        for i, line in enumerate(lines):
            if not removed[i]:
                continue

            if not _is_ambiguous_label_line(line):
                continue

            next_index = i + 1

            if next_index >= len(lines):
                continue

            if removed[next_index]:
                continue

            next_line = lines[next_index].strip()

            # 글자 사이에 공백이 낀 값("2 0 1 6 - 0 5 - 1 4")은 원문
            # 길이가 실제보다 부풀려지므로, 공백을 뺀 길이로 판단한다.
            next_line_compact = re.sub(
                r"\s+",
                "",
                next_line,
            )

            if (
                next_line
                and len(next_line_compact) <= _ORPHAN_VALUE_MAX_LEN
                and not _looks_like_content_header(next_line)
            ):
                removed[next_index] = True

        kept_lines = [
            line
            for line, is_removed in zip(
                lines,
                removed,
            )
            if not is_removed
        ]

        cleaned_text = "\n".join(
            kept_lines
        ).strip()

        if cleaned_text:
            cleaned_pages.append(
                cleaned_text
            )

    return "\n\n".join(
        cleaned_pages
    )


# ============================================================
# 3. 전체 텍스트 합치기
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

    clean_text = strip_administrative_noise(
        pages
    )

    pages_without_text_layer = [
        page["page_number"]
        for page in pages
        if not page["has_text_layer"]
    ]

    return {
        "page_count": len(pages),
        "text": full_text,
        "clean_text": clean_text,
        "pages": pages,
        "pages_without_text_layer": pages_without_text_layer,
    }


# ============================================================
# 4. CLI 데모
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
