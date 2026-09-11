import os
import datetime
import random
import pandas as pd
import numpy as np
from glob import glob
import re
import json

from sklearn.model_selection import train_test_split  
from sklearn.metrics import f1_score, classification_report, confusion_matrix
from sklearn import metrics
from tqdm.auto import tqdm

from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor ,RobertaModel, AutoTokenizer,RobertaForSequenceClassification 

from utils.Datasets import CustomDataset, calculate_confusion_matrix, CustomDataset_Infer
from utils.Model import ConNet

import torch
import torch.nn as nn
from torch.nn.parallel import DataParallel
import torch.nn.functional
import torchaudio
from torch.optim import Adam
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt

import warnings
warnings.filterwarnings("ignore")
from transformers import logging
logging.set_verbosity_error()


if torch.cuda.is_available():
    device = torch.cuda.is_available()
    n_gpus = torch.cuda.device_count()
    print(f"Available GPUs ::: {n_gpus}")
else:
    print("CUDA device is not available")

MODEL = "klue/roberta-base"

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


nums = '0607'

mp3_file = r"C:\Users\USER\Desktop\최종_프로젝트\최종프로젝트_데이터셋\VS_in\VS_in_data\0008.mp3"
json_file = r"C:\Users\USER\Desktop\최종_프로젝트\최종프로젝트_데이터셋\VL_out\VL_out_data\0008.json"

print("file load complete!!", mp3_file)
print("file load complete!!", json_file)

file_size = os.path.getsize(json_file) / 1024 
if file_size <= 1: 
    print(f"{json_file} is Empty File!")
    
with open(json_file, 'r', encoding='utf-8') as json_file:
    json_data = json.load(json_file)

info = json_data["info"]
abuse_classification = info["상호작용 특성(종합)"]  # interaction classification 일경우 사용

first_list_item = json_data["list"]

audio_texts = []
list_max_num = len(first_list_item)
for i in range(list_max_num) :
    text_sector = first_list_item[i]

    audio_list = text_sector.get("list")
    # print(audio_list)
    for in_audio in audio_list :
        # print(in_audio)

        audio_items = in_audio.get("audio", [])
        
        audio_text= [item for item in audio_items if item.get("type") == "A"]
        # print(audio_text)

        for item in audio_text:
            text_values = item.get("text", "")

            if text_values == "질문" :
                break
            if text_values == "":
                break
            audio_texts.append(text_values)
data = {
        "file" : [mp3_file],
        "audio_text": [str(audio_texts)]
        }

data_df= pd.DataFrame(data)

def reduce_consecutive_spaces(text):
    return re.sub(r'\s+', ' ', text) # 하나 이상의 공백 문자를 한번으로 축소


data_df["audio_text"] = data_df["audio_text"].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 0-9]", "", regex=True)
data_df["audio_text"] = data_df["audio_text"].apply(reduce_consecutive_spaces)

print(data_df)


infer_dataset = CustomDataset_Infer(wav_paths= data_df['file'].values, sampling_rate=16000, text=data_df['audio_text'].values)
infer_loader = DataLoader(infer_dataset, batch_size=1, shuffle=False)

model = ConNet(num_classes=4)
model.load_state_dict(torch.load(
    r"C:\Users\USER\Desktop\최종_프로젝트\최종프로젝트_데이터셋\hub_model\1.모델소스코드\01_interaction_classification\weight\w2v-nofocal_2023-11-29_cpu.pth",
    map_location="cpu"
), strict=False)

model.to(device)

model.eval()

with torch.no_grad():
    for vecs, masks, toks, toks_masks in infer_loader :
        vecs = vecs.to(device)
        masks = masks.to(device)
        toks = toks.to(device)
        toks_masks = toks_masks.to(device)
        pred = model(vecs, masks, toks, toks_masks)
        print("pred:",pred) # pred: tensor([[ 2.0105, -2.5953, -2.4016, -2.3731],[ 1.2937, -2.0779, -1.8172, -2.4349]], device='cuda:0')
        preds = pred.argmax(1).detach().cpu().numpy()
        print(preds)
        
print("preds:", preds)
    
if preds == 0 :
    preds = "협조적"
if preds == 1:
    preds = "수동적"
if preds == 2:
    preds = "회피적"
if preds == 3:
    preds = "공격적"


print("last preds :", preds)