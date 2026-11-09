# /api/v1 router 조합.

from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    audio,
    auth,
    child_app,
    case_forms,
    cases,
    documents,
    followup_checklist,
    followup_checks,
    followup_questions,
    law_guide,
    risk_assessments,
    schedule,
    sessions,
    source_documents,
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
# /sessions/{session_id}/followup-checks — 다음 상담 전 확인할 사항 목록(18.1절, 2026-10-30).
api_router.include_router(followup_checks.router)
# /sessions/{session_id}/followup-checklist — 다음 상담 체크리스트(rag 확인 사항 · 추가 질문 공식 근거, 19절).
api_router.include_router(followup_checklist.router)
api_router.include_router(tasks.router)
api_router.include_router(voice_marks.router)
# /law-guide/questions — 회차 · 사례와 묶이지 않는 법령 · 매뉴얼 AI 질문(17절).
api_router.include_router(law_guide.router)
# /schedule/events — 일정(20절, 2026-11-02).
api_router.include_router(schedule.router)
# /sessions/{session_id}/source-document — 상담 기록 문서 회차(21절, 2026-11-02).
api_router.include_router(source_documents.router)
# /cases/{case_id}/forms — 기관 서식 작성 기록(22절, 2026-11-02).
api_router.include_router(case_forms.router)
# /child-app/* · /cases/{case_id}/child-app — 아이 앱(22절, 2026-11-09).
api_router.include_router(child_app.device_router)
api_router.include_router(child_app.case_router)
api_router.include_router(child_app.staff_router)
