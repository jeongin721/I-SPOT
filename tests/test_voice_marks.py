"""stt/voice_marks.py 시험 (합성 신호만 사용한다. 실제 음성 · 대본은 쓰지 않는다).

실행(저장소 루트에서): python -B -m pytest tests/test_voice_marks.py -p no:cacheprovider -q
librosa, soundfile, numba 가 없으면 건너뛴다. 첫 실행은 numba 컴파일 때문에 몇 초 더 걸린다.
"""
import atexit
import json
import shutil
import tempfile

import pytest

pytest.importorskip("scipy")
numba = pytest.importorskip("numba")
# numba 캐시를 임시 폴더에 둔다(가상환경 폴더에 쓰지 않도록). librosa 를 불러오기 전에 정해야 한다.
_NUMBA_CACHE = tempfile.mkdtemp(prefix="numba_cache_voice_marks_")
numba.config.CACHE_DIR = _NUMBA_CACHE
atexit.register(shutil.rmtree, _NUMBA_CACHE, True)
pytest.importorskip("librosa")
sf = pytest.importorskip("soundfile")

import numpy as np  # noqa: E402

from stt import voice_marks as vm  # noqa: E402

ALLOWED_REASONS = {
    "TOO_SHORT", "NO_VOICED_FRAMES", "NOT_CHILD_SEGMENT", "TOO_FEW_CHILD_SEGMENTS", "NO_REFERENCE",
    "INVALID_TIME_RANGE", "DECODE_FAILED", "AUDIO_TOO_LONG", "ANALYSIS_ERROR",
}
TOP_KEYS = {"schema_version", "analyzer", "analyzer_version", "status", "reason", "reference", "thresholds", "segments"}
SEG_KEYS = {"segment_id", "speaker", "start_ms", "end_ms", "status", "reason", "tremor", "mumble", "soft", "flag_any"}


def voiced(f0, dur, sr, vib_cents=0.0, vib_hz=6.0, gain=0.1, harmonics=8):
    """목소리 비슷한 합성 신호: 배음이 있는 음에 떨림(vib_cents)을 줄 수 있다."""
    t = np.arange(int(dur * sr)) / sr
    inst = f0 * 2 ** (vib_cents * np.sin(2 * np.pi * vib_hz * t) / 1200)
    phase = 2 * np.pi * np.cumsum(inst) / sr
    x = sum(np.sin(k * phase) / k for k in range(1, harmonics + 1))
    return gain * x / np.max(np.abs(x))


def build_recording(sr=44100):
    """아동 구간 14개(떨림 큰 것 1개, 작은 소리 1개 포함) + 상담사 구간 2개를 이어 붙인 음성."""
    parts, segs, pos = [], [], 0

    def add(x, speaker, seg_id):
        nonlocal pos
        gap = np.zeros(int(0.3 * sr))
        segs.append({"segment_id": seg_id, "speaker": speaker,
                     "start_ms": int(pos * 1000 / sr), "end_ms": int((pos + x.size) * 1000 / sr)})
        parts.extend([x, gap])
        pos += x.size + gap.size

    add(voiced(180, 1.5, sr, gain=0.1), "COUNSELOR", "seg_001")
    for i in range(14):
        dur = 1.2 + 0.1 * (i % 5)
        vib = 35.0 if i == 5 else (3.0 if i % 3 == 0 else 0.0)
        gain = 0.02 if i == 9 else 0.08 + 0.01 * (i % 4)
        add(voiced(230 + 6 * (i % 7), dur, sr, vib_cents=vib, gain=gain), "CHILD", f"seg_{i + 2:03d}")
    add(voiced(180, 1.5, sr, gain=0.1), "COUNSELOR", "seg_016")
    return np.concatenate(parts), segs


def write_wav(path, audio, sr, channels=1):
    pcm = np.clip(np.round(audio * 32767), -32768, 32767).astype(np.int16)
    if channels == 2:
        pcm = np.stack([pcm, pcm], axis=1)
    sf.write(str(path), pcm, sr, subtype="PCM_16")


@pytest.fixture(scope="module")
def recording(tmp_path_factory):
    d = tmp_path_factory.mktemp("voice_marks")
    audio, segs = build_recording(44100)
    path = d / "rec_44k.wav"
    write_wav(path, audio, 44100)
    return path, segs, audio, d


@pytest.fixture(scope="module")
def result(recording):
    path, segs, _, _ = recording
    return vm.analyze_voice_marks(path, segs)


# --- 계산 도우미 -----------------------------------------------------------
def test_robust_z_matches_formula():
    values = [float(v) for v in range(1, 11)]  # 중앙값 5.5, Q1 3.25, Q3 7.75
    z = vm._robust_z(values)
    assert z[9] == pytest.approx((10 - 5.5) / (7.75 - 3.25))
    assert z[0] == pytest.approx((1 - 5.5) / 4.5)


def test_robust_z_none_cases():
    assert vm._robust_z([1.0, 2.0, 3.0]) == [None, None, None]  # 8개 미만
    assert vm._robust_z([2.0] * 9) == [None] * 9  # Q3 - Q1 == 0
    z = vm._robust_z([float(v) for v in range(1, 10)] + [float("nan")])
    assert z[-1] is None and all(v is not None for v in z[:-1])
    assert vm._robust_z([float("nan")] * 3 + [1.0] * 7) == [None] * 10  # 값이 유한한 구간 7개 < 8


def test_flag_thresholds_are_strict():
    assert vm._flag(vm.TREMOR_Z_ABOVE, "tremor") is False
    assert vm._flag(vm.TREMOR_Z_ABOVE + 1e-9, "tremor") is True
    assert vm._flag(vm.MUMBLE_Z_BELOW, "mumble") is False
    assert vm._flag(vm.MUMBLE_Z_BELOW - 1e-9, "mumble") is True
    assert vm._flag(vm.SOFT_Z_BELOW, "soft") is False
    assert vm._flag(vm.SOFT_Z_BELOW - 1e-9, "soft") is True
    assert vm._flag(None, "tremor") is None


def test_threshold_values_are_pinned():
    # 기준값이 의도 없이 바뀌지 않도록 고정한다. 바꿀 때는 근거 비교를 다시 하고 이 값도 함께 고친다.
    assert vm.TREMOR_Z_ABOVE == 1.6066
    assert vm.MUMBLE_Z_BELOW == -1.6190
    assert vm.SOFT_Z_BELOW == -2.5
    assert vm._flag(-2.0, "soft") is False  # 옛 기준(-1.3719)에서는 표시되던 값
    assert vm._flag(-2.6, "soft") is True


def test_l_active_shifts_with_gain():
    x = voiced(250, 1.0, 16000, gain=0.2)
    assert vm._l_active(0.5 * x, 16000) == pytest.approx(vm._l_active(x, 16000) - 6.0206, abs=1e-4)


def test_vibrato_has_more_tremor_than_steady_tone():
    steady = vm._features(voiced(250, 2.0, 16000))
    vib = vm._features(voiced(250, 2.0, 16000, vib_cents=30.0))
    assert steady[0] < 3.0
    assert 10.0 < vib[0] < 30.0  # 6 Hz, 30 cent 진폭 -> 표준편차 약 21 cent
    assert steady[3] > 10 and vib[3] > 10  # 소리 나는 프레임 수


# --- 전체 흐름 --------------------------------------------------------------
def test_output_shape_and_json(result, recording):
    _, segs, _, _ = recording
    assert set(result) == TOP_KEYS
    assert result["schema_version"] == "1.0" and result["analyzer"] == "stt.voice_marks"
    json.dumps(result, allow_nan=False)  # NaN 이 없어야 한다
    assert [e["segment_id"] for e in result["segments"]] == [s["segment_id"] for s in segs]
    for e, s in zip(result["segments"], segs):
        assert set(e) == SEG_KEYS
        assert (e["speaker"], e["start_ms"], e["end_ms"]) == (s["speaker"], s["start_ms"], s["end_ms"])
        assert e["status"] in ("ANALYZED", "UNDETERMINED")
        assert e["reason"] is None or e["reason"] in ALLOWED_REASONS


def test_analyzed_recording(result):
    assert result["status"] == "ANALYZED" and result["reason"] is None
    assert result["reference"]["child_segments_total"] == 14 and result["reference"]["child_segments_used"] == 14
    assert result["reference"]["min_required"] == 8
    child = [e for e in result["segments"] if e["speaker"] == "CHILD"]
    assert all(e["status"] == "ANALYZED" and e["flag_any"] in (True, False) for e in child)
    for e in child:
        assert e["tremor"]["unit"] == "cent" and e["mumble"]["unit"] == "Hz" and e["soft"]["unit"] == "LUFS"
    counselors = [e for e in result["segments"] if e["speaker"] == "COUNSELOR"]
    assert all(e["status"] == "UNDETERMINED" and e["reason"] == "NOT_CHILD_SEGMENT" for e in counselors)
    assert all(e["tremor"] is None and e["flag_any"] is None for e in counselors)


def test_outlier_segments_are_flagged(result):
    by_id = {e["segment_id"]: e for e in result["segments"]}
    assert by_id["seg_007"]["tremor"]["flag"] is True  # 떨림 35 cent 구간 (아동 6번째)
    assert by_id["seg_007"]["flag_any"] is True
    assert by_id["seg_011"]["soft"]["flag"] is True  # 소리가 작은 구간 (아동 10번째)
    assert by_id["seg_011"]["flag_any"] is True


def test_deterministic(recording, result):
    path, segs, _, _ = recording
    assert vm.analyze_voice_marks(path, segs) == result


def test_stereo_equals_mono(recording, result):
    _, segs, audio, d = recording
    path = d / "rec_44k_stereo.wav"
    write_wav(path, audio, 44100, channels=2)
    assert vm.analyze_voice_marks(path, segs) == result


@pytest.mark.parametrize("sr", [16000, 22050, 48000])
def test_other_sample_rates_are_close(recording, result, sr):
    _, _, _, d = recording
    # 같은 신호를 다른 표본율로 다시 만든다 (표본율이 달라도 값이 거의 같아야 한다)
    audio_sr, segs_sr = build_recording(sr)
    path = d / f"rec_{sr}.wav"
    write_wav(path, audio_sr, sr)
    r16 = vm.analyze_voice_marks(path, segs_sr)
    assert r16["status"] == "ANALYZED"
    for a, b in zip(result["segments"], r16["segments"]):
        if a["status"] != "ANALYZED":
            continue
        assert abs(a["soft"]["value"] - b["soft"]["value"]) < 0.5
        assert abs(a["mumble"]["value"] - b["mumble"]["value"]) < 0.03 * a["mumble"]["value"]


def test_reasons_for_each_segment(recording):
    _, segs, audio, d = recording
    sr = 44100
    silence = np.zeros(int(1.5 * sr))
    audio2 = np.concatenate([audio, silence])
    total_ms = int(audio2.size * 1000 / sr)
    path = d / "rec_reasons.wav"
    write_wav(path, audio2, sr)
    last_end = segs[-1]["end_ms"]
    extra = [
        {"segment_id": "x_short", "speaker": "CHILD", "start_ms": 1000, "end_ms": 1500},
        {"segment_id": "x_bad_order", "speaker": "CHILD", "start_ms": 5000, "end_ms": 4000},
        {"segment_id": "x_outside", "speaker": "CHILD", "start_ms": total_ms + 5000, "end_ms": total_ms + 7000},
        {"segment_id": "x_negative", "speaker": "CHILD", "start_ms": -10, "end_ms": 2000},
        {"segment_id": "x_silence", "speaker": "CHILD", "start_ms": last_end + 100, "end_ms": last_end + 1500},
        {"segment_id": "x_guardian", "speaker": "GUARDIAN", "start_ms": 1000, "end_ms": 3000},
        {"segment_id": "x_end_clamped", "speaker": "CHILD", "start_ms": segs[-2]["start_ms"], "end_ms": total_ms + 90000},
    ]
    r = vm.analyze_voice_marks(path, segs + extra)
    got = {e["segment_id"]: (e["status"], e["reason"]) for e in r["segments"]}
    assert got["x_short"] == ("UNDETERMINED", "TOO_SHORT")
    assert got["x_bad_order"] == ("UNDETERMINED", "INVALID_TIME_RANGE")
    assert got["x_outside"] == ("UNDETERMINED", "INVALID_TIME_RANGE")
    assert got["x_negative"] == ("UNDETERMINED", "INVALID_TIME_RANGE")
    assert got["x_silence"] == ("UNDETERMINED", "NO_VOICED_FRAMES")
    assert got["x_guardian"] == ("UNDETERMINED", "NOT_CHILD_SEGMENT")
    assert got["x_end_clamped"][0] == "ANALYZED"  # 끝 시각이 음성 길이를 넘으면 길이에 맞춰 자른다
    # 입력에 적은 시각은 그대로 돌려준다
    assert [e for e in r["segments"] if e["segment_id"] == "x_end_clamped"][0]["end_ms"] == total_ms + 90000
    assert r["status"] == "ANALYZED"


def test_too_few_child_segments(recording):
    path, segs, _, _ = recording
    few = [s for s in segs if s["speaker"] == "COUNSELOR"] + [s for s in segs if s["speaker"] == "CHILD"][:5]
    r = vm.analyze_voice_marks(path, few)
    assert r["status"] == "UNDETERMINED" and r["reason"] == "TOO_FEW_CHILD_SEGMENTS"
    assert r["reference"]["child_segments_total"] == 5 and r["reference"]["child_segments_used"] == 5
    for e in r["segments"]:
        expected = "NOT_CHILD_SEGMENT" if e["speaker"] == "COUNSELOR" else "TOO_FEW_CHILD_SEGMENTS"
        assert (e["status"], e["reason"]) == ("UNDETERMINED", expected)


def test_no_child_segments_or_empty_list(recording):
    path, segs, _, _ = recording
    r = vm.analyze_voice_marks(path, [s for s in segs if s["speaker"] != "CHILD"])
    assert r["status"] == "UNDETERMINED" and r["reason"] == "TOO_FEW_CHILD_SEGMENTS"
    r = vm.analyze_voice_marks(path, [])
    assert r["status"] == "UNDETERMINED" and r["segments"] == []


def test_unreadable_audio_never_raises(tmp_path, recording):
    _, segs, _, _ = recording
    for path in (tmp_path / "missing.wav", tmp_path):
        r = vm.analyze_voice_marks(path, segs)
        assert r["status"] == "UNDETERMINED" and r["reason"] == "DECODE_FAILED"
        assert all(e["status"] == "UNDETERMINED" and e["reason"] == "DECODE_FAILED" for e in r["segments"])
    bad = tmp_path / "not_audio.wav"
    bad.write_text("this is not audio", encoding="utf-8")
    r = vm.analyze_voice_marks(bad, segs)
    assert r["reason"] == "DECODE_FAILED"
    json.dumps(r, allow_nan=False)


def test_audio_too_long(recording, monkeypatch):
    path, segs, _, _ = recording
    monkeypatch.setattr(vm, "MAX_AUDIO_MINUTES", 0.01)
    r = vm.analyze_voice_marks(path, segs)
    assert r["status"] == "UNDETERMINED" and r["reason"] == "AUDIO_TOO_LONG"
    assert all(e["reason"] == "AUDIO_TOO_LONG" for e in r["segments"])


def test_bad_segment_input_never_raises(recording):
    path, _, _, _ = recording
    junk = [None, 5, "x", {}, {"segment_id": "a", "speaker": "CHILD"}, {"segment_id": "b", "speaker": "CHILD", "start_ms": "x", "end_ms": 1}]
    r = vm.analyze_voice_marks(path, junk)
    assert len(r["segments"]) == len(junk)
    json.dumps(r, allow_nan=False)
    assert vm.analyze_voice_marks(path, None)["segments"] == []


def test_mp3_is_readable_if_supported(recording, tmp_path):
    if "MP3" not in sf.available_formats():
        pytest.skip("이 libsndfile 은 MP3 쓰기를 지원하지 않는다")
    _, segs, audio, _ = recording
    path = tmp_path / "rec.mp3"
    sf.write(str(path), audio, 44100, format="MP3")
    r = vm.analyze_voice_marks(path, segs)
    assert r["status"] == "ANALYZED"
    assert r["reference"]["child_segments_used"] >= 8


def test_warm_up():
    assert vm.warm_up() is True
