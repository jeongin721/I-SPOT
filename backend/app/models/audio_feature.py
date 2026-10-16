# 음성 Paralinguistic Feature 저장.
#
# STT 로 변환된 "말한 내용" 외에, "말하는 방식"(휴지·응답지연·발화속도·피치·에너지)을
# 화자별로 보관한다. 텍스트 기반 위험도 분류를 멀티모달로 확장하기 위한 입력이다.
#
# 추출에는 audio 파일과 STT segment 가 모두 필요하므로(발화속도는 segment 의 text 길이를
# 사용한다), 어떤 Transcript version 을 기준으로 뽑았는지 AIAnalysis 와 같은 방식으로
# 추적한다. 상담사가 원문을 수정해 새 version 이 생기면 특징도 다시 추출할 수 있다.

import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audio import AudioFile
    from app.models.session import ConsultationSession
    from app.models.transcript import Transcript


class AudioFeature(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audio_features"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audio_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audio_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 발화속도/휴지 계산이 segment 에 의존하므로 기준 version 을 남긴다.
    transcript_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transcripts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transcript_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    schema_version: Mapped[str] = mapped_column(String(10), default="1.0", nullable=False)

    # 특징을 뽑은 모듈. 추출 로직이 바뀌었을 때 과거 값과 구분하기 위해 남긴다.
    extractor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # {speaker: {turn_count, mean_pause_ms, pitch_mean_hz, energy_mean, ...}}
    # 화자 라벨은 STT Contract 의 Speaker 를 그대로 사용한다.
    features: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    session: Mapped["ConsultationSession"] = relationship(
        back_populates="audio_features"
    )
    audio_file: Mapped["AudioFile"] = relationship(back_populates="features")
    transcript: Mapped[Optional["Transcript"]] = relationship()

    def __repr__(self) -> str:
        return f"<AudioFeature id={self.id} audio_file={self.audio_file_id}>"
