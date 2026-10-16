from pathlib import Path


def test_summary_and_risk_prompts_exist():
    root = Path(__file__).resolve().parents[1]
    summary_prompt = root / "ai" / "prompts" / "consultation_summary.txt"
    risk_prompt = root / "ai" / "prompts" / "risk_utterance.txt"

    assert summary_prompt.exists()
    assert risk_prompt.exists()

    summary_text = summary_prompt.read_text(encoding="utf-8")
    risk_text = risk_prompt.read_text(encoding="utf-8")

    assert "현재 1차 구현" in summary_text
    assert "segment_id" in risk_text
    assert "추가 확인이 필요한 표현" in risk_text
