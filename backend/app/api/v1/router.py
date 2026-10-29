# /api/v1 router 조합.

from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    audio,
    auth,
    cases,
    documents,
    followup,
    followup_questions,
    law_guide,
    risk_assessments,
    sessions,
    summary,
    tasks,
    transcript,
    voice_marks,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(cases.router)
# /cases/{case_id}/sessions — 주소는 Case 하위지만 sessions 그룹으로 묶는다.
api_router.include_router(cases.session_router)
api_router.include_router(sessions.router)
api_router.include_router(audio.router)
api_router.include_router(transcript.router)
api_router.include_router(analysis.router)
api_router.include_router(summary.router)
api_router.include_router(documents.router)
api_router.include_router(risk_assessments.router)
# /sessions/{session_id}/followup-questions — 승인한 추가 질문 목록(18절).
api_router.include_router(followup_questions.router)
api_router.include_router(tasks.router)
api_router.include_router(voice_marks.router)
# /sessions/{session_id}/followup-suggestions — 다음 상담 체크리스트(19절).
api_router.include_router(followup.router)
# /law-guide/questions — 회차 · 사례와 묶이지 않는 법령 · 매뉴얼 AI 질문(17절).
api_router.include_router(law_guide.router)
