import os
import pandas as pd
import numpy as np
import json
import re
import datetime

import torch
from torch.utils.data import Dataset, DataLoader

from transformers import ElectraTokenizer, ElectraForSequenceClassification
from transformers import AutoTokenizer, AutoModelForSequenceClassification

import warnings
warnings.filterwarnings("ignore")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


##########################################################################################################
# 상담 json 데이터셋 (원천데이터)

json_file = r"C:\Users\USER\Desktop\최종_프로젝트\최종프로젝트_데이터셋\VL_out\VL_out_data\0008.json"

##########################################################################################################


audio_texts = []
file_size = os.path.getsize(json_file) / 1024 
if file_size <= 1: 
    print(f"{json_file} is Empty File!")


with open(json_file, 'r', encoding='utf-8') as json_file:
    json_data = json.load(json_file)
    
info = json_data["info"]
abuse_classification = info["상호작용 특성(종합)"]  # interaction classification
    
first_list_item = json_data["list"]

audio_texts = []
list_max_num = len(first_list_item)
for i in range(list_max_num) :
    text_sector = first_list_item[i]
    
    audio_list = text_sector.get("list")
    for in_audio in audio_list :
        audio_text= [item for item in in_audio.get('audio', []) if item.get('type') == 'A']
        for item in audio_text:
            text_values = item['text']
            audio_texts.append(text_values)

data = {
        "file" : [json_file],
        "audio_text": [str(audio_texts)]
        }

data_df= pd.DataFrame(data)

def reduce_consecutive_spaces(text):
    return re.sub(r'\s+', ' ', text) # 하나 이상의 공백 문자를 한번으로 축소


data_df["audio_text"] = data_df["audio_text"].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 0-9]", "", regex=True)  ## 한글, 숫자, 공백 이외의 특수문자 제거
data_df["audio_text"] = data_df["audio_text"].apply(reduce_consecutive_spaces)


class KavaTextDataset(Dataset):
    def __init__(self, df, tokenizer, max_len, with_labels=True):
        self.tokenizer = tokenizer
        self.data = df
        self.sentences = df["audio_text"].values
        self.labels = df["abuse_label"].values if with_labels else None
        self.max_len = max_len
        self.with_labels = with_labels

    def __len__(self):
        return len(self.sentences)

    def __getitem__(self, index):
        sentence = self.sentences[index]

        inputs = self.tokenizer.encode_plus(
            sentence,
            add_special_tokens=True,
            max_length=self.max_len,
            pad_to_max_length=True,
            return_attention_mask=True,
            truncation=True
        )

        ids = torch.tensor(inputs['input_ids'], dtype=torch.long)
        mask = torch.tensor(inputs['attention_mask'], dtype=torch.long)
        token_type_ids = torch.tensor(inputs['token_type_ids'], dtype=torch.long)

        if self.with_labels:
            label = self.labels[index]
            return {
                'ids': ids,
                'mask': mask,
                'token_type_ids': token_type_ids,
                'labels': torch.tensor(label, dtype=torch.long)
            }
        else:
            return {
                'ids': ids,
                'mask': mask,
                'token_type_ids': token_type_ids
            }
            

klue_roberta_tokenizer = AutoTokenizer.from_pretrained("klue/roberta-base")
klue_roberta_model = AutoModelForSequenceClassification.from_pretrained("klue/roberta-base", num_labels=5)

text_data = KavaTextDataset(data_df, klue_roberta_tokenizer, 512,  with_labels=False)
text_dataloader = DataLoader(text_data, batch_size=1)    

## 모델 가중치 로드
model = klue_roberta_model
model.load_state_dict(
    torch.load(
        r"C:\Users\USER\Desktop\최종_프로젝트\최종프로젝트_데이터셋\hub_model\1.모델소스코드\02_abuse_classification\weight\roberta_base-2023-11-29_cpu.pth",
        map_location=device
    ),
    strict=False
)
model.to(device)

model.eval()

with torch.no_grad():
    for data in text_dataloader:
        ids = data['ids'].to(device)
        mask = data['mask'].to(device)
        token_type_ids = data['token_type_ids'].to(device)

        outputs = model(ids, attention_mask=mask, token_type_ids=token_type_ids)
        
        prediction = outputs.logits.argmax(1).detach().cpu().numpy()
       
    
print(prediction)

# 0:해당없음, 1:신체학대, 2:정서학대, 3:성학대, 4:방임
