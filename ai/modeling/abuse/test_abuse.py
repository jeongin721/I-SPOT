import pandas as pd
import numpy as np
import datetime
import re

# Custom library
from utils.Custom_utils import FocalLoss, calculate_confusion_matrix, KoreanTextDataset

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import ElectraTokenizer, ElectraForSequenceClassification
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, classification_report

from tqdm.auto import tqdm
import matplotlib.pyplot as plt

import warnings
warnings.filterwarnings("ignore")

from transformers import logging
logging.set_verbosity_error()

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print("device : ", device)


def set_seed(seed=69):
    np.random.seed(seed) 
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

set_seed(seed=69)

####################################################################################################

## make_csv.py 코드로 생성한 평가용 데이터셋을 불러옵니다.
df = pd.read_csv("/workspace/02_abuse_classification/datasets/test.csv")

## 모델 weight 경로 설정
model_path = "/workspace/02_abuse_classification/weight/roberta_base-2023-11-29_cpu.pth"

## 개별 결과값 csv 저장 경로 설정
result_path = "/workspace/02_results.csv"

####################################################################################################

label_mapping = {
                    "(해당 없음)" : 0,   
                    "신체학대": 1,   
                    "정서학대": 2,   
                    "성학대": 3,
                    "방임" : 4
                }

df['label'] = df['label'].map(label_mapping)

test_df=df.copy()

print("Test label")
print(test_df['label'].value_counts())
print(f"Test_data shape : {test_df.shape}")

# Roberta model load
klue_roberta_tokenizer = AutoTokenizer.from_pretrained("klue/roberta-base")
klue_roberta_model = AutoModelForSequenceClassification.from_pretrained("klue/roberta-base", num_labels=5)

# Custom Dataset Loader
test_data = KoreanTextDataset(test_df, klue_roberta_tokenizer, 512)

# GPU 상황에 따라 batch size 조정 필요
test_dataloader = DataLoader(test_data, batch_size=32, num_workers=8)


## Load Training Weight
model = klue_roberta_model
model.load_state_dict(torch.load(model_path, map_location="cpu"))
klue_roberta_model.to(device)

model.eval()
test_loss = 0.0
preds, true_labels = [], []

with torch.no_grad():
    for data in test_dataloader:
        ids = data['ids'].to(device)
        mask = data['mask'].to(device)
        token_type_ids = data['token_type_ids'].to(device)
        labels = data['labels'].to(device)

        outputs = model(ids, attention_mask=mask, token_type_ids=token_type_ids)
        preds += outputs.logits.argmax(1).detach().cpu().numpy().tolist()
        true_labels += labels.detach().cpu().numpy().tolist()
        
val_f1 = f1_score(true_labels, preds, average ='weighted' )

y_true = np.array(true_labels)

print(f"Test F1 Score : {val_f1}")
cm, cr= calculate_confusion_matrix(preds, true_labels)

print(f"==============================Test Confusion Matrix ==============================")
print(cm)
print()
print("=============================Test classification report=============================")
print(cr)


def reverse_label_map(label):
    for k, v in label_mapping.items():
        if v == label:
            return k


test_df['prediction'] = preds
test_df['prediction'] = test_df['prediction'].apply(reverse_label_map)
test_df['label'] = test_df['label'].apply(reverse_label_map)

result_df = test_df[['file', 'label', 'prediction']]


## 평가용 데이터셋의 개별 예측값과 원래 라벨값을 출력하여 csv 파일로 저장합니다.
result_df.to_csv(result_path, index=False, encoding='utf-8-sig'
                 )
print("Results saved to CSV.")