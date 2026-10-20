"""
law/ 모듈(feature/rag 브랜치, jeongin 담당, 2026-10-19 포팅)을 이
파이프라인에 연결하는 어댑터. 탐지된 학대유형마다 관련 법령 조문을
찾아 호(clause) 단위로 쪼개 붙인다.

[2026-10-20 Mingyu 리뷰로 rag.pipeline 대신 law/만 직접 호출하도록 변경]

처음엔 rag.pipeline.analyze_consultation_evidence()를 거쳤는데, Mingyu가
실제로 돌려서 확인해보니 그 함수는 법령 조회 외에도 유형마다 OpenAI
임베딩 5번(체크리스트·매뉴얼/지침/서식·판례 — 색인이 비어 있어도 검색어
임베딩은 나감)과 채팅 1번(법령이 하나라도 찾아지면 상담 발화를 포함해
다음 상담 체크리스트를 만듦, rag/checklist_builder.py)을 내보냈다.
우리는 그 결과에서 related_laws만 썼으니 나머지는 전부 쓰지도 않는
외부 호출이었다. 그래서 law/query.py가 하는 패턴
(LawApiClient.get_law_by_name → extract_articles → rank_law_articles →
attach_portal_urls)을 이 어댑터에서 직접 불러, OpenAI로 나가는 걸
없앴다. 이제 상담 텍스트는 로컬 키워드 매칭(law.mapper, 네트워크 없음)
에만 쓰여서 마스킹도 필요 없다(512 토큰 잘림 문제와도 무관해짐).

[코드 소유 — law/는 손대지 않는다]

law/는 jeongin님이 만드는 feature/rag 브랜치의 코드를 그대로 복사해 온
것이다 — 여기서 그 파일들을 고치면 나중에 feature/rag가 main에 들어올
때 각자 고친 게 충돌한다(요약 변환기 때와 같은 문제). 그래서 호 단위
파싱 같은 새 로직은 전부 이 어댑터(내 소유 파일) 안에서, law/가
돌려주는 값을 가공하는 방식으로만 구현한다. law.go.kr 요청 타임아웃을
줄이는 것도 rag/config.py의 LAW_TIMEOUT_SECONDS를 고치지 않고,
LawApiClient 생성자의 timeout_seconds 인자로만 넘긴다.

[Contract 모양 — 2026-10-19 Mingyu 제안, 2026-10-20 재확인]

유형별로 묶은 dict가 아니라 평평한 목록 하나로 돌려준다. 각 항목은
{major_type, law_name, article, clause, title, content, url}. relevance_score·
matched_keywords는 정렬/호 선택에만 쓰고 바깥으로 내보내지 않는다.
manual_references·precedents(매뉴얼·판례)는 원본 자료 색인이 생기기
전까지는 다루지 않는다 — 그때는 이 OpenAI 호출 제거와 별도로, 마스킹과
deadline을 갖춘 경로를 새로 만들어야 한다.

[law.go.kr로 나가는 것 — 2026-10-19 Mingyu 질문 답변]

law.go.kr 자체(law/client.py)에는 상담 원문이 전혀 나가지 않는다 —
LawApiClient.get_law_by_name()은 LAW_TARGET_LAWS의 고정된 법령명
("아동복지법" 등)과 내부 법령ID/일련번호만 보낸다. 상담 텍스트는 로컬
키워드 매칭(law.mapper, 네트워크 없음)에만 쓰인다. law.go.kr 요청이
실패하면 requests 예외 문구에 요청 주소 전체(OC 인증값 포함)가 들어갈
수 있어(law/client.py), 그 문구를 그대로 warnings에 올리지 않고 고정
문구로 바꾼다(2026-10-20 Mingyu 지적 — OC가 화면·DB까지 노출될 수
있었음).

[법령 본문은 세션당 한 번만 조회]

LAW_TARGET_LAWS 2개는 학대유형과 무관하게 항상 같다 — 유형이 다른 건
"어느 조문이 관련 있는지" 랭킹만 달라진다. 그래서 법령 본문(HTTP 조회,
캐시 없으면 느림)은 세션당 한 번만 받고, 유형별로는 이미 받아온 조문
목록을 rank_law_articles()로 로컬에서만 다시 랭킹한다(2026-10-20
Mingyu 제안). law.go.kr 캐시가 있으면 이 함수는 네트워크를 전혀 안
탄다.

[지금 비어 있는 것]

- related_laws: LAW_API_OC(국가법령정보센터 Open API 키)가 .env에
  없으면 건너뛴다(law.client.LawApiClient.configured가 False).

[처리시간 · deadline]

law.go.kr 조회(최대 법령 2개 × 요청 2번, 각 _LAW_CLIENT_TIMEOUT_SECONDS
로 제한)가 끝나면 나머지(유형별 랭킹·호 분리)는 전부 로컬 계산이라
빠르다. 그래도 한 번 시작된 HTTP 요청은 못 끊으므로, 뒤에 남은 필수
단계(서사 요약·심각도·다음 상담 확인사항, infer_audio_session.py)가
deadline에 걸리지 않도록 _MIN_REMAINING_SECONDS_TO_ATTEMPT 미만이면
법령 조회 자체를 시작하지 않고 건너뛴다(2026-10-20 Mingyu 지적 — 전엔
법령 조회가 늦어지면 그 뒤 필수 단계가 deadline에 걸려 '일부 건너뜀'
경고조차 못 남기고 분석 전체가 TimeoutError로 사라졌음).
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from law.client import LawApiClient
from law.mapper import build_law_keywords, rank_law_articles
from law.parser import extract_articles
from law.portal import attach_portal_urls
from rag.config import LAW_TARGET_LAWS

MAJOR_TYPE_TO_RAG_ABUSE_TYPE = {
    "신체학대": "physical",
    "정서학대": "emotional",
    "성학대": "sexual",
    "방임": "neglect",
}

# law.go.kr 기본 타임아웃(rag/config.py의 LAW_TIMEOUT_SECONDS=15초)보다
# 줄인다 — 법령 2개 × 요청 2번이 최악의 경우 겹칠 수 있어, 전체 지연
# 상한을 낮추려는 목적(2026-10-20 Mingyu 요청). rag/config.py는 안
# 건드리고 LawApiClient 생성자 인자로만 넘긴다.
_LAW_CLIENT_TIMEOUT_SECONDS = 8

# 법령 조회 뒤에도 서사 요약·심각도·다음 상담 확인사항 세 단계가 남아
# 있다(infer_audio_session.py, 각 LLM 호출 1번씩 — 정확한 실측치는 없어
# 넉넉히 잡음). 남은 시간이 이보다 적으면 law.go.kr 요청을 시작도 하지
# 않는다 — 시작하면 한 번의 요청을 못 끊어 뒤 필수 단계가 deadline에
# 걸릴 수 있기 때문(2026-10-20 Mingyu 지적).
_MIN_REMAINING_SECONDS_TO_ATTEMPT = 60

# law.go.kr 조회가 실패했을 때 쓰는 고정 문구 — requests 예외 문구에는
# 요청 주소 전체(OC 인증값 포함)가 들어갈 수 있어 그대로 노출하지
# 않는다(2026-10-20 Mingyu 지적).
_LAW_LOOKUP_FAILED_WARNING = "관련 법령을 불러오지 못했습니다."

# 조문 content 끝에 붙는 "제17조(금지행위) 누구든지 ... <개정 ...>" 같은
# 머리말/개정이력 줄 — 호가 아니라서 버린다.
_ARTICLE_HEADING_RE = re.compile(r"^제\d+조")
# 항(①~⑳) 경계 — 항마다 호 번호가 1부터 다시 시작돼서, 이 경계를 모르면
# 서로 다른 항의 같은 번호 호끼리 내용이 섞인다. ⑩을 넘는 항(예: 아동복지법
# 제15조의 ⑪)도 있어 ⑳까지 넓힌다(2026-10-20 Mingyu 지적 — 전엔 ①~⑩만
# 봐서 ⑪ 이상이 앞 항 마지막 호에 붙었음).
_PARAGRAPH_MARK_RE = re.compile(r"^([①-⑳])")
_PARAGRAPH_MARK_TO_NUM = {chr(0x2460 + offset): offset + 1 for offset in range(20)}
# "7의2." 같은 가지 호(아동복지법 제3조 7의2·8의2, 아동학대처벌법 제2조
# 4의2·4의3·9의2 등 실제로 있음)도 호 시작으로 인식한다(2026-10-20
# Mingyu 지적 — 전엔 숫자+마침표만 봐서 가지 호가 앞 호 뒤에 붙었음).
_CLAUSE_START_RE = re.compile(r"^(\d+(?:의\d+)?)\.\s*(.*)")


def _split_into_clauses(content: str) -> List[Dict[str, str]]:
    """
    조문 content를 호 단위로 쪼갠다. "1. ...", "7의2. ..."처럼 줄 앞의
    숫자(+가지번호)+마침표를 호 경계로 본다. 항(①②③...)이 있으면 호
    라벨에 "N항 "을 붙여, 서로 다른 항의 같은 번호 호를 구분할 수 있게
    한다(2026-10-20 Mingyu 지적). 삭제된 호("4. 삭제<2014.1.28>")도
    그대로 호 하나로 남긴다 — 화면에서 걸러낼지는 상담사 판단.
    """

    clauses: List[Dict[str, str]] = []
    current_num: Optional[str] = None
    current_lines: List[str] = []
    current_paragraph: Optional[int] = None

    def flush() -> None:
        if current_num is not None and current_lines:
            text = " ".join(
                line for line in current_lines if line
            ).strip()
            if text:
                label = f"{current_num}호"
                if current_paragraph is not None:
                    label = f"{current_paragraph}항 {label}"
                clauses.append({"clause": label, "content": text})

    for raw_line in content.split("\n"):
        line = raw_line.strip()
        clause_match = _CLAUSE_START_RE.match(line)
        paragraph_match = _PARAGRAPH_MARK_RE.match(line)

        if clause_match:
            flush()
            current_num = clause_match.group(1)
            current_lines = [clause_match.group(2)]
        elif paragraph_match:
            # 새 항 시작 — 호 번호가 1부터 다시 시작되므로 지금까지 모은
            # 호만 저장하고, 이후 호 라벨에 붙일 항 번호를 갱신한다.
            flush()
            current_num = None
            current_lines = []
            current_paragraph = _PARAGRAPH_MARK_TO_NUM.get(paragraph_match.group(1))
        elif _ARTICLE_HEADING_RE.match(line):
            # 조문 머리말/개정이력 — 호가 아니므로 지금까지 모은 호만
            # 저장한다. 항 번호는 그대로 둔다(머리말은 항보다 먼저 나와
            # current_paragraph가 아직 None인 게 보통이라 영향 없음).
            flush()
            current_num = None
            current_lines = []
        elif current_num is not None:
            current_lines.append(line)

    flush()

    return clauses


def _matching_clauses(
    law: Dict[str, Any],
    keywords: List[str],
) -> List[Dict[str, str]]:
    """
    조문을 호 단위로 쪼갠 뒤, 학대유형 키워드가 들어간 호만 남긴다.
    호 단위로 하나도 안 걸리면(파싱이 이 조문 형식과 안 맞는 경우 등)
    조문 전체를 "호 없음"으로 돌려줘 근거 자체는 잃지 않는다.
    """

    content = law.get("content", "")
    clauses = _split_into_clauses(content)
    matched = [
        clause
        for clause in clauses
        if any(keyword in clause["content"] for keyword in keywords)
    ]

    if matched:
        return matched

    # 호는 쪼개졌는데 키워드가 하나도 안 걸렸거나, 호 구조 자체가 없는
    # 조문(제5조 등) — 조문 자체는 rank_law_articles()에서 이미 관련
    # 있다고 랭킹된 것이므로, 안전하게 전체를 "호 없음" 한 건으로 남긴다.
    return [{"clause": "", "content": content}]


def _evidence_text_for_major_type(
    risk_signal_points: List[Dict[str, Any]],
    major_type: str,
) -> str:
    texts = [
        point.get("text", "")
        for point in risk_signal_points
        if point.get("major_type") == major_type and point.get("text")
    ]

    return "\n".join(texts)


def _load_target_law_articles(
    deadline: Optional[float],
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
    """
    LAW_TARGET_LAWS 2개의 조문 목록을 세션당 한 번만 받아온다(캐시가
    있으면 네트워크 없이 끝난다). 학대유형과 무관하므로 유형별로 다시
    받지 않는다.
    """

    client = LawApiClient(timeout_seconds=_LAW_CLIENT_TIMEOUT_SECONDS)
    articles_by_law: Dict[str, List[Dict[str, Any]]] = {}
    warnings: List[str] = []

    for law_name in LAW_TARGET_LAWS:
        if deadline is not None and time.monotonic() >= deadline:
            warnings.append(_LAW_LOOKUP_FAILED_WARNING)
            break

        try:
            cached = client.get_law_by_name(law_name)
            articles = extract_articles(
                cached.get("body", {}), fallback_law_name=law_name
            )
            articles_by_law[law_name] = attach_portal_urls(
                articles, cached.get("search_item", {})
            )
        except Exception:
            # 실패 문구(requests 예외)에는 OC 인증값이 그대로 들어갈 수
            # 있어 고정 문구로만 남긴다(모듈 docstring 참고).
            if _LAW_LOOKUP_FAILED_WARNING not in warnings:
                warnings.append(_LAW_LOOKUP_FAILED_WARNING)

    return articles_by_law, warnings


def build_legal_references(
    detected_major_types: List[str],
    risk_signal_points: List[Dict[str, Any]],
    deadline: Optional[float] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    탐지된 학대유형마다 관련 법령 조문을 찾아 호 단위로 쪼갠 평평한
    목록으로 돌려준다(모듈 docstring의 Contract 모양 참고).

    반환값은 (items, warnings) 튜플이다. items의 각 항목은
    {major_type, law_name, article, clause, title, content, url}.
    """

    items: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if (
        deadline is not None
        and (deadline - time.monotonic()) < _MIN_REMAINING_SECONDS_TO_ATTEMPT
    ):
        warnings.append("시간이 부족해 관련 법령 조회를 건너뛰었습니다.")
        return items, warnings

    articles_by_law, load_warnings = _load_target_law_articles(deadline)
    warnings.extend(load_warnings)

    if not articles_by_law:
        return items, warnings

    for major_type in detected_major_types:
        rag_abuse_type = MAJOR_TYPE_TO_RAG_ABUSE_TYPE.get(major_type)

        if not rag_abuse_type:
            continue

        evidence_text = _evidence_text_for_major_type(
            risk_signal_points, major_type
        )

        if not evidence_text.strip():
            continue

        # 법령마다 최대 3개씩 랭킹한 뒤 합쳐서 점수순으로 정렬한다
        # (rag/pipeline.py의 기존 기본값과 동일 — 2026-10-19 Mingyu가
        # 이미 검토한 랭킹 동작은 그대로 유지).
        ranked_all: List[Dict[str, Any]] = []
        for articles in articles_by_law.values():
            ranked_all.extend(
                rank_law_articles(
                    articles,
                    abuse_type=rag_abuse_type,
                    consultation_text=evidence_text,
                    limit=3,
                )
            )

        ranked_all.sort(
            key=lambda item: float(item.get("relevance_score", 0)),
            reverse=True,
        )

        seen_articles: set = set()
        top_articles: List[Dict[str, Any]] = []
        for article in ranked_all:
            key = (article.get("law_name", ""), article.get("article", ""))
            if key in seen_articles:
                continue
            seen_articles.add(key)
            top_articles.append(article)
            if len(top_articles) >= 3:
                break

        keywords = build_law_keywords(rag_abuse_type, evidence_text)

        for law in top_articles:
            for clause in _matching_clauses(law, keywords):
                items.append(
                    {
                        "major_type": major_type,
                        "law_name": law.get("law_name", ""),
                        "article": law.get("article", ""),
                        "clause": clause["clause"],
                        "title": law.get("title", ""),
                        "content": clause["content"],
                        "url": law.get("portal_url", ""),
                    }
                )

    return items, warnings
