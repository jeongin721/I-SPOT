"""음성 참고 표시 (떨림 / 웅얼거림 / 작은 소리) - 아동 발화 구간별 계산.

상담사가 "다시 들어 볼 구간"을 찾도록 돕는 참고 표시이다. 학대 여부나 위험을 판정하지 않는다.
결과 형식과 한계는 같은 폴더의 voice_marks.md 에 있다.

    analyze_voice_marks(audio_path, segments) -> dict

- DB / 네트워크를 쓰지 않는 순수 함수이다. 읽을 수 없는 음성이 와도 예외를 던지지 않고
  모든 구간을 UNDETERMINED 로 돌려준다.
- 계산 정의(떨림 / 웅얼거림 / 작은 소리)와 표시 기준은 합성 음성 실험(작업 27, 55)에서 가져왔다.
  기준값은 합성 음성으로 정한 잠정값이며 실제 아동 음성으로 검증하지 않았다.
- 서버 시작 때 warm_up() 을 한 번 부르면 첫 요청이 느려지는 것(numba 컴파일)을 피할 수 있다.
  numba 캐시를 쓰려면 서버 환경에 NUMBA_CACHE_DIR(쓰기 가능한 폴더)를 지정한다.
"""
from __future__ import annotations

import math
import os
from typing import Any

import numpy as np
from scipy.signal import butter, lfilter, resample_poly, sosfiltfilt

SCHEMA_VERSION = "1.0"
ANALYZER = "stt.voice_marks"
ANALYZER_VERSION = "0.1.0"

CHILD = "CHILD"
SR16 = 16000
MIN_SEGMENT_MS = 1000  # 이보다 짧은 구간은 TOO_SHORT (실험: run_55b.py:115)
MIN_REFERENCE_SEGMENTS = 8  # 비교 기준(한 녹음 안)을 만들 최소 구간 수 (실험: run_55b.py:227)
MAX_AUDIO_MINUTES = 60  # 이보다 긴 음성은 AUDIO_TOO_LONG (백엔드와 협의 전 잠정값)

# 표시 기준 (z 값). 떨림: z > 기준, 웅얼거림 / 작은 소리: z < 기준 (등호 없음).
# 떨림과 웅얼거림은 합성 음성(V0 clean, 효과 없는 구간)의 z 백분위로 정한 잠정값이며
# 소수 넷째 자리까지 옮겼다.
# 작은 소리는 같은 방식의 값(-1.3719)이 STT 아동 구간 기준에서 효과 없는 음성의 11.5%에
# 표시되어(작업 78), -2.5 로 올렸다. 효과 없는 음성 표시율 11.5% -> 4.9%, 합성 효과 줄
# 탐지 9/11 로 변화 없음. 같은 데이터로 고른 값이며 합성 음성 기준 잠정값이다.
TREMOR_Z_ABOVE = 1.6066
MUMBLE_Z_BELOW = -1.6190
SOFT_Z_BELOW = -2.5
THRESHOLD_BASIS = "합성 음성 기준 잠정값. 실제 아동 음성으로 검증되지 않음."
REFERENCE_NOTE = "z 는 이 녹음 안의 아동 구간끼리 비교한 상대값입니다."

# L_active 상수 (합성 음성 실험 코드 data_prep/synthetic/assemble.py 와 같은 값)
L_ACTIVE_FRAME_SEC = 0.010
L_ACTIVE_REL_DB = -40.0

_BP_F0 = butter(2, [4, 8], btype="band", fs=200, output="sos")

_LIBROSA = None
_SOUNDFILE = None


def _librosa():
    global _LIBROSA
    if _LIBROSA is None:
        import librosa

        _LIBROSA = librosa
    return _LIBROSA


def _soundfile():
    global _SOUNDFILE
    if _SOUNDFILE is None:
        import soundfile

        _SOUNDFILE = soundfile
    return _SOUNDFILE


# ---------------------------------------------------------------------------
# 계산 (실험 코드 원문과 같은 정의)
# ---------------------------------------------------------------------------
def _k_weighting(sr: int):
    """BS.1770 K-weighting: high-shelf (+4 dB, 1681.97 Hz) then high-pass (38.14 Hz) biquads.

    실험 코드 data_prep/synthetic/assemble.py 의 _k_weighting 과 같다.
    """
    G, Q, fc = 3.999843853973347, 0.7071752369554196, 1681.974450955533
    A = 10 ** (G / 40); w0 = 2 * np.pi * fc / sr; al = np.sin(w0) / (2 * Q); c = np.cos(w0); sA = np.sqrt(A)
    b = [A * ((A + 1) + (A - 1) * c + 2 * sA * al), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - 2 * sA * al)]
    a = [(A + 1) - (A - 1) * c + 2 * sA * al, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - 2 * sA * al]
    shelf = (np.array(b) / a[0], np.array(a) / a[0])
    Q, fc = 0.5003270373238773, 38.13547087602444
    w0 = 2 * np.pi * fc / sr; al = np.sin(w0) / (2 * Q); c = np.cos(w0)
    b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]; a = [1 + al, -2 * c, 1 - al]
    return shelf, (np.array(b) / a[0], np.array(a) / a[0])


def _l_active(audio: np.ndarray, sr: int) -> float:
    """L_active: K-weighting 한 뒤 10 ms 프레임으로 나누고, 가장 큰 프레임보다 40 dB 이내인 프레임만 남겨
    -0.691 + 10*log10(남은 프레임 평균 에너지) 를 돌려준다 (LUFS 방식 값). 실험 코드 l_active 와 같다.
    """
    shelf, hp = _k_weighting(sr)
    z = lfilter(*hp, lfilter(*shelf, np.asarray(audio, dtype=np.float64)))
    frame = int(L_ACTIVE_FRAME_SEC * sr)
    n = z.size // frame
    if n == 0:
        raise ValueError("clip shorter than one 10 ms frame; L_active undefined")
    energy = np.mean(z[: n * frame].reshape(n, frame) ** 2, axis=1)
    energy_db = 10 * np.log10(energy + 1e-20)
    keep = energy_db > energy_db.max() + L_ACTIVE_REL_DB
    return float(-0.691 + 10 * np.log10(np.mean(energy[keep]) + 1e-20))


def _features(x16: np.ndarray):
    """16 kHz 모노 구간 -> (떨림 cent, 웅얼거림 Hz, 작은 소리 LUFS, 소리 나는 프레임 수).

    실험 코드 detect_27.py 의 features 와 같다. 떨림은 계산할 수 없으면 NaN.
    """
    librosa = _librosa()
    f0, vflag, _ = librosa.pyin(x16, fmin=150, fmax=600, sr=SR16, frame_length=512, hop_length=80)
    v = vflag & np.isfinite(f0)
    trem = float("nan")
    if v.sum() >= 10:
        med = np.median(f0[v]); idx = np.flatnonzero(v); runs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
        band = [sosfiltfilt(_BP_F0, 1200 * np.log2(f0[r] / med)) for r in runs if r.size >= 50]
        if band: trem = float(np.std(np.concatenate(band)))
    cent = librosa.feature.spectral_centroid(y=x16, sr=SR16, n_fft=512, hop_length=80)[0]
    n = min(cent.size, v.size)
    mumb = float(np.mean(cent[:n][v[:n]])) if v[:n].any() else float("nan")
    return trem, mumb, _l_active(x16, SR16), int(v.sum())


def _robust_z(values: list[float]) -> list[float | None]:
    """z = (값 - 중앙값) / (Q3 - Q1). 값이 유한한 구간이 8개 미만이거나 Q3 - Q1 이 0 이하이면 모두 None."""
    x = np.asarray(values, dtype=float)
    if int(np.isfinite(x).sum()) < MIN_REFERENCE_SEGMENTS:
        return [None] * len(values)
    med = float(np.nanmedian(x))
    q1, q3 = np.nanpercentile(x, [25, 75])
    iqr = float(q3 - q1)
    if not iqr > 0:
        return [None] * len(values)
    return [float((v - med) / iqr) if np.isfinite(v) else None for v in x]


def _flag(z: float | None, kind: str) -> bool | None:
    if z is None:
        return None
    if kind == "tremor":
        return bool(z > TREMOR_Z_ABOVE)
    if kind == "mumble":
        return bool(z < MUMBLE_Z_BELOW)
    return bool(z < SOFT_Z_BELOW)


# ---------------------------------------------------------------------------
# 결과 만들기
# ---------------------------------------------------------------------------
def _normalize(segments: Any) -> list[dict]:
    try:
        items = list(segments)
    except Exception:
        return []
    out = []
    for raw in items:
        d = raw if isinstance(raw, dict) else {}
        try:
            start, end = int(d["start_ms"]), int(d["end_ms"])
        except Exception:
            start = end = None
        out.append({"segment_id": d.get("segment_id"), "speaker": d.get("speaker"), "start_ms": start, "end_ms": end})
    return out


def _entry(seg: dict, status: str, reason: str | None, tremor=None, mumble=None, soft=None, flag_any=None) -> dict:
    return {
        "segment_id": seg["segment_id"], "speaker": seg["speaker"],
        "start_ms": seg["start_ms"], "end_ms": seg["end_ms"],
        "status": status, "reason": reason,
        "tremor": tremor, "mumble": mumble, "soft": soft, "flag_any": flag_any,
    }


def _result(status: str, reason: str | None, child_total: int, used: int, entries: list[dict]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "analyzer": ANALYZER,
        "analyzer_version": ANALYZER_VERSION,
        "status": status,
        "reason": reason,
        "reference": {
            "child_segments_total": child_total,
            "child_segments_used": used,
            "min_required": MIN_REFERENCE_SEGMENTS,
            "note": REFERENCE_NOTE,
        },
        "thresholds": {
            "tremor_z_above": TREMOR_Z_ABOVE,
            "mumble_z_below": MUMBLE_Z_BELOW,
            "soft_z_below": SOFT_Z_BELOW,
            "basis": THRESHOLD_BASIS,
        },
        "segments": entries,
    }


def _whole_undetermined(segs: list[dict], reason: str) -> dict:
    child_total = sum(1 for s in segs if s["speaker"] == CHILD)
    return _result("UNDETERMINED", reason, child_total, 0, [_entry(s, "UNDETERMINED", reason) for s in segs])


def _metric(value: float, unit: str, z: float | None, flag: bool | None) -> dict:
    return {"value": float(value) if np.isfinite(value) else None, "unit": unit, "z": z, "flag": flag}


def _measure(fh, sr: int, n_frames: int, duration_ms: float, s: dict) -> dict:
    """구간 하나를 계산한다. 반환: {"seg", "reason"(None 이면 계산 성공), "values"}."""
    if s["speaker"] != CHILD:
        return {"seg": s, "reason": "NOT_CHILD_SEGMENT"}
    a_ms, b_ms = s["start_ms"], s["end_ms"]
    if a_ms is None or b_ms is None or a_ms < 0 or b_ms <= a_ms or a_ms >= duration_ms:
        return {"seg": s, "reason": "INVALID_TIME_RANGE"}
    b_ms = min(b_ms, duration_ms)
    if b_ms - a_ms < MIN_SEGMENT_MS:
        return {"seg": s, "reason": "TOO_SHORT"}
    try:
        a = int(a_ms * sr / 1000)
        b = min(int(b_ms * sr / 1000), n_frames)
        fh.seek(a)
        x = fh.read(b - a, dtype="float64", always_2d=True)
        mono = x[:, 0] if x.shape[1] == 1 else x.mean(axis=1)
        if sr == SR16:
            x16 = mono
        else:
            g = math.gcd(SR16, sr)
            x16 = resample_poly(mono, SR16 // g, sr // g)
        trem, mumb, soft, _nv = _features(np.ascontiguousarray(x16, dtype=np.float64))
    except Exception:
        return {"seg": s, "reason": "ANALYSIS_ERROR"}
    if not np.isfinite(mumb):
        return {"seg": s, "reason": "NO_VOICED_FRAMES"}
    if not np.isfinite(soft):
        return {"seg": s, "reason": "ANALYSIS_ERROR"}
    return {"seg": s, "reason": None, "values": (trem, mumb, soft)}


def _analyze(audio_path, segs: list[dict]) -> dict:
    sf = _soundfile()
    try:
        path = os.fspath(audio_path)
        info = sf.info(path)
        sr, n_frames = int(info.samplerate), int(info.frames)
        if sr <= 0 or n_frames <= 0:
            raise ValueError("empty audio")
        fh = sf.SoundFile(path)
    except Exception:
        return _whole_undetermined(segs, "DECODE_FAILED")
    duration_ms = n_frames * 1000 / sr
    if duration_ms / 60000 > MAX_AUDIO_MINUTES:
        fh.close()
        return _whole_undetermined(segs, "AUDIO_TOO_LONG")

    with fh:
        measured = [_measure(fh, sr, n_frames, duration_ms, s) for s in segs]

    child_total = sum(1 for s in segs if s["speaker"] == CHILD)
    ok = [m for m in measured if m["reason"] is None]
    if len(ok) < MIN_REFERENCE_SEGMENTS:
        entries = [
            _entry(m["seg"], "UNDETERMINED", m["reason"] or "TOO_FEW_CHILD_SEGMENTS") for m in measured
        ]
        return _result("UNDETERMINED", "TOO_FEW_CHILD_SEGMENTS", child_total, len(ok), entries)

    z_trem = _robust_z([m["values"][0] for m in ok])
    z_mumb = _robust_z([m["values"][1] for m in ok])
    z_soft = _robust_z([m["values"][2] for m in ok])
    by_id = {id(m): i for i, m in enumerate(ok)}

    entries = []
    analyzed = 0
    for m in measured:
        s = m["seg"]
        if m["reason"] is not None:
            entries.append(_entry(s, "UNDETERMINED", m["reason"]))
            continue
        i = by_id[id(m)]
        trem, mumb, soft = m["values"]
        f_t, f_m, f_s = _flag(z_trem[i], "tremor"), _flag(z_mumb[i], "mumble"), _flag(z_soft[i], "soft")
        flags = [f for f in (f_t, f_m, f_s) if f is not None]
        if not flags:
            entries.append(_entry(s, "UNDETERMINED", "NO_REFERENCE"))
            continue
        analyzed += 1
        entries.append(_entry(
            s, "ANALYZED", None,
            tremor=_metric(trem, "cent", z_trem[i], f_t),
            mumble=_metric(mumb, "Hz", z_mumb[i], f_m),
            soft=_metric(soft, "LUFS", z_soft[i], f_s),
            flag_any=any(flags),
        ))
    if analyzed == 0:
        return _result("UNDETERMINED", "NO_REFERENCE", child_total, len(ok), entries)
    return _result("ANALYZED", None, child_total, len(ok), entries)


# ---------------------------------------------------------------------------
# 공개 함수
# ---------------------------------------------------------------------------
def analyze_voice_marks(audio_path, segments) -> dict:
    """아동 발화 구간별 떨림 / 웅얼거림 / 작은 소리 참고 표시를 계산한다.

    audio_path: 음성 파일 경로 (soundfile 로 읽히는 wav, flac, ogg, mp3).
    segments: segment_id, speaker, start_ms, end_ms 를 가진 dict 목록 (정수 ms).
    반환값은 JSON 으로 저장할 수 있는 dict 이다 (NaN 없음). 예외를 던지지 않는다.
    """
    segs = _normalize(segments)
    try:
        return _analyze(audio_path, segs)
    except Exception:
        return _whole_undetermined(segs, "ANALYSIS_ERROR")


def warm_up() -> bool:
    """서버 시작 때 한 번 부르는 준비 함수. numba 컴파일을 미리 끝낸다. 성공하면 True."""
    try:
        t = np.arange(int(2.0 * SR16)) / SR16
        x = 0.1 * np.sin(2 * np.pi * 220.0 * t)
        _features(x)
        return True
    except Exception:
        return False
