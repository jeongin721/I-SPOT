"""
음성파일이 있는 in 폴더와 json 파일이 있는 out 폴더를 기반으로
BERT 를 사용한 문장분류 학습이 가능하도록 하는 전처리 코드 입니다.
"""

import os
import re
import json
import pandas as pd

## 중복된 띄어쓰기 제거 함수
def reduce_consecutive_spaces(text):
    return re.sub(r'\s+', ' ', text)

 
# json 경로
json_dir = '/workspace/kavadata/out/'

# make_mp3file.py 로 생성한 평가용 데이터셋 경로(mp3 경로 - json 파일과의 짝이 맞는지 확인하기 위해)
wav_dir = "/workspace/kavadata/in_cut/"

# 저장경로 + 파일명 설정
save_path = "/workspace/01_interaction_classification/datasets/01_train_dataset.csv"


final_df = pd.DataFrame()
audio_texts = []
error_list = []
for filename in os.listdir(json_dir):
# for filename in json_list:
    wavname = filename.split(".")[0]+".mp3"

    if wavname not in os.listdir(wav_dir):
        print("no wav file")
        continue
        
    if filename.endswith('.json'):
        json_file_path = os.path.join(json_dir, filename)
        
        file_size = os.path.getsize(json_file_path) / 1024 
        if file_size <= 3:  # 3KB 이하인 경우 건너뛰기
            print("no size!")
            continue
    
        with open(json_file_path, 'r') as json_file:
            json_data = json.load(json_file)
            # print(json_data)
            
        info = json_data["info"]
        interaction_classification = info["상호작용 특성(종합)"]  # interaction classification 사용

        first_list_item = json_data["list"]
        audio_texts = []
        list_max_num = len(first_list_item)
        for i in range(list_max_num) :
            text_sector = first_list_item[i]
            
            audio_list = text_sector.get("list")
            try :
                for in_audio in audio_list :
            
                    audio_text= [item for item in in_audio['audio'] if item['type'] == 'A']
                
                    for item in audio_text:
                        text_values = item['text']
                        audio_texts.append(text_values)
            except KeyError:
                pass
                    
        if audio_texts == None :
            print(f"{filename}  : empty!!!!!")
            continue
        
        data = {
                "file" : [filename],
                "label" : [interaction_classification],
                "audio_text": [str(audio_texts)]
                }

    df = pd.DataFrame(data)
    final_df = pd.concat([final_df, df], ignore_index=True)


final_df['audio_text'] = final_df['audio_text'].apply(lambda x: x[1:-1] if len(x) > 2 else "")

df = final_df.copy()

df['file'] = df['file'].str.replace('.json', '.mp3', regex=True)


df["audio_text"] = df["audio_text"].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 0-9]", "", regex=True)
df["audio_text"] = df["audio_text"].str.replace("  ", " ")
df["audio_text"] = df["audio_text"].apply(reduce_consecutive_spaces)


print("null 값 체크.....")
print(df.isnull().sum())
df = df.dropna() ## null 값 제거


print(df)
## csv 저장 경로 및 이름 설정
df.to_csv(save_path, index=False, encoding='utf-8-sig')
print(f"error_list : {error_list}")
print("Finished!")