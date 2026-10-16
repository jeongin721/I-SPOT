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


from utils.Datasets import CustomDataset, calculate_confusion_matrix
from utils.Model import ConNet, FocalLoss

from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor ,RobertaModel, AutoTokenizer,RobertaForSequenceClassification

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
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# 학습시 모델 저장할 경로
model_path = "/workspace/01_interaction_classification/weight/"

## 원천데이터셋- cut mp3 경로
wav_path = "/workspace/kavadata/in_cut/"  
MODEL = "klue/roberta-base"


CFG = {
        'EPOCHS': 50,
        'LEARNING_RATE': 1e-5,
        'BATCH_SIZE': 4,
        'SEED': 69,
        'SAMPLE_RATE': 16000,
        'NUM_WORK' : 4,
        'PATIENCE' : 20,
        'LABEL' : 'label'
        }

print("CFG : ",CFG)


def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True

seed_everything(CFG['SEED'])  



df = pd.read_csv("/workspace/01_interaction_classification/datasets/학습용,검증용데이터셋목록.csv")
df = df[['file', CFG['LABEL'],'audio_text']]
# print(df)


df['file'] = df['file'].str.replace('.json', '.mp3', regex=True)
df['file'] = wav_path + df['file'].astype(str)
existing_file = df['file'].apply(os.path.exists)

df = df[existing_file]
df = df.dropna()




def reduce_consecutive_spaces(text):
    return re.sub(r'\s+', ' ', text) # 하나이상의 공백문자를 한번으로 축소
    
df["audio_text"] = df["audio_text"].apply(reduce_consecutive_spaces)
df["audio_text"] = df["audio_text"].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 0-9]", "", regex=True)

# print(df.head())
print(f"Total Datasets : {df.shape}")

df = df.copy()

print(df[CFG['LABEL']].value_counts())

trainset, valset, _, _ = train_test_split(df, df[CFG['LABEL']], test_size=0.2, stratify=df[CFG['LABEL']], random_state=CFG['SEED'])

print(f"train/val split  -  train:{trainset.shape} , val:{valset.shape}")




def validation(model, criterion, val_loader, device) :
    model.eval()
    val_loss = []
    preds, true_labels = [], []
    
    with torch.no_grad():
        for vecs, masks, toks, toks_masks, labels in val_loader :
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
        print("validation Confusion Matrix:")
        print(cm)
        print("validation classification report")
        print(cr)
    
    return _val_loss, _val_score



def train(model, optimizer, train_loader, val_loader, scheduler, device):
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1).to(device)
    #criterion = FocalLoss(alpha=1.0, gamma=2.0, reduction="mean")
    early_stopping_counter = 0
    best_score = 0
    best_model = None
    
    train_losses = []
    val_losses = []
    val_f1_scores = []

    try:
        for epoch in range(1, CFG['EPOCHS']+1):
            model.train()
            train_loss = []
            
            for vecs, masks, toks, toks_masks, labels in tqdm(iter(train_loader)):
                vecs = vecs.to(device)
                masks = masks.to(device)
                toks = toks.to(device)
                toks_masks = toks_masks.to(device)
                labels = labels.to(device)
                
                
                
                output = model(vecs, masks, toks, toks_masks)
                loss = criterion(output, labels)
                
                loss.backward()
                optimizer.step()
                optimizer.zero_grad()
                
                train_loss.append(loss.item())
                
            _val_loss, _val_score = validation(model, criterion, val_loader, device)
            _train_loss = np.mean(train_loss)
            
            print(f'Epoch[{epoch}] ::: Train Loss : [{_train_loss:.5f}]   Val Loss : [{_val_loss:.5f}]    Val Weighted F1 Score : [{_val_score:.5f}]')
            
            train_losses.append(_train_loss)
            val_losses.append(_val_loss)
            val_f1_scores.append(_val_score)
            
            if scheduler is not None:
                scheduler.step(_val_score)
                
            if best_score < _val_score:
                best_score = _val_score
                best_model = model
                best_model = best_model.module
                best_model.to("cpu")
                torch.save(best_model.state_dict(), f"{model_path}w2v+roberta_newlayer_{datetime.date.today()}_cpu.pth" )
                best_model.to(device)
                
                print(f"{epoch} ::::: update the best model best score(f1)  :::::")
                
            else:
                early_stopping_counter += 1
                if early_stopping_counter >= CFG["PATIENCE"]:
                    print(f'Early stopping: Validation score did not improve by at least {early_stopping_counter} for {CFG["PATIENCE"]} consecutive epochs.')
                    break
    except KeyboardInterrupt:
        print("KeyboardInterrupt 학습이 중단되었습니다. 그래프를 그립니다.")
        
    # 그래프 그리기
    plt.figure(figsize=(12, 6))
    
    # 첫 번째 그래프: Loss
    plt.plot(train_losses, label='Train Loss')
    plt.plot(val_losses, label='Validation Loss')
    plt.title(f"{datetime.date.today()} interaction Loss History")
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.legend()
    plt.savefig(f'/workspace/01_interaction_classification/history/training_loss_results_{datetime.date.today()}.png')

    # 두 번째 그래프: Accuracy
    plt.figure(figsize=(12, 6))  # 새로운 figure 생성
    plt.plot(val_f1_scores, label='Validation f1 score')
    plt.title(f"{datetime.date.today()} interaction f1 score History")
    plt.xlabel('Epochs')
    plt.ylabel('f1 score')
    plt.legend()
    plt.savefig(f'/workspace/01_interaction_classification/history/training_score_results_{datetime.date.today()}.png')

    return best_model




########################################################################################################################
print("Train Start Time : ", datetime.datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분"))


train_dataset = CustomDataset(wav_paths=trainset['file'].values, target_labels=trainset[CFG['LABEL']].values, sampling_rate=CFG['SAMPLE_RATE'], text=trainset['audio_text'].values)
train_loader = DataLoader(train_dataset, batch_size=CFG['BATCH_SIZE'], num_workers=CFG['NUM_WORK'])

val_dataset = CustomDataset(valset['file'].values, valset[CFG['LABEL']].values, sampling_rate=CFG['SAMPLE_RATE'], text= valset['audio_text'].values)
val_loader = DataLoader(val_dataset, batch_size=CFG['BATCH_SIZE'], num_workers=CFG['NUM_WORK']) 

model = ConNet(num_classes=4)
model = DataParallel(model, device_ids=[0, 1])
model.to(device)

optimizer = torch.optim.Adam(params = model.parameters(), lr = CFG["LEARNING_RATE"])
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                optimizer, mode='max', factor=0.5, patience=5, threshold_mode='abs', min_lr=1e-8, verbose=True
                )

infer_model = train(model, optimizer, train_loader, val_loader, scheduler, device)


print("Train End Time : ", datetime.datetime.now().strftime("%Y년 %m월 %d일  %H시 %M분"))
########################################################################################################################
