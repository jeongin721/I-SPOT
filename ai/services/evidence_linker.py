# 요약의 각 key_point와 실제 Transcript의 근거 segment_id를 연결한다.
# CHILD 발화를 우선하며 필요하면 상담사 질문→아동 답변(Q-A) 문맥까지 활용한다.

import re
from typing import List

from pydantic import BaseModel

from ai.schemas.analysis import Transcript


class EvidenceLink(BaseModel):
    text: str
    segment_ids: List[str]
    score: float


def normalize_text(text: str) -> str:
    text = text.lower()

    text = re.sub(
        r"[^\w가-힣\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def extract_words(text: str) -> set[str]:
    normalized = normalize_text(text)

    return {
        word
        for word in normalized.split()
        if len(word) >= 2
    }


def calculate_similarity(
    target_text: str,
    source_text: str,
) -> float:
    """
    요약 문장과 Transcript segment 간
    단순 단어 overlap 비율을 계산한다.
    """

    target_words = extract_words(
        target_text
    )

    source_words = extract_words(
        source_text
    )

    if not target_words:
        return 0.0

    matched = (
        target_words & source_words
    )

    return len(matched) / len(
        target_words
    )


def find_evidence_segments(
    text: str,
    transcript: Transcript,
    threshold: float = 0.2,
    max_segments: int = 3,
) -> EvidenceLink:
    """
    요약 문장과 관련된 근거 segment를 찾는다.

    우선순위:
    1. 직접적으로 유사한 CHILD 발화
    2. COUNSELOR 질문과 유사한 경우,
       바로 다음 CHILD 응답을 근거로 연결
    3. 근거가 충분하지 않으면 빈 결과 반환
    """

    segments = transcript.segments

    child_candidates = []

    # 1. CHILD 발화 직접 검색
    for segment in segments:
        if segment.speaker != "CHILD":
            continue

        score = calculate_similarity(
            target_text=text,
            source_text=segment.text,
        )

        if score >= threshold:
            child_candidates.append(
                (
                    segment.segment_id,
                    score,
                )
            )

    if child_candidates:
        child_candidates.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        selected = child_candidates[
            :max_segments
        ]

        return EvidenceLink(
            text=text,
            segment_ids=[
                segment_id
                for segment_id, _ in selected
            ],
            score=max(
                score
                for _, score in selected
            ),
        )

    # 2. CHILD 직접 매칭이 없으면
    # COUNSELOR 질문 → 바로 다음 CHILD 응답 확인
    qa_candidates = []

    for index, segment in enumerate(
        segments
    ):
        if segment.speaker != "COUNSELOR":
            continue

        question_score = calculate_similarity(
            target_text=text,
            source_text=segment.text,
        )

        if question_score < threshold:
            continue

        # 질문 이후 첫 CHILD 발화 탐색
        for next_segment in segments[
            index + 1:
        ]:
            if next_segment.speaker == "CHILD":
                qa_candidates.append(
                    (
                        next_segment.segment_id,
                        question_score,
                    )
                )
                break

            # 다음 상담사 질문이 나오면
            # 현재 Q-A pair 종료
            if next_segment.speaker == "COUNSELOR":
                break

    if qa_candidates:
        qa_candidates.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        selected = qa_candidates[
            :max_segments
        ]

        return EvidenceLink(
            text=text,
            segment_ids=[
                segment_id
                for segment_id, _ in selected
            ],
            score=max(
                score
                for _, score in selected
            ),
        )

    # 3. 근거 없음
    return EvidenceLink(
        text=text,
        segment_ids=[],
        score=0.0,
    )

def link_summary_evidence(
    key_points: List[str],
    transcript: Transcript,
) -> List[EvidenceLink]:
    """
    Summary key_points 각각에 대해
    근거 segment_id를 연결한다.
    """

    return [
        find_evidence_segments(
            text=key_point,
            transcript=transcript,
        )
        for key_point in key_points
    ]