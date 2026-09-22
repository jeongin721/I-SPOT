"""
음성 파일 업로드 → STT → 오늘 만든 신규 파이프라인(analyze_audio_session)
전체를 확인하는 테스트 웹.

STT provider는 환경변수 I_SPOT_STT_PROVIDER로 고른다.
- "elevenlabs"(기본값): ElevenLabs Scribe v2(팀 STT 파트 최종본) — 화자분리
  정확도 때문에 채택. 외부 유료 API를 호출하므로 실제 상담 음성이 외부로
  나간다는 점은 감수한 선택이다(정확도 우선). 화자를 CHILD/COUNSELOR로
  확정하기 어려운 구간은 UNKNOWN으로 남기고 review_needed로 넘긴다.
  응답 실패 시에만 내부적으로 Deepgram으로 자동 대체된다.
- "whisperx": WhisperX(전사+화자분리) — 완전 로컬, API 호출 없음. 외부로
  음성을 보내지 않아야 할 때 이 값으로 전환.
- "deepgram": 기존 SelectiveFallbackSTTProvider(Deepgram 기반, 유료 API)를
  단독으로 사용.

Provider마다 confidence의 스케일/의미가 달라(WhisperX는 wav2vec2 정렬
점수, ElevenLabs는 제공되지 않아 항상 0.0/False, Deepgram은 자체 신뢰도)
STTPostProcessor의 저신뢰 임계값도 provider에 맞춰 따로 잡는다.
STTPostProcessor/ChildAnalysisTextBuilder/TranscriptBuilder는 provider와
무관하게 그대로 재사용한다 — TranscriptBuilder의 출력이 이미 Contract
v1.0 형식이라 infer_audio_session.analyze_audio_session()에 그대로 들어간다.
"""

import json
import os
import tempfile
from datetime import datetime
from html import escape

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
import uvicorn

from ispot_stt import (
    DeepgramSTTProvider,
    ElevenLabsScribeV2Provider,
    ProviderFailureFallbackSTTProvider,
    SelectiveFallbackSTTProvider,
    WhisperXSTTProvider,
)
from ispot_postprocess import STTPostProcessor
from child_analysis_text import ChildAnalysisTextBuilder
from transcript_builder import TranscriptBuilder

from ai.modeling.abuse.infer_audio_session import (
    analyze_audio_session,
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
# 1. STT 객체 (test_web_qa.py와 동일한 구성)
# ============================================================

_stt_provider_name = os.getenv(
    "I_SPOT_STT_PROVIDER",
    "elevenlabs",
).lower()

if _stt_provider_name == "deepgram":
    stt_provider = SelectiveFallbackSTTProvider()
    post_processor = STTPostProcessor(
        low_confidence_threshold=0.70
    )
elif _stt_provider_name == "whisperx":
    stt_provider = WhisperXSTTProvider()
    post_processor = STTPostProcessor(
        low_confidence_threshold=(
            WhisperXSTTProvider.LOW_CONFIDENCE_THRESHOLD
        )
    )
else:
    # ElevenLabs는 실패 시에만 Deepgram으로 자동 대체(ProviderFailureFallback).
    # confidence는 항상 0.0/is_low_confidence=False로 오므로(호환 가능한 값이
    # 없음), 저신뢰 임계값은 사실상 이 provider에서는 쓰이지 않는다 — 화자
    # 확정 불가 구간은 confidence가 아니라 UNKNOWN speaker로 걸러진다.
    stt_provider = ProviderFailureFallbackSTTProvider(
        primary=ElevenLabsScribeV2Provider(),
        fallback=DeepgramSTTProvider(),
    )
    post_processor = STTPostProcessor(low_confidence_threshold=0.0)

child_builder = ChildAnalysisTextBuilder()
transcript_builder = TranscriptBuilder()


# ============================================================
# 2. FastAPI 앱
# ============================================================

app = FastAPI(
    title="I-SPOT 음성 파이프라인 테스트",
)

register_case_workflow_routes(app)


# ============================================================
# 3. 페이지 렌더링
# ============================================================

SPEAKER_OPTIONS = [
    "COUNSELOR",
    "CHILD",
    "GUARDIAN",
    "OTHER",
    "UNKNOWN",
]


def build_transcript_review_html(
    transcript,
):
    """
    STT segment를 화자/텍스트만 수정 가능한 형태로 렌더링한다.
    segment_id/start_ms/end_ms/confidence는 hidden으로 그대로 들고 간다.
    """

    rows = []

    for segment in transcript.get(
        "segments",
        [],
    ):
        segment_id = str(
            segment.get(
                "segment_id",
                "",
            )
        )

        speaker = segment.get(
            "speaker",
            "UNKNOWN",
        )

        text = segment.get(
            "text",
            "",
        )

        start_ms = segment.get(
            "start_ms",
            0,
        )

        end_ms = segment.get(
            "end_ms",
            0,
        )

        confidence = segment.get(
            "confidence",
            0.0,
        )

        # TranscriptBuilder.build()가 is_low_confidence 필드 자체를
        # 제거하므로(공용 Transcript에서는 제외), 여기서 0.70을
        # 하드코딩하면 ElevenLabs(confidence 항상 0.0)는 모든 행이
        # 항상 low-confidence로 표시되어 정작 봐야 할 신호(UNKNOWN
        # 화자)가 묻힌다. STTPostProcessor가 provider별로 이미 잡아 둔
        # post_processor.threshold를 그대로 재사용한다.
        row_classes = []
        if confidence < post_processor.threshold:
            row_classes.append("low-confidence")
        if speaker == "UNKNOWN":
            # ElevenLabs 등에서 화자를 확정하지 못해 review가 필요한 구간.
            row_classes.append("needs-review")
        low_conf_class = (
            " " + " ".join(row_classes)
            if row_classes
            else ""
        )

        options_html = "".join(
            f'<option value="{option}"'
            f'{" selected" if option == speaker else ""}>'
            f"{option}</option>"
            for option in SPEAKER_OPTIONS
        )

        rows.append(
            f"""
            <div class="segment-row{low_conf_class}">
                <input type="hidden" name="segment_id" value="{escape(segment_id)}">
                <input type="hidden" name="start_ms" value="{start_ms}">
                <input type="hidden" name="end_ms" value="{end_ms}">
                <input type="hidden" name="confidence" value="{confidence}">

                <select name="speaker" class="segment-speaker-select">
                    {options_html}
                </select>

                <input
                    type="text"
                    name="text"
                    class="segment-text-input"
                    value="{escape(str(text), quote=True)}"
                >

                <span class="segment-conf">conf {confidence:.2f}</span>
            </div>
            """
        )

    return "".join(rows)


def build_page(
    filename=None,
    transcript=None,
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
        chunk_meta_html = "".join(
            f"""
            <div class="chunk-meta">
                chunk {c['chunk_index']}
                (segment {', '.join(c['segment_ids'])}){' — 저신뢰 구간 포함' if c['has_low_confidence'] else ''}
            </div>
            """
            for c in analysis.get(
                "chunk_results",
                [],
            )
        )

        result_html = f"""
        <section class="panel">
            <h2>1차 학대 위험신호</h2>
            {build_major_types_html(analysis.get("major_types", {}))}
            <div class="chunk-meta-box">
                {chunk_meta_html}
            </div>
        </section>

        <section class="panel">
            <h2>2차 세부 위험신호</h2>
            {build_subtypes_html(analysis.get("subtype_analysis", {}))}
        </section>

        {build_approval_form_html(session_id, analysis)}

        {build_download_form_html(analysis)}
        """

    elif transcript:
        # ------------------------------------------------------
        # 검수 단계: STT 결과를 바로 분석하지 않고,
        # 화자/텍스트를 확인·수정한 뒤에만 분석으로 넘어간다.
        # ------------------------------------------------------

        result_html = f"""
        <section class="panel">
            <h2>STT 결과 검수 — {escape(filename)}</h2>

            <div class="meta">
                총 {len(transcript.get("segments", []))}개 발화.
                화자 표시나 텍스트가 잘못됐으면 직접 수정한 뒤
                분석하기를 눌러주세요. 노란 배경은 STT 신뢰도가
                낮은(신뢰도 {post_processor.threshold:.2f} 미만) 구간입니다.
            </div>

            <form method="post" action="/analyze-transcript">
                <input
                    type="text"
                    name="case_id"
                    class="case-id-input"
                    placeholder="사례 ID (예: CASE-2026-001)"
                    value="{escape(case_id)}"
                    required
                >

                <div class="transcript-review-box">
                    {build_transcript_review_html(transcript)}
                </div>

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

        <title>I-SPOT 음성 파이프라인 테스트</title>

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
                margin-bottom: 12px;
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

            .transcript-box {{
                max-height: 420px;
                overflow-y: auto;
                background: #f9fafb;
                border-radius: 10px;
                padding: 8px 16px;
            }}

            .segment {{
                padding: 8px 0;
                border-bottom: 1px solid #e5e7eb;
                font-size: 14px;
                display: flex;
                gap: 10px;
                align-items: baseline;
            }}

            .segment:last-child {{
                border-bottom: none;
            }}

            .segment.low-confidence {{
                background: #fffbeb;
            }}

            .segment-speaker {{
                font-weight: 700;
                min-width: 80px;
                color: #3730a3;
            }}

            .segment-text {{
                flex: 1;
            }}

            .segment-conf {{
                font-size: 11px;
                color: #9ca3af;
                white-space: nowrap;
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

            .segment-row.needs-review {{
                background: #fee2e2;
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

            .chunk-meta-box {{
                margin-top: 14px;
            }}

            .chunk-meta {{
                font-size: 12px;
                color: #6b7280;
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
                <h1>I-SPOT 음성 파이프라인 테스트</h1>

                <p>
                    음성 파일을 업로드하면 먼저 STT 결과를 보여줍니다.
                    화자·텍스트를 확인·수정한 뒤 "분석하기"를 누르면
                    1차 → 2차 → 상담 요약·일지 → 체크리스트 초안까지
                    이어서 생성합니다.
                    STT는 기존 SelectiveFallbackSTTProvider(Deepgram 기반)를
                    임시로 쓰고 있으며, 실제 음성 모델이 제공되면
                    이 자리만 교체하면 됩니다.
                </p>
            </div>

            <section class="panel">
                <form
                    method="post"
                    action="/transcribe"
                    enctype="multipart/form-data"
                >
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

            {result_html}

        </div>
    </body>
    </html>
    """


# ============================================================
# 4. Routes
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def index():
    return build_page()


@app.post(
    "/transcribe",
    response_class=HTMLResponse,
)
def transcribe(
    file: UploadFile = File(...),
):
    temp_path = None

    try:
        extension = os.path.splitext(
            file.filename
        )[1]

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:

            temp_file.write(
                file.file.read()
            )

            temp_path = temp_file.name

        # ----------------------------------------------------
        # STT (기존 SelectiveFallbackSTTProvider 재사용)
        # ----------------------------------------------------

        raw_result = stt_provider.transcribe(
            temp_path
        )

        final_result = post_processor.process(
            raw_result
        )

        if _stt_provider_name == "elevenlabs":
            # ElevenLabsScribeV2Provider는 provider 단계에서 이미
            # RuntimeSpeakerRoleMapper로 CHILD/COUNSELOR/UNKNOWN을
            # 확정해서 내려준다(segment["speaker"]가 raw id가 아니라
            # canonical role). WhisperX/Deepgram용으로 만든
            # ChildAnalysisTextBuilder를 여기에 또 돌리면 raw
            # speaker_id 대신 이미 확정된 역할 문자열("CHILD" 등)을
            # 다시 텍스트 휴리스틱으로 재분류하게 되어, provider가
            # 내린 결정을 뒤집을 수 있다. 그래서 이미 정해진 role을
            # 그대로 통과시키는 identity mapping만 사용한다.
            role_mapping = {
                role: {"role": role}
                for role in (
                    "COUNSELOR",
                    "CHILD",
                    "GUARDIAN",
                    "OTHER",
                    "UNKNOWN",
                )
            }
        else:
            child_result = child_builder.build(
                final_result
            )
            role_mapping = child_result.get(
                "role_mapping",
                {},
            )

        transcript = transcript_builder.build(
            stt_data=final_result,
            role_mapping=role_mapping,
        )

        # 여기서 바로 분석하지 않는다.
        # 상담사가 화자/텍스트를 검수·수정한 뒤 /analyze-transcript로 넘어간다.
        return build_page(
            filename=file.filename,
            transcript=transcript,
        )

    except Exception as exc:
        return build_page(
            filename=file.filename,
            error=exc,
        )

    finally:
        if (
            temp_path
            and os.path.exists(temp_path)
        ):
            os.remove(
                temp_path
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

        segments = []

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
        ):
            segments.append(
                {
                    "segment_id": segment_id,
                    "speaker": speaker,
                    "text": text,
                    "start_ms": int(start_ms),
                    "end_ms": int(end_ms),
                    "confidence": float(confidence),
                }
            )

        transcript = {
            "schema_version": "1.0",
            "segments": segments,
        }

        analysis = analyze_audio_session(
            stt_result=transcript
        )

        session_id = case_store.save_draft_session(
            case_id=case_id,
            input_mode="qa",
            source_type="audio",
            raw_text=analysis.get("full_text", ""),
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
# 5. 실행
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7866,
    )
