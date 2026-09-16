"""
PDF 상담일지 업로드 → 텍스트 추출 → note 전용 모델로 예측까지
한 번에 확인하는 테스트 웹.

1차는 note 전용 모델(roberta_abuse_note_v1)을 쓰고, 이후 2차 세부유형/
상담 요약/상담일지/체크리스트 초안은 analyze_session(input_mode="note")을
그대로 재사용한다.
"""

import json
import tempfile
from datetime import datetime
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
import uvicorn

from ai.modeling.abuse.pdf_text_extractor import (
    extract_text_from_pdf,
)
from ai.modeling.abuse.infer_abuse_pipeline import (
    analyze_session,
)
from ai.modeling.abuse.test_pipeline_web import (
    build_major_types_html,
    build_subtypes_html,
    build_approval_form_html,
    build_download_text,
    build_download_form_html,
)
from ai.modeling.abuse import case_store
from ai.modeling.abuse.case_workflow_routes import (
    register_case_workflow_routes,
)


# ============================================================
# 1. FastAPI 앱
# ============================================================

app = FastAPI(
    title="I-SPOT PDF 상담일지 예측 테스트",
)

register_case_workflow_routes(app)


# ============================================================
# 2. 페이지 렌더링
# ============================================================

def build_page(
    filename=None,
    extraction=None,
    analysis=None,
    case_id="",
    session_id=None,
    error=None,
):
    result_html = ""

    if error:
        result_html = f"""
        <section class="panel error-panel">
            <h2>오류</h2>
            <pre>{escape(str(error))}</pre>
        </section>
        """

    elif analysis:
        result_html = f"""
        <section class="panel">
            <h2>1차 학대 위험신호 (note 전용 모델)</h2>
            {build_major_types_html(analysis.get("major_types", {}))}
        </section>

        <section class="panel">
            <h2>2차 세부 위험신호</h2>
            {build_subtypes_html(analysis.get("subtype_analysis", {}))}
        </section>

        {build_approval_form_html(session_id, analysis)}

        {build_download_form_html(analysis)}
        """

    elif extraction:
        # ------------------------------------------------------
        # 검수 단계: 추출된 텍스트를 바로 분석하지 않고,
        # 상담사가 확인·수정한 뒤에만 분석으로 넘어간다.
        # ------------------------------------------------------

        warning_html = ""

        if extraction["pages_without_text_layer"]:
            pages_str = ", ".join(
                str(n)
                for n in extraction["pages_without_text_layer"]
            )

            warning_html = f"""
            <div class="warning">
                텍스트 레이어가 없는 페이지
                (스캔 이미지일 가능성): {pages_str}
                — 해당 페이지 내용은 비어있을 수 있으니 직접 확인해주세요.
            </div>
            """

        result_html = f"""
        <section class="panel">
            <h2>추출 결과 검수 — {escape(filename)}</h2>

            <div class="meta">
                총 {extraction['page_count']}페이지.
                아래 텍스트를 확인하고, 잘못 추출된 부분이 있으면
                직접 수정한 뒤 분석하기를 눌러주세요.
            </div>

            {warning_html}

            <form method="post" action="/analyze">
                <input
                    type="text"
                    name="case_id"
                    class="case-id-input"
                    placeholder="사례 ID (예: CASE-2026-001)"
                    value="{escape(case_id)}"
                    required
                >

                <textarea
                    name="text"
                    class="editable"
                >{escape(extraction['text'])}</textarea>

                <button type="submit">
                    검수 완료 — 분석하기
                </button>
            </form>
        </section>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <title>I-SPOT PDF 상담일지 예측 테스트</title>

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

            input[type="file"] {{
                display: block;
                margin-bottom: 16px;
            }}

            .case-id-input {{
                width: 100%;
                padding: 12px 14px;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                font-size: 14px;
                margin-bottom: 8px;
            }}

            button {{
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

            .meta {{
                font-size: 13px;
                color: #6b7280;
                margin-bottom: 12px;
            }}

            .warning {{
                background: #fffbeb;
                border: 1px solid #fcd34d;
                color: #92400e;
                padding: 10px 14px;
                border-radius: 8px;
                margin-bottom: 12px;
                font-size: 14px;
            }}

            textarea {{
                width: 100%;
                min-height: 260px;
                resize: vertical;
                border: 1px solid #d1d5db;
                border-radius: 12px;
                padding: 16px;
                font-size: 14px;
                line-height: 1.7;
                white-space: pre-wrap;
                background: #f9fafb;
            }}

            textarea.editable {{
                background: white;
                border-color: #93c5fd;
                min-height: 420px;
                margin-bottom: 14px;
            }}

            textarea.editable:focus {{
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
            }}

            .error-panel {{
                border-color: #fca5a5;
                background: #fef2f2;
            }}

            pre {{
                white-space: pre-wrap;
                word-break: break-word;
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
                <h1>I-SPOT PDF 상담일지 예측 테스트</h1>

                <p>
                    PDF를 업로드하면 먼저 텍스트를 추출해서 보여줍니다.
                    내용을 확인·수정한 뒤 "분석하기"를 누르면
                    note 전용 1차 모델로 4대 학대 위험신호를 예측하고,
                    2차 세부유형·상담 요약·상담일지·체크리스트 초안까지
                    이어서 생성합니다.
                </p>
            </div>

            <section class="panel">
                <form
                    method="post"
                    action="/extract"
                    enctype="multipart/form-data"
                >
                    <input
                        type="file"
                        name="file"
                        accept="application/pdf"
                        required
                    >

                    <button type="submit">
                        텍스트 추출
                    </button>
                </form>
            </section>

            {result_html}

        </div>
    </body>
    </html>
    """


# ============================================================
# 3. Routes
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def index():
    return build_page()


@app.post(
    "/extract",
    response_class=HTMLResponse,
)
async def extract(
    file: UploadFile = File(...),
):
    try:
        suffix = Path(
            file.filename
        ).suffix or ".pdf"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as tmp_file:
            tmp_file.write(
                await file.read()
            )

            tmp_path = Path(
                tmp_file.name
            )

        try:
            extraction = extract_text_from_pdf(
                tmp_path
            )
        finally:
            tmp_path.unlink(
                missing_ok=True,
            )

        # 여기서 바로 분석하지 않는다.
        # 상담사가 추출 결과를 검수/수정한 뒤 /analyze로 넘어간다.
        return build_page(
            filename=file.filename,
            extraction=extraction,
        )

    except Exception as exc:
        return build_page(
            filename=file.filename,
            error=exc,
        )


@app.post(
    "/analyze",
    response_class=HTMLResponse,
)
def analyze(
    text: str = Form(...),
    case_id: str = Form(...),
):
    try:
        if not text.strip():
            raise ValueError(
                "분석할 텍스트가 없습니다."
            )

        analysis = analyze_session(
            text=text,
            input_mode="note",
        )

        session_id = case_store.save_draft_session(
            case_id=case_id,
            input_mode="note",
            source_type="pdf",
            raw_text=text,
            analysis=analysis,
        )

        return build_page(
            analysis=analysis,
            case_id=case_id,
            session_id=session_id,
        )

    except Exception as exc:
        return build_page(
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
# 4. 실행
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7864,
    )
