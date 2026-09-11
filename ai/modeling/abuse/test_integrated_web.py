"""
I-SPOT STT + A-only 학대 분석 통합 테스트 웹.
음성 파일 또는 아동 발화를 입력받아 1차/2차/XAI 분석 결과를 확인한다.
"""

# ============================================================
# Imports
# ============================================================

import json
import os
import tempfile

import requests
import streamlit as st

from ai.modeling.abuse.infer_session import analyze_stt_session


# ============================================================
# 설정
# ============================================================

STT_API_URL = os.getenv(
    "I_SPOT_STT_API_URL",
    "http://127.0.0.1:8000/api/v1/analyze",
)

ABUSE_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 아동 발화 → 공용 Transcript 변환
# ============================================================

def child_text_to_transcript(text: str) -> dict:
    """
    음성 없이 직접 입력한 아동 발화를
    팀 공용 Transcript Schema 형태로 변환한다.
    """

    text = text.strip()

    if not text:
        return {
            "schema_version": "1.0",
            "segments": [],
        }

    return {
        "schema_version": "1.0",
        "segments": [
            {
                "segment_id": "manual_001",
                "speaker": "CHILD",
                "start_ms": 0,
                "end_ms": 0,
                "text": text,
                "confidence": 1.0,
            }
        ],
    }


# ============================================================
# STT API 호출
# ============================================================

def request_stt(audio_file) -> dict:
    """
    업로드된 음성 파일을 STT 팀 FastAPI에 전달하고
    전체 API 응답을 반환한다.
    """

    files = {
        "file": (
            audio_file.name,
            audio_file.getvalue(),
            audio_file.type or "application/octet-stream",
        )
    }

    response = requests.post(
        STT_API_URL,
        files=files,
        timeout=600,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# 분석 결과 UI
# ============================================================

def render_analysis_result(result: dict):
    """
    infer_session의 결과를 웹 화면에 표시한다.
    """

    # ========================================================
    # 1차 학대유형
    # ========================================================

    st.subheader("1차 학대유형 분석")

    abuse_signals = result.get(
        "abuse_signals",
        {},
    )

    cols = st.columns(4)

    for index, label in enumerate(ABUSE_LABELS):

        detected = (
            abuse_signals
            .get(label, {})
            .get("detected", False)
        )

        with cols[index]:

            st.markdown(f"**{label}**")

            if detected:
                st.success("관련 신호 탐지 있음")
            else:
                st.info("관련 신호 탐지 없음")

    # ========================================================
    # 2차 세부유형
    # ========================================================

    st.divider()

    st.subheader("2차 세부유형 분석")

    subtype_signals = result.get(
        "subtype_signals",
        {},
    )

    detected_count = 0

    for subtype, subtype_result in subtype_signals.items():

        if not subtype_result.get(
            "detected",
            False,
        ):
            continue

        detected_count += 1

        subtype_name = subtype_result.get(
            "display_name",
            subtype,
        )

        with st.expander(
            f"{subtype_name} ({subtype})",
            expanded=True,
        ):

            st.success("관련 신호 탐지 있음")

            # --------------------------------------------
            # 탐지된 chunk
            # --------------------------------------------

            evidence_chunks = subtype_result.get(
                "evidence_chunks",
                [],
            )

            if evidence_chunks:

                st.markdown("**탐지 발화**")

                for chunk in evidence_chunks:

                    segment_ids = chunk.get(
                        "segment_ids",
                        [],
                    )

                    st.write(
                        "Segment:",
                        ", ".join(segment_ids),
                    )

            # --------------------------------------------
            # XAI 근거
            # --------------------------------------------

            evidence = subtype_result.get(
                "evidence",
                [],
            )

            if evidence:

                st.markdown(
                    "**모델 예측에 기여한 주요 표현**"
                )

                for item in evidence:

                    phrase = item.get(
                        "evidence_text",
                        "",
                    )

                    source_text = item.get(
                        "source_text",
                        "",
                    )

                    segment_id = item.get(
                        "segment_id",
                        "",
                    )

                    if phrase:
                        st.markdown(
                            f"- **{phrase}**"
                        )

                    if source_text:
                        st.caption(
                            f"원문: {source_text}"
                        )

                    if segment_id:
                        st.caption(
                            f"Segment: {segment_id}"
                        )

    if detected_count == 0:
        st.info(
            "탐지된 세부유형 신호가 없습니다."
        )

    # ========================================================
    # Warning
    # ========================================================

    warnings = result.get(
        "warnings",
        [],
    )

    if warnings:

        st.divider()

        st.subheader("분석 주의사항")

        for warning in warnings:
            st.warning(warning)


# ============================================================
# Streamlit
# ============================================================

st.set_page_config(
    page_title="I-SPOT AI 통합 테스트",
    layout="wide",
)

st.title("I-SPOT 상담 AI 분석")

st.caption(
    "실제 상담 음성을 업로드하거나 "
    "아동 발화를 직접 입력하여 분석할 수 있습니다."
)


# ============================================================
# 입력 방식 선택
# ============================================================

input_mode = st.radio(
    "입력 방식",
    [
        "음성 파일",
        "아동 발화 직접 입력",
    ],
    horizontal=True,
)


# ============================================================
# 음성 입력
# ============================================================

if input_mode == "음성 파일":

    uploaded_audio = st.file_uploader(
        "상담 음성 파일",
        type=[
            "wav",
            "mp3",
            "m4a",
            "flac",
            "ogg",
            "aac",
        ],
    )

    if uploaded_audio is not None:

        st.audio(
            uploaded_audio.getvalue()
        )

        if st.button(
            "STT + AI 분석 시작",
            type="primary",
        ):

            try:

                # ----------------------------------------
                # STT 실행
                # ----------------------------------------

                with st.spinner(
                    "음성을 STT로 변환하고 있습니다..."
                ):

                    stt_response = request_stt(
                        uploaded_audio
                    )

                # ----------------------------------------
                # 공용 Transcript 획득
                # ----------------------------------------

                transcript = stt_response.get(
                    "transcript"
                )

                if not transcript:

                    st.error(
                        "STT 결과에 transcript가 없습니다."
                    )

                    st.stop()

                # ----------------------------------------
                # Transcript 표시
                # ----------------------------------------

                st.subheader("STT 결과")

                for segment in transcript.get(
                    "segments",
                    [],
                ):

                    speaker = segment.get(
                        "speaker",
                        "UNKNOWN",
                    )

                    text = segment.get(
                        "text",
                        "",
                    )

                    st.write(
                        f"**[{speaker}]** {text}"
                    )

                # ----------------------------------------
                # AI 분석
                # ----------------------------------------

                with st.spinner(
                    "학대 관련 신호를 분석하고 있습니다..."
                ):

                    result = analyze_stt_session(
                        transcript
                    )

                st.divider()

                render_analysis_result(
                    result
                )

            except requests.exceptions.RequestException as exc:

                st.error(
                    f"STT API 호출 실패: {exc}"
                )

            except Exception as exc:

                st.exception(exc)


# ============================================================
# 아동 발화 직접 입력
# ============================================================

else:

    child_text = st.text_area(
        "아동 발화",
        height=180,
        placeholder=(
            "예: 아빠가 화가 나서 "
            "막대기로 제 다리를 여러 번 때렸어요."
        ),
    )

    if st.button(
        "AI 분석 시작",
        type="primary",
    ):

        if not child_text.strip():

            st.warning(
                "아동 발화를 입력해주세요."
            )

        else:

            try:

                transcript = (
                    child_text_to_transcript(
                        child_text
                    )
                )

                with st.spinner(
                    "학대 관련 신호를 분석하고 있습니다..."
                ):

                    result = analyze_stt_session(
                        transcript
                    )

                render_analysis_result(
                    result
                )

            except Exception as exc:

                st.exception(exc)