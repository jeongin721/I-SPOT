from abuse_model.infer_abuse import predict_abuse

text = (
    "사실 있었어요. 저번 달에 클리닉 앞에 앉아있던 아저씨가 "
    "나를 한번 업으라고 하더니 제 엉덩이랑 가슴을 세게 잡았어요."
)

result = predict_abuse(text)

print("=" * 70)
print("Whisper large-v3 → 학대 분류 결과")
print("=" * 70)

for label, info in result.items():
    print(label, ":", info)