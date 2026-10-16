"""
json file(원천데이터)을 기반으로 위기단계 분류를 위한 csv 데이터로 변환하는 코드 입니다.
"""

import os
import json
import pandas as pd


# 평가용 원천데이터 JSON 폴더
json_dir = r"C:\Users\USER\Desktop\최종_프로젝트\최종프로젝트_데이터셋\VL_out\VL_out_data"

# CSV 저장 경로
save_path = "test.csv"


final_df = pd.DataFrame()

# 테스트할 JSON 하나만 지정
for filename in ["0008.json"]:

    json_file_path = os.path.join(json_dir, filename)

    file_size = os.path.getsize(json_file_path) / 1024

    if file_size <= 3:
        continue

    with open(json_file_path, "r", encoding="utf-8") as json_file:
        json_data = json.load(json_file)

    # 기본 정보
    info = json_data["info"]

    gender = info["성별"]
    age = info["나이"]
    crisis_level = info["위기단계"]
    group = info["유형구분"]
    enviroment = info["가정환경"]
    class_level = info["학년"]
    interaction_label = info["상호작용 특성(종합)"]
    abuse_label = info["학대의심"]

    # 혹시 특정 항목이 없는 경우를 대비해 기본값 0 설정
    pain_score = 0
    physical_injury_score = 0
    joy_score = 0
    anger_score = 0
    sleep_score = 0

    father_problem_score = 0
    mother_problem_score = 0
    others_problem_score = 0
    siblings_score = 0

    friends_score = 0
    teacher_score = 0

    worry_score = 0
    happiness_score = 0
    future_score = 0

    neglect_score = 0
    emotional_abuse_score = 0
    physical_abuse_score = 0
    sexual_abuse_score = 0

    domestic_violence_score = 0
    school_violence_score = 0
    self_harm_score = 0
    trauma_score = 0
    runaway_score = 0

    # 상담 문항 데이터
    first_list_item = json_data["list"]

    for text_sector in first_list_item:

        if "list" not in text_sector:
            continue

        problem_list = text_sector.get("list", [])

        for item in problem_list:

            problem_name = item.get("항목")
            score = item.get("점수", 0)

            if problem_name == "통증":
                pain_score = score

            elif problem_name == "신체손상":
                physical_injury_score = score

            elif problem_name == "즐거움":
                joy_score = score

            elif problem_name == "분노/짜증":
                anger_score = score

            elif problem_name == "수면":
                sleep_score = score

            elif problem_name == "아버지":
                father_problem_score = score

            elif problem_name == "어머니":
                mother_problem_score = score

            elif problem_name == "기타 보호자":
                others_problem_score = score

            elif problem_name == "형제자매":
                siblings_score = score

            elif problem_name == "친구":
                friends_score = score

            elif problem_name == "교사":
                teacher_score = score

            elif problem_name == "걱정":
                worry_score = score

            elif problem_name == "행복":
                happiness_score = score

            elif problem_name == "미래/진로":
                future_score = score

            elif problem_name == "방임":
                neglect_score = score

            elif problem_name == "정서학대":
                emotional_abuse_score = score

            elif problem_name == "신체학대":
                physical_abuse_score = score

            elif problem_name == "성학대":
                sexual_abuse_score = score

            elif problem_name == "가정폭력":
                domestic_violence_score = score

            elif problem_name == "학교폭력":
                school_violence_score = score

            elif problem_name == "자해/자살":
                self_harm_score = score

            elif problem_name == "트라우마":
                trauma_score = score

            elif problem_name == "가출경험 및 가출중 정황":
                runaway_score = score

    # 0008.json 한 건을 1개의 행으로 생성
    data = {
        "file": [filename],
        "crisis_level": [crisis_level],
        "gender": [gender],
        "age": [age],
        "class_level": [class_level],
        "interaction_label": [interaction_label],
        "abuse_label": [abuse_label],
        "group": [group],
        "enviroment": [enviroment],

        "pain": [pain_score],
        "physical_injury": [physical_injury_score],
        "joy": [joy_score],
        "anger": [anger_score],
        "sleep": [sleep_score],

        "father_problem": [father_problem_score],
        "mother_problem": [mother_problem_score],
        "ohthers": [others_problem_score],
        "siblings": [siblings_score],

        "friends": [friends_score],
        "teacher": [teacher_score],

        "worry": [worry_score],
        "happiness": [happiness_score],
        "future": [future_score],

        "neglect": [neglect_score],
        "emotional_abuse": [emotional_abuse_score],
        "physical_abuse": [physical_abuse_score],
        "sexual_abuse": [sexual_abuse_score],

        "domestic_violence": [domestic_violence_score],
        "school_violence": [school_violence_score],
        "self_harm": [self_harm_score],
        "runaway": [runaway_score],
    }

    df = pd.DataFrame(data)
    final_df = pd.concat([final_df, df], ignore_index=True)


print(final_df)

print("\n결측치 개수")
print(final_df.isnull().sum())

final_df.to_csv(
    save_path,
    index=False,
    encoding="utf-8-sig"
)

print("\ndone")
print("저장 위치:", os.path.abspath(save_path))