"""
I-SPOT 텍스트 기반 전체 파이프라인 테스트 웹.
QA / Child-only 입력을 받아 1차 대분류, 2차 세부유형, 근거 발화,
상담 요약, 상담일지를 한 화면에서 확인한다.
"""

import io
import json
from datetime import datetime
from html import escape
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
import uvicorn
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ai.modeling.abuse.infer_abuse_pipeline import analyze_session
from ai.modeling.abuse import case_store
from ai.modeling.abuse.case_workflow_routes import (
    register_case_workflow_routes,
)


# ============================================================
# 0-1. PDF 다운로드용 한글 폰트 등록
# ============================================================
# 시스템에 한글 TTF가 별도로 설치돼 있지 않을 수 있어, 이미 설치된
# koreanize_matplotlib 패키지가 들고 있는 나눔고딕을 그대로 재사용한다.

try:
    import koreanize_matplotlib

    _NANUM_FONT_PATH = (
        Path(koreanize_matplotlib.__file__).parent
        / "fonts"
        / "NanumGothic.ttf"
    )
except ImportError:
    _NANUM_FONT_PATH = Path("")

if _NANUM_FONT_PATH.exists():
    pdfmetrics.registerFont(
        TTFont(
            "NanumGothic",
            str(_NANUM_FONT_PATH),
        )
    )
    _PDF_FONT_NAME = "NanumGothic"
else:
    # 폰트를 못 찾으면 한글이 깨지지만, PDF 생성 자체는 실패하지
    # 않도록 기본 폰트로 대체한다.
    _PDF_FONT_NAME = "Helvetica"


# ============================================================
# 0. 결과 다운로드 (간단한 텍스트 파일)
# ============================================================

def build_download_text(
    result: dict,
) -> str:
    checklist_draft = (
        result.get(
            "checklist_draft"
        )
        or {}
    )

    lines = [
        "I-SPOT 상담 분석 결과",
        f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        "",
        "[상담 요약]",
        result.get(
            "counseling_summary",
            "",
        )
        or "(없음)",
        "",
        "[상담일지]",
        result.get(
            "counseling_note",
            "",
        )
        or "(없음)",
        "",
        "[AI 상담 체크리스트 초안 - 상담사 확인 필요]",
        "",
    ]

    for category in (
        "가정상황",
        "아동 특성",
    ):
        items = [
            item
            for item in checklist_draft.get(
                "checklist",
                [],
            )
            if item.get("category") == category
            and item.get("suggested")
        ]

        lines.append(f"■ {category}")

        if not items:
            lines.append(
                "  (근거 있는 항목 없음)"
            )

        for item in items:
            lines.append(
                f"  - {item['item']}"
            )

            for evidence in item.get(
                "evidence",
                [],
            ):
                lines.append(
                    "      근거: "
                    f"\"{evidence.get('evidence', '')}\""
                )

        lines.append("")

    lines.append(
        "■ 안전영역 관련 근거 (등급은 상담사가 직접 판단)"
    )

    for entry in checklist_draft.get(
        "safety_assessment_evidence",
        [],
    ):
        if not entry.get("evidence"):
            continue

        lines.append(
            f"  [{entry['category']}] {entry['item']}"
        )

        for evidence in entry["evidence"]:
            lines.append(
                "      근거: "
                f"\"{evidence.get('evidence', '')}\""
            )

    lines.append("")

    environment = checklist_draft.get(
        "environment_key_person"
    )

    lines.append(
        "■ 환경 - 신뢰할 만한 주위 사람"
    )

    if environment:
        lines.append(
            f"  {environment.get('status', '')}"
        )

        for evidence in environment.get(
            "evidence",
            [],
        ):
            lines.append(
                "      근거: "
                f"\"{evidence.get('evidence', '')}\""
            )
    else:
        lines.append(
            "  관련 언급 없음"
        )

    lines.extend(
        [
            "",
            "[문제력 초안]",
            checklist_draft.get(
                "problem_history_draft",
                "",
            )
            or "(없음)",
            "",
            "[상담원 소견 초안]",
            checklist_draft.get(
                "counselor_opinion_draft",
                "",
            )
            or "(없음)",
            "",
            "=" * 60,
            "본 문서는 AI가 생성한 초안이며, "
            "상담사의 확인·수정·승인이 필요합니다.",
        ]
    )

    return "\n".join(lines)


def _build_family_situation_text(
    checklist_draft: dict,
) -> str:
    """상담일지 서식의 "가정사항" 칸에 들어갈 텍스트를 만든다."""

    lines = []

    problem_history = checklist_draft.get(
        "problem_history_draft",
        "",
    )

    if problem_history:
        lines.append(problem_history)

    household_items = [
        item
        for item in checklist_draft.get("checklist", [])
        if item.get("category") == "가정상황"
        and item.get("suggested")
    ]

    for item in household_items:
        evidences = [
            evidence.get("evidence", "")
            for evidence in item.get("evidence", [])
            if evidence.get("evidence")
        ]

        if evidences:
            lines.append(
                f"- {item['item']}: "
                + " / ".join(evidences)
            )
        else:
            lines.append(f"- {item['item']}")

    return "\n".join(lines) if lines else "(해당 사항 없음)"


def _build_special_notes_text(
    result: dict,
) -> str:
    """상담일지 서식의 "특기사항" 칸에 들어갈 텍스트를 만든다 —
    탐지된 학대유형 + 안전영역 관련 근거 요약(등급은 상담사가 직접 판단)."""

    lines = []

    detected = [
        label
        for label, info in result.get(
            "major_types",
            {},
        ).items()
        if info.get("detected")
    ]

    if detected:
        lines.append(
            "탐지된 학대유형(AI 제안, 상담사 확인 필요): "
            + ", ".join(detected)
        )

    checklist_draft = (
        result.get("checklist_draft") or {}
    )

    for entry in checklist_draft.get(
        "safety_assessment_evidence",
        [],
    ):
        evidences = [
            evidence.get("evidence", "")
            for evidence in entry.get("evidence", [])
            if evidence.get("evidence")
        ]

        if evidences:
            lines.append(
                f"[{entry['category']}] {entry['item']}: "
                + " / ".join(evidences)
            )

    return "\n".join(lines) if lines else "(해당 사항 없음)"


def build_download_pdf(
    result: dict,
) -> bytes:
    """
    기관에서 쓰는 공식 "아동 상담일지" 서식과 같은 표 형태로 PDF를 만든다.

    아동명/성별/보호자명/관계/전화번호/주소/상담교사/상담종류/상담사유는
    이 파이프라인이 수집하지 않는 정보라 빈칸으로 두고 상담사가 직접
    기입하게 한다 — 공식 문서의 신원 정보를 AI가 추측해서 채우는 건
    위험하다고 판단했다(상담사와 합의한 매핑, 2026-10-01).

    AI가 채우는 칸은 가정사항/상담내용/상담결과/특기사항 네 곳뿐이며,
    전부 "AI 초안" 상태로 상담사의 확인·수정·승인이 필요하다.
    """

    checklist_draft = (
        result.get("checklist_draft") or {}
    )

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    title_style = ParagraphStyle(
        "title",
        fontName=_PDF_FONT_NAME,
        fontSize=18,
        leading=22,
        alignment=1,
    )

    label_style = ParagraphStyle(
        "label",
        fontName=_PDF_FONT_NAME,
        fontSize=9,
        leading=12,
    )

    value_style = ParagraphStyle(
        "value",
        fontName=_PDF_FONT_NAME,
        fontSize=9,
        leading=14,
    )

    footer_style = ParagraphStyle(
        "footer",
        fontName=_PDF_FONT_NAME,
        fontSize=8,
        textColor=colors.grey,
    )

    label_fill = colors.Color(0.85, 0.93, 0.96)

    def _label(text):
        return Paragraph(text, label_style)

    def _value(text=""):
        return Paragraph(
            escape(text) if text else "",
            value_style,
        )

    def _multiline(text):
        return Paragraph(
            escape(text).replace("\n", "<br/>"),
            value_style,
        )

    # ---- 상단: 제목 + 결재란 ----
    approval_table = Table(
        [
            ["담당", "", ""],
            ["", "", ""],
        ],
        colWidths=[18 * mm] * 3,
        rowHeights=[6 * mm, 12 * mm],
    )
    approval_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), _PDF_FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    header_table = Table(
        [[Paragraph("아동 상담일지", title_style), approval_table]],
        colWidths=[126 * mm, 54 * mm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    # ---- 기본 정보 (좌: 날짜/아동/보호자/주소/상담종류,
    #      우: 상담교사/나이/성별/관계/전화번호) ----
    info_table = Table(
        [
            [_label("상담일지"), _value(), _label("상담교사"), _value()],
            [_label("아동명"), _value(), _label("나이"), _value()],
            [_label("보호자명"), _value(), _label("성별"), _value()],
            [_label("주소"), _value(), _label("관계"), _value()],
            [_label("상담종류"), _value(), _label("전화번호"), _value()],
        ],
        colWidths=[22 * mm, 68 * mm, 22 * mm, 68 * mm],
        rowHeights=[8 * mm] * 5,
    )
    info_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), label_fill),
                ("BACKGROUND", (2, 0), (2, -1), label_fill),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    reason_table = Table(
        [[_label("상담사유"), _value()]],
        colWidths=[22 * mm, 158 * mm],
        rowHeights=[14 * mm],
    )
    reason_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), label_fill),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    # ---- AI 초안 내용 (가정사항/상담내용/상담결과/특기사항) ----
    content_table = Table(
        [
            [
                _label("가정사항"),
                _multiline(
                    _build_family_situation_text(checklist_draft)
                ),
            ],
            [
                _label("상담내용"),
                _multiline(
                    result.get("counseling_note", "")
                    or "(없음)"
                ),
            ],
            [
                _label("상담결과"),
                _multiline(
                    checklist_draft.get(
                        "counselor_opinion_draft",
                        "",
                    )
                    or "(없음)"
                ),
            ],
            [
                _label("특기사항"),
                _multiline(_build_special_notes_text(result)),
            ],
        ],
        colWidths=[22 * mm, 158 * mm],
    )
    content_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), label_fill),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    flowables = [
        header_table,
        Spacer(1, 6 * mm),
        info_table,
        reason_table,
        Spacer(1, 2 * mm),
        content_table,
        Spacer(1, 4 * mm),
        Paragraph(
            "가정사항/상담내용/상담결과/특기사항은 AI가 생성한 초안이며, "
            "상담사의 확인·수정·승인이 필요합니다. 그 외 항목은 "
            "상담사가 직접 기입합니다.",
            footer_style,
        ),
    ]

    doc.build(flowables)

    return buffer.getvalue()


def build_download_form_html(
    result: dict,
) -> str:
    payload = json.dumps(
        result,
        ensure_ascii=False,
    )

    return f"""
    <section class="panel">
        <form method="post" action="/download" style="display: inline-block;">
            <input
                type="hidden"
                name="payload"
                value='{escape(payload, quote=True)}'
            >
            <button type="submit">
                결과 텍스트 파일로 다운로드
            </button>
        </form>

        <form method="post" action="/download-pdf" style="display: inline-block; margin-left: 8px;">
            <input
                type="hidden"
                name="payload"
                value='{escape(payload, quote=True)}'
            >
            <button type="submit">
                결과 PDF로 다운로드
            </button>
        </form>
    </section>
    """


# ============================================================
# 1. FastAPI 앱
# ============================================================

app = FastAPI(
    title="I-SPOT Pipeline Test",
)

register_case_workflow_routes(app)


# ============================================================
# 2. 기본 HTML
# ============================================================

def build_page(
    text="",
    input_mode="qa",
    case_id="",
    result=None,
    session_id=None,
    error=None,
):
    mode_qa_checked = "checked" if input_mode == "qa" else ""
    mode_child_checked = "checked" if input_mode == "child_only" else ""

    result_html = ""

    if error:
        result_html = f"""
        <section class="panel error-panel">
            <h2>오류</h2>
            <pre>{escape(str(error))}</pre>
        </section>
        """

    elif result:
        triage_html = build_triage_summary_html(
            result.get("major_types", {}),
            result.get("subtype_analysis", {}),
        )

        major_html = build_major_types_html(
            result.get("major_types", {}),
            result.get("subtype_analysis", {}),
            highlighted_labels=get_top_signal_labels(
                result.get("major_types", {}),
                result.get("subtype_analysis", {}),
            ),
        )

        subtype_html = build_subtypes_html(
            result.get("subtype_analysis", {})
        )

        result_html = f"""
        <section class="panel">
            {triage_html}
            <h2>1차 학대 위험신호</h2>
            {major_html}
        </section>

        <section class="panel">
            <h2>2차 세부 위험신호</h2>
            {subtype_html}
        </section>

        {build_approval_form_html(session_id, result)}

        {build_download_form_html(result)}
        """

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <title>I-SPOT Pipeline Test</title>

        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                background: #f5f7fb;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    sans-serif;
                color: #1f2937;
            }}

            .container {{
                max-width: 1100px;
                margin: 40px auto;
                padding: 0 24px 80px;
            }}

            .header {{
                margin-bottom: 24px;
            }}

            .header h1 {{
                margin-bottom: 8px;
            }}

            .header p {{
                margin: 0;
                color: #6b7280;
            }}

            .panel {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 20px;
                box-shadow:
                    0 4px 14px rgba(0, 0, 0, 0.04);
            }}

            .panel h2 {{
                margin-top: 0;
                font-size: 20px;
            }}

            .mode-area {{
                display: flex;
                gap: 24px;
                margin-bottom: 18px;
            }}

            textarea {{
                width: 100%;
                min-height: 220px;
                resize: vertical;
                border: 1px solid #d1d5db;
                border-radius: 12px;
                padding: 16px;
                font-size: 15px;
                line-height: 1.6;
            }}

            button {{
                margin-top: 16px;
                border: none;
                border-radius: 10px;
                padding: 12px 22px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                background: #111827;
                color: white;
            }}

            button:hover {{
                opacity: 0.9;
            }}

            .major-grid {{
                display: grid;
                grid-template-columns:
                    repeat(4, minmax(0, 1fr));
                gap: 12px;
            }}

            .major-card {{
                padding: 20px 14px;
                border-radius: 12px;
                border: 1px solid #d1d5db;
                text-align: center;
                background: #f9fafb;
                color: #6b7280;
                font-weight: 700;
            }}

            .major-card.detected {{
                background: #fee2e2;
                border-color: #f87171;
                color: #991b1b;
            }}

            .subtype-block {{
                border-top: 1px solid #e5e7eb;
                padding-top: 18px;
                margin-top: 18px;
            }}

            .subtype-block:first-child {{
                border-top: none;
                padding-top: 0;
                margin-top: 0;
            }}

            .subtype-title {{
                font-size: 17px;
                font-weight: 700;
                margin-bottom: 10px;
            }}

            .major-label {{
                display: inline-block;
                margin-bottom: 12px;
                padding: 6px 10px;
                border-radius: 8px;
                background: #eef2ff;
                color: #3730a3;
                font-weight: 700;
            }}

            .evidence {{
                background: #f9fafb;
                border-left: 4px solid #9ca3af;
                padding: 12px 14px;
                margin-top: 10px;
                border-radius: 8px;
            }}

            .evidence-quote {{
                font-weight: 600;
                margin-bottom: 8px;
            }}

            .meta {{
                font-size: 13px;
                color: #6b7280;
                line-height: 1.6;
            }}

            .borderline-tag {{
                display: inline-block;
                font-size: 11px;
                font-weight: 700;
                color: #1e40af;
                background: #dbeafe;
                border-radius: 999px;
                padding: 1px 8px;
                margin-left: 8px;
                vertical-align: middle;
            }}

            .needs-review-tag {{
                display: inline-block;
                font-size: 11px;
                font-weight: 700;
                color: #b45309;
                background: #fef3c7;
                border-radius: 999px;
                padding: 1px 8px;
                margin-left: 4px;
            }}

            .triage-summary {{
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 16px 18px;
                margin-bottom: 18px;
                background: #fafafa;
            }}

            .triage-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 6px;
            }}

            .triage-count {{
                font-size: 13px;
                font-weight: 600;
                color: #374151;
                background: #eef2ff;
                padding: 2px 10px;
                border-radius: 999px;
            }}

            .triage-note {{
                font-size: 12px;
                color: #9ca3af;
                margin-bottom: 10px;
            }}

            .triage-row {{
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 6px 0;
                border-top: 1px solid #eee;
            }}

            .triage-row:first-of-type {{
                border-top: none;
            }}

            .triage-label {{
                font-weight: 700;
                min-width: 70px;
            }}

            .triage-badge {{
                font-size: 12px;
                font-weight: 600;
                color: #374151;
                background: #f3f4f6;
                border: 1px solid #e5e7eb;
                padding: 2px 10px;
                border-radius: 999px;
            }}

            .triage-empty {{
                font-size: 13px;
                color: #9ca3af;
            }}

            .triage-row.top-signal {{
                background: #fff7ed;
                border-top-color: #fdba74;
                border-radius: 8px;
                padding-left: 8px;
                padding-right: 8px;
            }}

            .triage-highlight-tag {{
                display: inline-block;
                font-size: 11px;
                font-weight: 700;
                color: #9a3412;
                background: #ffedd5;
                border-radius: 999px;
                padding: 1px 8px;
                margin-left: auto;
            }}

            .major-card.detected.top-signal {{
                border-width: 3px;
                border-color: #ea580c;
                box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.15);
            }}

            .tdraft-split {{
                display: grid;
                grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
                gap: 16px;
            }}

            @media (max-width: 860px) {{
                .tdraft-split {{
                    grid-template-columns: 1fr;
                }}
            }}

            .tdraft-panel {{
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                overflow: hidden;
                min-width: 0;
            }}

            .tdraft-panel-header {{
                padding: 10px 14px;
                font-weight: 700;
                background: #f9fafb;
                border-bottom: 1px solid #e5e7eb;
            }}

            .tdraft-transcript {{
                max-height: 560px;
                overflow-y: auto;
                padding: 6px 0;
            }}

            .tdraft-line {{
                display: grid;
                grid-template-columns: 48px 56px minmax(0, 1fr);
                gap: 8px;
                padding: 6px 14px;
                font-size: 13.5px;
                border-left: 3px solid transparent;
            }}

            .tdraft-line.k .tdraft-sp {{
                color: #b45309;
            }}

            .tdraft-ts {{
                font-family: ui-monospace, Menlo, Consolas, monospace;
                font-size: 11.5px;
                color: #9ca3af;
                padding-top: 2px;
            }}

            .tdraft-sp {{
                font-size: 11.5px;
                font-weight: 700;
                color: #6b7280;
                padding-top: 2px;
            }}

            .tdraft-flash {{
                background: #fff3c4 !important;
                border-left-color: #d97706;
            }}

            .tdraft-field {{
                border-bottom: 1px solid #e5e7eb;
                padding: 12px 16px;
            }}

            .tdraft-field:last-child {{
                border-bottom: none;
            }}

            .tdraft-field-head {{
                font-weight: 700;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                gap: 6px;
            }}

            .tdraft-field-body {{
                font-size: 13.5px;
                color: #374151;
            }}

            .tdraft-point {{
                padding: 6px 0;
                border-top: 1px dashed #eee;
            }}

            .tdraft-point:first-child {{
                border-top: none;
            }}

            .tdraft-cite {{
                font-family: ui-monospace, Menlo, Consolas, monospace;
                font-size: 11px;
                border: 1px solid #e5e7eb;
                background: #f3f4f6;
                color: #1d5c63;
                border-radius: 5px;
                padding: 0 5px;
                margin-left: 4px;
                text-decoration: none;
                white-space: nowrap;
            }}

            .tdraft-cite:hover {{
                border-color: #1d5c63;
            }}

            .tdraft-textarea {{
                width: 100%;
                min-height: 72px;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 8px 10px;
                font: inherit;
                font-size: 13.5px;
                resize: vertical;
            }}

            .tag.t-ai {{
                display: inline-block;
                font-size: 11px;
                font-weight: 700;
                color: #3730a3;
                background: #eef2ff;
                border-radius: 999px;
                padding: 1px 8px;
            }}

            .tag.t-manual {{
                display: inline-block;
                font-size: 11px;
                font-weight: 700;
                color: #b45309;
                background: #fef3c7;
                border-radius: 999px;
                padding: 1px 8px;
            }}

            .closest-snippet {{
                margin-top: 8px;
                padding: 8px 10px;
                background: #fef3c7;
                border-left: 3px solid #d97706;
                border-radius: 6px;
                font-size: 12px;
                color: #78350f;
                line-height: 1.6;
            }}

            .text-box {{
                white-space: pre-wrap;
                line-height: 1.75;
                background: #f9fafb;
                padding: 16px;
                border-radius: 10px;
            }}

            .empty {{
                color: #6b7280;
            }}

            .ai-banner {{
                background: #eff6ff;
                border: 1px solid #93c5fd;
                color: #1e3a8a;
                padding: 10px 14px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                margin-bottom: 18px;
            }}

            .checklist-category {{
                font-size: 15px;
                font-weight: 700;
                margin: 18px 0 10px;
            }}

            .checklist-category:first-child {{
                margin-top: 0;
            }}

            .checklist-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }}

            .case-id-input {{
                width: 100%;
                padding: 12px 14px;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                font-size: 14px;
                margin-bottom: 8px;
            }}

            textarea.editable {{
                background: white;
                border-color: #93c5fd;
            }}

            .checklist-edit-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-bottom: 8px;
            }}

            .checklist-edit-item {{
                display: inline-flex;
                flex-direction: column;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 13px;
                background: #f9fafb;
                cursor: pointer;
            }}

            .checklist-edit-item.has-evidence {{
                border-color: #f87171;
                background: #fee2e2;
            }}

            .checklist-edit-item input[type="checkbox"] {{
                margin-right: 6px;
            }}

            .checklist-edit-item .checklist-evidence-box {{
                margin: 6px 0 0;
                background: white;
            }}

            .confirm-panel ul {{
                padding-left: 20px;
            }}

            .confirm-links {{
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin-top: 16px;
            }}

            .confirm-links a {{
                display: inline-block;
                padding: 10px 18px;
                border-radius: 10px;
                background: #111827;
                color: white;
                text-decoration: none;
                font-size: 14px;
                font-weight: 600;
            }}

            table.case-table {{
                width: 100%;
                border-collapse: collapse;
            }}

            table.case-table th,
            table.case-table td {{
                text-align: left;
                padding: 10px 12px;
                border-bottom: 1px solid #e5e7eb;
                font-size: 14px;
            }}

            table.case-table a {{
                color: #2563eb;
                text-decoration: none;
                font-weight: 600;
            }}

            .status-badge {{
                display: inline-block;
                padding: 2px 10px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 700;
            }}

            .status-badge.approved {{
                background: #dcfce7;
                color: #166534;
            }}

            .status-badge.draft {{
                background: #fef3c7;
                color: #92400e;
            }}

            @media print {{
                .no-print {{
                    display: none !important;
                }}

                body {{
                    background: white;
                }}

                .panel {{
                    box-shadow: none;
                    border: none;
                }}
            }}

            .checklist-pill {{
                border: 1px solid #d1d5db;
                border-radius: 999px;
                padding: 6px 14px;
                font-size: 13px;
                color: #9ca3af;
                background: #f9fafb;
            }}

            .checklist-pill.checked {{
                border-color: #f87171;
                background: #fee2e2;
                color: #991b1b;
                font-weight: 600;
                cursor: pointer;
                padding: 0;
            }}

            .checklist-pill.checked summary {{
                padding: 6px 14px;
                list-style: none;
                cursor: pointer;
            }}

            .checklist-pill.checked summary::-webkit-details-marker {{
                display: none;
            }}

            .checklist-pill.checked[open] {{
                width: 100%;
            }}

            .checklist-evidence-box {{
                margin: 0 14px 10px;
                padding: 10px 12px;
                background: white;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 400;
                color: #374151;
                line-height: 1.6;
            }}

            .checklist-evidence-box div {{
                margin-bottom: 4px;
            }}

            .safety-item {{
                border-top: 1px solid #e5e7eb;
                padding: 10px 0;
            }}

            .safety-item:first-child {{
                border-top: none;
            }}

            .safety-item-title {{
                font-weight: 600;
                margin-bottom: 4px;
            }}

            .safety-item-evidence {{
                font-size: 13px;
                color: #374151;
                background: #f9fafb;
                border-radius: 8px;
                padding: 8px 12px;
                margin-top: 4px;
            }}

            .safety-item-empty {{
                font-size: 13px;
                color: #9ca3af;
            }}

            .review-note {{
                margin-top: 16px;
                font-size: 12px;
                color: #6b7280;
                text-align: center;
            }}

            .error-panel {{
                border-color: #fca5a5;
                background: #fef2f2;
            }}

            pre {{
                white-space: pre-wrap;
                word-break: break-word;
            }}

            @media (max-width: 760px) {{
                .major-grid {{
                    grid-template-columns:
                        repeat(2, minmax(0, 1fr));
                }}
            }}
        </style>
    </head>

    <body>
        <div class="container">

            <div class="header">
                <h1>I-SPOT 전체 파이프라인 테스트</h1>

                <p>
                    1차 학대 위험신호 →
                    2차 세부 위험신호 →
                    상담 요약 →
                    상담일지
                </p>
            </div>

            <section class="panel">

                <form method="post" action="/analyze">

                    <h2>사례 ID</h2>

                    <input
                        type="text"
                        name="case_id"
                        class="case-id-input"
                        placeholder="예: CASE-2026-0001 (같은 사례의 다음 회기는 동일한 ID를 입력하세요)"
                        value="{escape(case_id)}"
                        required
                    >

                    <h2>입력 방식</h2>

                    <div class="mode-area">

                        <label>
                            <input
                                type="radio"
                                name="input_mode"
                                value="qa"
                                {mode_qa_checked}
                            >
                            상담사 + 아동 대화
                        </label>

                        <label>
                            <input
                                type="radio"
                                name="input_mode"
                                value="child_only"
                                {mode_child_checked}
                            >
                            아동 발화만
                        </label>

                    </div>

                    <textarea
                        name="text"
                        placeholder="상담 내용을 입력하세요."
                    >{escape(text)}</textarea>

                    <button type="submit">
                        분석하기
                    </button>

                </form>

            </section>

            {result_html}

        </div>
    </body>
    </html>
    """


# ============================================================
# 2-1. 우선순위 참고 신호 HTML (신규, 기존 major/subtype 표시는 그대로 둠)
# ============================================================

_EVIDENCE_STRENGTH_RANK = {"높음": 3, "중간": 2, "낮음": 1}

_MAJOR_TYPE_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


def _rank_detected_types(major_types, subtype_analysis=None):
    """
    탐지된 유형들을 "이 사례 안에서" 근거 신호(세부유형 개수, 최고
    근거강도)가 더 뚜렷한 순서로 정렬한다(2026-10-08 추가).

    이건 유형 자체의 본질적 위험도(신체학대가 정서학대보다 항상 더
    위험한가 같은 임상적 판단)를 매기는 게 아니다 — 그건 기관/
    슈퍼바이저의 사례관리 지침에서 가져와야 할 기준이라 여기서
    만들지 않는다(설계 논의 참고). 여기서 하는 건 오직 "같이 탐지된
    유형들 중 이 사례에서 어느 쪽 근거가 상대적으로 더 뚜렷한가"
    비교뿐이다.

    정렬 기준(우선순위 순): 최고 근거강도 -> 세부유형 개수. 동점이면
    둘 다 "공동 1위"로 처리한다(강제로 하나만 고르지 않는다).
    """

    detected_labels = [
        label
        for label in _MAJOR_TYPE_LABELS
        if major_types.get(label, {}).get("detected", False)
    ]

    subtypes_by_major = {
        result.get("major_type"): result.get("subtypes", [])
        for result in (subtype_analysis or {}).get("results", [])
    }

    ranked = []

    for label in detected_labels:
        subtypes = subtypes_by_major.get(label, [])
        subtype_count = len(subtypes)

        strengths = [
            evidence.get("evidence_strength")
            for subtype in subtypes
            for evidence in subtype.get("evidences", [])
            if evidence.get("evidence_strength") in _EVIDENCE_STRENGTH_RANK
        ]

        top_strength = (
            max(strengths, key=lambda s: _EVIDENCE_STRENGTH_RANK[s])
            if strengths
            else None
        )

        strength_rank = _EVIDENCE_STRENGTH_RANK.get(top_strength, 0)

        ranked.append(
            {
                "label": label,
                "subtype_count": subtype_count,
                "top_strength": top_strength,
                "sort_key": (strength_rank, subtype_count),
            }
        )

    ranked.sort(key=lambda r: r["sort_key"], reverse=True)
    return ranked


def get_top_signal_labels(major_types, subtype_analysis=None):
    """
    같이 탐지된 유형이 2개 이상일 때만, 이 사례 안에서 근거 신호가
    가장 뚜렷한 유형(공동 1위 포함)을 반환한다. 1개만 탐지됐거나
    아무 신호가 없으면(세부유형도 근거강도도 전혀 없으면) 빈 리스트를
    반환한다 — 비교할 대상이 없거나 강조할 근거 자체가 없을 때는
    강조하지 않는다.
    """

    ranked = _rank_detected_types(major_types, subtype_analysis)

    if len(ranked) < 2:
        return []

    top_key = ranked[0]["sort_key"]

    if top_key == (0, 0):
        return []

    return [r["label"] for r in ranked if r["sort_key"] == top_key]


def build_triage_summary_html(major_types, subtype_analysis=None):
    """
    여러 케이스를 훑어볼 때 우선순위를 가늠할 수 있도록, 서로 다른
    신호 세 가지를 뱃지로 나란히 보여준다(2026-10-08 추가). 기존
    build_major_types_html/build_subtypes_html은 그대로 두고 이 함수를
    추가로 호출하는 방식이다 — 둘 다 그대로 보여주고 이 카드는 위에
    요약만 더해준다.

    하나의 "위험도" 점수로 합치지 않는다 — 확신도(얼마나 명확한 근거인가)
    와 복합도(몇 가지 다른 방식의 행위가 겹쳤는가)는 서로 다른 의미라
    하나로 합치면 상담사가 오독할 위험이 있다(둘 다 낮은데 등급만
    높게 나오거나, 그 반대인 경우를 구분 못 하게 된다). 그래서 신호를
    따로따로 보여주고, 심각도 판단 자체는 하지 않는다 — 참고용이며
    최종 판단은 상담사가 근거 원문을 직접 보고 내린다.

    - 탐지된 유형 수: 1차가 detected=True로 본 대분류 개수(0~4)
    - 세부유형 개수: 그 대분류 아래 2차 분석에서 서로 다른 세부유형이
      몇 개나 잡혔는가(여러 방식의 행위가 겹쳐 있는지를 보는 복합도)
    - 최고 근거강도: 그 대분류의 근거들 중 가장 높은 evidence_strength
      (낮음/중간/높음 중 최댓값)

    복합 유형(2개 이상 탐지)일 때는, 같이 탐지된 유형들 중 이 사례
    안에서 근거 신호가 가장 뚜렷한 쪽에 강조 표시를 추가한다(유형의
    본질적 위험도가 아니라 "이 사례에서 상대적으로 더 뚜렷한 근거"라는
    뜻 — get_top_signal_labels 참고).
    """

    detected_labels = [
        label
        for label in _MAJOR_TYPE_LABELS
        if major_types.get(label, {}).get("detected", False)
    ]

    ranked = _rank_detected_types(major_types, subtype_analysis)
    ranked_by_label = {r["label"]: r for r in ranked}
    top_labels = set(get_top_signal_labels(major_types, subtype_analysis))

    rows = []

    for label in detected_labels:
        info = ranked_by_label.get(label, {})
        subtype_count = info.get("subtype_count", 0)
        top_strength = info.get("top_strength") or "-"

        is_top = label in top_labels
        row_class = "triage-row top-signal" if is_top else "triage-row"
        highlight_tag = (
            '<span class="triage-highlight-tag">이 사례에서 근거 가장 뚜렷함</span>'
            if is_top
            else ""
        )

        rows.append(
            f"""
            <div class="{row_class}">
                <span class="triage-label">{escape(label)}</span>
                <span class="triage-badge">세부유형 {subtype_count}개</span>
                <span class="triage-badge">최고 근거강도 {escape(str(top_strength))}</span>
                {highlight_tag}
            </div>
            """
        )

    body = (
        "".join(rows)
        if rows
        else '<div class="triage-empty">탐지된 유형이 없습니다.</div>'
    )

    return f"""
    <div class="triage-summary">
        <div class="triage-header">
            <strong>우선순위 참고 신호</strong>
            <span class="triage-count">탐지된 유형 {len(detected_labels)}개 / {len(_MAJOR_TYPE_LABELS)}개</span>
        </div>
        <div class="triage-note">
            심각도 점수가 아닙니다 — 여러 신호를 참고용으로만 보여줍니다.
            "근거 가장 뚜렷함" 표시도 유형 자체의 위험도가 아니라, 같이
            탐지된 유형들 중 이 사례에서 근거가 상대적으로 더 많이
            나온 쪽이라는 뜻입니다. 최종 판단은 근거 원문을 직접
            확인해 주세요.
        </div>
        {body}
    </div>
    """


# ============================================================
# 3. 1차 대분류 HTML
# ============================================================

def build_major_types_html(
    major_types,
    subtype_analysis=None,
    highlighted_labels=None,
):
    """
    subtype_analysis를 함께 넘기면, 1차가 탐지했지만 2차 세부유형
    분석에서 그 대분류에 해당하는 근거를 하나도 찾지 못한 경우
    "AI 근거 확인 필요" 안내를 함께 보여준다 — 1차가 표준 문진
    질문 문구만으로 오탐하고 아동은 부인한 경우가 대표적이다.
    실제로 유형이 없다는 뜻이 아니라, 상담사가 직접 원문을 봐야
    한다는 뜻이다.

    highlighted_labels(선택, 기본값 None — 기존 호출부는 동작이
    그대로다)를 넘기면 해당 카드에 추가 강조 테두리를 준다.
    get_top_signal_labels()가 반환하는 라벨을 그대로 넘기면 된다 —
    유형의 본질적 위험도가 아니라 "복합 탐지된 유형들 중 이 사례에서
    근거가 더 뚜렷한 쪽"이라는 뜻(build_triage_summary_html 참고).
    """

    highlighted_labels = set(highlighted_labels or [])

    labels = [
        "신체학대",
        "정서학대",
        "성학대",
        "방임",
    ]

    detected_majors_in_subtypes = {
        result.get("major_type")
        for result in (subtype_analysis or {}).get("results", [])
    }

    cards = []

    for label in labels:
        prediction = major_types.get(
            label,
            {},
        )

        detected = prediction.get(
            "detected",
            False,
        )

        card_class = (
            "major-card detected"
            if detected
            else "major-card"
        )

        if detected and label in highlighted_labels:
            card_class += " top-signal"

        status = (
            "위험신호 탐지"
            if detected
            else "미탐지"
        )

        no_subtype_evidence = (
            detected
            and subtype_analysis is not None
            and label not in detected_majors_in_subtypes
        )

        note = (
            '<div style="margin-top: 6px;">'
            '<span class="needs-review-tag">'
            "AI 근거 확인 필요 — 2차 분석에서 근거를 찾지 못했습니다"
            "</span></div>"
            if no_subtype_evidence
            else ""
        )

        cards.append(
            f"""
            <div class="{card_class}">
                <div>{escape(label)}</div>
                <div
                    style="
                        margin-top: 8px;
                        font-size: 13px;
                        font-weight: 500;
                    "
                >
                    {status}
                </div>
                {note}
            </div>
            """
        )

    return f"""
    <div class="major-grid">
        {''.join(cards)}
    </div>
    """


# ============================================================
# 4. 2차 세부유형 HTML
# ============================================================

def build_subtypes_html(subtype_analysis):
    results = subtype_analysis.get(
        "results",
        [],
    )

    if not results:
        note = subtype_analysis.get(
            "note",
            "탐지된 세부 위험신호가 없습니다.",
        )

        return f"""
        <div class="empty">
            {escape(note)}
        </div>
        """

    blocks = []

    for major_result in results:
        major_type = major_result.get(
            "major_type",
            "",
        )

        subtypes = major_result.get(
            "subtypes",
            [],
        )

        subtype_blocks = []

        for subtype in subtypes:
            subtype_name = subtype.get(
                "type",
                "",
            )

            evidences = subtype.get(
                "evidences",
                [],
            )

            evidence_blocks = []

            for evidence in evidences:
                matched = evidence.get(
                    "matched_evidence"
                )

                original = evidence.get(
                    "evidence",
                    "",
                )

                display_evidence = (
                    matched
                    if matched
                    else original
                )

                verified = evidence.get(
                    "evidence_verified",
                    False,
                )

                method = evidence.get(
                    "evidence_match_method",
                    "",
                )

                strength = evidence.get(
                    "evidence_strength",
                    "",
                )

                strength_reason = evidence.get(
                    "strength_reason",
                    "",
                )

                action = evidence.get(
                    "action"
                )

                instrument = evidence.get(
                    "instrument"
                )

                body_part = evidence.get(
                    "target_body_part"
                )

                timestamps = evidence.get(
                    "timestamps"
                )

                closest_snippet = evidence.get(
                    "closest_source_snippet"
                )

                meta_parts = []

                if strength:
                    meta_parts.append(
                        f"근거 강도: {escape(str(strength))}"
                    )

                if strength_reason:
                    meta_parts.append(
                        f"근거 강도 이유: {escape(str(strength_reason))}"
                    )

                if action:
                    meta_parts.append(
                        f"행위: {escape(str(action))}"
                    )

                if instrument:
                    meta_parts.append(
                        f"도구: {escape(str(instrument))}"
                    )

                if body_part:
                    meta_parts.append(
                        f"신체 부위: {escape(str(body_part))}"
                    )

                timestamp_html = ""

                if timestamps:
                    start_sec = timestamps["start_ms"] / 1000
                    end_sec = timestamps["end_ms"] / 1000

                    timestamp_html = (
                        '<div style="margin-top: 4px;">'
                        '<button type="button" class="play-btn" '
                        f'onclick="playAt({start_sec})">'
                        f"▶ 원본 음성 {start_sec:.1f}s ~ {end_sec:.1f}s 재생"
                        "</button></div>"
                    )

                if verified:
                    meta_parts.append(
                        f"근거 검증: {escape(str(method))}"
                    )
                elif closest_snippet:
                    meta_parts.append(
                        "근거 검증: AI 인용문이 원문과 정확히 "
                        "일치하지 않음 — 아래는 원문에서 가장 "
                        "비슷한 부분(참고용)"
                    )
                else:
                    meta_parts.append(
                        "근거 검증: AI 인용문을 원문에서 찾지 "
                        "못함 — 원문 재확인 필요"
                    )

                closest_snippet_html = (
                    f"""
                    <div class="closest-snippet">
                        원문에서 가장 비슷한 부분:
                        “{escape(str(closest_snippet))}”
                    </div>
                    """
                    if not verified and closest_snippet
                    else ""
                )

                evidence_blocks.append(
                    f"""
                    <div class="evidence">

                        <div class="evidence-quote">
                            “{escape(str(display_evidence))}”
                        </div>

                        <div class="meta">
                            {'<br>'.join(meta_parts)}
                        </div>

                        {timestamp_html}

                        {closest_snippet_html}

                    </div>
                    """
                )

            subtype_blocks.append(
                f"""
                <div class="subtype-block">

                    <div class="subtype-title">
                        {escape(subtype_name)}
                        {'<span class="borderline-tag">판단 애매 — 상담사 확인</span>' if subtype.get("borderline") else ""}
                    </div>

                    {
                        ''.join(evidence_blocks)
                        if evidence_blocks
                        else '<div class="empty">근거 발화 없음</div>'
                    }

                </div>
                """
            )

        blocks.append(
            f"""
            <div class="subtype-block">

                <div class="major-label">
                    {escape(major_type)}
                </div>

                {''.join(subtype_blocks)}

            </div>
            """
        )

    return "".join(blocks)


# ============================================================
# 5. AI 상담 체크리스트 초안 HTML
# ============================================================

def build_evidence_list_html(
    evidence_entries,
):
    lines = []

    for entry in evidence_entries:
        quote = entry.get(
            "matched_evidence"
        ) or entry.get(
            "evidence",
            "",
        )

        # LLM이 원문을 그대로 인용하지 못해 evidence_verified가
        # False인 근거도(이제는 숨기지 않고) 보여주되, 상담사가
        # 원문을 직접 확인해야 함을 표시한다.
        review_tag = (
            ""
            if entry.get("evidence_verified")
            else ' <span class="needs-review-tag">원문 재확인 필요</span>'
        )

        closest_snippet = entry.get("closest_source_snippet")

        closest_snippet_html = (
            f'<div class="closest-snippet">원문에서 가장 비슷한 부분: '
            f'“{escape(str(closest_snippet))}”</div>'
            if not entry.get("evidence_verified") and closest_snippet
            else ""
        )

        lines.append(
            f"<div>“{escape(str(quote))}”{review_tag}</div>"
            f"{closest_snippet_html}"
        )

    return "".join(lines)


def build_checklist_pills_html(
    checklist,
    category,
):
    pills = []

    for entry in checklist:
        if entry.get("category") != category:
            continue

        item = entry.get(
            "item",
            "",
        )

        evidence = entry.get(
            "evidence",
            [],
        )

        if entry.get("suggested"):
            evidence_html = build_evidence_list_html(
                evidence
            )

            pills.append(
                f"""
                <details class="checklist-pill checked">
                    <summary>☑ {escape(item)}</summary>
                    <div class="checklist-evidence-box">
                        {evidence_html}
                    </div>
                </details>
                """
            )
        else:
            pills.append(
                f"""
                <div class="checklist-pill">
                    ☐ {escape(item)}
                </div>
                """
            )

    return f"""
    <div class="checklist-grid">
        {''.join(pills)}
    </div>
    """


def build_safety_assessment_html(
    safety_assessment_evidence,
):
    categories = [
        "피해아동",
        "가족구성원",
        "사례관리대상자",
    ]

    blocks = []

    for category in categories:
        items_html = []

        for entry in safety_assessment_evidence:
            if entry.get("category") != category:
                continue

            item = entry.get(
                "item",
                "",
            )

            evidence = entry.get(
                "evidence",
                [],
            )

            if evidence:
                evidence_html = build_evidence_list_html(
                    evidence
                )

                items_html.append(
                    f"""
                    <div class="safety-item">
                        <div class="safety-item-title">
                            {escape(item)}
                        </div>
                        <div class="safety-item-evidence">
                            {evidence_html}
                        </div>
                    </div>
                    """
                )
            else:
                items_html.append(
                    f"""
                    <div class="safety-item">
                        <div class="safety-item-title">
                            {escape(item)}
                        </div>
                        <div class="safety-item-empty">
                            관련 근거를 찾지 못했습니다. (등급은 상담사가 직접 판단)
                        </div>
                    </div>
                    """
                )

        blocks.append(
            f"""
            <div class="checklist-category">
                {escape(category)}
            </div>
            {''.join(items_html)}
            """
        )

    return "".join(blocks)


def build_checklist_draft_html(
    checklist_draft,
):
    if not checklist_draft:
        return ""

    household_html = build_checklist_pills_html(
        checklist_draft.get(
            "checklist",
            [],
        ),
        "가정상황",
    )

    child_trait_html = build_checklist_pills_html(
        checklist_draft.get(
            "checklist",
            [],
        ),
        "아동 특성",
    )

    safety_html = build_safety_assessment_html(
        checklist_draft.get(
            "safety_assessment_evidence",
            [],
        )
    )

    environment = checklist_draft.get(
        "environment_key_person"
    )

    if environment:
        environment_evidence_html = build_evidence_list_html(
            environment.get(
                "evidence",
                [],
            )
        )

        environment_html = f"""
        <div class="checklist-category">환경</div>
        <div class="safety-item">
            <div class="safety-item-title">
                {escape(environment.get("item", ""))}
                — {escape(environment.get("status", ""))}
            </div>
            <div class="safety-item-evidence">
                {environment_evidence_html}
            </div>
        </div>
        """
    else:
        environment_html = """
        <div class="checklist-category">환경</div>
        <div class="safety-item-empty">
            신뢰할 만한 주위 사람 관련 언급을 찾지 못했습니다.
        </div>
        """

    problem_history = escape(
        checklist_draft.get(
            "problem_history_draft",
            "",
        )
    )

    counselor_opinion = escape(
        checklist_draft.get(
            "counselor_opinion_draft",
            "",
        )
    )

    return f"""
    <section class="panel">
        <h2>AI 상담 체크리스트 초안</h2>

        <div class="ai-banner">
            상담사가 확인하지 않은 AI 제안입니다.
            체크된 항목은 근거를 확인한 뒤 승인해주세요.
        </div>

        <div class="checklist-category">가정상황</div>
        {household_html}

        <div class="checklist-category">아동 특성</div>
        {child_trait_html}

        <div class="checklist-category">
            안전영역 관련 근거
            <span style="font-weight: 400; font-size: 12px; color: #6b7280;">
                (등급은 AI가 매기지 않습니다 — 상담사가 직접 판단)
            </span>
        </div>
        {safety_html}

        {environment_html}

        <div class="checklist-category">문제력 초안</div>
        <div class="text-box">
            {problem_history if problem_history else "생성된 초안이 없습니다."}
        </div>

        <div class="checklist-category">상담원 소견 초안</div>
        <div class="text-box">
            {counselor_opinion if counselor_opinion else "생성된 초안이 없습니다."}
        </div>

        <div class="review-note">
            모든 제안 항목은 원문 근거 검증을 거쳤지만,
            최종 확인·수정·승인은 상담사가 직접 해야 합니다.
        </div>
    </section>
    """


# ============================================================
# 6. 승인 워크플로 + 사례관리 HTML
# ============================================================

def build_checklist_edit_html(
    checklist_draft: dict,
) -> str:
    def render_category(category):
        blocks = []

        for item in checklist_draft.get(
            "checklist",
            [],
        ):
            if item.get("category") != category:
                continue

            if not item.get("suggested"):
                continue

            key = f"{item['category']}::{item['item']}"

            checked_attr = (
                "checked"
                if item.get("suggested")
                else ""
            )

            evidence = item.get(
                "evidence",
                [],
            )

            has_evidence_class = (
                " has-evidence"
                if evidence
                else ""
            )

            evidence_html = (
                f'<div class="checklist-evidence-box">'
                f'{build_evidence_list_html(evidence)}</div>'
                if evidence
                else ""
            )

            blocks.append(
                f"""
                <label class="checklist-edit-item{has_evidence_class}">
                    <span>
                        <input
                            type="checkbox"
                            name="checked_items"
                            value="{escape(key, quote=True)}"
                            {checked_attr}
                        >
                        {escape(item['item'])}
                    </span>
                    {evidence_html}
                </label>
                """
            )

        return "".join(blocks)

    environment = checklist_draft.get(
        "environment_key_person"
    )

    if environment:
        environment_evidence_html = build_evidence_list_html(
            environment.get(
                "evidence",
                [],
            )
        )

        environment_html = f"""
        <div class="checklist-category">환경</div>
        <div class="safety-item">
            <div class="safety-item-title">
                {escape(environment.get("item", ""))}
                — {escape(environment.get("status", ""))}
            </div>
            <div class="safety-item-evidence">
                {environment_evidence_html}
            </div>
        </div>
        """
    else:
        environment_html = """
        <div class="checklist-category">환경</div>
        <div class="safety-item-empty">
            신뢰할 만한 주위 사람 관련 언급을 찾지 못했습니다.
        </div>
        """

    return f"""
    <section class="panel">
        <h2>AI 상담 체크리스트 초안 — 검수 후 승인</h2>

        <div class="ai-banner">
            체크된 항목은 AI 제안입니다. 근거를 확인하고,
            잘못됐거나 빠진 항목은 직접 체크박스를 수정한 뒤 승인해주세요.
        </div>

        <div class="checklist-category">가정상황</div>
        <div class="checklist-edit-grid">
            {render_category("가정상황")}
        </div>

        <div class="checklist-category">아동 특성</div>
        <div class="checklist-edit-grid">
            {render_category("아동 특성")}
        </div>

        {environment_html}
    </section>
    """


# ============================================================
# 2-2. 축어록 + 기록 초안 분할 화면 (신규, 2026-10-08)
# ============================================================
# 음성 세션(infer_audio_session.analyze_audio_session)이 만드는
# result["segments"]/result["record_draft"]가 있을 때만 렌더링한다.
# 텍스트/PDF 입력 경로는 이 필드가 없으므로 호출부가 조건부로만
# 이 함수를 부르면 된다(기존 1차/2차 표시는 그대로 두고 추가하는
# 화면이라 build_major_types_html 등은 건드리지 않았다).
#
# "향후 계획" 섹션은 없다 — 질문 추천은 자유생성보다 검증된 질문
# 은행에서 RAG로 찾는 쪽이 안전한데 지금 그 은행이 없어서 뺐다
# (record_draft_llm.py 모듈 docstring 참고, 2026-10-08 논의).

_SPEAKER_DISPLAY_LABEL = {
    "COUNSELOR": "상담원",
    "CHILD": "아동",
}


def _format_timestamp_label(start_ms):
    total_seconds = int(start_ms or 0) // 1000
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


def _build_citation_chips_html(segment_ids, segment_lookup=None):
    """
    근거 칩에 segment_id 원문("seg_002")이 아니라 타임스탬프("00:31")를
    보여준다 — 상담사가 실제로 필요한 건 녹취의 어느 지점인지지,
    내부 ID가 아니다. segment_lookup이 없거나 해당 id를 못 찾으면
    ID 문자열로 대체 표시한다(안전망).
    """

    segment_lookup = segment_lookup or {}

    chips = []

    for segment_id in segment_ids:
        segment = segment_lookup.get(str(segment_id))

        label = (
            _format_timestamp_label(segment.get("start_ms", 0))
            if segment
            else str(segment_id)
        )

        chips.append(
            f'<a class="tdraft-cite" href="#{escape(str(segment_id), quote=True)}" '
            f'onclick="return tdraftJump(\'{escape(str(segment_id), quote=True)}\')">'
            f"{escape(label)}</a>"
        )

    return "".join(chips)


def _build_statement_points_html(points, empty_text, segment_lookup=None):
    if not points:
        return f'<p class="triage-empty">{escape(empty_text)}</p>'

    items = []

    for point in points:
        items.append(
            f"""
            <div class="tdraft-point">
                <span>{escape(point.get("text", ""))}</span>
                {_build_citation_chips_html(point.get("segment_ids", []), segment_lookup)}
            </div>
            """
        )

    return "".join(items)


def _build_risk_points_html(points, segment_lookup=None):
    if not points:
        return '<p class="triage-empty">탐지된 위험 신호가 없습니다.</p>'

    items = []

    for point in points:
        label_parts = [
            part
            for part in [point.get("major_type"), point.get("subtype")]
            if part
        ]
        label = " · ".join(label_parts)
        strength = point.get("evidence_strength") or "-"

        items.append(
            f"""
            <div class="tdraft-point">
                <div class="meta">{escape(label)} · 근거강도 {escape(str(strength))}</div>
                <span>{escape(point.get("text", ""))}</span>
                {_build_citation_chips_html(point.get("segment_ids", []), segment_lookup)}
            </div>
            """
        )

    return "".join(items)


def build_record_draft_view_html(result):
    """
    목업(2026-10-08 공유)의 "축어록 + 기록 초안" 분할 화면을 렌더링한다.

    왼쪽: 축어록(타임스탬프+화자), 각 줄에 segment_id를 id 속성으로
    달아둔다 — 오른쪽 "기록 초안"의 근거 칩을 누르면 그 줄로 스크롤
    이동하고 잠깐 강조된다(아래 tdraftJump 스크립트).

    오른쪽: 기록 초안 4개 섹션. "상담원 관찰"만 AI가 채우지 않는
    직접 입력 칸이다(상담사가 상담 직후 쓰는 메모라서 — 모듈 docstring
    참고).
    """

    segments = result.get("segments", []) or []
    record_draft = result.get("record_draft") or {}

    segment_lookup = {
        str(segment.get("segment_id", "")): segment
        for segment in segments
    }

    transcript_lines = []

    for segment in segments:
        segment_id = str(segment.get("segment_id", ""))
        speaker = segment.get("speaker", "UNKNOWN")
        speaker_label = _SPEAKER_DISPLAY_LABEL.get(speaker, speaker)
        speaker_class = "k" if speaker == "CHILD" else "c"
        text = segment.get("text", "")
        ts_label = _format_timestamp_label(segment.get("start_ms", 0))

        transcript_lines.append(
            f"""
            <div class="tdraft-line {speaker_class}" id="{escape(segment_id, quote=True)}">
                <span class="tdraft-ts">{ts_label}</span>
                <span class="tdraft-sp">{escape(speaker_label)}</span>
                <span class="tdraft-tx">{escape(text)}</span>
            </div>
            """
        )

    transcript_html = (
        "".join(transcript_lines)
        if transcript_lines
        else '<p class="triage-empty">축어록이 없습니다.</p>'
    )

    return f"""
    <section class="panel">
        <h2>축어록 + 기록 초안</h2>
        <div class="tdraft-split">
            <div class="tdraft-panel">
                <div class="tdraft-panel-header">축어록</div>
                <div class="tdraft-transcript">{transcript_html}</div>
            </div>
            <div class="tdraft-panel">
                <div class="tdraft-panel-header">기록 초안</div>

                <div class="tdraft-field">
                    <div class="tdraft-field-head">
                        상담 개요 <span class="tag t-ai">AI 초안</span>
                    </div>
                    <div class="tdraft-field-body">
                        {escape(record_draft.get("session_overview", "") or "-")}
                    </div>
                </div>

                <div class="tdraft-field">
                    <div class="tdraft-field-head">
                        아동 진술 요지 <span class="tag t-ai">AI 초안</span>
                    </div>
                    <div class="tdraft-field-body">
                        {_build_statement_points_html(
                            record_draft.get("child_statement_points", []),
                            "진술 요지가 없습니다.",
                            segment_lookup,
                        )}
                    </div>
                </div>

                <div class="tdraft-field">
                    <div class="tdraft-field-head">
                        위험 신호 <span class="tag t-ai">AI 초안</span>
                    </div>
                    <div class="tdraft-field-body">
                        {_build_risk_points_html(
                            record_draft.get("risk_signal_points", []),
                            segment_lookup,
                        )}
                    </div>
                </div>

                <div class="tdraft-field">
                    <div class="tdraft-field-head">
                        상담원 관찰 <span class="tag t-manual">직접 입력</span>
                    </div>
                    <div class="tdraft-field-body">
                        <textarea
                            name="counselor_observation"
                            class="tdraft-textarea"
                            placeholder="상담 직후 관찰 내용을 입력하세요"
                        >{escape(record_draft.get("counselor_observation", ""))}</textarea>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <script>
    function tdraftJump(segmentId) {{
        var el = document.getElementById(segmentId);
        if (el) {{
            el.scrollIntoView({{behavior: "smooth", block: "center"}});
            el.classList.add("tdraft-flash");
            setTimeout(function () {{ el.classList.remove("tdraft-flash"); }}, 1500);
        }}
        return false;
    }}
    </script>
    """


def build_approval_form_html(
    session_id,
    result: dict,
) -> str:
    checklist_draft = (
        result.get(
            "checklist_draft"
        )
        or {}
    )

    summary = escape(
        result.get(
            "counseling_summary",
            "",
        )
    )

    note = escape(
        result.get(
            "counseling_note",
            "",
        )
    )

    problem_history = escape(
        checklist_draft.get(
            "problem_history_draft",
            "",
        )
    )

    counselor_opinion = escape(
        checklist_draft.get(
            "counselor_opinion_draft",
            "",
        )
    )

    return f"""
    <form method="post" action="/approve">
        <input type="hidden" name="session_id" value="{session_id}">

        <section class="panel">
            <h2>상담 요약 (수정 가능)</h2>
            <textarea name="counseling_summary" class="editable">{summary}</textarea>
        </section>

        <section class="panel">
            <h2>상담일지 (수정 가능)</h2>
            <textarea name="counseling_note" class="editable">{note}</textarea>
        </section>

        {build_checklist_edit_html(checklist_draft)}

        <section class="panel">
            <h2>문제력 초안 (수정 가능)</h2>
            <textarea name="problem_history_draft" class="editable">{problem_history}</textarea>
        </section>

        <section class="panel">
            <h2>상담원 소견 초안 (수정 가능)</h2>
            <textarea name="counselor_opinion_draft" class="editable">{counselor_opinion}</textarea>
        </section>

        <section class="panel">
            <button type="submit">승인하고 저장</button>
        </section>
    </form>
    """


# ============================================================
# 7. Routes
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def index():
    default_text = """상담사: 아빠가 어떻게 했어?
아동: 아빠가 막대기로 제 팔을 여러 번 때렸어요.
상담사: 또 다른 일도 있었어?
아동: 저번에는 벨트로 허벅지를 때렸어요."""

    return build_page(
        text=default_text,
        input_mode="qa",
    )


@app.post(
    "/analyze",
    response_class=HTMLResponse,
)
def analyze(
    text: str = Form(...),
    input_mode: str = Form(...),
    case_id: str = Form(...),
):
    try:
        result = analyze_session(
            text=text,
            input_mode=input_mode,
        )

        session_id = case_store.save_draft_session(
            case_id=case_id,
            input_mode=input_mode,
            source_type="text",
            raw_text=text,
            analysis=result,
        )

        return build_page(
            text=text,
            input_mode=input_mode,
            case_id=case_id,
            result=result,
            session_id=session_id,
        )

    except Exception as exc:
        return build_page(
            text=text,
            input_mode=input_mode,
            case_id=case_id,
            error=exc,
        )


@app.post(
    "/download",
    response_class=PlainTextResponse,
)
def download(
    payload: str = Form(...),
):
    result = json.loads(payload)

    filename = (
        "ispot_report_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    return PlainTextResponse(
        content=build_download_text(result),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


@app.post(
    "/download-pdf",
)
def download_pdf(
    payload: str = Form(...),
):
    result = json.loads(payload)

    filename = (
        "ispot_report_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )

    return Response(
        content=build_download_pdf(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


# ============================================================
# 8. 실행
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7862,
    )