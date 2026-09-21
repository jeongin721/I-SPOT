"""
I-SPOT 텍스트 기반 전체 파이프라인 테스트 웹.
QA / Child-only 입력을 받아 1차 대분류, 2차 세부유형, 근거 발화,
상담 요약, 상담일지를 한 화면에서 확인한다.
"""

import json
from datetime import datetime
from html import escape

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
import uvicorn

from ai.modeling.abuse.infer_abuse_pipeline import analyze_session
from ai.modeling.abuse import case_store
from ai.modeling.abuse.case_workflow_routes import (
    register_case_workflow_routes,
)


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


def build_download_form_html(
    result: dict,
) -> str:
    payload = json.dumps(
        result,
        ensure_ascii=False,
    )

    return f"""
    <section class="panel">
        <form method="post" action="/download">
            <input
                type="hidden"
                name="payload"
                value='{escape(payload, quote=True)}'
            >
            <button type="submit">
                결과 텍스트 파일로 다운로드
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
        major_html = build_major_types_html(
            result.get("major_types", {})
        )

        subtype_html = build_subtypes_html(
            result.get("subtype_analysis", {})
        )

        result_html = f"""
        <section class="panel">
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
# 3. 1차 대분류 HTML
# ============================================================

def build_major_types_html(major_types):
    labels = [
        "신체학대",
        "정서학대",
        "성학대",
        "방임",
    ]

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

        status = (
            "위험신호 탐지"
            if detected
            else "미탐지"
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

                meta_parts = []

                if strength:
                    meta_parts.append(
                        f"근거 강도: {escape(str(strength))}"
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

                if timestamps:
                    start_sec = timestamps["start_ms"] / 1000
                    end_sec = timestamps["end_ms"] / 1000

                    meta_parts.append(
                        "원본 음성 위치: "
                        f"{start_sec:.1f}s ~ {end_sec:.1f}s"
                    )

                if verified:
                    meta_parts.append(
                        f"근거 검증: {escape(str(method))}"
                    )
                else:
                    meta_parts.append(
                        "근거 검증: 확인 필요"
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

                    </div>
                    """
                )

            subtype_blocks.append(
                f"""
                <div class="subtype-block">

                    <div class="subtype-title">
                        {escape(subtype_name)}
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

        lines.append(
            f"<div>“{escape(str(quote))}”</div>"
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


# ============================================================
# 8. 실행
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7862,
    )