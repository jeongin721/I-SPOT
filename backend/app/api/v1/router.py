# /api/v1 router 조합.

from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    audio,
    auth,
    cases,
    documents,
    sessions,
    summary,
    transcript,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(sessions.router)
api_router.include_router(audio.router)
api_router.include_router(transcript.router)
api_router.include_router(analysis.router)
api_router.include_router(summary.router)
api_router.include_router(documents.router)
