# /api/v1 router 조합.

from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    audio,
    auth,
    cases,
    documents,
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
api_router.include_router(tasks.router)
api_router.include_router(voice_marks.router)
