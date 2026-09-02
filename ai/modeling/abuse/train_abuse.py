import pandas as pd
import numpy as np
import datetime
import re

from utils.Custom_utils import FocalLoss, calculate_confusion_matrix, KoreanTextDataset
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import ElectraTokenizer, ElectraForSequenceClassification
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import AdamW

from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, classification_report

from tqdm.auto import tqdm
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

print("device", device)

CFG = {
        'EPOCHS': 50,
        'LEARNING_RATE': 2e-5,
        'BATCH_SIZE': 8,
        'SEED': 69,
        'MAX_LEN': 512,
        'EARLY_STOP': 20,
        'LABEL' : 'label',
        'MODEL_ID' : 'klue/roberta-base',
        'CRITERION': FocalLoss()
        }
# nn.CrossEntropyLoss()
model_title = CFG['MODEL_ID']
print(f"Training Parameters : {CFG}")


def set_seed(seed=CFG['SEED']):
    np.random.seed(seed) 
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
set_seed()

## upload csv dataset
# df = pd.read_csv("/workspace/02_abuse_classification/datasets/학습용,검증용데이터셋목록.csv")
# print(df.info())


# train_df, valset, _,_ = train_test_split(df, df[CFG['LABEL']], train_size=2640, stratify=df[CFG['LABEL']], random_state=CFG['SEED'])
# val_df, test_df,  _,_ = train_test_split(valset, valset[CFG['LABEL']], train_size=330, stratify=valset[CFG['LABEL']], random_state=CFG['SEED'])
# print(train_df['label'].value_counts())
# print(val_df['label'].value_counts())
# print(test_df['label'].value_counts())
# print(f"Total trainset : {train_df.shape}")
# print(f"Total validset : {val_df.shape}")
# print(f"Total testset : {test_df.shape}")
# train_df['split'] = "train"
# val_df['split'] = "valid"
# test_df['split'] = "test"
# df = pd.concat([train_df,val_df,test_df])
# print(df)
# df.to_csv("/home/home/dyon/KAVA/abuse_classification/datasets/split_ver.csv", index=False, encoding='utf-8-sig')




df = pd.read_csv("/workspace/02_abuse_classification/datasets/final_abuse_split_ver.csv")




print(df['label'].value_counts())
print(df['split'].value_counts())



label_mapping = {
                    "(해당 없음)" : 0,   
                    "신체학대": 1,   
                    "정서학대": 2,   
                    "성학대": 3,
                    "방임" : 4
                }

df['label'] = df['label'].map(label_mapping)

train_df = df[df['split'] == 'train']
val_df = df[df['split'] == 'valid']


print("train label")
print(train_df['label'].value_counts())
print("valid label")
print(val_df['label'].value_counts())

print(f"Train_data shape : {train_df.shape}")
print(f"Valid_data shape : {val_df.shape}")


def train_model(model, tokenizer, train_dataframe, epochs, epochs_earlystop):
    BATCH_SIZE = CFG['BATCH_SIZE']
    MAX_LEN = CFG['MAX_LEN']

    
    train_data = KoreanTextDataset(train_df, tokenizer, MAX_LEN)
    val_data = KoreanTextDataset(val_df, tokenizer, MAX_LEN)
    
    train_dataloader = DataLoader(train_data, batch_size=BATCH_SIZE, num_workers=8, shuffle=True)
    val_dataloader = DataLoader(val_data, batch_size=BATCH_SIZE, num_workers=8)
    
    
    optimizer = AdamW(model.parameters(), lr=CFG['LEARNING_RATE'])
    criterion = CFG['CRITERION']
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.9, patience=20, verbose=True)

    
    no_improve = 0
    prev_loss = float('inf')
    best_score=0
    train_losses = []
    val_losses = []
    val_accuracies = []
    for epoch in range(epochs):
        
        model.train()
        
        running_loss = 0.0
        for step, data in enumerate(tqdm(train_dataloader)):
            ids = data['ids'].to(device)
            mask = data['mask'].to(device)
            token_type_ids = data['token_type_ids'].to(device)
            labels = data['labels'].to(device)

            outputs = model(ids, attention_mask=mask, token_type_ids=token_type_ids)
            loss = criterion(outputs.logits, labels)

            torch.cuda.empty_cache()

            loss.backward()
            running_loss += loss.item()
            optimizer.step()
            optimizer.zero_grad()

        model.eval()
        val_loss = 0.0
        preds, true_labels = [], []
        with torch.no_grad():
            for data in val_dataloader:
                ids = data['ids'].to(device)
                mask = data['mask'].to(device)
                token_type_ids = data['token_type_ids'].to(device)
                labels = data['labels'].to(device)

                outputs = model(ids, attention_mask=mask, token_type_ids=token_type_ids)
                preds += outputs.logits.argmax(1).detach().cpu().numpy().tolist()
                true_labels += labels.detach().cpu().numpy().tolist()
                
                loss = criterion(outputs.logits, labels)
                val_loss += loss.item()

        avg_val_loss = val_loss / len(val_dataloader)
        val_f1 = f1_score(true_labels,preds, average ='weighted' )
        
        y_true = np.array(true_labels)
        
        print(f"EPOCH {epoch+1} completed, Training Loss: {running_loss/len(train_dataloader)}, Validation Loss: {avg_val_loss},  Validation f1 score: {val_f1}")
        cm, cr = calculate_confusion_matrix(preds, true_labels)
        print(f"EPOCH {epoch+1} confusion_matrix :")
        print(cm)
        print()
        print("validation classification report")
        print(cr)

        train_losses.append(running_loss/len(train_dataloader))
        val_losses.append(avg_val_loss)
        val_accuracies.append(val_f1)
        
        scheduler.step(avg_val_loss)

        if prev_loss - avg_val_loss <= 0.0001:
            no_improve += 1
        else:
            no_improve = 0

        prev_loss = avg_val_loss
        
        if best_score < val_f1:
                best_score = val_f1
                best_model = model
                # best_model = best_model.module ## multigpu training 일때만 사용
                best_model.to("cpu")
                
                torch.save(best_model.state_dict(), f"/workspace/02_abuse_classification/weight/roberta_base-{datetime.date.today()}_cpu.pth" )

                best_model.to(device)
                
                print(f"::: Update best model at {epoch+1} epoch ::: ")

        if no_improve == epochs_earlystop:
            print("Early stopping due to no improvement in validation loss.")
            break
    
    
    # 그래프 그리기
    plt.figure(figsize=(12, 6))

    # 첫 번째 그래프: Loss
    plt.plot(train_losses, label='Train Loss')
    plt.plot(val_losses, label='Validation Loss')
    plt.title(f"{datetime.date.today()}_{{CFG['MODEL_ID']}} Loss History")
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.legend()
    plt.savefig(f'/home/home/dyon/KAVA/abuse_classification/history/roberta_base-training_loss_results-cross_{datetime.date.today()}.png')

    # 두 번째 그래프: Accuracy
    plt.figure(figsize=(12, 6))  # 새로운 figure 생성
    plt.plot(val_accuracies, label='Validation f1 score')
    plt.title(f"{datetime.date.today()} {CFG['MODEL_ID']} f1 score History")
    plt.xlabel('Epochs')
    plt.ylabel('Acc and f1 score')
    plt.legend()
    plt.savefig(f'/home/home/dyon/KAVA/abuse_classification/history/roberta_base-training_score_results-cross{datetime.date.today()}.png')
        

    return model


print("Train Start Time : ", datetime.datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분"))

start_time = time.time()



klue_roberta_tokenizer = AutoTokenizer.from_pretrained(CFG['MODEL_ID'])
klue_roberta_model = AutoModelForSequenceClassification.from_pretrained(CFG['MODEL_ID'], num_labels=5)
klue_roberta_model.to(device)
klue_roberta_model_trained = train_model(klue_roberta_model, klue_roberta_tokenizer, df, epochs=CFG['EPOCHS'], epochs_earlystop=CFG['EARLY_STOP']) # 50 epochs, 5 epochs_stop


end_time = time.time()

print("Train End Time : ", datetime.datetime.now().strftime("%Y년 %m월 %d일  %H시 %M분"))
total_training_time = end_time - start_time
total_training_time = total_training_time/60
print(f"total time : {total_training_time:.2f}")