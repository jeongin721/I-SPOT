"""
I-SPOT v3 1차 학대유형 모델을 브라우저에서 간단히 테스트하는 웹 페이지.
상담 텍스트 또는 음성 파일을 입력하고 관련 학대 신호를 확인한다.
"""

# ============================================================
# 1. Import
# ============================================================

import os
import tempfile

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from ai.modeling.abuse.infer_abuse_v3_adapter import predict_abuse

from ispot_stt import SelectiveFallbackSTTProvider
from ispot_postprocess import STTPostProcessor
from child_analysis_text import ChildAnalysisTextBuilder
from transcript_builder import TranscriptBuilder

from ai.modeling.abuse.infer_subtype import (
    LABEL_DISPLAY_NAMES,
    predict_subtype,
)

# ============================================================
# 2. STT 객체
# ============================================================

stt_provider = SelectiveFallbackSTTProvider()

post_processor = STTPostProcessor(
    low_confidence_threshold=0.70
)

child_builder = ChildAnalysisTextBuilder()
transcript_builder = TranscriptBuilder()


# ============================================================
# 세부유형 → 4대 학대유형 매핑
# ============================================================

SUBTYPE_TO_ABUSE = {
    "physical_direct": "신체학대",
    "physical_object": "신체학대",
    "physical_force": "신체학대",

    "emotional_verbal": "정서학대",
    "emotional_threat": "정서학대",
    "emotional_restriction": "정서학대",
    "emotional_discrimination": "정서학대",
    "emotional_dv_exposure": "정서학대",
    "emotional_cruelty": "정서학대",

    "sexual_exposure": "성학대",
    "sexual_molestation": "성학대",
    "sexual_intercourse": "성학대",

    "neglect_physical": "방임",
    "neglect_education": "방임",
    "neglect_medical": "방임",
}

# ============================================================
# 3. FastAPI
# ============================================================

app = FastAPI(
    title="I-SPOT v3 Test Web"
)


# ============================================================
# 4대 학대유형 + 세부유형 결과 HTML
# ============================================================

def build_result_html(
    results,
    subtype_results=None,
):

    labels = [
        "신체학대",
        "정서학대",
        "성학대",
        "방임",
    ]

    if not results:
        results = {
            label: {
                "detected": False
            }
            for label in labels
        }

    if subtype_results is None:
        subtype_results = {}

    html = '<div class="signal-grid">'

    for label in labels:

        detected = results.get(
            label,
            {}
        ).get(
            "detected",
            False
        )

        card_class = (
            "signal-card detected"
            if detected
            else "signal-card"
        )

        status_text = (
            "관련 신호 탐지"
            if detected
            else "관련 신호 없음"
        )

        html += f"""
        <div
            class="{card_class}"
            onclick="toggleSubtype('{label}')"
        >
            <div class="signal-title">
                {label}
            </div>

            <div class="signal-status">
                {status_text}
            </div>
        </div>
        """

    html += "</div>"

    # --------------------------------------------------------
    # 유형별 세부유형 패널
    # --------------------------------------------------------

    for abuse_label in labels:

        abuse_detected = results.get(
            abuse_label,
            {}
        ).get(
            "detected",
            False
        )

        subtype_html = ""

        if abuse_detected:

            for subtype, result in subtype_results.items():

                if (
                    SUBTYPE_TO_ABUSE.get(subtype)
                    != abuse_label
                ):
                    continue

                if not result.get(
                    "detected",
                    False
                ):
                    continue

                display_name = (
                    LABEL_DISPLAY_NAMES.get(
                        subtype,
                        subtype,
                    )
                )

                subtype_html += f"""
                <div class="subtype-item detected-subtype">
                    ✓ {display_name}
                </div>
                """

            if not subtype_html:

                subtype_html = """
                <div class="subtype-empty">
                    탐지된 세부유형이 없습니다.
                </div>
                """

        else:

            subtype_html = """
            <div class="subtype-empty">
                1차 모델에서 관련 신호가 탐지되지 않았습니다.
            </div>
            """

        html += f"""
        <div
            id="panel-{abuse_label}"
            class="subtype-panel"
        >
            <div class="subtype-title">
                {abuse_label} 세부 유형
            </div>

            {subtype_html}
        </div>
        """

    return html

# ============================================================
# 5. 웹 화면
# ============================================================

def render_page(
    text="",
    results=None,
    transcript="",
    subtype_results=None,
):

    result_html = build_result_html(
        results,
        subtype_results,
    )

    transcript_html = (
        transcript
        if transcript
        else "-"
    )

    return f"""
<!DOCTYPE html>

<html lang="ko">

<head>

<meta charset="UTF-8">

<title>I-SPOT v3 Test</title>

<style>

body {{
    font-family: Arial, sans-serif;
    background: #f5f6f8;
    margin: 0;
    padding: 40px;
}}

.container {{
    max-width: 900px;
    margin: auto;
}}

.card {{
    background: white;
    padding: 25px;
    margin-bottom: 20px;
    border-radius: 12px;
    box-shadow: 0 3px 12px rgba(0,0,0,0.08);
}}

h1 {{
    margin-top: 0;
}}

textarea {{
    width: 100%;
    height: 150px;
    box-sizing: border-box;
    padding: 15px;
    font-size: 16px;
    border: 1px solid #ccc;
    border-radius: 8px;
    resize: vertical;
}}

button {{
    margin-top: 12px;
    padding: 12px 20px;
    border: 0;
    border-radius: 8px;
    background: #222;
    color: white;
    cursor: pointer;
    font-size: 15px;
}}

input {{
    margin-top: 10px;
}}

.signal-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}}

.signal-card {{
    padding: 18px;
    border: 1px solid #ddd;
    border-radius: 10px;
    background: #fafafa;
    cursor: pointer;
    transition: 0.2s;
}}

.signal-card:hover {{
    border-color: #999;
}}

.signal-card.detected {{
    border: 2px solid #222;
    background: #f0f0f0;
}}

.signal-title {{
    font-size: 18px;
    font-weight: bold;
}}

.signal-status {{
    margin-top: 8px;
    font-size: 13px;
    color: #777;
}}

.signal-card.detected .signal-status {{
    color: #111;
    font-weight: bold;
}}

.subtype-panel {{
    display: none;
    margin-top: 18px;
    padding: 18px;
    background: #f8f8f8;
    border-radius: 10px;
}}

.subtype-panel.active {{
    display: block;
}}

.empty {{
    color: #888;
}}

.output {{
    white-space: pre-wrap;
    line-height: 1.7;
    background: #f8f8f8;
    padding: 15px;
    border-radius: 8px;
}}

.notice {{
    font-size: 13px;
    color: #666;
}}

</style>

</head>

<body>

<div class="container">

<div class="card">

<h1>I-SPOT</h1>

<p>
아동 상담 텍스트 · 음성 기반 학대 관련 신호 탐지
</p>

</div>


<div class="card">

<h2>텍스트 분석</h2>

<form
    method="post"
    action="/predict-text"
>

<textarea
    name="text"
    placeholder="[CHILD] 아빠가 어제 저를 때렸어요.

또는

[COUNSELOR] 아빠가 때린 적이 있나요?
[CHILD] 네."
    required>{text}</textarea>

<button type="submit">
분석하기
</button>

</form>

</div>


<div class="card">

<h2>음성 분석</h2>

<form
    method="post"
    action="/predict-audio"
    enctype="multipart/form-data"
>

<input
    type="file"
    name="file"
    accept=".wav,.mp3,.m4a,.flac,.ogg,.aac"
    required
>

<br>

<button type="submit">
음성 업로드 및 분석
</button>

</form>

</div>


<div class="card">

<h2>관련 신호 탐지</h2>

{result_html}


</div>


<div class="card notice">

본 결과는 학대 여부에 대한 최종 판단이 아니라
상담 내용에서 관련 신호를 탐지하기 위한 AI 보조 결과입니다.

</div>

</div>

<script>

function toggleSubtype(label) {{

    const selected =
        document.getElementById(
            "panel-" + label
        );

    if (!selected) {{
        return;
    }}

    const wasActive =
        selected.classList.contains(
            "active"
        );

    document
        .querySelectorAll(".subtype-panel")
        .forEach(
            panel => panel.classList.remove("active")
        );

    if (!wasActive) {{
        selected.classList.add(
            "active"
        );
    }}

}}

</script>

</body>

</html>
"""


# ============================================================
# 6. 메인 페이지
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def home():

    return render_page()


# ============================================================
# 7. 텍스트 분석
# ============================================================

@app.post(
    "/predict-text",
    response_class=HTMLResponse,
)
def predict_text(
    text: str = Form(...),
):
    """
    사용자가 입력한 상담 텍스트를 수정하지 않고
    그대로 v3 1차 학대유형 모델에 전달한다.
    """

    text = text.strip()

    print("\n" + "=" * 70)
    print("[WEB TEXT INPUT]")
    print(text)
    print("=" * 70)

    results = predict_abuse(
        text
    )

    subtype_results = predict_subtype(
        text
    )

    print("[V3 RESULT]")
    print(results)
    print("=" * 70 + "\n")

    return render_page(
        text=text,
        results=results,
        transcript=text,
        subtype_results=subtype_results,
    )


# ============================================================
# 8. 음성 분석
# ============================================================

@app.post(
    "/predict-audio",
    response_class=HTMLResponse,
)
def predict_audio(
    file: UploadFile = File(...),
):

    extension = os.path.splitext(
        file.filename
    )[1]

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:

            temp_file.write(
                file.file.read()
            )

            temp_path = temp_file.name

        # STT
        raw_result = stt_provider.transcribe(
            temp_path
        )

        # STT 후처리
        final_result = post_processor.process(
            raw_result
        )

        # 아동 화자 판별
        child_result = child_builder.build(
            final_result
        )

        # 공용 Transcript
        transcript = transcript_builder.build(
            stt_data=final_result,
            role_mapping=child_result.get(
                "role_mapping",
                {},
            ),
        )

        # --------------------------------------------------------
        # v3 1차 모델 입력 생성
        # --------------------------------------------------------

        segments = transcript.get(
            "segments",
            []
        )

        model_lines = []

        for segment in segments:

            speaker = str(
                segment.get(
                    "speaker",
                    ""
                )
            ).strip().upper()

            segment_text = str(
                segment.get(
                    "text",
                    ""
                )
            ).strip()

            if (
                speaker in {
                    "COUNSELOR",
                    "CHILD",
                }
                and segment_text
            ):
                model_lines.append(
                    f"[{speaker}] {segment_text}"
                )

        model_text = "\n".join(
            model_lines
        )

        # v3 1차 학대유형 분석
        results = predict_abuse(
            model_text
        )

        # 2차 세부유형 분석
        subtype_results = predict_subtype(
            model_text
        )

        return render_page(
            results=results,
            transcript=model_text,
            subtype_results=subtype_results,
        )

    finally:

        if (
            temp_path
            and os.path.exists(temp_path)
        ):
            os.remove(
                temp_path
            )


# ============================================================
# 9. 실행
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860,
    )