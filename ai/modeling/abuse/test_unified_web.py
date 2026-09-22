"""
I-SPOT 통합 파이프라인 테스트 웹.

텍스트(상담사+아동 대화) / 음성 파일 업로드 / PDF 상담일지 업로드
세 가지 입력 방식을 한 화면(탭)에서 받아 동일한 결과 화면
(1차 학대 위험신호 → 2차 세부 위험신호 → 상담 요약 → 상담일지 →
체크리스트 초안)으로 보여준다.

각 입력 방식의 실제 분석 로직은 이미 검증된 기존 모듈을 그대로 재사용한다.
- 텍스트: infer_abuse_pipeline.analyze_session(input_mode="qa"/"child_only")
- 음성: STT(SelectiveFallbackSTTProvider 등, test_audio_pipeline_web.py와 동일 구성)
       → infer_audio_session.analyze_audio_session
- PDF: pdf_text_extractor.extract_text_from_pdf
       → infer_abuse_pipeline.analyze_session(input_mode="note")

음성/PDF는 업로드 즉시 분석하지 않고, 상담사가 STT 결과(화자/텍스트)나
추출된 텍스트를 확인·수정한 뒤에만 분석으로 넘어간다.
분석 결과의 상담 요약/상담일지/체크리스트는 register_case_workflow_routes가
제공하는 /approve 화면에서 상담사가 추가로 수정·승인할 수 있다.
"""

import json
import os
import tempfile
from datetime import datetime
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
import uvicorn

from ai.modeling.abuse.infer_abuse_pipeline import analyze_session
from ai.modeling.abuse.infer_audio_session import analyze_audio_session
from ai.modeling.abuse.pdf_text_extractor import extract_text_from_pdf

from ai.modeling.abuse.test_pipeline_web import (
    build_major_types_html,
    build_subtypes_html,
    build_approval_form_html,
    build_download_form_html,
    build_download_text,
)
from ai.modeling.abuse.test_audio_pipeline_web import (
    build_transcript_review_html,
    SPEAKER_OPTIONS,
    stt_provider,
    post_processor,
    child_builder,
    transcript_builder,
)

from ai.modeling.abuse import case_store
from ai.modeling.abuse.case_workflow_routes import (
    register_case_workflow_routes,
)


# ============================================================
# 1. FastAPI 앱
# ============================================================

app = FastAPI(
    title="I-SPOT 통합 파이프라인 테스트",
)

register_case_workflow_routes(app)


# ============================================================
# 2. 결과 패널 (텍스트/음성/PDF 공통)
# ============================================================

def build_result_html(
    result,
    session_id,
):
    return f"""
    <section class="panel">
        <h2>1차 학대 위험신호</h2>
        {build_major_types_html(result.get("major_types", {}))}
    </section>

    <section class="panel">
        <h2>2차 세부 위험신호</h2>
        {build_subtypes_html(result.get("subtype_analysis", {}))}
    </section>

    {build_approval_form_html(session_id, result)}

    {build_download_form_html(result)}
    """


def build_error_html(error):
    return f"""
    <section class="panel error-panel">
        <h2>오류</h2>
        <pre>{escape(str(error))}</pre>
    </section>
    """


# ============================================================
# 3. 페이지 렌더링 (탭 3개: 텍스트 / 음성 / PDF)
# ============================================================

def build_page(
    active_tab="text",
    # 텍스트 탭
    text="",
    input_mode="qa",
    text_case_id="",
    text_panel="",
    # 음성 탭
    audio_panel="",
    # PDF 탭
    pdf_panel="",
):
    mode_qa_checked = "checked" if input_mode == "qa" else ""
    mode_child_checked = "checked" if input_mode == "child_only" else ""

    tab_text_checked = "checked" if active_tab == "text" else ""
    tab_audio_checked = "checked" if active_tab == "audio" else ""
    tab_pdf_checked = "checked" if active_tab == "pdf" else ""

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <title>I-SPOT 통합 파이프라인 테스트</title>

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

            input[type="file"] {{
                display: block;
                margin-bottom: 16px;
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
                margin-bottom: 12px;
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
                margin-bottom: 12px;
            }}

            textarea.editable {{
                background: white;
                border-color: #93c5fd;
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

            .error-panel {{
                border-color: #fca5a5;
                background: #fef2f2;
            }}

            pre {{
                white-space: pre-wrap;
                word-break: break-word;
            }}

            .transcript-review-box {{
                max-height: 520px;
                overflow-y: auto;
                background: #f9fafb;
                border-radius: 10px;
                padding: 8px 16px;
                margin-bottom: 16px;
            }}

            .segment-row {{
                padding: 6px 0;
                border-bottom: 1px solid #e5e7eb;
                display: flex;
                gap: 8px;
                align-items: center;
            }}

            .segment-row:last-child {{
                border-bottom: none;
            }}

            .segment-row.low-confidence {{
                background: #fffbeb;
            }}

            .segment-speaker-select {{
                min-width: 110px;
                font-weight: 700;
                color: #3730a3;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 13px;
                background: white;
            }}

            .segment-text-input {{
                flex: 1;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 13px;
            }}

            /* --- 탭 (CSS-only, JS 없음) --- */

            .tab-input {{
                display: none;
            }}

            .tab-bar {{
                display: flex;
                gap: 8px;
                margin-bottom: 20px;
            }}

            .tab-label {{
                display: inline-block;
                padding: 12px 22px;
                border-radius: 10px;
                background: white;
                border: 1px solid #d1d5db;
                color: #6b7280;
                font-weight: 700;
                cursor: pointer;
            }}

            #tab-text:checked ~ .tab-bar label[for="tab-text"],
            #tab-audio:checked ~ .tab-bar label[for="tab-audio"],
            #tab-pdf:checked ~ .tab-bar label[for="tab-pdf"] {{
                background: #111827;
                border-color: #111827;
                color: white;
            }}

            .tab-panel {{
                display: none;
            }}

            #tab-text:checked ~ .tab-panels .panel-text,
            #tab-audio:checked ~ .tab-panels .panel-audio,
            #tab-pdf:checked ~ .tab-panels .panel-pdf {{
                display: block;
            }}

            @media (max-width: 760px) {{
                .major-grid {{
                    grid-template-columns:
                        repeat(2, minmax(0, 1fr));
                }}

                .tab-bar {{
                    flex-wrap: wrap;
                }}
            }}
        </style>
    </head>

    <body>
        <div class="container">

            <div class="header">
                <h1>I-SPOT 통합 파이프라인 테스트</h1>

                <p>
                    텍스트 / 음성 파일 / PDF 상담일지 중 하나로 입력하면
                    1차 학대 위험신호 → 2차 세부 위험신호 →
                    상담 요약 → 상담일지까지 동일하게 처리됩니다.
                </p>
            </div>

            <input
                type="radio"
                name="tab"
                id="tab-text"
                class="tab-input"
                {tab_text_checked}
            >
            <input
                type="radio"
                name="tab"
                id="tab-audio"
                class="tab-input"
                {tab_audio_checked}
            >
            <input
                type="radio"
                name="tab"
                id="tab-pdf"
                class="tab-input"
                {tab_pdf_checked}
            >

            <div class="tab-bar">
                <label for="tab-text" class="tab-label">
                    텍스트 (상담사+아동 대화)
                </label>
                <label for="tab-audio" class="tab-label">
                    음성 파일 업로드
                </label>
                <label for="tab-pdf" class="tab-label">
                    PDF 상담일지 업로드
                </label>
            </div>

            <div class="tab-panels">

                <div class="tab-panel panel-text">

                    <section class="panel">
                        <form method="post" action="/analyze">

                            <h2>사례 ID</h2>

                            <input
                                type="text"
                                name="case_id"
                                class="case-id-input"
                                placeholder="예: CASE-2026-0001 (같은 사례의 다음 회기는 동일한 ID를 입력하세요)"
                                value="{escape(text_case_id)}"
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

                    {text_panel}

                </div>

                <div class="tab-panel panel-audio">

                    <section class="panel">
                        <form
                            method="post"
                            action="/transcribe"
                            enctype="multipart/form-data"
                        >
                            <h2>사례 ID</h2>

                            <input
                                type="text"
                                name="case_id"
                                class="case-id-input"
                                placeholder="예: CASE-2026-0001"
                                required
                            >

                            <h2>음성 파일</h2>

                            <input
                                type="file"
                                name="file"
                                accept="audio/*"
                                required
                            >

                            <button type="submit">
                                STT 실행
                            </button>
                        </form>
                    </section>

                    {audio_panel}

                </div>

                <div class="tab-panel panel-pdf">

                    <section class="panel">
                        <form
                            method="post"
                            action="/extract-pdf"
                            enctype="multipart/form-data"
                        >
                            <h2>사례 ID</h2>

                            <input
                                type="text"
                                name="case_id"
                                class="case-id-input"
                                placeholder="예: CASE-2026-0001"
                                required
                            >

                            <h2>PDF 상담일지</h2>

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

                    {pdf_panel}

                </div>

            </div>

        </div>
    </body>
    </html>
    """


# ============================================================
# 4. 텍스트 탭
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
        active_tab="text",
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

        panel = build_result_html(result, session_id)

    except Exception as exc:
        panel = build_error_html(exc)

    return build_page(
        active_tab="text",
        text=text,
        input_mode=input_mode,
        text_case_id=case_id,
        text_panel=panel,
    )


# ============================================================
# 5. 음성 탭
# ============================================================

@app.post(
    "/transcribe",
    response_class=HTMLResponse,
)
def transcribe(
    case_id: str = Form(...),
    file: UploadFile = File(...),
):
    temp_path = None

    try:
        extension = os.path.splitext(file.filename)[1]

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:
            temp_file.write(file.file.read())
            temp_path = temp_file.name

        raw_result = stt_provider.transcribe(temp_path)
        final_result = post_processor.process(raw_result)
        child_result = child_builder.build(final_result)

        transcript = transcript_builder.build(
            stt_data=final_result,
            role_mapping=child_result.get("role_mapping", {}),
        )

        panel = f"""
        <section class="panel">
            <h2>STT 결과 검수 — {escape(file.filename)}</h2>

            <div class="meta">
                총 {len(transcript.get("segments", []))}개 발화.
                화자 표시나 텍스트가 잘못됐으면 직접 수정한 뒤
                분석하기를 눌러주세요. 노란 배경은 STT 신뢰도가
                낮은(신뢰도 {post_processor.threshold:.2f} 미만) 구간입니다.
            </div>

            <form method="post" action="/analyze-transcript">
                <input type="hidden" name="case_id" value="{escape(case_id)}">

                <div class="transcript-review-box">
                    {build_transcript_review_html(transcript)}
                </div>

                <button type="submit">
                    검수 완료 — 분석하기
                </button>
            </form>
        </section>
        """

    except Exception as exc:
        panel = build_error_html(exc)

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

    return build_page(
        active_tab="audio",
        audio_panel=panel,
    )


@app.post(
    "/analyze-transcript",
    response_class=HTMLResponse,
)
async def analyze_transcript(
    request: Request,
):
    case_id = ""

    try:
        form = await request.form()

        case_id = form.get("case_id", "")

        segment_ids = form.getlist("segment_id")
        speakers = form.getlist("speaker")
        texts = form.getlist("text")
        start_ms_list = form.getlist("start_ms")
        end_ms_list = form.getlist("end_ms")
        confidence_list = form.getlist("confidence")

        segments = [
            {
                "segment_id": segment_id,
                "speaker": speaker,
                "text": text,
                "start_ms": int(start_ms),
                "end_ms": int(end_ms),
                "confidence": float(confidence),
            }
            for (
                segment_id,
                speaker,
                text,
                start_ms,
                end_ms,
                confidence,
            ) in zip(
                segment_ids,
                speakers,
                texts,
                start_ms_list,
                end_ms_list,
                confidence_list,
            )
        ]

        transcript = {
            "schema_version": "1.0",
            "segments": segments,
        }

        result = analyze_audio_session(stt_result=transcript)

        session_id = case_store.save_draft_session(
            case_id=case_id,
            input_mode="qa",
            source_type="audio",
            raw_text=result.get("full_text", ""),
            analysis=result,
        )

        panel = build_result_html(result, session_id)

    except Exception as exc:
        panel = build_error_html(exc)

    return build_page(
        active_tab="audio",
        audio_panel=panel,
    )


# ============================================================
# 6. PDF 탭
# ============================================================

@app.post(
    "/extract-pdf",
    response_class=HTMLResponse,
)
async def extract_pdf(
    case_id: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        suffix = Path(file.filename).suffix or ".pdf"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as tmp_file:
            tmp_file.write(await file.read())
            tmp_path = Path(tmp_file.name)

        try:
            extraction = extract_text_from_pdf(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        warning_html = ""

        if extraction["pages_without_text_layer"]:
            pages_str = ", ".join(
                str(n) for n in extraction["pages_without_text_layer"]
            )
            warning_html = f"""
            <div class="meta">
                텍스트 레이어가 없는 페이지(스캔 이미지일 가능성):
                {pages_str}
            </div>
            """

        panel = f"""
        <section class="panel">
            <h2>텍스트 추출 결과 — {escape(file.filename)}</h2>

            <div class="meta">
                총 {extraction["page_count"]}페이지.
                문서번호/페이지번호/작성일자/담당자 같은 행정 정보는
                자동으로 걸러냈습니다 (확실한 것만 제거 — 애매하면
                그대로 둡니다). 아래 내용을 확인·수정한 뒤
                분석하기를 눌러주세요.
            </div>

            {warning_html}

            <form method="post" action="/analyze-pdf">
                <input type="hidden" name="case_id" value="{escape(case_id)}">

                <textarea name="text" class="editable">{escape(extraction["clean_text"])}</textarea>

                <button type="submit">
                    검수 완료 — 분석하기
                </button>
            </form>
        </section>
        """

    except Exception as exc:
        panel = build_error_html(exc)

    return build_page(
        active_tab="pdf",
        pdf_panel=panel,
    )


@app.post(
    "/analyze-pdf",
    response_class=HTMLResponse,
)
def analyze_pdf(
    case_id: str = Form(...),
    text: str = Form(...),
):
    try:
        if not text.strip():
            raise ValueError("분석할 텍스트가 없습니다.")

        result = analyze_session(
            text=text,
            input_mode="note",
        )

        session_id = case_store.save_draft_session(
            case_id=case_id,
            input_mode="note",
            source_type="pdf",
            raw_text=text,
            analysis=result,
        )

        panel = build_result_html(result, session_id)

    except Exception as exc:
        panel = build_error_html(exc)

    return build_page(
        active_tab="pdf",
        pdf_panel=panel,
    )


# ============================================================
# 7. 다운로드 (공통)
# ============================================================

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
