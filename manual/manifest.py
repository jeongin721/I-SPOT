"""2026년 아동학대 대응 업무 매뉴얼 6장(서식 및 참고자료) 이미지 목록.

경진님이 실물 책자를 촬영해 올린 19장(2026-10-26, `사례관리_업무/`) 중
6장(서식·척도) 10장만 1차로 다룬다 — 5장(신변안전매뉴얼, 상담원 본인
안전)은 "현장에서 헷갈려서 바로 찾아보고 싶은 것"이라는 인터뷰 요청과
결이 달라 범위에서 뺐다(project_law_qa_feature.md, 2026-10-26 판단).
나중에 필요하면 ManualPage를 추가하는 식으로 확장하면 된다.

keywords는 law/mapper.py의 TEXT_SIGNAL_MAP과 같은 단순 포함-매칭용이다 —
질문 문자열에 이 키워드가 들어 있으면 해당 페이지 이미지를 LLM에 같이
보여준다. 페이지 10장 전부를 매번 보낼 필요가 없게 하는 1차 필터일 뿐,
정밀한 검색은 아니다.
"""

from __future__ import annotations

from typing import NamedTuple


class ManualPage(NamedTuple):
    id: str
    filename: str
    page: str
    title: str
    keywords: tuple[str, ...]


# page가 "?"인 두 장(서식29 종결보고서)은 사진에 페이지 번호가 안 찍혀
# 있어서 정확한 쪽수를 확인 못 했다 — 서식 번호(서식29)로만 특정한다.
CHAPTER6_PAGES: tuple[ManualPage, ...] = (
    ManualPage(
        id="form4_initial_interview_1",
        filename="KakaoTalk_20260812_115041522.jpg",
        page="312",
        title="서식4 초기면접지(아동용) 1/2 — 신고접수일·대상아동·학대유형·가정상황·가족유형·가족관계",
        keywords=(
            "초기면접", "초기면접지", "서식4", "학대유형", "가족유형",
            "가정상황", "신고접수", "가족관계", "사례연계",
        ),
    ),
    ManualPage(
        id="form4_initial_interview_2",
        filename="KakaoTalk_20260812_115041522_01.jpg",
        page="313",
        title="서식4 초기면접지(아동용) 2/2 — 아동 특성 체크리스트·문제력·건강정도(질병/장애/병원치료/정신과진단/타기관상담)",
        keywords=(
            "초기면접", "아동특성", "문제력", "건강정도", "질병", "장애",
            "병원치료", "정신과", "약물복용", "타기관상담",
        ),
    ),
    ManualPage(
        id="form6_assessment_record_1",
        filename="KakaoTalk_20260812_115041522_02.jpg",
        page="316",
        title="서식6 사정기록지 1/2 — 가족영역(가족관계·가계도·생태도·복지자원), 개인영역(생육사·발달사·교육사)",
        keywords=(
            "사정기록지", "서식6", "가계도", "생태도", "복지자원",
            "생육사", "발달사", "교육사",
        ),
    ),
    ManualPage(
        id="form6_assessment_record_2",
        filename="KakaoTalk_20260812_115041522_03.jpg",
        page="317",
        title="서식6 사정기록지 2/2 — 안전영역(아동학대 위험수준별 개입 사정 척도 요약표, 안전점수), 사정결과(집중/일반/모니터링관리)",
        keywords=(
            "사정기록지", "안전영역", "위험수준별", "개입사정", "사정결과",
            "집중관리", "일반관리", "모니터링관리", "안전점수",
        ),
    ),
    ManualPage(
        id="ref3_risk_scale_1",
        filename="KakaoTalk_20260812_115041522_04.jpg",
        page="350",
        title="참고자료3 아동학대 위험수준별 개입 사정 척도 1/2 — 위험요인 문항 1~21(0~3점)",
        keywords=(
            "위험수준별", "개입사정척도", "위험요인", "보호요인", "척도",
            "참고자료3",
        ),
    ),
    ManualPage(
        id="ref3_risk_scale_2",
        filename="KakaoTalk_20260812_115041522_05.jpg",
        page="351",
        title="참고자료3 아동학대 위험수준별 개입 사정 척도 2/2 — 보호요인 문항 22~43(0~3점)",
        keywords=(
            "위험수준별", "개입사정척도", "보호요인", "척도", "참고자료3",
        ),
    ),
    ManualPage(
        id="ref1_family_scale",
        filename="KakaoTalk_20260812_115041522_06.jpg",
        page="348",
        title="참고자료1 축약형 가족관계척도 — 15문항(전혀 그렇지 않다~항상 그렇다, 5점 리커트)",
        keywords=(
            "가족관계척도", "축약형", "참고자료1",
        ),
    ),
    ManualPage(
        id="form27_case_check",
        filename="KakaoTalk_20260812_115041522_07.jpg",
        page="342",
        title="서식27 사례관리 점검표 — 계획 이행·지지망·안전·만족도·사례관리 지속/재사정/종결 여부 점검(9문항)",
        keywords=(
            "사례관리점검표", "서식27", "점검", "재사정", "종결여부",
        ),
    ),
    ManualPage(
        id="form29_closure_report_1",
        filename="KakaoTalk_20260812_115041522_08.jpg",
        page="?",
        title="서식29 사례관리 종결보고서 1/2 — 종결사유·개입목표(장단기)·제공된 서비스·안전평가",
        keywords=(
            "종결보고서", "서식29", "종결사유", "개입목표", "안전평가",
        ),
    ),
    ManualPage(
        id="form29_closure_report_2",
        filename="KakaoTalk_20260812_115041522_09.jpg",
        page="?",
        title="서식29 사례관리 종결보고서 2/2 — 안전점수, 대상자 변화상황(초기/종결 비교), 종결심의일·종결상담일",
        keywords=(
            "종결보고서", "안전점수", "변화상황", "종결심의일", "종결상담일",
        ),
    ),
)
