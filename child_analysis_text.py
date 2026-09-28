from typing import Any, Dict, List

from speaker_role_runtime import RuntimeSpeakerRoleMapper


class ChildAnalysisTextBuilder:
    """
    STT 결과에서 아동 발화만 추출하고,
    selective fallback으로 복구된 gap_text를 시간순으로 보완한다.

    주의:
    - fallback 전체 text가 아니라 gap_text만 사용한다.
    - speaker_hint가 실제 CHILD로 판정된 경우에만 gap_text를 사용한다.
    - 원본 STT segment는 수정하지 않는다.
    """

    def _split_sentences(self, text: str) -> list[str]:
        """
        fallback gap_text를 간단한 문장 단위로 분리한다.
        ?, !, . 기준으로 문장 끝을 최대한 보존한다.
        """
        import re

        if not text:
            return []

        sentences = re.findall(r'[^.!?]+[.!?]?', text)

        return [
            sentence.strip()
            for sentence in sentences
            if sentence.strip()
        ]


    def _filter_fallback_child_text(self, text: str) -> str:
        """
        fallback으로 복구된 문장 중
        명확한 질문형 발화를 CHILD 분석 텍스트에서 제외한다.

        주의:
        이것은 화자분리 모델이 아니라 보수적 필터링 규칙이다.
        """
        if not text:
            return ""

        kept_sentences = []

        for sentence in self._split_sentences(text):

            # 가장 명확한 질문 표시
            if sentence.rstrip().endswith("?"):
                continue

            kept_sentences.append(sentence)

        return " ".join(kept_sentences).strip()


    def __init__(self):
        self.role_mapper = RuntimeSpeakerRoleMapper()

    def build(
        self,
        stt_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        segments = stt_data.get("segments", [])
        fallback_evidence = stt_data.get(
            "fallback_evidence",
            [],
        )

        # -------------------------------------------------
        # 1. Runtime speaker role 판정
        # -------------------------------------------------

        role_mapping = self.role_mapper.map_roles(
            segments
        )

        child_speakers = [
            speaker
            for speaker, info in role_mapping.items()
            if info.get("role") == "CHILD"
        ]

        # CHILD가 정확히 1명일 때만
        # 분석 텍스트를 생성한다.
        if len(child_speakers) != 1:
            return {
                "status": "UNRESOLVED_CHILD_SPEAKER",
                "child_speaker": None,
                "child_analysis_text": "",
                "role_mapping": role_mapping,
                "items": [],
            }

        child_speaker = child_speakers[0]

        # -------------------------------------------------
        # 2. 기존 Deepgram CHILD 발화 수집
        # -------------------------------------------------

        timeline_items: List[Dict[str, Any]] = []

        for segment in segments:

            if segment.get("speaker") != child_speaker:
                continue

            text = (
                segment.get("text")
                or ""
            ).strip()

            if not text:
                continue

            start_ms = segment.get(
                "start_ms",
                0,
            )

            timeline_items.append(
                {
                    "source": "deepgram",
                    "start_ms": int(start_ms),
                    "text": text,
                }
            )

        # -------------------------------------------------
        # 3. fallback gap_text 추가
        # -------------------------------------------------

        for evidence in fallback_evidence:

            speaker_hint = evidence.get(
                "speaker_hint"
            )

            gap_text = (
                evidence.get("gap_text")
                or ""
            ).strip()

            gap_start_ms = evidence.get(
                "gap_start_ms"
            )

            # fallback이 CHILD 쪽에서 발생한 경우에만 사용
            if speaker_hint != child_speaker:
                continue

            if not gap_text:
                continue

            if not isinstance(
                gap_start_ms,
                (int, float),
            ):
                continue

            filtered_gap_text = self._filter_fallback_child_text(
                gap_text
            )

            if not filtered_gap_text:
                continue

            timeline_items.append(
                {
                    "source": "fallback_gap",
                    "start_ms": int(
                        gap_start_ms
                    ),
                    "text": filtered_gap_text,
                }
            )

        # -------------------------------------------------
        # 4. 시간순 정렬
        # -------------------------------------------------

        timeline_items.sort(
            key=lambda item: item["start_ms"]
        )

        # -------------------------------------------------
        # 5. 최종 child_analysis_text 생성
        # -------------------------------------------------

        child_analysis_text = " ".join(
            item["text"]
            for item in timeline_items
        ).strip()

        return {
            "status": "OK",
            "child_speaker": child_speaker,
            "child_analysis_text":
                child_analysis_text,
            "role_mapping": role_mapping,
            "items": timeline_items,
        }