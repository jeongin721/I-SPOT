"""

위기단계분류 학습/검증 을 위한 코드 입니다.
Jupyter notebook을 사용하여 시각화 자료를 볼 수 있습니다. (cirisis_stage.ipynb)


"""


import pandas as pd
import random
import os
import numpy as np
import warnings
import matplotlib.pylab as plt
import koreanize_matplotlib
import seaborn as sns

from tqdm.notebook import tqdm
from sklearn.model_selection import train_test_split, cross_val_score, cross_validate
from autogluon.tabular import TabularDataset, TabularPredictor
warnings.filterwarnings('ignore')


## Data Load

# ori_df = pd.read_csv("/workspace/autoML/crisis_1127ver2.csv")
ori_df = pd.read_csv("/workspace/03_crisis_classification/datasets/시연용.csv")
print(ori_df.head())


df = ori_df.copy()

## 라벨 컬럼 분포 확인
print(df['crisis_level'].value_counts())

## Data Split
## 총 수량 3300개 중 90% 해당하는 2970개만 사용합니다.
## 나머지 dataset은 Test 용으로 사용합니다.
## randomseed 고정 필수

train_df = pd.read_csv("./datasets/train_valid_dataset.csv")
print(train_df.shape)

print("train df 라벨 분포")
print(train_df['crisis_level'].value_counts())


## 라벨 값 설정
label = 'crisis_level'


# 학습에 불필요한 file 컬럼 제거
df = ori_df.drop(columns=["file"])
print("학습에불필요한 file 컬럼을 제거합니다.")
print(df.head())


## 학습을 시작합니다. 모델이 저장될 경로를 설정하세요 / 예) "/workspace/crirsis_level_classification/weight/weight/"
predictor = TabularPredictor(label=label, eval_metric='f1_weighted', path='/workspace/03_crisis_classification/시연용_weight/').fit(train_data=train_df, auto_stack=True, num_gpus=1, verbosity=4)
print("Model Leaderboard")
print(predictor.leaderboard())

summary = predictor.fit_summary()
print("Model Summary")
print(summary)


print(predictor.feature_importance(data=train_df, feature_stage="original"))