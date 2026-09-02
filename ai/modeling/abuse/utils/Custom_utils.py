"""
I-SPOT 학대 유형 Multi-label 분류 모델 공통 유틸리티

이 파일은 학대 유형 분류 모델의 학습/평가/추론 과정에서
공통으로 사용하는 데이터 전처리 및 평가 기능을 정의한다.

[주요 기능]

1. 학대 유형 Multi-label 변환
   - 신체학대
   - 정서학대
   - 성학대
   - 방임

   기존 Single-label 방식:
       신체학대 -> 1
       정서학대 -> 2

   변경된 Multi-label 방식:
       신체학대          -> [1, 0, 0, 0]
       정서학대          -> [0, 1, 0, 0]
       신체학대 + 정서학대 -> [1, 1, 0, 0]
       해당 없음         -> [0, 0, 0, 0]

2. Multi-label 학습용 Loss 제공
   - BCEWithLogitsLoss 사용
   - 4개의 학대 유형을 서로 독립적으로 학습

3. Multi-label 평가 기능
   - 유형별 Confusion Matrix
   - Precision / Recall / F1-score 계산

4. PyTorch Dataset 구성
   - 상담 텍스트 Tokenization
   - Multi-label 정답을 float tensor로 변환

※ 본 모델의 출력은 학대 여부에 대한 최종 판정이 아니라
   상담 텍스트에서 각 학대 유형과 관련된 신호를 탐지하기 위한 보조 결과이다.
"""

import ast

import pandas as pd
import torch
import torch.nn as nn

from torch.utils.data import Dataset
from sklearn.metrics import classification_report, multilabel_confusion_matrix


# ============================================================
# Multi-label 설정
# 출력 순서:
# [신체학대, 정서학대, 성학대, 방임]
# ============================================================

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

LABEL_TO_INDEX = {
    "신체학대": 0,
    "정서학대": 1,
    "성학대": 2,
    "방임": 3,
}


# ============================================================
# 문자열 label -> Multi-hot vector
#
# 예:
# "(해당 없음)"       -> [0, 0, 0, 0]
# "신체학대"          -> [1, 0, 0, 0]
# "정서학대"          -> [0, 1, 0, 0]
# "신체학대,정서학대" -> [1, 1, 0, 0]
# ============================================================

def encode_multilabel(label):
    encoded = [0.0, 0.0, 0.0, 0.0]

    if label is None:
        return encoded

    # 이미 list 형태로 들어온 경우
    if isinstance(label, (list, tuple)):
        # 이미 [1, 0, 1, 0] 형태라면 그대로 사용
        if len(label) == 4 and all(
            isinstance(x, (int, float, bool)) for x in label
        ):
            return [float(x) for x in label]

        # ["신체학대", "정서학대"] 형태
        for item in label:
            item = str(item).strip()

            if item in LABEL_TO_INDEX:
                encoded[LABEL_TO_INDEX[item]] = 1.0

        return encoded

    # NaN 처리
    try:
        if pd.isna(label):
            return encoded
    except (TypeError, ValueError):
        pass

    label_text = str(label).strip()

    if label_text in {
        "",
        "(해당 없음)",
        "해당 없음",
        "해당없음",
        "없음",
    }:
        return encoded

    # CSV에 "[1, 0, 1, 0]" 형태로 저장된 경우
    if label_text.startswith("[") and label_text.endswith("]"):
        try:
            parsed = ast.literal_eval(label_text)

            if (
                isinstance(parsed, list)
                and len(parsed) == 4
                and all(isinstance(x, (int, float, bool)) for x in parsed)
            ):
                return [float(x) for x in parsed]

        except (ValueError, SyntaxError):
            pass

    # 단일/복합 문자열 모두 처리
    # 예: "신체학대", "신체학대,정서학대", "신체학대/정서학대"
    for label_name, index in LABEL_TO_INDEX.items():
        if label_name in label_text:
            encoded[index] = 1.0

    return encoded


# ============================================================
# Multi-label Loss
#
# 기존:
# CrossEntropyLoss / 단일 클래스
#
# 변경:
# BCEWithLogitsLoss / 각 학대 유형 독립 예측
# ============================================================

class MultiLabelLoss(nn.Module):
    def __init__(self, pos_weight=None):
        super().__init__()

        if pos_weight is not None:
            pos_weight = torch.tensor(
                pos_weight,
                dtype=torch.float32
            )

        self.loss_fn = nn.BCEWithLogitsLoss(
            pos_weight=pos_weight
        )

    def forward(self, inputs, targets):
        return self.loss_fn(
            inputs,
            targets.float()
        )


# 기존 train_abuse.py에서
# FocalLoss()를 import하고 있기 때문에
# 일단 호환성을 위해 이름 유지
class FocalLoss(MultiLabelLoss):
    """
    기존 코드와의 import 호환용.

    현재 Multi-label baseline에서는
    BCEWithLogitsLoss를 사용한다.
    """

    def __init__(
        self,
        alpha=1,
        gamma=2,
        reduce=True,
        pos_weight=None,
    ):
        super().__init__(pos_weight=pos_weight)


# ============================================================
# Multi-label 평가
# ============================================================

def calculate_confusion_matrix(preds, labels):
    """
    preds:
        [[1,0,0,0],
         [1,1,0,0],
         ...]

    labels:
        [[1,0,0,0],
         [0,1,0,0],
         ...]
    """

    cm = multilabel_confusion_matrix(
        labels,
        preds
    )

    cm_dict = {}

    for i, label_name in enumerate(LABEL_NAMES):
        cm_dict[label_name] = pd.DataFrame(
            cm[i],
            index=["실제 Negative", "실제 Positive"],
            columns=["예측 Negative", "예측 Positive"],
        )

    report = classification_report(
        labels,
        preds,
        target_names=LABEL_NAMES,
        zero_division=0,
    )

    return cm_dict, report


# ============================================================
# Dataset
# ============================================================

class KoreanTextDataset(Dataset):
    def __init__(
        self,
        df,
        tokenizer,
        max_len,
        with_labels=True,
    ):
        self.tokenizer = tokenizer
        self.data = df.reset_index(drop=True)
        self.sentences = (
            self.data["audio_text"]
            .fillna("")
            .astype(str)
            .values
        )

        self.max_len = max_len
        self.with_labels = with_labels

        if with_labels:
            self.labels = [
                encode_multilabel(label)
                for label in self.data["label"].values
            ]
        else:
            self.labels = None

    def __len__(self):
        return len(self.sentences)

    def __getitem__(self, index):
        sentence = self.sentences[index]

        inputs = self.tokenizer(
            sentence,
            add_special_tokens=True,
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_attention_mask=True,
            return_tensors=None,
        )

        ids = torch.tensor(
            inputs["input_ids"],
            dtype=torch.long,
        )

        mask = torch.tensor(
            inputs["attention_mask"],
            dtype=torch.long,
        )

        # RoBERTa에는 token_type_ids가 없을 수도 있으므로 안전하게 처리
        token_type_ids = torch.tensor(
            inputs.get(
                "token_type_ids",
                [0] * len(inputs["input_ids"]),
            ),
            dtype=torch.long,
        )

        if self.with_labels:
            label = torch.tensor(
                self.labels[index],
                dtype=torch.float32,
            )

            return {
                "ids": ids,
                "mask": mask,
                "token_type_ids": token_type_ids,
                "labels": label,
            }

        return {
            "ids": ids,
            "mask": mask,
            "token_type_ids": token_type_ids,
        }