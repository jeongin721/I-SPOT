"""

위기단계분류 평가 를 위한 코드 입니다.
모델의 웨이트(가중치)는 weight 폴더에 저장되어 있습니다.
평가용데이터는 "평가용데이터셋.csv"를 사용할 수 있으며, 이 데이터는 make_csv.py 코드를 실행하여 원천데이터(json)으로부터 얻을 수 있습니다.
Jupyter notebook을 사용하여 시각화 자료를 볼 수 있습니다. (cirisis_stage.ipynb 참조)


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
import sklearn.metrics as metrics
from autogluon.tabular import TabularDataset, TabularPredictor
warnings.filterwarnings('ignore')

####################################################################################################

# 모델 웨이트가 있는 경로 설정 - ./crirsis_level_classification/weight/
predictor = TabularPredictor.load(
    path="/app/weight/",
    require_py_version_match=False
)
## make_csv.py 를 실행하여 생성한 평가용 데이터셋 load
df1 = pd.read_csv("/app/test.csv")

## 개별 결과값 csv 저장 경로 설정
save_path = "/app/03_results.csv"

####################################################################################################



# 평가(test)에 불필요한 file 컬럼 제거
df = df1.drop(columns=["file"])
df.head()


prediction = predictor.predict(df)

print("예측 결과:")
print(prediction)

cm = metrics.confusion_matrix(df['crisis_level'], prediction)

print("Test confusion matrics")
print(cm)

# print("F1 socre :")
# print(predictor.evaluate(data=df, detailed_report=False))

df1['prediction'] = prediction
result_df = df1[['file', 'crisis_level', 'prediction']]
#result_df['file'] = result_df['file'].apply(lambda x: x.replace('.mp3', '.json'))

result_df.to_csv(save_path, index=False, encoding='utf-8-sig')
print("Results saved to CSV.")