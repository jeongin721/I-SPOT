import os
import tempfile
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ispot 모듈 불러오기
from ispot_stt import SelectiveFallbackSTTProvider
from ispot_postprocess import STTPostProcessor
from child_analysis_text import ChildAnalysisTextBuilder
from transcript_builder import TranscriptBuilder
from abuse_model.infer_abuse import predict_abuse
from rag.pipeline import analyze_consultation_evidence

load_dotenv()

# ---------------------------------------------------------
# KLUE-RoBERTa 멀티라벨 결과 → RAG abuse_type 매핑
# ---------------------------------------------------------
ABUSE_LABEL_TO_RAG_TYPE = {
    "신체학대": "physical",
    "정서학대": "emotional",
    "성학대": "sexual",
    "방임": "neglect",
}


def resolve_rag_abuse_type(abuse_prediction: dict | None) -> str | None:
    """abuse_prediction에서 threshold를 넘긴(detected) 라벨을 RAG abuse_type으로 변환한다.

    감지된 라벨이 없으면 None, 2개 이상이면 "multiple"을 반환한다.
    """
    if not abuse_prediction:
        return None

    detected_types = [
        ABUSE_LABEL_TO_RAG_TYPE[label]
        for label in ABUSE_LABEL_TO_RAG_TYPE
        if abuse_prediction.get(label, {}).get("detected")
    ]

    if not detected_types:
        return None
    if len(detected_types) > 1:
        return "multiple"
    return detected_types[0]

# ---------------------------------------------------------
# 서버 공용 AI / STT 객체
# ---------------------------------------------------------
# 요청마다 새로 만들지 않고 서버 실행 시 한 번만 생성한다.
#
# Whisper large-v3는 SelectiveFallbackSTTProvider 내부에서
# 실제 fallback이 필요한 순간에만 lazy loading되고,
# 이후 요청에서는 같은 모델 인스턴스를 재사용한다.
# ---------------------------------------------------------

stt_provider = SelectiveFallbackSTTProvider()

post_processor = STTPostProcessor(
    low_confidence_threshold=0.70
)

child_builder = ChildAnalysisTextBuilder()
transcript_builder = TranscriptBuilder()

app = FastAPI(
    title="I-SPOT AI Backend API",
    description="아동학대 위험 감지 음성 분석 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 허용할 오디오 확장자 목록
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}

@app.get("/")
def read_root():
    return {"status": "online", "message": "I-SPOT API Server is running!"}

@app.post("/api/v1/analyze")
def analyze_audio(file: UploadFile = File(...)):
    filename = file.filename
    print(f"📥 오디오 파일 수신 요청: {filename}")
    
    # 1. 파일 확장자 검증 예외 처리
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 파일 형식입니다. ({', '.join(ALLOWED_EXTENSIONS)} 지원)"
        )

    temp_file_path = None

    try:
        # 2. 파일 데이터 읽기 및 빈 파일 검증
        audio_bytes = file.file.read()
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="업로드된 파일이 비어 있습니다."
            )
        
        # 3. 임시 파일 안전 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name

        print(f"🔄 임시 파일 생성 완료: {temp_file_path}")

        # 4. Deepgram STT 변환 (예외 처리 포함)
        print("1️⃣ Deepgram STT 진행 중...")
        try:
            raw_stt_result = stt_provider.transcribe(
                temp_file_path
            )
        except Exception as stt_err:
            print(f"❌ STT 엔진 오류: {str(stt_err)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"STT 엔진 처리 중 오류가 발생했습니다: {str(stt_err)}"
            )

        # 5. 후처리 및 발화 병합
        print("2️⃣ STT 결과 후처리 및 발화 병합 중...")
        try:
            final_result = post_processor.process(raw_stt_result)
        except Exception as post_err:
            print(f"❌ 후처리 모듈 오류: {str(post_err)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"STT 후처리 작업 중 오류가 발생했습니다: {str(post_err)}"
            )

        print("✅ STT 파이프라인 분석 완수!")

        # 6. Runtime speaker role 판별 + 아동 분석 텍스트 생성
        print("3️⃣ 아동 화자 판별 및 분석 텍스트 생성 중...")

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

                # 7. 팀 공용 Transcript 생성
        print("4️⃣ 팀 공용 Transcript 생성 중...")

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
                    f"오류가 발생했습니다: {str(transcript_err)}"
                ),
            )


        # 8. KLUE-RoBERTa 학대 유형 분석
        abuse_prediction = None

        if (
            child_result.get("status") == "OK"
            and child_analysis_text
        ):

            print("5️⃣ KLUE-RoBERTa 학대 유형 분석 중...")

            try:
                abuse_prediction = predict_abuse(
                    child_analysis_text
                )

            except Exception as abuse_err:
                print(
                    f"❌ 학대 유형 분석 오류: "
                    f"{str(abuse_err)}"
                )

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "학대 유형 분석 중 "
                        f"오류가 발생했습니다: {str(abuse_err)}"
                    ),
                )

        else:
            print(
                "⚠️ 아동 화자를 확정하지 못해 "
                "학대 유형 분석을 건너뜁니다."
            )

        # 9. RAG 근거자료 / 관련 법령 / 다음 상담 체크리스트 분석
        rag_analysis = None
        rag_abuse_type = resolve_rag_abuse_type(abuse_prediction)

        if rag_abuse_type and child_analysis_text:
            print("6️⃣ RAG 근거자료 및 관련 법령 분석 중...")

            try:
                rag_analysis = analyze_consultation_evidence(
                    text=child_analysis_text,
                    abuse_type=rag_abuse_type,
                )
            except Exception as rag_err:
                # RAG는 보조 참고정보이므로 실패해도 STT/학대유형 분석 결과는 그대로 반환한다.
                print(f"❌ RAG 근거자료 분석 오류: {str(rag_err)}")
                rag_analysis = {
                    "error": f"RAG 근거자료 분석 중 오류가 발생했습니다: {str(rag_err)}"
                }
        else:
            print(
                "⚠️ 감지된 학대 유형이 없어 "
                "RAG 근거자료 분석을 건너뜁니다."
            )

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

            "rag_analysis":
                rag_analysis,
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        print(f"❌ 미처리 내부 서버 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 내부 오류 발생: {str(e)}"
        )

    finally:
        # 6. 임시 파일 안전 삭제 보장 (항상 실행)
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"🧹 임시 파일 정원 삭제 완료: {temp_file_path}")
            except Exception as remove_err:
                print(f"⚠️ 임시 파일 삭제 실패: {str(remove_err)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)