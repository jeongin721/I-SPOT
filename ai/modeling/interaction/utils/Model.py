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



class ConNet(nn.Module):
    def __init__(self, num_classes):
        super(ConNet, self).__init__()
        self.num_classes = num_classes
        self.wav_model = Wav2Vec2ForCTC.from_pretrained("kresnik/wav2vec2-large-xlsr-korean")
        self.bert_model = RobertaModel.from_pretrained('roberta-base')
        
        self.audio_fc = nn.Linear(1205, 512)
        self.text_fc = nn.Linear(768, 512)
        self.drop = nn.Dropout1d(0.1)
        self.sumpool = nn.AvgPool1d(5)
        self.linear_classifier = nn.Linear(204, num_classes)

    def forward(self, input_values, attention_mask, text_input_ids, text_attention_mask):
        wav_features = self.wav_model(input_values=input_values, attention_mask=attention_mask).logits
        wav_features = wav_features[:, -1, :]
        
        text_out = self.bert_model(text_input_ids, attention_mask = text_attention_mask)
        text_features = text_out.pooler_output
        wav_f = self.audio_fc(wav_features)
        text_f = self.text_fc(text_features)
        wavtxt = wav_f*text_f
        wavtxt_dr = self.drop(wavtxt)
        
        concatenated_features = torch.cat([wavtxt, wavtxt_dr], dim=1)
        concatenated_features= self.sumpool(concatenated_features)
        output = self.linear_classifier(concatenated_features)
        
        return output


# focal loss 정의
class FocalLoss(torch.nn.Module):
    def __init__(self, alpha=1, gamma=2, reduction="mean"):
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs, targets):
        BCE_loss = torch.nn.functional.cross_entropy(inputs, targets, reduction="none")
        pt = torch.exp(-BCE_loss)
        F_loss = self.alpha * (1 - pt) ** self.gamma * BCE_loss
        if self.reduction == "mean":
            return torch.mean(F_loss)
        elif self.reduction == "sum":
            return torch.sum(F_loss)
        else:
            return F_loss
