# 모든 model 을 import 해 Base.metadata 를 완성한다.
# Alembic autogenerate 와 테스트용 create_all 이 이 모듈에 의존한다.

from app.models.analysis import AIAnalysis
from app.models.audio import AudioFile
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.case import Case
from app.models.document import Document
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.models.transcript import Transcript, TranscriptSegment
from app.models.user import User

__all__ = [
    "AIAnalysis",
    "AudioFile",
    "AuditLog",
    "Base",
    "Case",
    "ConsultationSession",
    "ConsultationSummary",
    "Document",
    "Transcript",
    "TranscriptSegment",
    "User",
]
