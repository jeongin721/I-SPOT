# 고령자(온담 시니어) 화면을 붙여 볼 합성 데이터를 실행 중인 Backend 에 만든다(feature/senior).
#
# 전부 지어낸 데이터다. 실제 어르신 정보를 쓰지 않는다. 발화는 mock STT 대본(8줄)의 글을 고령자 상담 말로 바꿔 넣은 것이다.
# 어르신 셋: 회차 둘(영역 변화 · 확인사항 · 재방문 일정까지) · 회차 하나(요약 검토 대기) · 측정만.
#
# 사용 예(STT_PROVIDER=mock, SENIOR_AI_PROVIDER=rule 로 띄운 로컬 Backend):
#   python -m scripts.seed_senior_demo --email counselor@ispot.example.com --password '...'

import argparse
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from scripts.seed_demo_data import ApiClient, make_wav_bytes

KST = timezone(timedelta(hours=9))

SENIORS = [
    {"alias": "김순자", "name": "김순자", "birth": 1944, "gender": "F", "living": "ALONE", "grade": "NONE",
     "health": "고혈압 · 무릎 관절염", "meds": "혈압약 아침 1회 · 진통제", "needs": ["MEAL", "EMOTIONAL", "SAFETY_CHECK"]},
    {"alias": "최만석", "name": "최만석", "birth": 1938, "gender": "M", "living": "COUPLE", "grade": "GRADE_4",
     "health": "당뇨", "meds": "당뇨약 아침 · 저녁", "needs": ["MEDICATION", "HOSPITAL_ESCORT"]},
    {"alias": "서복례", "name": "서복례", "birth": 1941, "gender": "F", "living": "WITH_FAMILY", "grade": "UNKNOWN",
     "health": None, "meds": None, "needs": []},
]

# 회차별 대본(mock STT 의 8줄 자리에 차례로 넣는다. 짝수 줄이 어르신).
VISITS = {
    "김순자": [
        ["안녕하세요, 어르신. 오늘 건강 측정 결과 같이 보면서 이야기 나눠요.", "네, 어서 와요.",
         "요즘 식사는 어떻게 하세요?", "혼자 먹으니 밥이 잘 안 넘어가요. 하루 두 끼 정도 먹어요.",
         "밤에 주무시는 건 어떠세요?", "밤에 자꾸 깨요. 두세 시간 자면 많이 잔 거지요.",
         "경로당은 요즘도 나가세요?", "무릎이 아파서 요즘은 집에만 있어요."],
        ["어르신, 지난번 말씀하신 식사는 좀 어떠세요?", "복지관 도시락 오고부터는 세 끼 다 먹어요.",
         "잠은 좀 주무세요?", "아직도 밤에 깨요. 낮잠을 좀 자요.",
         "요즘 기분은 어떠세요?", "아들이 전화를 안 해서 좀 외롭지요.",
         "산책은 다녀오셨어요?", "날 좋은 날 시장까지 걸어갔다 왔어요."],
    ],
    "최만석": [
        ["어르신, 혈당 재 보니 조금 높게 나왔어요.", "어제 떡을 좀 먹었어요.",
         "약은 잘 챙겨 드세요?", "아침 약은 먹는데 저녁 약은 가끔 잊어요.",
         "병원은 언제 가세요?", "다음 달에 가야 하는데 혼자 가기가 힘들어요.",
         "할머니랑은 잘 지내세요?", "할멈이 잘 챙겨 줘서 괜찮아요."],
    ],
}


def at(days_ago: int, hour: int = 10) -> str:
    d = datetime.now(KST).replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return d.isoformat()


def run_visit(api: ApiClient, case_id: str, number: int, days_ago: int, lines: List[str], approve: bool) -> str:
    session = api.call("POST", f"/api/v1/cases/{case_id}/sessions", 201, json={
        "title": f"{'초기상담' if number == 1 else '정기상담'} {number}회차", "consulted_at": at(days_ago),
        "location": "카라반 상담실", "consultation_type": "VISIT" if number > 1 else "INITIAL",
    })
    sid = session["id"]
    m = api.call("POST", f"/api/v1/cases/{case_id}/health-measurements", 201, json={
        "measured_at": at(days_ago, 9), "session_id": sid, "systolic": 128 + number * 9, "diastolic": 80 + number * 3,
        "pulse": 74, "blood_glucose": 112 + number * 6, "glucose_timing": "FASTING", "weight_kg": 52.4 - number * 0.8,
        "extra_results": [{"kind": "COGNITIVE_SCREENING", "name": "CIST", "value": 24 - number, "max_value": 30}],
    })
    assert m["id"]
    api.call("POST", f"/api/v1/sessions/{sid}/audio", 201, files={"file": ("visit.wav", make_wav_bytes(), "audio/wav")})
    api.call("POST", f"/api/v1/sessions/{sid}/transcript", 202)
    if api.wait_for_status(sid, {"STT_REVIEW_REQUIRED", "STT_FAILED"}, "STT") == "STT_FAILED":
        raise SystemExit("STT 실패")
    segs = api.call("GET", f"/api/v1/sessions/{sid}/transcript", 200)["transcript"]["segments"]
    api.call("PATCH", f"/api/v1/sessions/{sid}/transcript", 200, json={
        "segments": [{"segment_id": s["segment_id"], "text": text} for s, text in zip(segs, lines)]
    })
    api.call("POST", f"/api/v1/sessions/{sid}/transcript/confirm", 200)
    api.call("POST", f"/api/v1/sessions/{sid}/analysis", 202)
    if api.wait_for_status(sid, {"AI_REVIEW_REQUIRED", "AI_FAILED"}, "통합 요약") == "AI_FAILED":
        raise SystemExit("통합 요약 실패")
    if not approve:
        return sid
    api.call("POST", f"/api/v1/sessions/{sid}/summary/approve", 200)
    domains = api.call("GET", f"/api/v1/sessions/{sid}/care-domains", 200)["domains"]
    items: List[Dict[str, Any]] = []
    for row in domains:
        draft = row.get("draft") or {}
        if not draft.get("text"):
            items.append({"domain": row["domain"], "change": "NOT_MENTIONED"})
            continue
        change = draft.get("change") or ("CHANGED" if row["domain"] in ("MEAL", "OUTING") else "SIMILAR")
        items.append({
            "domain": row["domain"], "change": change, "text": draft["text"], "segment_ids": draft["segment_ids"],
            "change_note": "하루 두 끼 → 도시락으로 세 끼" if change == "CHANGED" and row["domain"] == "MEAL"
            else "집에만 있음 → 시장까지 걸어감" if change == "CHANGED" else None,
            "origin": "RULE",
        })
    api.call("PUT", f"/api/v1/sessions/{sid}/care-domains", 200, json={"items": items})
    return sid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    api = ApiClient(args.base_url)
    api.login(args.email, args.password)
    for i, person in enumerate(SENIORS):
        case = api.call("POST", "/api/v1/cases", 201, json={
            "title": f"{person['alias']} 어르신", "subject_type": "SENIOR", "child_alias": person["alias"],
            "child_birth_year": person["birth"], "child_gender": person["gender"],
            "report_date": (date.today() - timedelta(days=60 - i * 10)).isoformat(),
            "personal_info": {"child_name": person["name"]},
        })
        cid = case["id"]
        api.call("PATCH", f"/api/v1/cases/{cid}/senior-profile", 200, json={
            "living_arrangement": person["living"], "care_grade": person["grade"], "health_notes": person["health"],
            "takes_medication": bool(person["meds"]) if person["meds"] is not None else None,
            "medication_notes": person["meds"], "care_needs": person["needs"],
        })
        visits = VISITS.get(person["alias"], [])
        last_sid = None
        for n, lines in enumerate(visits, start=1):
            approve = not (person["alias"] == "최만석")
            last_sid = run_visit(api, cid, n, days_ago=(len(visits) - n) * 21 + 3, lines=lines, approve=approve)
        if not visits:
            api.call("POST", f"/api/v1/cases/{cid}/health-measurements", 201, json={
                "measured_at": at(40, 9), "systolic": 135, "diastolic": 84, "pulse": 70,
            })
        if person["alias"] == "김순자" and last_sid:
            saved = api.call("POST", f"/api/v1/cases/{cid}/next-checks", 201, json={
                "source_session_id": last_sid,
                "items": [
                    {"kind": "CHECK", "text": "아드님과 통화했는지 여쭤 보기", "origin": "COUNSELOR"},
                    {"kind": "ACTION", "text": "경로당 프로그램 다시 연결해 드리기", "origin": "COUNSELOR",
                     "due_date": (date.today() + timedelta(days=5)).isoformat()},
                ],
            })
            api.call("POST", f"/api/v1/cases/{cid}/followup-visits", 201, json={
                "consult_type": "VISIT", "date": (date.today() + timedelta(days=7)).isoformat(), "time": "14:00",
                "place": "댁 방문", "check_ids": [saved[0]["id"]],
            })
            api.call("PUT", f"/api/v1/cases/{cid}/care-status", 200, json={"status": "REVISIT_NEEDED"})
        print("만듦:", person["alias"], cid)
    api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
