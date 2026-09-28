"""Resumable, ElevenLabs-only Scribe v2 runner for the independent 500 cohort.

This runner deliberately does not use any production fallback provider.  A failed
ElevenLabs request remains an ElevenLabs failure so the expansion evaluation is
not contaminated by another STT provider.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PILOT_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs_500" / "pilot_500.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs_500" / "outputs"
DEFAULT_SUMMARY_CSV = PROJECT_ROOT / "data_prep" / "evaluation" / "elevenlabs_500" / "run_summary.csv"
DEFAULT_TS_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training\01.원천데이터\TS_in.zip"
)

MODEL_ID = "scribe_v2"
LANGUAGE_CODE = "kor"
DIARIZE = True
TAG_AUDIO_EVENTS = False
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5.0

SUMMARY_FIELDS = [
    "sample_id",
    "status",
    "audio_duration_seconds",
    "elapsed_seconds",
    "rtf",
    "word_count",
    "raw_speaker_count",
    "raw_speaker_ids",
    "model_id",
    "language_code",
    "diarize",
    "started_at",
    "finished_at",
    "attempt_count",
    "error_type",
    "error_message",
]


@dataclass(frozen=True)
class RunnerPaths:
    pilot_csv: Path = DEFAULT_PILOT_CSV
    ts_zip: Path = DEFAULT_TS_ZIP
    output_dir: Path = DEFAULT_OUTPUT_DIR
    summary_csv: Path = DEFAULT_SUMMARY_CSV


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def response_to_json_safe(value: Any) -> Any:
    """Preserve SDK response fields while converting them to JSON-safe values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [response_to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [response_to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): response_to_json_safe(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json")
        except TypeError:
            dumped = value.model_dump()
        return response_to_json_safe(dumped)
    if hasattr(value, "dict"):
        return response_to_json_safe(value.dict())
    if hasattr(value, "__dict__"):
        return {
            str(key): response_to_json_safe(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def validate_response_data(data: Any) -> bool:
    """Require the raw response fields needed by later STT/diarization evaluation."""
    return (
        isinstance(data, dict)
        and isinstance(data.get("text"), str)
        and isinstance(data.get("words"), list)
    )


def read_valid_existing_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if validate_response_data(data) else None


def word_and_speaker_stats(data: dict[str, Any]) -> tuple[int, list[str]]:
    speaker_ids: list[str] = []
    word_count = 0
    for item in data["words"]:
        if not isinstance(item, dict) or item.get("type") != "word":
            continue
        word_count += 1
        speaker_id = item.get("speaker_id")
        if speaker_id is not None and str(speaker_id) not in speaker_ids:
            speaker_ids.append(str(speaker_id))
    return word_count, speaker_ids


def sanitize_error(error: Exception, api_key: str | None = None) -> str:
    """Keep diagnostics useful without writing an API key or bearer token to disk."""
    message = str(error)
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    for marker in ("authorization:", "bearer ", "x-api-key:"):
        position = message.lower().find(marker)
        if position >= 0:
            end = message.find("\n", position)
            message = message[:position] + marker + " [REDACTED]" + ("" if end < 0 else message[end:])
    return message[:1000]


def is_quota_error(error: Exception) -> bool:
    message = str(error).lower()
    keywords = (
        "quota_exceeded",
        "quota exceeded",
        "insufficient credits",
        "0 credits remaining",
        "credits remaining",
        "exceeds your quota",
    )
    return any(keyword in message for keyword in keywords)


def is_auth_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(keyword in message for keyword in ("unauthorized", "authentication", "invalid api key", "forbidden", "401", "403"))


def is_transient_error(error: Exception) -> bool:
    if is_quota_error(error) or is_auth_error(error):
        return False
    message = str(error).lower()
    keywords = (
        "timeout",
        "timed out",
        "connection",
        "network",
        "temporar",
        "rate limit",
        "too many requests",
        "429",
        "500",
        "502",
        "503",
        "504",
    )
    return any(keyword in message for keyword in keywords)


def build_audio_index(archive: zipfile.ZipFile) -> dict[str, str]:
    index: dict[str, str] = {}
    for name in archive.namelist():
        if name.lower().endswith(".mp3"):
            index[Path(name).stem] = name
    return index


class ElevenLabsEval500Runner:
    """Runs one independent cohort without any provider fallback path."""

    def __init__(
        self,
        paths: RunnerPaths,
        client: Any,
        *,
        api_key: str | None = None,
        max_retries: int = MAX_RETRIES,
        retry_wait_seconds: float = RETRY_WAIT_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.paths = paths
        self.client = client
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_wait_seconds = retry_wait_seconds
        self.sleep = sleep
        self.clock = clock
        self.rows = self._load_pilot_rows()

    def _load_pilot_rows(self) -> list[dict[str, str]]:
        with self.paths.pilot_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        required = {"sample_id", "duration_seconds"}
        if not rows or not required.issubset(rows[0]):
            raise ValueError(f"Pilot CSV must contain {sorted(required)}: {self.paths.pilot_csv}")
        sample_ids = [str(row["sample_id"]).strip() for row in rows]
        if len(rows) != 500 or len(set(sample_ids)) != 500 or any(not sample_id for sample_id in sample_ids):
            raise ValueError("pilot_500.csv must contain exactly 500 unique non-empty sample_id values")
        for row in rows:
            duration = float(row["duration_seconds"])
            if duration <= 0:
                raise ValueError(f"Invalid duration_seconds for sample_id={row['sample_id']}")
        return rows

    def preflight(self, *, require_api_key: bool) -> dict[str, int]:
        if require_api_key and not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")
        if not self.paths.ts_zip.is_file():
            raise FileNotFoundError(f"TS_in.zip not found: {self.paths.ts_zip}")
        self.paths.output_dir.mkdir(parents=True, exist_ok=True)
        self.paths.summary_csv.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.paths.ts_zip, "r") as archive:
            audio_index = build_audio_index(archive)
        missing_audio = [str(row["sample_id"]).strip() for row in self.rows if str(row["sample_id"]).strip() not in audio_index]
        if missing_audio:
            raise FileNotFoundError(f"MP3 missing for {len(missing_audio)} sample(s), first={missing_audio[0]}")
        return {"rows": len(self.rows), "audio": len(audio_index), "missing_audio": 0}

    def _base_summary_row(self, row: dict[str, str], status: str = "PENDING") -> dict[str, str]:
        return {
            "sample_id": str(row["sample_id"]).strip(),
            "status": status,
            "audio_duration_seconds": f"{float(row['duration_seconds']):.6f}",
            "elapsed_seconds": "",
            "rtf": "",
            "word_count": "",
            "raw_speaker_count": "",
            "raw_speaker_ids": "",
            "model_id": MODEL_ID,
            "language_code": LANGUAGE_CODE,
            "diarize": str(DIARIZE).lower(),
            "started_at": "",
            "finished_at": "",
            "attempt_count": "0",
            "error_type": "",
            "error_message": "",
        }

    def _load_summary_rows(self) -> dict[str, dict[str, str]]:
        if not self.paths.summary_csv.is_file():
            return {}
        try:
            with self.paths.summary_csv.open("r", encoding="utf-8-sig", newline="") as handle:
                return {str(row["sample_id"]).strip(): row for row in csv.DictReader(handle) if row.get("sample_id")}
        except (OSError, csv.Error):
            return {}

    def _save_summary(self, summary: dict[str, dict[str, str]]) -> None:
        self.paths.summary_csv.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False, dir=self.paths.summary_csv.parent) as handle:
            temporary_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in self.rows:
                writer.writerow(summary[str(row["sample_id"]).strip()])
        os.replace(temporary_path, self.paths.summary_csv)

    def _write_response_atomically(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
            temporary_path = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2)
        if read_valid_existing_json(temporary_path) is None:
            temporary_path.unlink(missing_ok=True)
            raise ValueError("Saved response did not pass required raw-response validation")
        os.replace(temporary_path, path)

    def _success_summary(self, row: dict[str, str], data: dict[str, Any], elapsed: float, attempts: int, started_at: str, finished_at: str, status: str) -> dict[str, str]:
        result = self._base_summary_row(row, status)
        word_count, speaker_ids = word_and_speaker_stats(data)
        duration = float(row["duration_seconds"])
        result.update(
            elapsed_seconds=f"{elapsed:.6f}",
            rtf=f"{elapsed / duration:.8f}",
            word_count=str(word_count),
            raw_speaker_count=str(len(speaker_ids)),
            raw_speaker_ids=json.dumps(speaker_ids, ensure_ascii=False),
            started_at=started_at,
            finished_at=finished_at,
            attempt_count=str(attempts),
        )
        return result

    def _skipped_existing_summary(
        self, row: dict[str, str], data: dict[str, Any], previous: dict[str, str] | None
    ) -> dict[str, str]:
        """Mark this invocation as a skip without discarding original API timing."""
        elapsed = 0.0
        attempts = 0
        started_at = ""
        finished_at = ""
        if previous and previous.get("status") in {"SUCCESS", "SKIPPED_EXISTING"}:
            try:
                elapsed = float(previous.get("elapsed_seconds") or 0.0)
            except ValueError:
                elapsed = 0.0
            try:
                attempts = int(previous.get("attempt_count") or 0)
            except ValueError:
                attempts = 0
            started_at = previous.get("started_at", "")
            finished_at = previous.get("finished_at", "")
        return self._success_summary(row, data, elapsed, attempts, started_at, finished_at, "SKIPPED_EXISTING")

    def run(self) -> dict[str, int]:
        self.preflight(require_api_key=False)
        summary = {str(row["sample_id"]).strip(): self._base_summary_row(row) for row in self.rows}
        summary.update({sample_id: row for sample_id, row in self._load_summary_rows().items() if sample_id in summary})
        counts = {"success": 0, "skipped": 0, "failed": 0, "quota_stopped": 0}

        with zipfile.ZipFile(self.paths.ts_zip, "r") as archive:
            audio_index = build_audio_index(archive)
            for row in self.rows:
                sample_id = str(row["sample_id"]).strip()
                output_path = self.paths.output_dir / f"{sample_id}_elevenlabs.json"
                existing = read_valid_existing_json(output_path)
                if existing is not None:
                    summary[sample_id] = self._skipped_existing_summary(row, existing, summary.get(sample_id))
                    counts["skipped"] += 1
                    self._save_summary(summary)
                    continue

                audio_bytes = archive.read(audio_index[sample_id])
                started_at = utc_now()
                total_api_elapsed = 0.0
                final_error: Exception | None = None
                attempts = 0
                quota_stopped = False

                for attempt in range(1, self.max_retries + 1):
                    attempts = attempt
                    try:
                        start = self.clock()
                        response = self.client.speech_to_text.convert(
                            file=audio_bytes,
                            model_id=MODEL_ID,
                            language_code=LANGUAGE_CODE,
                            diarize=DIARIZE,
                            tag_audio_events=TAG_AUDIO_EVENTS,
                        )
                        total_api_elapsed += self.clock() - start
                        data = response_to_json_safe(response)
                        if not validate_response_data(data):
                            raise ValueError("ElevenLabs response is missing text or words")
                        self._write_response_atomically(output_path, data)
                        summary[sample_id] = self._success_summary(
                            row, data, total_api_elapsed, attempts, started_at, utc_now(), "SUCCESS"
                        )
                        counts["success"] += 1
                        final_error = None
                        break
                    except Exception as error:  # API SDK uses several exception classes.
                        final_error = error
                        if is_quota_error(error):
                            quota_stopped = True
                            break
                        if not is_transient_error(error) or attempt == self.max_retries:
                            break
                        self.sleep(self.retry_wait_seconds)

                if final_error is not None:
                    status = "QUOTA_EXHAUSTED" if quota_stopped else ("AUTH_FAILED" if is_auth_error(final_error) else "FAILED")
                    failure = self._base_summary_row(row, status)
                    duration = float(row["duration_seconds"])
                    failure.update(
                        elapsed_seconds=f"{total_api_elapsed:.6f}",
                        rtf=f"{total_api_elapsed / duration:.8f}" if total_api_elapsed else "",
                        started_at=started_at,
                        finished_at=utc_now(),
                        attempt_count=str(attempts),
                        error_type=type(final_error).__name__,
                        error_message=sanitize_error(final_error, self.api_key),
                    )
                    summary[sample_id] = failure
                    counts["failed"] += 1

                self._save_summary(summary)
                if quota_stopped:
                    counts["quota_stopped"] = 1
                    break

        self._save_summary(summary)
        return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the independent ElevenLabs Scribe v2 500-sample evaluation cohort.")
    parser.add_argument("--pilot-csv", type=Path, default=DEFAULT_PILOT_CSV)
    parser.add_argument("--ts-zip", type=Path, default=DEFAULT_TS_ZIP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--preflight", action="store_true", help="Validate inputs and API-key presence without making API calls.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("ELEVENLABS_API_KEY")
    paths = RunnerPaths(args.pilot_csv, args.ts_zip, args.output_dir, args.summary_csv)
    # A placeholder is sufficient for preflight because no provider method is invoked.
    runner = ElevenLabsEval500Runner(paths, client=None, api_key=api_key)
    preflight = runner.preflight(require_api_key=True)
    print(f"preflight: pilot_rows={preflight['rows']}, audio_missing={preflight['missing_audio']}")
    print(f"output_dir: {paths.output_dir}")
    if args.preflight:
        print("preflight complete; no ElevenLabs API calls were made")
        return

    from elevenlabs.client import ElevenLabs

    runner.client = ElevenLabs(api_key=api_key)
    counts = runner.run()
    print("run complete: " + ", ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
