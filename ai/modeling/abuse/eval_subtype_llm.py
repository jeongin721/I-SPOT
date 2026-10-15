"""
datasets/subtype_review_v1.json(판례집 기반 2차 세부유형 검수셋, 60건,
docs/subtype_rubric_v1.md 참고)으로 지금 프로덕션 2차
(second_stage_llm.analyze_subtypes, 2026-10-02부터 항상 OpenAI)를 실제로
돌려서 결과를 저장한다. 채점은 score_review_set.py가 한다.

이 검수셋 자체가 "정답 라벨"이 아니라 전문가 검수 전 AI 초안이라는 점에
유의 — 판례집 근거는 있지만 사람이 최종 확인한 라벨은 아니다.

사용법:
    python3 -m ai.modeling.abuse.eval_subtype_llm
    python3 -m ai.modeling.abuse.eval_subtype_llm --limit 10
    python3 -m ai.modeling.abuse.score_review_set.py results/subtype_llm_eval.json
"""

import argparse
import json
import re
from pathlib import Path

from ai.modeling.abuse.second_stage_llm import analyze_subtypes
from ai.modeling.abuse.llm_backend import build_openai_client_and_model
from ai.modeling.abuse.privacy_gateway import mask_for_outbound

REVIEW_PATH = (
    Path(__file__).resolve().parent / "datasets" / "subtype_review_v1.json"
)
DEFAULT_OUT = (
    Path(__file__).resolve().parent / "results" / "subtype_llm_eval.json"
)

_TAG_PATTERN = re.compile(r"\[(COUNSELOR|CHILD)\]\s*")
_TAG_TO_SPEAKER = {"COUNSELOR": "상담사", "CHILD": "아동"}


def _to_production_format(text: str) -> str:
    return _TAG_PATTERN.sub(
        lambda m: f"{_TAG_TO_SPEAKER[m.group(1)]}: ", text
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    review = json.load(open(REVIEW_PATH, encoding="utf-8"))
    if args.limit:
        review = review[: args.limit]

    client, model = build_openai_client_and_model(
        default_openai_model="gpt-5.6-luna",
    )

    results_log = []
    errors = 0

    for i, item in enumerate(review):
        text = _to_production_format(item["text"])
        major = item["major"]

        try:
            masked_text, _ = mask_for_outbound(text)

            result = analyze_subtypes(
                text=masked_text,
                major_types=[major],
                client=client,
                model=model,
            )

            predicted = []
            for major_result in result.get("results", []):
                if major_result.get("major_type") != major:
                    continue
                for subtype in major_result.get("subtypes", []):
                    predicted.append(subtype["type"])
        except Exception as exc:
            errors += 1
            print(
                f"  case_id={item['case_id']} ({major}) 호출 실패: {exc}",
                flush=True,
            )
            predicted = []

        results_log.append(
            {
                "major_type": major,
                "case_id": item["case_id"],
                "predicted_raw": predicted,
            }
        )

        print(
            f"  [{i + 1}/{len(review)}] case_id={item['case_id']} "
            f"major={major} predicted={predicted}",
            flush=True,
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"results_log": results_log},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n{len(review)}건 완료 (호출 실패 {errors}건) -> {out_path}")


if __name__ == "__main__":
    main()
