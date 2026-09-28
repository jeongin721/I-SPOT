import os
import datetime
import random
import pandas as pd
import numpy as np
from glob import glob
import re

from sklearn.model_selection import train_test_split  
from sklearn.metrics import f1_score, classification_report, confusion_matrix
from sklearn import metrics
from tqdm.auto import tqdm

from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor, RobertaConfig, RobertaModel, AutoTokenizer

# Custom library
from utils.Datasets import CustomDataset, calculate_confusion_matrix, CustomDataset_Infer
from utils.Model import ConNet, FocalLoss

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


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


# GPU 상태에 따라 batch size 조절 필요
CFG = {
        'LEARNING_RATE': 1e-6,
        'BATCH_SIZE': 8,
        'SEED': 69,
        'SAMPLE_RATE': 16000,
        'NUM_WORK' : 8,
        'PATIENCE' : 10,
        'LABEL' : 'label'
        }

print("CFG:",CFG)
def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True

seed_everything(CFG['SEED'])  

## 모델 웨이트값이 있는 경로 설정
model_path = "/workspace/01_interaction_classification/weight/w2v-nofocal_2023-11-29_cpu.pth"

## make_mp3file.py 를 통해 생성한 상호작용행동특성 용 음원파일이 있는 경로 설정
wav_path = "/workspace/kavadata/in_cut/"

## 평가용 데이터셋 (csv 파일) 경로 설정
df = pd.read_csv("/workspace/01_interaction_classification/datasets/평가용데이터셋.csv")

## 파일 별 정답과 예측값을 저장하는 경로 설정
result_path = "/workspace/01_results.csv"



df1 = df.copy()
print(df.head())
print(f"Total Datasets : {df.shape}")

df['file'] = df['file'].str.replace('.json', '.mp3')
df['file'] = wav_path + df['file'].astype(str)
df = df.copy()

print("::: Test dataset class 별 분포 :::")
print(df[CFG['LABEL']].value_counts())

label_mapping = {   "협조적": 0,   
                    "수동적": 1,   
                    "회피적": 2,   
                    "공격적": 3
                }

######################################################################################################################################


def validation(model, criterion, val_loader, device) :
    model.eval()
    val_loss = []
    preds, true_labels = [], []
    
    with torch.no_grad():
        for vecs, masks, toks, toks_masks, labels  in  tqdm(iter(val_loader)) :
            vecs = vecs.to(device)
            masks = masks.to(device)
            toks = toks.to(device)
            toks_masks = toks_masks.to(device)
            labels = labels.to(device)
            
            pred = model(vecs, masks, toks, toks_masks)
           
            loss = criterion(pred, labels)
            
            preds += pred.argmax(1).detach().cpu().numpy().tolist()
            true_labels += labels.detach().cpu().numpy().tolist()
            
            val_loss.append(loss.item())
        
        _val_loss = np.mean(val_loss)
        _val_score = f1_score(true_labels, preds, average='weighted')
        
        cm, cr = calculate_confusion_matrix(preds, true_labels)
        print("===================================================================")
        print("Test Confusion Matrix:")
        print(cm)
        print("Test classification report")
        print(cr)
        print("Test score : ", _val_score)
        print("===================================================================")
    
    return preds

print("Test Start Time : ", datetime.datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분"))

test_dataset = CustomDataset(wav_paths=df['file'].values, target_labels= df['label'].values, sampling_rate=CFG['SAMPLE_RATE'], text= df['audio_text'].values)
test_loader = DataLoader(test_dataset, batch_size=CFG['BATCH_SIZE'], num_workers=CFG['NUM_WORK']) 

model = ConNet(num_classes=4)
model.load_state_dict(torch.load(model_path, map_location="cpu"))
model.to(device)

criterion = nn.CrossEntropyLoss(label_smoothing=0.1).to(device)
infer_model = validation(model, criterion, test_loader, device)



print("Test End Time : ", datetime.datetime.now().strftime("%Y년 %m월 %d일  %H시 %M분"))



label_mapping = {  
                    "협조적": 0,   
                    "수동적": 1,   
                    "회피적": 2,   
                    "공격적": 3
                }

def reverse_label_map(label):
    for k, v in label_mapping.items():
        if v == label:
            return k


df1['prediction'] = infer_model
df1['prediction'] = df1['prediction'].apply(reverse_label_map)

result_df = df1[['file', 'label', 'prediction']]


## 평가용 데이터셋의 개별 예측값과 원래 라벨값을 출력하여 csv 파일로 저장합니다.
result_df.to_csv(result_path, index=False, encoding='utf-8-sig')
print("Results saved to CSV.")