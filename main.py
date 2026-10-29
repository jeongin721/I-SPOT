import os
import sys
import tempfile
from typing import Any, Literal, Optional
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# ---------------------------------------------------------
# 콘솔 출력 인코딩을 UTF-8 로 고정한다.
#
# Windows 한국어 환경의 콘솔 기본 인코딩은 cp949 이고, cp949 에는
# 이모지가 없다. 아래 print 들이 쓰는 📥 1️⃣ ✅ 같은 문자를 만나면
# UnicodeEncodeError 가 나고, 그 지점에서 요청 처리가 중단되어
# /api/v1/analyze 가 500 을 돌려준다. (macOS/Linux 는 기본이 UTF-8
# 이라 드러나지 않는다.)
#
# 출력이 파일·파이프로 리다이렉트되어 reconfigure 가 없는 객체일
# 수 있으므로 방어적으로 처리한다.
# ---------------------------------------------------------
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# ispot 모듈 불러오기
from stt.ispot_stt import Transcriber
from stt.ispot_postprocess import STTPostProcessor
from child_analysis_text import ChildAnalysisTextBuilder
from transcript_builder import TranscriptBuilder
from abuse_model.infer_abuse import predict_abuse
from rag.session import analyze_reviewed_transcript, child_text_from_transcript

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

# ElevenLabs is the default production provider. The provider-level fallback
# uses Deepgram only for an ElevenLabs API/network/response failure.
stt_provider = Transcriber(
    provider=os.getenv("I_SPOT_STT_PROVIDER") or "elevenlabs"
)

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
            # This boundary heuristic is Deepgram-oriented; leave ElevenLabs
            # output untouched until it has its own production regression test.
            final_result = (
                raw_stt_result
                if stt_provider.provider_name == "elevenlabs"
                else post_processor.process(raw_stt_result)
            )
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

        # RAG(근거자료 · 법령 · 판례 · 화면별 매뉴얼 근거)는 여기서 돌리지 않는다.
        # 이 단계의 발화는 STT 검수 전이라 화자 · 문장이 바뀔 수 있다.
        # 상담사가 검수를 마친 Transcript 로 /api/v1/rag/analyze 를 부른다.

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

class PreviousCheckItem(BaseModel):
    # 이전 회차 '다음 상담 전 확인할 사항'과 처리 상태. open 이면 다음 질문에서 이행 여부를 다시 확인한다.
    item: str
    status: Literal["confirmed", "open"] = "open"
    note: str = ""


class PreviousSession(BaseModel):
    session_no: int
    # Backend 회차 ID. 근거를 누르면 그 회차 STT 검수 · 상세로 가는 링크에 쓴다(외부로 보내지 않음).
    session_id: Optional[str] = None
    # 상담사가 확정한 회차 요약 · 안전 계획. 보호자 진술을 그대로 옮기지 않은 확정본을 넣는다.
    summary: str = ""
    safety_plan: str = ""
    check_items: list[PreviousCheckItem] = Field(default_factory=list)
    # 이전 회차 검수본. 넣으면 아동(CHILD) 발화만 근거로 쓴다.
    transcript: Optional[dict[str, Any]] = None


class ChildAppResponse(BaseModel):
    response_id: str = ""
    question: str = ""
    answer: str
    answered_at: str = ""  # ISO 날짜(2026-10-07). 화면 근거 표기 "10/7 아이 앱 응답" 에 쓴다.


class ReviewedTranscriptRequest(BaseModel):
    # 검수가 끝난 Transcript(팀 공용 Contract). segments[].speaker 는 CHILD/GUARDIAN/COUNSELOR/OTHER/UNKNOWN.
    transcript: dict[str, Any]
    # 학대 유형을 이미 알면 넘긴다. 없으면 검수된 아동 발화로 KLUE-RoBERTa 를 다시 돌려 정한다.
    abuse_type: Optional[Literal["physical", "emotional", "sexual", "neglect", "multiple"]] = None
    # 사례에 등록된 아동 · 보호자 실명 등. 비식별에서 정확 매칭으로 한 번 더 가린다.
    known_identifiers: list[str] = Field(default_factory=list)
    # 다음 상담 질문의 근거로 함께 쓸 사례 기록. 없으면 이번 회차 아동 발화만 쓴다.
    session_no: Optional[int] = None
    session_id: Optional[str] = None  # 이번 회차 Backend ID(근거 링크용)
    previous_sessions: list[PreviousSession] = Field(default_factory=list)
    child_app_responses: list[ChildAppResponse] = Field(default_factory=list)


@app.post("/api/v1/rag/analyze")
def analyze_reviewed(request: ReviewedTranscriptRequest):
    """STT 검수 후 Transcript 로 근거자료 · 관련 법령 · 유사 판례 · 화면별 매뉴얼 근거를 만든다.

    - 아동(CHILD) 발화만 쓴다. 보호자 · 상담원 · 미확정 화자 발화는 넣지 않는다.
    - OpenAI(임베딩 · LLM)로 보내기 전에 비식별한다. 비식별 검증에 실패하면 전송하지 않고
      해당 결과에 privacy_blocked 와 사유를 담는다.
    - previous_sessions · child_app_responses 를 주면 다음 상담 질문이 이전 회차 · 아이 앱 응답까지 근거로 쓴다.
    """
    if not request.transcript.get("segments"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="분석할 Transcript segment 가 없습니다.",
        )

    abuse_type = request.abuse_type
    abuse_prediction = None
    if abuse_type is None:
        child_text = child_text_from_transcript(request.transcript)["text"]
        if child_text:
            try:
                abuse_prediction = predict_abuse(child_text)
            except Exception as abuse_err:
                print(f"❌ 학대 유형 분석 오류: {type(abuse_err).__name__}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"학대 유형 분석 중 오류가 발생했습니다: {type(abuse_err).__name__}",
                )
            abuse_type = resolve_rag_abuse_type(abuse_prediction)

    if not abuse_type:
        print("⚠️ 감지된 학대 유형이 없어 RAG 근거자료 분석을 건너뜁니다.")

    result = analyze_reviewed_transcript(
        request.transcript,
        abuse_type,
        known_identifiers=request.known_identifiers,
        session_no=request.session_no,
        session_id=request.session_id,
        previous_sessions=[session.model_dump() for session in request.previous_sessions],
        child_app_responses=[response.model_dump() for response in request.child_app_responses],
    )

    return {
        "status": "success",
        "abuse_type": abuse_type,
        "abuse_prediction": abuse_prediction,
        **result,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
