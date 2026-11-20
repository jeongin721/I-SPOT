"""
STT 검수(원문 확정 전) '1차 임시 핵심 발화' 를 LLM 으로 한 번 더 확인한다(2026-11-20, 팀장 결정).

[왜]
1차 모델은 문맥을 거의 보지 않고 '다쳤어요 · 병원 · 뼈' 같은 말에 반응한다. 11/20 시험 녹음에서 "오토바이에 치여서 다쳤어요.
병원 갔는데 다행히 뼈는 안 부러졌어요." 가 신체학대(아동복지법 제17조 제3호)로 STT 화면에 떴다. 확정 뒤 정식 분석(2차)은
이 줄을 걸렀지만 상담원은 그 전에 잘못된 표시를 먼저 본다. law_match(로컬 임베딩, PR #188)는 '닮은 말' 만 보므로
"다쳤어요" 와 "맞아서 다쳤어요" 를 잘 가르지 못한다 — 누가 · 왜 다치게 했는지는 문맥을 읽어야 안다.

[팀장 결정 2026-11-20 — 11/09 '검수 전 외부 전송 없음' 을 바꿈]
확정 전에는 **1차가 고른 아동 발화와 그 앞뒤 몇 줄만** 이름을 가려 OpenAI 로 보낸다. 원문 전체는 지금처럼 확정 뒤 정식
분석에서만 나간다. (녹음 파일 자체는 STT 를 위해 이미 ElevenLabs 로 나가고 있다 — 새로 늘어나는 것은 이름을 가린 일부 문장.)

[어떻게]
1. 고른 줄마다 앞뒤 KEY_SCAN_LLM_CONTEXT_LINES(기본 2)줄을 붙여 덩어리를 만든다(겹치면 합침, 떨어진 덩어리 사이는 '…').
2. 이름 가리기: privacy_gateway.mask_for_outbound(차단형 재검사) + 사례 등록 이름. 확정 전 원문은 STT 오인식이 남아
   등록 이름과 한 글자 다르게 적힐 수 있어(김수아 → 김수하) **성이 같고 이름 한 글자만 다른 표기**도 등록 이름으로 더해 가린다
   (similar_name_variants — 더 가리는 쪽으로만 틀린다).
3. LLM 은 ▶ 줄마다 1차 후보 유형 가운데 실제로 해당하는 유형과 짧은 이유를 준다. 사고 · 또래 다툼 · 부정 대답은 뺀다.
4. 확인된 유형만 조문(law_match.statute_reference)을 붙이고 이유를 excerpt 로, basis="LLM" 으로 표시한다. LLM 이 어느 유형도
   확인하지 않은 줄은 결과에서 뺀다.

[실패 — STT 를 막지 않는다]
꺼짐(KEY_SCAN_LLM_VERIFY=off) · OPENAI_API_KEY 없음 · 가리기 차단 · 시간 초과 · 형식 오류면 None 을 돌려주고, 호출부
(contract_adapter.key_scan_as_contract)는 PR #188 의 로컬 임베딩 매칭으로 돌아간다. 원문 · 예외 문구는 로그에 남기지 않는다.

판정이 아니다 — 화면 문구는 '임시 · AI 확인' 이고 법 위반을 확정하지 않는다(05_RULES §1). 정식 판정은 확정 뒤 분석이 한다.
표준 라이브러리만 맨 위에서 가져온다(가리기 · OpenAI 는 지연 import — backend/tests 에서 시험).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5.6-luna"  # 2차 세부유형 분석(infer_audio_session subtype_model)과 같은 모델

ENV_VERIFY = "KEY_SCAN_LLM_VERIFY"
ENV_TIMEOUT = "KEY_SCAN_LLM_TIMEOUT_SECONDS"
ENV_CONTEXT = "KEY_SCAN_LLM_CONTEXT_LINES"

DEFAULT_TIMEOUT_SECONDS = 30.0  # 11/20 실측 한 번 10~16초(가상 대화 18줄 중 8줄 확인)
DEFAULT_CONTEXT_LINES = 2
MAX_REASON_CHARS = 60

TYPES = ("신체학대", "정서학대", "성학대", "방임")

SPEAKER_LABELS = {"CHILD": "아동", "COUNSELOR": "상담사"}

_HANGUL_NAME = re.compile(r"^[가-힣]{3,4}$")


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LlmVerifyConfig:
    enabled: bool = True
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    context_lines: int = DEFAULT_CONTEXT_LINES


def llm_verify_config(environ: Mapping[str, str] | None = None) -> LlmVerifyConfig:
    """환경 변수에서 읽는다. 잘못된 값은 경고 뒤 기본값."""

    env = os.environ if environ is None else environ
    enabled = str(env.get(ENV_VERIFY, "on")).strip().lower() not in {"off", "0", "false", "no"}

    def number(name: str, default: float, low: float, high: float) -> float:
        raw = env.get(name)
        if raw is None or not str(raw).strip():
            return default
        try:
            value = float(raw)
        except ValueError:
            value = None
        if value is None or not low <= value <= high:
            logger.warning("%s 값이 범위(%s~%s)를 벗어나 기본값 %s 를 씁니다.", name, low, high, default)
            return default
        return value

    return LlmVerifyConfig(
        enabled=enabled,
        timeout_seconds=number(ENV_TIMEOUT, DEFAULT_TIMEOUT_SECONDS, 1.0, 120.0),
        context_lines=int(number(ENV_CONTEXT, DEFAULT_CONTEXT_LINES, 0, 5)),
    )


# ---------------------------------------------------------------------------
# 보낼 덩어리 만들기
# ---------------------------------------------------------------------------


def build_excerpt(
    segments: Sequence[Mapping[str, Any]],
    targets: Mapping[str, Sequence[str]],
    context_lines: int = DEFAULT_CONTEXT_LINES,
) -> tuple[str, dict[int, str], dict[int, list[str]]]:
    """고른 줄과 앞뒤 context_lines 줄만 → (보낼 글, 줄 번호 → segment_id, ▶ 줄 번호 → 후보 유형).

    줄 번호는 1부터 원문 순서. 떨어진 덩어리 사이에는 '…' 한 줄을 넣는다. 원문 전체는 넣지 않는다(팀장 결정 11/20).
    """

    rows = [segment for segment in segments if isinstance(segment, Mapping)]
    index_of = {str(segment.get("segment_id", "")): index for index, segment in enumerate(rows)}

    keep: set[int] = set()
    for segment_id in targets:
        index = index_of.get(segment_id)
        if index is None:
            continue
        keep.update(range(max(0, index - context_lines), min(len(rows), index + context_lines + 1)))

    lines: list[str] = []
    line_map: dict[int, str] = {}
    target_lines: dict[int, list[str]] = {}
    previous: int | None = None
    number = 0

    for index in sorted(keep):
        if previous is not None and index != previous + 1:
            lines.append("…")
        previous = index
        segment = rows[index]
        segment_id = str(segment.get("segment_id", ""))
        number += 1
        line_map[number] = segment_id
        speaker = SPEAKER_LABELS.get(str(segment.get("speaker")), "화자 미확인")
        text = " ".join(str(segment.get("text") or "").split())
        marker = "▶ " if segment_id in targets else ""
        lines.append(f"{marker}[{number}] {speaker}: {text}")
        if segment_id in targets:
            target_lines[number] = [label for label in targets[segment_id] if label in TYPES]

    return "\n".join(lines), line_map, target_lines


def similar_name_variants(text: str, names: Sequence[str] | None) -> list[str]:
    """등록 이름(성 + 이름 2~3글자)과 성이 같고 이름 한 글자만 다른 표기 — STT 오인식(김수아 → 김수하)을 가리려고.

    더 가리는 쪽으로만 틀린다(같은 성의 다른 사람 이름을 가려도 안전). 두 글자 이름은 보지 않는다(너무 많이 걸림).
    """

    variants: list[str] = []
    seen = set(names or [])
    for name in names or []:
        if not isinstance(name, str) or not _HANGUL_NAME.match(name):
            continue
        size = len(name)
        for start in range(len(text) - size + 1):
            word = text[start : start + size]
            if word in seen or word[0] != name[0]:
                continue
            if not _HANGUL_NAME.match(word):
                continue
            if sum(1 for a, b in zip(word, name, strict=True) if a != b) == 1:
                variants.append(word)
                seen.add(word)
    return variants


# ---------------------------------------------------------------------------
# 프롬프트
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """너는 아동 상담 녹취의 일부 줄을 보고, ▶ 표시한 아동 발화가 1차 모델이 짚은 학대 유형에 실제로 해당하는지 확인하는 보조 분석기다.
결과는 상담원이 원문을 확정하기 전에 '먼저 들어볼 곳' 을 고르는 데만 쓴다. 판정이 아니다.

[유형 기준]
- 신체학대: 보호자나 어른이 아동에게 직접 한 신체 폭력(때림 · 발로 참 · 물건을 아동에게 던짐 · 밀침 · 목 조름 · 화상 등)과 그로 인한 상처.
- 정서학대: 보호자나 어른의 욕 · 폭언 · 위협 · 모욕 · 차별 · 가둠 · 쫓아냄, 가정폭력을 보거나 들음, 보호자 때문에 아동이 느끼는 공포.
- 성학대: 어른이나 연장자의 성적 접촉 · 노출 · 음란물 보여 줌 · 촬영 요구 등.
- 방임: 보호자가 먹을 것 · 안전 · 감독 · 치료 · 교육을 돌보지 않음.

[해당하지 않는 것]
- 사고(교통사고 · 넘어짐 · 운동하다 다침 등)로 다친 일, 또래끼리 다툼, 아동 스스로의 실수.
- 학대를 부정하는 대답("아니요", "없어요"), 학대와 관계없는 일상 이야기, 보호자와 관계없는 감정.
- 상담사 질문에만 학대 내용이 있고 아동은 그 내용을 인정하지 않은 경우.

[규칙]
1. 판단 대상은 ▶ 줄이다. 앞뒤 줄은 맥락으로만 본다.
2. ▶ 줄이 짧은 대답이어도 바로 앞 상담사 질문과 합쳐 학대 내용을 인정하는 것이면 해당으로 본다(예: "아빠가 때렸어?" → "네").
3. 각 ▶ 줄에 적힌 후보 유형 안에서만 고른다. 근거가 분명하지 않으면 넣지 않는다.
4. reason 은 왜 해당하는지 30자 안팎의 짧은 말(예: "아빠가 때렸다고 말함"). 해당 유형이 없으면 types 는 빈 배열.
5. [이름1] 같은 가린 표시는 그대로 둔다.

반드시 아래 JSON 하나만 출력한다.
{"items": [{"line": 3, "types": ["신체학대"], "reason": "..."}]}"""


def build_user_prompt(masked_excerpt: str, target_lines: Mapping[int, Sequence[str]]) -> str:
    asks = "\n".join(
        f"▶ [{number}] 후보: {', '.join(labels)}" for number, labels in sorted(target_lines.items()) if labels
    )
    return f"[녹취 일부]\n{masked_excerpt}\n\n[확인할 줄과 후보 유형]\n{asks}"


# ---------------------------------------------------------------------------
# 응답 읽기
# ---------------------------------------------------------------------------


def parse_response(
    raw: Any,
    line_map: Mapping[int, str],
    target_lines: Mapping[int, Sequence[str]],
) -> dict[str, list[dict[str, str]]] | None:
    """LLM 응답 → {segment_id: [{"type": 한글 유형, "reason": 이유}]}. ▶ 줄이 아니거나 후보 밖 유형은 버린다.
    응답에 없는 ▶ 줄은 빈 목록(확인 안 됨). 모양이 아예 틀리면 None(→ 호출부가 임베딩 매칭으로 돌아감)."""

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(raw, Mapping) or not isinstance(raw.get("items"), list):
        return None

    result: dict[str, list[dict[str, str]]] = {line_map[number]: [] for number in target_lines}

    for item in raw["items"]:
        if not isinstance(item, Mapping):
            continue
        number = item.get("line")
        if isinstance(number, str) and number.strip().isdigit():
            number = int(number.strip())
        if not isinstance(number, int) or isinstance(number, bool) or number not in target_lines:
            continue
        types = item.get("types")
        if not isinstance(types, list):
            continue
        reason = " ".join(str(item.get("reason") or "").split())[:MAX_REASON_CHARS]
        confirmed = result[line_map[number]]
        for label in types:
            if label in target_lines[number] and all(entry["type"] != label for entry in confirmed):
                confirmed.append({"type": label, "reason": reason})

    return result


# ---------------------------------------------------------------------------
# 확인
# ---------------------------------------------------------------------------


def _call_llm(**kwargs: Any) -> Any:
    # 지연 import: second_stage_llm 은 openai 를 불러온다(backend 시험 환경에는 없을 수 있다).
    from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

    return _call_llm_with_retry(**kwargs)


def _default_mask(text: str, known_identifiers: list[str] | None) -> tuple[str, dict[str, str]]:
    from ai.modeling.abuse.privacy_gateway import mask_for_outbound

    return mask_for_outbound(text, known_identifiers=known_identifiers)


def _default_restore(value: Any, entity_map: dict[str, str]) -> Any:
    from ai.modeling.abuse.pii_masking import restore_pii

    return restore_pii(value, entity_map)


def _default_client() -> tuple[Any, str]:
    from ai.modeling.abuse.llm_backend import build_openai_client_and_model

    return build_openai_client_and_model(default_openai_model=DEFAULT_MODEL)


def verify_picks(
    segments: Sequence[Mapping[str, Any]],
    targets: Mapping[str, Sequence[str]],
    known_identifiers: Sequence[str] | None = None,
    *,
    config: LlmVerifyConfig | None = None,
    client: Any = None,
    model: str | None = None,
    mask: Callable[[str, list[str] | None], tuple[str, dict[str, str]]] | None = None,
    restore: Callable[[Any, dict[str, str]], Any] | None = None,
    call: Callable[..., Any] | None = None,
) -> dict[str, list[dict[str, str]]] | None:
    """1차가 고른 줄(targets: segment_id → 한글 후보 유형)을 LLM 으로 확인한다.

    반환: {segment_id: [{"type", "reason"}]} — 확인된 유형만(빈 목록 = 해당 없음). 확인하지 못했으면(꺼짐 · 키 없음 ·
    가리기 차단 · 시간 초과 · 형식 오류) None — 호출부는 로컬 임베딩 매칭으로 돌아간다. 어떤 예외도 올리지 않는다.
    """

    config = config or llm_verify_config()
    if not config.enabled or not targets:
        return None

    try:
        excerpt, line_map, target_lines = build_excerpt(segments, targets, config.context_lines)
        target_lines = {number: labels for number, labels in target_lines.items() if labels}
        if not target_lines:
            return None

        names = [name for name in (known_identifiers or []) if isinstance(name, str) and name.strip()]
        names = names + similar_name_variants(excerpt, names)
        # 긴 것부터 — 가리기가 목록 순서대로 바꾼다(personal_info_service.known_identifiers 와 같은 이유).
        names = sorted(dict.fromkeys(names), key=len, reverse=True) or None

        masked, entity_map = (mask or _default_mask)(excerpt, names)

        if client is None:
            client, model = _default_client()

        deadline = time.monotonic() + config.timeout_seconds
        raw = (call or _call_llm)(
            client=client,
            model=model or DEFAULT_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(masked, target_lines),
            max_retries=2,
            timeout_seconds=config.timeout_seconds,
            deadline=deadline,
        )

        parsed = parse_response(raw, line_map, target_lines)
        if parsed is None:
            logger.warning("STT 검수 임시 핵심 발화 LLM 확인 응답 모양이 달라 임베딩 매칭으로 돌아갑니다.")
            return None

        return {
            segment_id: [{**entry, "reason": str((restore or _default_restore)(entry["reason"], entity_map))} for entry in entries]
            for segment_id, entries in parsed.items()
        }
    except Exception as error:  # noqa: BLE001 — 확인 실패는 STT 를 막지 않는다(원문 · 예외 문구는 남기지 않음)
        logger.warning("STT 검수 임시 핵심 발화 LLM 확인을 못 해 임베딩 매칭으로 돌아갑니다. type=%s", type(error).__name__)
        return None
