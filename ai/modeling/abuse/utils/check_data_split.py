import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

# 예제를 위한 랜덤 데이터 생성
np.random.seed(42)


df = pd.read_csv("/home/home/dyon/KAVA/abuse_classification/datasets/1129final_abuse.csv")

# 각 클래스에서 랜덤으로 23 선택하여 test 컬럼에 'test'로 표시
test_samples = df.groupby('label').apply(lambda x: x.sample(23)).index.get_level_values(1)
df['trainvaltest'] = 'train'
df.loc[test_samples, 'trainvaltest'] = 'test'

ttrain_df =df[df['trainvaltest'] == 'train']
# train_test_split을 사용하여 train/val 데이터셋으로 나누기
train_df, val_df = train_test_split(df[df['trainvaltest'] == 'train'], stratify=ttrain_df['label'],train_size=2640, random_state=69)

# 나머지 데이터프레임에 대해 test 컬럼에 'train', 'val'로 표시
df.loc[train_df.index, 'trainvaltest'] = 'train'
df.loc[val_df.index, 'trainvaltest'] = 'val'




df['file'] = df['file'].apply(lambda x: x.replace('.mp3', '.json'))
df['file'] = df['file'].apply(lambda x: x.split("/")[-1])


print(df)
print(df['trainvaltest'].value_counts())


df.to_csv("/home/home/dyon/KAVA/abuse_classification/datasets/final_split.csv", index =False, encoding='utf-8-sig')