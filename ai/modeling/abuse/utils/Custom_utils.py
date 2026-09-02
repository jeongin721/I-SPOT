import pandas as pd
import numpy as np
import datetime
import re

import torch
import torch.nn as nn

from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import classification_report, confusion_matrix


label_mapping = {
                    "(해당 없음)" : 0,   
                    "신체학대": 1,   
                    "정서학대": 2,   
                    "성학대": 3,
                    "방임" : 4
                }

## for class imbalence
class FocalLoss(nn.Module):
    def __init__(self, alpha=1, gamma=2, reduce=True):
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduce = reduce

    def forward(self, inputs, targets):
    
        ce_loss = nn.CrossEntropyLoss()(inputs, targets)

        pt = torch.exp(-ce_loss)
        F_loss = self.alpha * (1-pt)**self.gamma * ce_loss

        if self.reduce:
            return torch.mean(F_loss)
        else:
            return F_loss
    
    
def calculate_confusion_matrix(preds, labels):
    cm = confusion_matrix(labels, preds)
    cm_df = pd.DataFrame(cm, index=label_mapping.keys(), columns=label_mapping.keys())
    target_names = ["해당없음","신체학대","정서학대","성학대", "방임"]
    cm_report = classification_report(labels, preds, target_names=target_names)
    return cm_df, cm_report
    


class KoreanTextDataset(Dataset):
    def __init__(self, df, tokenizer, max_len, with_labels=True):
        self.tokenizer = tokenizer
        self.data = df
        self.sentences = df["audio_text"].values
        self.labels = df["label"].values if with_labels else None
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
        # print(ids)
        # print(ids.shape)

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