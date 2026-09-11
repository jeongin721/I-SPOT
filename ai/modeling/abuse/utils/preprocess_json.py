import os
import re
import json
import pandas as pd


# json file dir
json_file = '/home/datahub/out_20231114/out/0007.json'



audio_texts = []
file_size = os.path.getsize(json_file) / 1024 
if file_size <= 1: 
    print(f"{json_file} is Empty File!")


with open(json_file, 'r') as json_file:
    json_data = json.load(json_file)
    # print(json_data)
    
info = json_data["info"]
# abuse_classification = info["학대의심"]
abuse_classification = info["상호작용 특성(종합)"]  # interaction classification 일경우 사용
    
first_list_item = json_data["list"]
# print(len(first_list_item))

audio_texts = []
list_max_num = len(first_list_item)
for i in range(list_max_num) :
    text_sector = first_list_item[i]
    
    audio_list = text_sector.get("list")
    # print(audio_list)
    for in_audio in audio_list :
        # print(in_audio)

        audio_text= [item for item in in_audio['audio'] if item['type'] == 'A']
        # print(audio_text)
        
        for item in audio_text:
            text_values = item['text']
            audio_texts.append(text_values)
            

data = {
        "file" : [json_file],
        "audio_text": [str(audio_texts)]
        }

data_df = pd.DataFrame(data)

# 하나 이상의 공백문자를 한번으로 축소
def reduce_consecutive_spaces(text):
    return re.sub(r'\s+', ' ', text) 

data_df["audio_text"] = data_df["audio_text"].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 0-9]", "", regex=True)  ## 한글, 숫자, 공백 이외의 특수문자 제거
data_df["audio_text"] = data_df["audio_text"].apply(reduce_consecutive_spaces)
print(data_df)

## Saving json file to csv
# df.to_csv('/home/home/dyon/KAVA/wav2vec2/datasets_interaction1114.csv', index=False, encoding='utf-8-sig')