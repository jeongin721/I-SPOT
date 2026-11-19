"""
상담 기록 문서 회차의 학대 신호 · 대화 주제(2026-11-04, 이경진 님 요청).

문서 회차(document_note_llm)는 1 · 2단계(기록 확인 · 학대 신호 확인)를 건너뛰어 AI 분석이 없었다. 그래서 상담 이력의
주제 비중 · 회차별 세부 신호와 상담 전 브리핑의 처음 나온 이야기가 '분석이 끝난 회차가 없습니다' 로 비었다. 상담사가 쓴
문서에도 어떤 신호 · 주제가 있는지는 읽을 수 있으므로, 녹음 분석과 같은 부품으로 같은 모양의 결과를 만든다.

[흐름] 문서 원문(업로드 때 뽑은 글) →
  1) 문장 나누기(document_segments) — 한 문장이 한 '발화'(segment_id doc_001…). 칸 이름 줄('[아동 진술]')은 뺀다.
  2) 1차: 상담일지 전용 RoBERTa(predict_major_types input_mode="note") — 4대 유형 탐지. 글 전체와 문장 2개씩 겹친 창을 모두
     판정해 유형별로 합친다(major_types_over_windows).
  3) 2차: 탐지된 유형만 세부 유형 · 근거 문장(second_stage_llm.analyze_subtypes) — 가린 글로 보내고 되돌린 뒤 문장에 잇는다.
  4) 유형별 심각도(severity_llm) · 대화 주제(topic_tag_llm)를 함께 띄운다.
  결과는 AI Output Contract 의 신호 칸(abuse_signals · risk_utterances · severity_ratings · topic_tags)만 채운다.
  상담 요약 · 일지 · 확인 메모 · 추가 질문은 만들지 않는다(문서 회차는 3 · 4단계를 문서에서 옮겨 채운다).

[녹음 분석과 다른 점]
- 근거는 문서 문장이다(전사본 · 음성 시각이 없다). topic_tags 의 start_ms 는 None 으로 둔다.
- 주제 분류 · 2차는 '아동 발화' 대신 '기록 문장' 을 본다. 주제 비중은 문장 수 기준이다.
- AI 제안일 뿐이다 — 학대 여부를 확정하지 않는다(녹음 분석과 같다).

[왜 창으로 나누나 — 2026-11-09 민규 발표 서버 확인] 글 전체를 한 번에 넣으면 위험 문장이 일상 문장에 묻혀 네 유형 모두 놓쳤다
(가상 글 실측: '머리채를 잡혔다고 진술함' 단독 0.926 → 일상 문장과 함께 0.010). 가상 평가 글(위험 문장 포함 48건 · 정상 60건, 표본이
작은 참고값)에서 전체 글만 19/48 · 오탐 0, 1문장 창 42/48 · 오탐 13(부인 진술에 정서학대), 2문장 창 38/48 · 오탐 3, 3문장 창 34/48 ·
오탐 5 — 2문장을 쓴다.

[근거 없는 신호] 1차가 탐지했어도 2차에서 근거 문장을 못 찾은 유형은 저장하지 않고 경고를 남긴다(drop_ungrounded_signals — 녹음
경로 ai_adapter.drop_ungrounded_risk_items 와 같은 규칙 · 문구, 05_RULES §1).

개인정보: 밖으로 나가는 글은 privacy_gateway.mask_for_outbound 로 가리고 답은 restore_pii 로 되돌린다.
무거운 모듈(RoBERTa · NER · openai)은 CI 에 없어 함수 안에서 import 한다(document_segments · risk_utterances_from 은 시험한다).
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_MODEL = "gpt-5.6-luna"
SEGMENT_PREFIX = "doc_"
#: 2차 · 근거 잇기에 쓰는 줄 머리(녹음은 '아동' · '상담사').
RECORD_LABEL = "기록"
#: 문장 수 상한(30,000자 문서도 이 안에 든다 — 넘는 뒤 문장은 보지 않는다).
MAX_SEGMENTS = 400
#: 1차 판정 창의 문장 수(한 문장씩 옮긴다). 고른 이유는 모듈 머리 '왜 창으로 나누나'.
WINDOW_SENTENCES = 2

_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+|\n+")
_HEADING_ONLY = re.compile(r"^\s*\[[^\]\n]{1,30}\]\s*$")

#: 2차 한글 대분류 → 계약 영문(contract_adapter.MAJOR_TYPE_TO_ENGLISH 와 같다).
_ENGLISH = {"신체학대": "PHYSICAL", "정서학대": "EMOTIONAL", "성학대": "SEXUAL", "방임": "NEGLECT"}
_STRENGTH = {"높음": "HIGH", "중간": "MEDIUM", "낮음": "LOW"}


def document_segments(text: str) -> List[Dict[str, Any]]:
    """문서 글 → 문장마다 하나의 발화 모양(STT segment 와 같은 칸). 시각은 순서를 나타내는 값일 뿐이다."""

    segments: List[Dict[str, Any]] = []
    for piece in _SENTENCE_END.split(text or ""):
        sentence = " ".join(piece.split())
        if not sentence or _HEADING_ONLY.match(sentence):
            continue
        index = len(segments) + 1
        segments.append(
            {
                "segment_id": f"{SEGMENT_PREFIX}{index:03d}",
                # 주제 분류(topic_tag_llm)는 아동 발화만 보므로 문장을 그 자리에 둔다(화면에는 화자로 나가지 않는다).
                "speaker": "CHILD",
                "text": sentence,
                "start_ms": index * 1000,
                "end_ms": index * 1000 + 999,
                "confidence": 1.0,
                "is_low_confidence": False,
            }
        )
        if len(segments) >= MAX_SEGMENTS:
            break
    return segments


def risk_utterances_from(subtype_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """2차 결과의 근거(문장에 이어진 것만) → 계약 risk_utterances. 근거 문장을 못 찾은 것은 뺀다."""

    rows: List[Dict[str, Any]] = []
    for major in subtype_result.get("results") or []:
        abuse_type = _ENGLISH.get(major.get("major_type"))
        if abuse_type is None:
            continue
        for subtype in major.get("subtypes") or []:
            name = subtype.get("type")
            if not isinstance(name, str) or not name.strip():
                continue
            for evidence in subtype.get("evidences") or []:
                stamps = evidence.get("timestamps") or {}
                segment_ids = [sid for sid in stamps.get("segment_ids") or [] if isinstance(sid, str)]
                if not segment_ids:
                    continue
                rows.append(
                    {
                        "text": evidence.get("matched_evidence") or evidence.get("evidence") or "",
                        "segment_ids": segment_ids,
                        "abuse_type": abuse_type,
                        "subtype": name.strip(),
                        "evidence_strength": _STRENGTH.get(evidence.get("evidence_strength"), "LOW"),
                        "reason": evidence.get("strength_reason") or "",
                        "evidence_verified": bool(evidence.get("evidence_verified")),
                        "legal_references": [],
                    }
                )
    return rows


def abuse_signals_from(major_types: Dict[str, Any], risk_utterances: List[Dict[str, Any]], labels: List[str]) -> List[Dict[str, Any]]:
    """1차 판정 → 계약 abuse_signals(유형마다 하나, 근거 문장은 같은 유형 risk_utterances 에서 모은다)."""

    signals = []
    for label in labels:
        info = major_types.get(label) or {}
        abuse_type = _ENGLISH[label]
        detected = bool(info.get("detected"))
        segment_ids: List[str] = []
        for row in risk_utterances:
            if row["abuse_type"] == abuse_type:
                segment_ids.extend(sid for sid in row["segment_ids"] if sid not in segment_ids)
        filtered = info.get("filtered_reason")
        signals.append(
            {
                "abuse_type": abuse_type,
                "detected": detected,
                "segment_ids": segment_ids,
                "detection_source": "MODEL" if detected else ("FILTERED" if filtered else None),
                "filtered_reason": filtered if not detected else None,
            }
        )
    return signals


def record_lines(segments: List[Dict[str, Any]]) -> Tuple[List[Tuple[str, str, Dict[str, Any]]], str]:
    """문장 목록 → (2차 · 근거 잇기에 쓰는 줄, 그 줄을 이은 원래 글). 2차에 보내는 글은 이 원래 글을 가린 것이다."""

    lines = [(RECORD_LABEL, segment["text"], segment) for segment in segments]
    return lines, "\n".join(f"{label}: {sentence}" for label, sentence, _ in lines)


def link_to_sentences(subtype_result: Dict[str, Any], segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """2차 근거 인용을 문장에 잇는다. 인용 위치는 가린 글 기준이라 원래 글에서 다시 찾는다(source_text) — 등록 이름이
    '[PERSON_01]' 처럼 길어지면 뒤 문장에 붙던 문제(민규 #134 리뷰, 녹음 경로와 같은 처리)."""

    from ai.modeling.abuse.evidence_location import build_line_char_spans, link_evidence_timestamps

    lines, full_text = record_lines(segments)
    return link_evidence_timestamps(subtype_result, build_line_char_spans(lines), source_text=full_text)


def document_windows(segments: List[Dict[str, Any]], size: int = WINDOW_SENTENCES) -> List[str]:
    """문장 목록 → size 문장씩 한 문장씩 옮긴 글. 문장이 size 보다 적으면 전체 하나."""

    sentences = [segment["text"] for segment in segments]
    return ["\n".join(sentences[start : start + size]) for start in range(max(1, len(sentences) - size + 1))] if sentences else []


def major_types_over_windows(
    segments: List[Dict[str, Any]],
    predict: Callable[[str], Dict[str, Any]],
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """글 전체와 창마다 1차 판정 → 유형별로 합친다. 어느 하나라도 탐지면 탐지, 아니면 처음 나온 filtered_reason 을 남긴다."""

    texts = ["\n".join(segment["text"] for segment in segments), *document_windows(segments)]
    merged: Dict[str, Dict[str, Any]] = {}

    for text in dict.fromkeys(texts):
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("문서 1차 판정이 제한 시간을 넘겼습니다.")
        for label, info in predict(text).items():
            current = merged.setdefault(label, {"detected": False})
            if info.get("detected"):
                current["detected"] = True
                current.pop("filtered_reason", None)
            elif not current["detected"] and info.get("filtered_reason") and "filtered_reason" not in current:
                current["filtered_reason"] = info["filtered_reason"]

    return merged


def drop_ungrounded_signals(signals: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """탐지됐는데 근거 문장이 없는 유형을 뺀다 → (남은 신호, 경고). 탐지 안 된 유형은 근거가 필요 없어 그대로 둔다."""

    kept = [signal for signal in signals if signal["detected"] is False or signal["segment_ids"]]
    dropped = len(signals) - len(kept)

    return kept, ([f"segment 근거가 없는 신호 {dropped}건을 제외했습니다."] if dropped else [])


def grounded_severity_ratings(ratings: List[Dict[str, Any]], signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """근거가 남은 탐지 유형의 심각도만 둔다 — 뺀 유형의 단계가 신호 이력 ai_level 로 읽히지 않게(민규 #164)."""

    kept = {signal["abuse_type"] for signal in signals if signal["detected"]}

    return [rating for rating in ratings if _ENGLISH.get(rating.get("major_type")) in kept]


def analyze_document_signals(
    text: str,
    known_identifiers: Optional[List[str]] = None,
    model: Optional[str] = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """문서 글 → 신호 칸만 채운 AI Output Contract 모양 dict(+ "model"). 문장이 없으면 ValueError."""

    from ai.modeling.abuse.infer_abuse_v3_adapter import predict_major_types
    from ai.modeling.abuse.infer_audio_session import ABUSE_LABELS
    from ai.modeling.abuse.llm_backend import build_openai_client_and_model
    from ai.modeling.abuse.pii_masking import restore_pii
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound
    from ai.modeling.abuse.second_stage_llm import analyze_subtypes
    from ai.modeling.abuse.severity_llm import build_evidence_block_text, rate_severity_from_text
    from ai.modeling.abuse.topic_tag_llm import generate_topic_tags_from_masked_text, mask_child_lines, wait_for_topic_tags

    segments = document_segments(text)
    if not segments:
        raise ValueError("분석할 문장이 없습니다.")
    known = list(known_identifiers or [])
    _lines, full_text = record_lines(segments)

    client, model_name = build_openai_client_and_model(default_openai_model=model or DEFAULT_MODEL)

    # 주제 분류는 1 · 2차와 상관없어 먼저 띄운다(가리기가 막히면 None — 분류하지 못함).
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        masked_lines = mask_child_lines(mask_for_outbound, segments, known)
        topic_future = (
            executor.submit(
                generate_topic_tags_from_masked_text,
                client=client,
                model=model_name,
                masked_child_lines=masked_lines,
                segments=segments,
                deadline=deadline,
            )
            if masked_lines is not None
            else None
        )

        # 1차: 상담일지(3인칭 서술) 전용 모델. 글 전체 + 2문장 창.
        major_types = major_types_over_windows(
            segments, lambda chunk: predict_major_types(text=chunk, input_mode="note"), deadline=deadline
        )
        detected = [label for label in ABUSE_LABELS if (major_types.get(label) or {}).get("detected")]

        if detected:
            masked_full, entity_map = mask_for_outbound(full_text, known_identifiers=known)
            subtype_result = analyze_subtypes(
                text=masked_full, major_types=detected, client=client, model=model_name, deadline=deadline
            )
            subtype_result = restore_pii(subtype_result, entity_map)
            subtype_result = link_to_sentences(subtype_result, segments)
        else:
            subtype_result = {"results": []}

        severity_ratings: List[Dict[str, Any]] = []
        blocks = build_evidence_block_text(subtype_result)
        if blocks:
            severity_text = "\n\n".join(f"[{major}]\n{block}" for major, block in blocks.items())
            masked_severity, severity_map = mask_for_outbound(severity_text, known_identifiers=known)
            rated = rate_severity_from_text(
                client=client,
                model=model_name,
                major_types=list(blocks.keys()),
                masked_evidence_text=masked_severity,
                deadline=deadline,
            )
            severity_ratings = [
                {
                    "major_type": rating.get("major_type"),
                    "level": rating.get("level"),
                    "reason": rating.get("reason", ""),
                    "matched_evidence": rating.get("matched_evidence", ""),
                    "reviewed": rating.get("reviewed", False),
                }
                for rating in restore_pii(rated, severity_map) or []
                if isinstance(rating, dict)
            ]

        topic_tags = wait_for_topic_tags(topic_future, deadline) if topic_future is not None else None
    finally:
        executor.shutdown(wait=False)

    risk_utterances = risk_utterances_from(subtype_result)
    abuse_signals, warnings = drop_ungrounded_signals(abuse_signals_from(major_types, risk_utterances, list(ABUSE_LABELS)))
    return {
        "schema_version": "1.0",
        "abuse_signals": abuse_signals,
        "risk_utterances": risk_utterances,
        "severity_ratings": grounded_severity_ratings(severity_ratings, abuse_signals),
        # 근거가 문장이라 음성 시각은 없다.
        "topic_tags": (
            [{**tag, "start_ms": None} for tag in topic_tags if isinstance(tag, dict)] if isinstance(topic_tags, list) else None
        ),
        "warnings": warnings,
        "model": model_name,
    }
