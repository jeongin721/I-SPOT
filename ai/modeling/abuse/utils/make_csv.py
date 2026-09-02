"""
json 파일이 있는 out 폴더를 기반으로(원천데이터)
BERT(roberta) 를 사용한 문장분류 학습이 가능하도록 하는 전처리 코드 입니다.
"""

import os
import re
import json
import pandas as pd

## 중복된 띄어쓰기 제거 함수
def reduce_consecutive_spaces(text):
    return re.sub(r'\s+', ' ', text)


## json파일과 mp3 파일의 짝이 맞는지 확인하기 위해 두 경로 모두 확인
json_dir = '/workspace/kavadata/out/'
save_path = "/workspace/02_abuse_classification/datasets/시연용.csv"


###########################################################################################################

final_df = pd.DataFrame()
audio_texts = []
error_list = []
for filename in os.listdir(json_dir):
    wavname = filename.split(".")[0]+".mp3"

    if filename.endswith('.json'):
        json_file_path = os.path.join(json_dir, filename)
        
        file_size = os.path.getsize(json_file_path) / 1024 
        if file_size <= 3:  # 3KB 이하인 경우 건너뛰기
            continue
    
        with open(json_file_path, 'r') as json_file:
            json_data = json.load(json_file)
            # print(json_data)
            
        info = json_data["info"]
        abuse_classification = info["학대의심"]  ## abuse classification 사용
        
        if abuse_classification == "해당없음":
            error_list.append(filename)
            abuse_classification = "(해당 없음)"
            
        
            
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

                        if text_values == "질문" :
                            break
                        if text_values == "":
                            break
                        audio_texts.append(text_values)
            except KeyError :
                pass

        data = {
                "file" : [filename],
                "label" : [abuse_classification],
                "audio_text": [str(audio_texts)]
                }

    df = pd.DataFrame(data)
    final_df = pd.concat([final_df, df], ignore_index=True)
# print(final_df)
final_df['audio_text'] = final_df['audio_text'].apply(lambda x: x[1:-1] if len(x) > 2 else "")

df = final_df.copy()


df["audio_text"] = df["audio_text"].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 0-9]", "", regex=True)
df["audio_text"] = df["audio_text"].str.replace("  ", " ")
df["audio_text"] = df["audio_text"].apply(reduce_consecutive_spaces)

# print(df.isnull().sum())

## csv 저장 경로 및 이름 설정
df.to_csv(save_path, index=False, encoding='utf-8-sig')
print(f"error_list : {error_list}")
print(df)
print("Convert Done!")