"""Offline tests for the resumable ElevenLabs-only 500-sample runner."""

import csv
import json
import zipfile
from pathlib import Path

from data_prep.scripts.run_elevenlabs_eval_500 import (
    ElevenLabsEval500Runner,
    RunnerPaths,
    read_valid_existing_json,
)


def _write_pilot_and_zip(root: Path) -> RunnerPaths:
    root.mkdir(parents=True, exist_ok=True)
    pilot = root / "pilot_500.csv"
    archive = root / "TS_in.zip"
    output_dir = root / "outputs"
    summary = root / "run_summary.csv"
    fields = ["sample_id", "duration_seconds"]
    with pilot.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({"sample_id": str(index), "duration_seconds": "10"} for index in range(1, 501))
    with zipfile.ZipFile(archive, "w") as handle:
        for index in range(1, 501):
            handle.writestr(f"audio/{index}.mp3", b"fake mp3")
    return RunnerPaths(pilot, archive, output_dir, summary)


class _SpeechToText:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def convert(self, **kwargs):
        self.calls.append(kwargs)
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class _Client:
    def __init__(self, outcomes):
        self.speech_to_text = _SpeechToText(outcomes)


RAW_RESPONSE = {
    "text": "상담사 안녕 아이 네",
    "words": [
        {"type": "word", "text": "상담사", "start": 0.0, "end": 0.2, "speaker_id": "speaker_0"},
        {"type": "spacing", "text": " ", "start": 0.2, "end": 0.2},
        {"type": "word", "text": "안녕", "start": 0.2, "end": 0.4, "speaker_id": "speaker_0"},
        {"type": "word", "text": "아이", "start": 0.4, "end": 0.6, "speaker_id": "speaker_1"},
    ],
    "language_code": "kor",
    "provider_metadata": {"retained": True},
}


def _runner(paths, client, **kwargs):
    runner = ElevenLabsEval500Runner(paths, client, api_key="test-secret", retry_wait_seconds=0, **kwargs)
    runner.rows = runner.rows[:2]
    return runner


def _summary(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["sample_id"]: row for row in csv.DictReader(handle)}


def test_preflight_and_successful_raw_response_save(tmp_path):
    paths = _write_pilot_and_zip(tmp_path)
    client = _Client([RAW_RESPONSE])
    clock_values = iter((10.0, 12.5))
    runner = ElevenLabsEval500Runner(paths, client, api_key="test-secret", retry_wait_seconds=0, clock=lambda: next(clock_values))

    # The full source list and ZIP are validated before narrowing this unit run.
    assert runner.preflight(require_api_key=True) == {"rows": 500, "audio": 500, "missing_audio": 0}
    runner.rows = runner.rows[:1]
    result = runner.run()

    assert result == {"success": 1, "skipped": 0, "failed": 0, "quota_stopped": 0}
    saved = read_valid_existing_json(paths.output_dir / "1_elevenlabs.json")
    assert saved == RAW_RESPONSE
    summary = _summary(paths.summary_csv)["1"]
    assert summary["status"] == "SUCCESS"
    assert summary["word_count"] == "3"
    assert summary["raw_speaker_count"] == "2"
    assert json.loads(summary["raw_speaker_ids"]) == ["speaker_0", "speaker_1"]
    assert summary["elapsed_seconds"] == "2.500000"
    assert summary["rtf"] == "0.25000000"
    assert client.speech_to_text.calls[0]["model_id"] == "scribe_v2"
    assert client.speech_to_text.calls[0]["language_code"] == "kor"
    assert client.speech_to_text.calls[0]["diarize"] is True
    assert client.speech_to_text.calls[0]["tag_audio_events"] is False


def test_resume_skips_valid_json_and_reprocesses_corrupt_json(tmp_path):
    paths = _write_pilot_and_zip(tmp_path)
    first_client = _Client([RAW_RESPONSE])
    first_runner = _runner(paths, first_client, clock=lambda: 0.0)
    first_runner.rows = first_runner.rows[:1]
    first_runner.run()

    resume_client = _Client([])
    resumed = _runner(paths, resume_client, clock=lambda: 0.0)
    resumed.rows = resumed.rows[:1]
    assert resumed.run()["skipped"] == 1
    assert resume_client.speech_to_text.calls == []

    (paths.output_dir / "1_elevenlabs.json").write_text("{not-json", encoding="utf-8")
    retry_client = _Client([RAW_RESPONSE])
    retried = _runner(paths, retry_client, clock=lambda: 0.0)
    retried.rows = retried.rows[:1]
    assert retried.run()["success"] == 1
    assert len(retry_client.speech_to_text.calls) == 1


def test_quota_stops_batch_and_transient_error_retries_without_fallback(tmp_path):
    paths = _write_pilot_and_zip(tmp_path)
    quota_client = _Client([RuntimeError("quota exceeded")])
    quota_runner = _runner(paths, quota_client, clock=lambda: 0.0)
    quota_result = quota_runner.run()
    assert quota_result == {"success": 0, "skipped": 0, "failed": 1, "quota_stopped": 1}
    assert len(quota_client.speech_to_text.calls) == 1
    assert _summary(paths.summary_csv)["1"]["status"] == "QUOTA_EXHAUSTED"

    retry_paths = _write_pilot_and_zip(tmp_path / "retry")
    retry_client = _Client([RuntimeError("temporary network timeout"), RAW_RESPONSE])
    sleeps = []
    retry_runner = _runner(retry_paths, retry_client, sleep=sleeps.append, clock=lambda: 0.0)
    retry_runner.rows = retry_runner.rows[:1]
    retry_result = retry_runner.run()
    assert retry_result["success"] == 1
    assert len(retry_client.speech_to_text.calls) == 2
    assert sleeps == [0]
    # Only the supplied ElevenLabs-shaped fake client is called; no fallback is present.
    assert not hasattr(retry_runner, "deepgram")
    assert not hasattr(retry_runner, "whisper")
