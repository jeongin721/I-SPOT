"""
I-SPOT 음성 분석 API 서버.
오디오 → STT → 화자 판별 → 공용 Transcript → 학대유형/세부유형/XAI 분석을 연결한다.
"""

# ============================================================
# 1. Imports
# ============================================================

import os
import tempfile

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

# I-SPOT STT / 분석 모듈
from ispot_stt import SelectiveFallbackSTTProvider
from ispot_postprocess import STTPostProcessor
from child_analysis_text import ChildAnalysisTextBuilder
from transcript_builder import TranscriptBuilder
from ai.modeling.abuse.infer_session import analyze_stt_session


# ============================================================
# 2. 환경변수 로드
# ============================================================

load_dotenv()


# ============================================================
# 3. 서버 공용 AI / STT 객체
# ============================================================
# 요청마다 새로 생성하지 않고 서버 실행 시 한 번만 생성한다.
#
# Whisper large-v3는 SelectiveFallbackSTTProvider 내부에서
# 실제 fallback이 필요한 순간에만 lazy loading되고,
# 이후 요청에서는 같은 모델 인스턴스를 재사용한다.
# ============================================================

stt_provider = SelectiveFallbackSTTProvider()

post_processor = STTPostProcessor(
    low_confidence_threshold=0.70
)

child_builder = ChildAnalysisTextBuilder()
transcript_builder = TranscriptBuilder()


# ============================================================
# 4. FastAPI 설정
# ============================================================

app = FastAPI(
    title="I-SPOT AI Backend API",
    description="아동학대 위험 감지 음성 분석 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 허용할 오디오 확장자
ALLOWED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".aac",
}


# ============================================================
# 5. 서버 상태 확인
# ============================================================

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "I-SPOT API Server is running!",
    }


# ============================================================
# 6. 음성 분석 API
# ============================================================

@app.post("/api/v1/analyze")
def analyze_audio(file: UploadFile = File(...)):

    filename = file.filename
    print(f"📥 오디오 파일 수신 요청: {filename}")

    # --------------------------------------------------------
    # 1) 파일 확장자 검증
    # --------------------------------------------------------

    file_ext = os.path.splitext(filename)[1].lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "지원하지 않는 파일 형식입니다. "
                f"({', '.join(ALLOWED_EXTENSIONS)} 지원)"
            ),
        )

    temp_file_path = None

    try:

        # ----------------------------------------------------
        # 2) 파일 데이터 읽기 / 빈 파일 검증
        # ----------------------------------------------------

        audio_bytes = file.file.read()

        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="업로드된 파일이 비어 있습니다.",
            )

        # ----------------------------------------------------
        # 3) 임시 오디오 파일 생성
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext,
        ) as temp_file:

            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name

        print(
            f"🔄 임시 파일 생성 완료: "
            f"{temp_file_path}"
        )

        print(
            f"📦 업로드 파일 크기: "
            f"{os.path.getsize(temp_file_path) / (1024 * 1024):.2f} MB"
        )

        # ----------------------------------------------------
        # 4) Deepgram STT
        # ----------------------------------------------------

        print("1️⃣ Deepgram STT 진행 중...")

        try:
            raw_stt_result = stt_provider.transcribe(
                temp_file_path
            )

        except Exception as stt_err:

            print(
                f"❌ STT 엔진 오류: "
                f"{str(stt_err)}"
            )

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "STT 엔진 처리 중 오류가 발생했습니다: "
                    f"{str(stt_err)}"
                ),
            )

        # ----------------------------------------------------
        # 5) STT 후처리 / 발화 병합
        # ----------------------------------------------------

        print(
            "2️⃣ STT 결과 후처리 및 "
            "발화 병합 중..."
        )

        try:
            final_result = post_processor.process(
                raw_stt_result
            )

        except Exception as post_err:

            print(
                f"❌ 후처리 모듈 오류: "
                f"{str(post_err)}"
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "STT 후처리 작업 중 "
                    f"오류가 발생했습니다: {str(post_err)}"
                ),
            )

        print("✅ STT 파이프라인 분석 완수!")

        # ----------------------------------------------------
        # 6) Runtime speaker role 판별
        #    + 아동 분석 텍스트 생성
        # ----------------------------------------------------

        print(
            "3️⃣ 아동 화자 판별 및 "
            "분석 텍스트 생성 중..."
        )

        try:
            child_result = child_builder.build(
                final_result
            )

        except Exception as child_err:

            print(
                f"❌ 아동 분석 텍스트 생성 오류: "
                f"{str(child_err)}"
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "아동 분석 텍스트 생성 중 "
                    f"오류가 발생했습니다: {str(child_err)}"
                ),
            )

        child_analysis_text = (
            child_result.get(
                "child_analysis_text",
                "",
            )
            or ""
        ).strip()

        # ----------------------------------------------------
        # 7) 팀 공용 Transcript 생성
        # ----------------------------------------------------

        print(
            "4️⃣ 팀 공용 Transcript 생성 중..."
        )

        try:
            transcript = transcript_builder.build(
                stt_data=final_result,
                role_mapping=child_result.get(
                    "role_mapping",
                    {},
                ),
            )

        except Exception as transcript_err:

            print(
                f"❌ Transcript 생성 오류: "
                f"{str(transcript_err)}"
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "팀 공용 Transcript 생성 중 "
                    f"오류가 발생했습니다: "
                    f"{str(transcript_err)}"
                ),
            )

        # ----------------------------------------------------
        # 8) I-SPOT 학대 분석
        # ----------------------------------------------------
        # 기본값을 먼저 None으로 설정한다.
        #
        # 아동 화자를 확정하지 못한 경우에는
        # 분석을 실행하지 않고 None을 반환한다.
        #
        # 분석이 가능한 경우:
        # 공용 Transcript
        # → CHILD 발화 추출
        # → 1차 학대유형
        # → 2차 세부유형
        # → XAI
        # ----------------------------------------------------

        abuse_prediction = None

        if (
            child_result.get("status") == "OK"
            and child_analysis_text
        ):

            print("5️⃣ I-SPOT 학대 분석 중...")

            try:
                abuse_prediction = analyze_stt_session(
                    transcript
                )

            except Exception as abuse_err:

                print(
                    f"❌ 학대 분석 오류: "
                    f"{str(abuse_err)}"
                )

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "학대 분석 중 "
                        f"오류가 발생했습니다: "
                        f"{str(abuse_err)}"
                    ),
                )

        else:
            print(
                "⚠️ 아동 화자를 확정하지 못해 "
                "학대 유형 분석을 건너뜁니다."
            )

        # ----------------------------------------------------
        # 9) 최종 API 응답
        # ----------------------------------------------------

        return {
            "status": "success",
            "file_name": filename,

            "stt_data": final_result,

            "transcript": transcript,

            "speaker_roles": child_result.get(
                "role_mapping",
                {},
            ),

            "child_speaker": child_result.get(
                "child_speaker"
            ),

            "child_analysis_status": child_result.get(
                "status"
            ),

            "child_analysis_text":
                child_analysis_text,

            "abuse_prediction":
                abuse_prediction,
        }

    # ========================================================
    # HTTP 예외
    # ========================================================

    except HTTPException as http_ex:
        raise http_ex

    # ========================================================
    # 예상하지 못한 서버 오류
    # ========================================================

    except Exception as e:

        print(
            f"❌ 미처리 내부 서버 오류: "
            f"{str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "서버 내부 오류 발생: "
                f"{str(e)}"
            ),
        )

    # ========================================================
    # 임시 파일 정리
    # ========================================================

    finally:

        if (
            temp_file_path
            and os.path.exists(temp_file_path)
        ):

            try:
                os.remove(temp_file_path)

                print(
                    "🧹 임시 파일 정상 삭제 완료: "
                    f"{temp_file_path}"
                )

            except Exception as remove_err:

                print(
                    f"⚠️ 임시 파일 삭제 실패: "
                    f"{str(remove_err)}"
                )


# ============================================================
# 7. 직접 실행
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )