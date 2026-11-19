# 종결 검토 기록(2026-10-30) — 사례마다 한 행. ① 핵심 요약(AI 초안 또는 승인 요약 묶음) · 상담원 확인 체크 · 고친 문장,
# ② 종결보고서 칸(초기상황 · 종결상황 · 종합의견 · 날짜). API_CONTRACT 4절 closure-summary.

import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.encrypted_field import EncryptedColumn

if TYPE_CHECKING:
    from app.models.case import Case

CLOSURE_TEXT_MAX_LENGTH = 2000


class CaseClosureReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "case_closure_reviews"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # {source: "AI" | "APPROVED_SUMMARIES", model, generated_at, sessions: [회차 번호],
    #  groups: [{title, items: [{key, text, sessions}]}], report: {initial_situation, closing_situation}}. 만들기 전이면 null.
    summary_plain: Mapped[Optional[Dict[str, Any]]] = mapped_column("summary", JSONType, nullable=True)
    summary_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary = EncryptedColumn("summary", empty=None, json_value=True)  # 상담 본문 암호화 2단계(encrypted_field)
    # 요약 문장 key → 확인했는가 / 상담원이 고친 문장. 요약을 다시 만들면 비운다(key 가 바뀌므로).
    checks: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    edits_plain: Mapped[Dict[str, Any]] = mapped_column("edits", JSONType, default=dict, nullable=False)
    edits_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    edits = EncryptedColumn("edits", empty={}, json_value=True)  # 상담 본문 암호화 2단계(encrypted_field)
    # 종결보고서 칸: initial_situation · closing_situation · opinion(글), review_date · closing_date(YYYY-MM-DD).
    report_plain: Mapped[Dict[str, Any]] = mapped_column("report", JSONType, default=dict, nullable=False)
    report_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report = EncryptedColumn("report", empty={}, json_value=True)  # 상담 본문 암호화 2단계(encrypted_field)

    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    case: Mapped["Case"] = relationship(back_populates="closure_review")
