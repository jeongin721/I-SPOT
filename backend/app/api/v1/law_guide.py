# 법령 · 매뉴얼 AI 질문 Router — API_CONTRACT 16절 (2026-10-28).
from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.law_guide import LawGuideAnswerResponse, LawGuideQuestionRequest
from app.services import law_guide_service

router = APIRouter(prefix="/law-guide", tags=["law-guide"])


@router.post("/questions", response_model=DataResponse[LawGuideAnswerResponse])
def ask_question(
    payload: LawGuideQuestionRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[LawGuideAnswerResponse]:
    """
    법령 질문 하나에 조문 근거를 달아 답한다(LawGuide 화면 'AI 에게 묻기').

    로그인한 사용자(상담원 · 관리자)면 누구나. 동기 응답이라 화면은 '찾는 중' 을 보이고 기다린다.
    꺼져 있으면 503 LAW_QA_DISABLED, 분당 한도 초과 429 RATE_LIMITED, 제한 시간 초과 504 AI_TIMEOUT,
    LLM 실패 502 AI_FAILED · AI_INVALID_OUTPUT, 법령 자료 없음 503 LAW_SOURCE_UNAVAILABLE.
    동기 def 라 FastAPI 스레드풀에서 돈다(분석의 BackgroundTasks 와 섞지 않는다).
    """

    return DataResponse(data=law_guide_service.ask(db, current_user, payload.question))
