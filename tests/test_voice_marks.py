"""stt/voice_marks.py 시험 (합성 신호만 사용한다. 실제 음성 · 대본은 쓰지 않는다).

실행(저장소 루트에서): python -B -m pytest tests/test_voice_marks.py -p no:cacheprovider -q
librosa, soundfile, numba 가 없으면 건너뛴다. 첫 실행은 numba 컴파일 때문에 몇 초 더 걸린다.
압축 음성(m4a · mp4 · webm) 시험은 PyAV(av)가 없으면 건너뛴다.
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


# --- 압축 음성(m4a · mp4 · webm): soundfile 이 못 열면 PyAV 로 읽는다 --------------------------
# 합성 신호로만 만든다. 기준값 근처 구간 때문에 흔들리지 않도록, 보통 구간은 떨림 · 음색 · 음량을 고르게 퍼뜨리고
# 표시될 구간은 세 가지(떨림 · 웅얼거림 · 작은 소리) 각각 기준에서 멀리 떨어지게 만든다.
MARGIN_OUTLIERS = {"k_04": "tremor", "k_08": "mumble", "k_11": "soft"}

# wav 대비 허용 범위(합성 신호 기준). 웅얼거림(스펙트럴 중심)은 낮은 비트레이트 AAC 에서 고음이 깎여 크게 낮아진다.
# 관측(작업 92, PyAV 19.0.2 · FFmpeg 9.0.2): 떨림 ≤ 0.83 cent, 작은 소리 ≤ 0.51 LUFS, 웅얼거림 ≤ 2.6 %(32 kbps 는 20.2 %).
COMPRESSED_FORMATS = {
    # 이름: (파일 이름, 컨테이너, 코덱, 표본율, 비트레이트, muxer 옵션, 웅얼거림 상대 허용)
    "m4a_aac_128k": ("rec.m4a", "mp4", "aac", 44100, 128000, None, 0.05),
    # MediaRecorder 처럼 조각(fragmented) mp4, 낮은 비트레이트
    "m4a_aac_32k_fragmented": ("rec_frag.m4a", "mp4", "aac", 48000, 32000,
                               {"movflags": "frag_keyframe+empty_moov+default_base_moof"}, 0.30),
    "webm_opus": ("rec.webm", "webm", "libopus", 48000, 64000, None, 0.05),
    "mp4_aac": ("rec.mp4", "mp4", "aac", 44100, 96000, None, 0.05),
}


def build_margin_recording(sr=44100):
    """아동 구간 12개(떨림 · 웅얼거림 · 작은 소리가 뚜렷한 것 각 1개) + 상담사 구간 2개."""
    parts, segs, pos = [], [], 0

    def add(x, speaker, seg_id):
        nonlocal pos
        gap = np.zeros(int(0.4 * sr))
        segs.append({"segment_id": seg_id, "speaker": speaker,
                     "start_ms": int(pos * 1000 / sr), "end_ms": int((pos + x.size) * 1000 / sr)})
        parts.extend([x, gap])
        pos += x.size + gap.size

    add(voiced(170, 2.0, sr, gain=0.1), "COUNSELOR", "c_01")
    for i in range(12):
        vib = (6.0, 9.0, 12.0, 15.0)[i % 4]
        harmonics = (6, 7, 8)[i % 3]
        gain = (0.06, 0.07, 0.08, 0.09, 0.10)[i % 5]
        if i == 3:
            vib = 60.0  # 떨림이 큰 구간
        if i == 7:
            harmonics = 1  # 배음이 없는(음색이 어두운) 구간 -> 웅얼거림
        if i == 10:
            gain = 0.008  # 소리가 작은 구간
        add(voiced(220 + 10 * (i % 6), 2.0, sr, vib_cents=vib, gain=gain, harmonics=harmonics), "CHILD", f"k_{i + 1:02d}")
    add(voiced(170, 2.0, sr, gain=0.1), "COUNSELOR", "c_02")
    return np.concatenate(parts), segs


def encode_with_pyav(av, path, audio, sr, fmt, codec, rate, bit_rate, options=None):
    """합성 신호(모노)를 PyAV 로 압축 파일로 만든다."""
    pcm = np.clip(np.round(audio * 32767), -32768, 32767).astype(np.int16)
    with av.open(str(path), "w", format=fmt, options=options or {}) as out:
        stream = out.add_stream(codec, rate=rate)
        stream.layout = "mono"
        stream.bit_rate = bit_rate
        resampler = av.AudioResampler(format=stream.format.name, layout="mono", rate=rate)

        def mux(frames):
            for frame in frames:
                for packet in stream.encode(frame):
                    out.mux(packet)

        for i in range(0, pcm.size, 4096):
            frame = av.AudioFrame.from_ndarray(pcm[i:i + 4096].reshape(1, -1), format="s16", layout="mono")
            frame.sample_rate = sr
            mux(resampler.resample(frame))
        mux(resampler.resample(None))
        for packet in stream.encode(None):
            out.mux(packet)


@pytest.fixture(scope="module")
def compressed(tmp_path_factory):
    av = pytest.importorskip("av")
    d = tmp_path_factory.mktemp("voice_marks_compressed")
    audio, segs = build_margin_recording(44100)
    wav = d / "rec.wav"
    write_wav(wav, audio, 44100)
    files = {}
    for name, (fname, fmt, codec, rate, bit_rate, options, _tol) in COMPRESSED_FORMATS.items():
        files[name] = d / fname
        encode_with_pyav(av, files[name], audio, 44100, fmt, codec, rate, bit_rate, options)
    return {"wav": wav, "segs": segs, "files": files, "dir": d, "ref": vm.analyze_voice_marks(wav, segs)}


def test_margin_recording_reference(compressed):
    ref = compressed["ref"]
    assert ref["status"] == "ANALYZED" and ref["reference"]["child_segments_used"] == 12
    by_id = {e["segment_id"]: e for e in ref["segments"]}
    for seg_id, metric in MARGIN_OUTLIERS.items():
        assert by_id[seg_id][metric]["flag"] is True and by_id[seg_id]["flag_any"] is True
    flagged = {e["segment_id"] for e in ref["segments"] if e["flag_any"]}
    assert flagged == set(MARGIN_OUTLIERS)


@pytest.mark.parametrize("name", list(COMPRESSED_FORMATS))
def test_compressed_audio_matches_wav(compressed, name):
    path = compressed["files"][name]
    with pytest.raises(Exception):
        sf.info(str(path))  # soundfile 이 열지 못하는 파일이어야 PyAV 경로를 시험한다
    ref, r = compressed["ref"], vm.analyze_voice_marks(path, compressed["segs"])
    mumble_tol = COMPRESSED_FORMATS[name][-1]
    assert r["status"] == "ANALYZED" and r["reason"] is None
    assert r["reference"] == ref["reference"]
    thresholds = {"tremor": vm.TREMOR_Z_ABOVE, "mumble": vm.MUMBLE_Z_BELOW, "soft": vm.SOFT_Z_BELOW}
    for a, b in zip(ref["segments"], r["segments"]):
        assert (a["segment_id"], a["status"], a["reason"]) == (b["segment_id"], b["status"], b["reason"])
        if a["status"] != "ANALYZED":
            continue
        assert abs(a["tremor"]["value"] - b["tremor"]["value"]) <= 2.0  # cent
        assert abs(a["soft"]["value"] - b["soft"]["value"]) <= 1.0  # LUFS
        assert abs(a["mumble"]["value"] - b["mumble"]["value"]) <= mumble_tol * a["mumble"]["value"]
        for metric, threshold in thresholds.items():
            if abs(a[metric]["z"] - threshold) >= 1.0:  # 기준에서 z 1 이상 떨어진 표시는 바뀌면 안 된다
                assert a[metric]["flag"] == b[metric]["flag"], (a["segment_id"], metric)
    by_id = {e["segment_id"]: e for e in r["segments"]}
    for seg_id, metric in MARGIN_OUTLIERS.items():
        assert by_id[seg_id][metric]["flag"] is True
    json.dumps(r, allow_nan=False)


def test_soundfile_path_does_not_touch_pyav(compressed, monkeypatch):
    def fail():
        raise AssertionError("soundfile 로 열리는 파일에서 PyAV 를 부르면 안 된다")

    monkeypatch.setattr(vm, "_pyav", fail)
    assert vm.analyze_voice_marks(compressed["wav"], compressed["segs"]) == compressed["ref"]


def test_pyav_missing_gives_decode_failed(compressed, monkeypatch):
    import sys

    monkeypatch.setattr(vm, "_AV", None)
    monkeypatch.setitem(sys.modules, "av", None)  # import av -> ImportError
    r = vm.analyze_voice_marks(compressed["files"]["m4a_aac_128k"], compressed["segs"])
    assert r["status"] == "UNDETERMINED" and r["reason"] == "DECODE_FAILED"
    assert all(e["reason"] == "DECODE_FAILED" for e in r["segments"])
    json.dumps(r, allow_nan=False)


def test_broken_compressed_files_give_decode_failed(compressed):
    d, segs = compressed["dir"], compressed["segs"]
    head_only = d / "head_only.m4a"  # 앞부분만 남은 mp4 (moov 없음)
    head_only.write_bytes(compressed["files"]["m4a_aac_128k"].read_bytes()[:2048])
    junk = d / "junk.webm"
    junk.write_bytes(bytes(range(256)) * 64)
    no_audio = d / "empty.webm"
    no_audio.write_bytes(b"")
    for path in (head_only, junk, no_audio):
        r = vm.analyze_voice_marks(path, segs)
        assert r["status"] == "UNDETERMINED" and r["reason"] == "DECODE_FAILED", path.name
        json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("name", ["m4a_aac_32k_fragmented", "webm_opus"])
def test_too_long_without_header_duration(compressed, monkeypatch, name):
    # 헤더에 길이가 없는 파일(조각 녹음)을 흉내 낸다: 풀면서 잰 시각으로 길이 제한을 판단해야 한다.
    calls = []

    def no_header(container, stream):
        calls.append(1)
        return None

    monkeypatch.setattr(vm, "_header_duration_s", no_header)
    monkeypatch.setattr(vm, "MAX_AUDIO_MINUTES", 0.1)  # 6초 (시험 음성은 약 33초)
    r = vm.analyze_voice_marks(compressed["files"][name], compressed["segs"])
    assert calls and r["status"] == "UNDETERMINED" and r["reason"] == "AUDIO_TOO_LONG"
    assert all(e["reason"] == "AUDIO_TOO_LONG" for e in r["segments"])
    # 제한이 넉넉하면 같은 파일이 계산된다(헤더 길이 없이도 끝까지 읽는다)
    monkeypatch.setattr(vm, "MAX_AUDIO_MINUTES", 60)
    assert vm.analyze_voice_marks(compressed["files"][name], compressed["segs"])["status"] == "ANALYZED"


def test_compressed_end_clamped_like_wav(compressed):
    # 끝 시각이 음성 길이를 크게 넘는 구간: wav 와 같이 길이에 맞춰 자르고, 큰 버퍼를 잡지 않는다.
    segs = compressed["segs"]
    last_child = [s for s in segs if s["speaker"] == "CHILD"][-1]
    extra = [{"segment_id": "k_huge_end", "speaker": "CHILD", "start_ms": last_child["start_ms"], "end_ms": 10 ** 12},
             {"segment_id": "k_after_end", "speaker": "CHILD", "start_ms": 10 ** 11, "end_ms": 10 ** 11 + 2000}]
    ref = vm.analyze_voice_marks(compressed["wav"], segs + extra)
    r = vm.analyze_voice_marks(compressed["files"]["webm_opus"], segs + extra)
    got = {e["segment_id"]: (e["status"], e["reason"], e["end_ms"]) for e in r["segments"]}
    want = {e["segment_id"]: (e["status"], e["reason"], e["end_ms"]) for e in ref["segments"]}
    assert got["k_huge_end"] == want["k_huge_end"] == ("ANALYZED", None, 10 ** 12)
    assert got["k_after_end"] == want["k_after_end"] == ("UNDETERMINED", "INVALID_TIME_RANGE", 10 ** 11 + 2000)


def test_too_long_with_header_duration(compressed, monkeypatch):
    monkeypatch.setattr(vm, "MAX_AUDIO_MINUTES", 0.1)
    r = vm.analyze_voice_marks(compressed["files"]["m4a_aac_128k"], compressed["segs"])
    assert r["status"] == "UNDETERMINED" and r["reason"] == "AUDIO_TOO_LONG"
