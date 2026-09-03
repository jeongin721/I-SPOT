import os
import datetime
import random
import pandas as pd
import numpy as np
from glob import glob

from sklearn.model_selection import train_test_split  
from sklearn.metrics import f1_score, classification_report, confusion_matrix
from sklearn import metrics
from tqdm.auto import tqdm

from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor ,RobertaModel, AutoTokenizer

import torch
import torch.nn as nn
from torch.nn.parallel import DataParallel
import torch.nn.functional
import torchaudio
from torch.optim import Adam
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt

MODEL = "klue/roberta-base"

label_mapping = {  
                    "협조적": 0,   
                    "수동적": 1,   
                    "회피적": 2,   
                    "공격적": 3
                }

class CustomDataset(Dataset) :
    def __init__(self, wav_paths, target_labels, sampling_rate, text) :
        self.wav_files = wav_paths
        self.target_labels = list(target_labels)
        self.sampling_rate = sampling_rate
        self.texts = text
        self.processor = Wav2Vec2Processor.from_pretrained("kresnik/wav2vec2-large-xlsr-korean")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL)
        
    def __len__(self):
        return len(self.wav_files)
    
    def __getitem__(self, index):
        wave_form_de = self.wav_files[index]
        target_label = torch.tensor(label_mapping[self.target_labels[index]])
        wave_form_de, sample_rate = torchaudio.load(wave_form_de, backend ="soundfile")
        if sample_rate != self.sampling_rate:
            wave_form_de = torchaudio.transforms.Resample(sample_rate, self.sampling_rate)(wave_form_de)
        wave_form_de = self.processor(wave_form_de, sampling_rate=16000, return_tensors="pt", padding=True)
        
        input_values = wave_form_de.input_values
        
        attention_mask = wave_form_de.attention_mask
        input_values = input_values.squeeze(0)
        
        attention_mask = attention_mask.squeeze(0)
        attention_mask = torch.nn.functional.pad(attention_mask, (0, input_values.size(-1)), 'constant', 1.0)
        
        input_values = torch.nn.functional.pad(input_values, (0, 400000 - input_values.size(-1)), 'constant', 0.0)
        attention_mask = torch.nn.functional.pad(attention_mask, (0, 400000 - attention_mask.size(-1)), 'constant', 0.0)
        
        text = self.texts[index]
        
        text_values = self.tokenizer.encode_plus(
            text,
            add_special_tokens=True,
            max_length=512,
            padding='longest', # pad_to_max_lengh 사라짐
            return_attention_mask=True,
            truncation=True
            )
        
        text_input_ids = torch.tensor(text_values["input_ids"], dtype=torch.long)[:512]
        text_input_ids = torch.nn.functional.pad(text_input_ids, (0, 512 - len(text_input_ids)))
        
        text_attention_mask = torch.tensor(text_values['attention_mask'], dtype=torch.long)[:512]
        text_attention_mask = torch.nn.functional.pad(text_attention_mask, (0, 512 - len(text_attention_mask)))
    
        
        return input_values[0], attention_mask, text_input_ids, text_attention_mask, target_label
        
    
def calculate_confusion_matrix(preds, labels):
    cm = confusion_matrix(labels, preds)
    cm_df = pd.DataFrame(cm, index=label_mapping.keys(), columns=label_mapping.keys())
    target_names = ["협조적","수동적","회피적","공격적"]
    cm_report = classification_report(labels, preds, target_names=target_names)
    return cm_df, cm_report



class CustomDataset_Infer(Dataset) :
    def __init__(self, wav_paths, sampling_rate, text) :
        self.wav_files = wav_paths
        self.sampling_rate = sampling_rate
        self.texts = text
        self.processor = Wav2Vec2Processor.from_pretrained("kresnik/wav2vec2-large-xlsr-korean")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL)
        
    def __len__(self):
        return len(self.wav_files)
    
    def __getitem__(self, index):
        wave_form_de = self.wav_files[index]
        wave_form_de, sample_rate = torchaudio.load(wave_form_de)
        if sample_rate != self.sampling_rate:
            wave_form_de = torchaudio.transforms.Resample(sample_rate, self.sampling_rate)(wave_form_de)
        wave_form_de = self.processor(wave_form_de, sampling_rate=16000, return_tensors="pt", padding=True)
        
        input_values = wave_form_de.input_values
        
        attention_mask = wave_form_de.attention_mask
        input_values = input_values.squeeze(0)
        
        attention_mask = attention_mask.squeeze(0)
        attention_mask = torch.nn.functional.pad(attention_mask, (0, input_values.size(-1)), 'constant', 1.0)
        
        input_values = torch.nn.functional.pad(input_values, (0, 400000 - input_values.size(-1)), 'constant', 0.0)
        attention_mask = torch.nn.functional.pad(attention_mask, (0, 400000 - attention_mask.size(-1)), 'constant', 0.0)
        
        text = self.texts[index]
        
        text_values = self.tokenizer.encode_plus(
            text,
            add_special_tokens=True,
            max_length=512,
            padding='longest', # pad_to_max_lengh 사라짐
            return_attention_mask=True,
            truncation=True
            )
        
        text_input_ids = torch.tensor(text_values["input_ids"], dtype=torch.long)[:512]
        text_input_ids = torch.nn.functional.pad(text_input_ids, (0, 512 - len(text_input_ids)))
        
        text_attention_mask = torch.tensor(text_values['attention_mask'], dtype=torch.long)[:512]
        text_attention_mask = torch.nn.functional.pad(text_attention_mask, (0, 512 - len(text_attention_mask)))
    
       
        return input_values[0], attention_mask, text_input_ids, text_attention_mask
        