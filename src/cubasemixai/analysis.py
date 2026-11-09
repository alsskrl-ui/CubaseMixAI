"""Offline measurements. No audio or embeddings are uploaded."""
from pathlib import Path
import hashlib
import math
import numpy as np
import soundfile as sf
from scipy import signal
import pyloudnorm as pyln


def fingerprint(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def db(value: float) -> float | None:
    return float(20 * np.log10(value)) if value > 0 else None


def analyze(path: str, start: float = 0, end: float | None = None) -> dict:
    info = sf.info(path)
    if info.format not in {"WAV", "WAVEX", "RF64"}:
        raise ValueError("WAV input required")
    if info.channels not in (1, 2):
        raise ValueError("Only mono and stereo WAV are supported")
    if not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
        raise ValueError("Invalid time range")
    stop = info.frames if end is None else round(end * info.samplerate)
    first = round(start * info.samplerate)
    if stop > info.frames or first >= stop:
        raise ValueError("Time range exceeds the audio")
    # Explicit bound: offline MVP loads a selected segment into memory.
    if stop - first > info.samplerate * 60 * 15:
        raise ValueError("Select a segment of at most 15 minutes")
    x, sr = sf.read(path, start=first, stop=stop, always_2d=True, dtype="float64")
    if len(x) < sr * .4 or not np.isfinite(x).all():
        raise ValueError("Need at least 400 ms of finite audio")
    rms = float(np.sqrt(np.mean(x ** 2)))
    sample_peak = float(np.max(np.abs(x)))
    # 4x oversampling estimate, not a certified BS.1770 true-peak meter.
    peak = max(sample_peak, float(np.max(np.abs(signal.resample_poly(x, 4, 1, axis=0)))))
    loudness = float(pyln.Meter(sr).integrated_loudness(x))
    freq, power = signal.welch(x, sr, nperseg=min(8192, len(x)), axis=0)
    power = np.mean(power, axis=1)
    total = float(np.sum(power))
    bands = {}
    for name, lo, hi in [("sub", 20, 60), ("bass", 60, 250), ("low_mid", 250, 500), ("mid", 500, 2000), ("presence", 2000, 6000), ("air", 6000, 20000)]:
        energy = float(np.sum(power[(freq >= lo) & (freq < hi)]))
        bands[name] = 100 * energy / total if total else 0.0
    block = max(1, round(sr * .4))
    blocks = [float(np.sqrt(np.mean(x[i:i+block] ** 2))) for i in range(0, len(x)-block+1, block)]
    levels = [db(v) for v in blocks if v > 0]
    stereo = {"correlation": None, "side_mid_db": None}
    if x.shape[1] == 2:
        left, right = x.T
        if np.std(left) > 0 and np.std(right) > 0:
            stereo["correlation"] = float(np.corrcoef(left, right)[0, 1])
        mid = np.sqrt(np.mean(((left+right)/2)**2))
        side = np.sqrt(np.mean(((left-right)/2)**2))
        stereo["side_mid_db"] = db(float(side / mid)) if mid else None
    return {"path": str(Path(path).resolve()), "sha256": fingerprint(path), "sample_rate": sr,
            "channels": x.shape[1], "start": start, "end": stop / sr, "duration": len(x)/sr,
            "lufs_i": loudness if math.isfinite(loudness) else None,
            "rms_dbfs": db(rms), "sample_peak_dbfs": db(sample_peak),
            "true_peak_estimate_dbtp": db(peak), "crest_db": db(sample_peak/rms) if rms else None,
            "block_rms_range_db": float(np.percentile(levels, 95)-np.percentile(levels, 10)) if levels else None,
            "bands_percent": bands, "stereo": stereo,
            "limitations": ["True peak is a 4x estimate, not a certified meter", "Block RMS range is not EBU LRA", "Frequency percentages are descriptive, not EQ targets"]}


def compare(mix: str, reference: str, start: float = 0, end: float | None = None,
            reference_start: float = 0, reference_end: float | None = None) -> dict:
    a, b = analyze(mix, start, end), analyze(reference, reference_start, reference_end)
    def delta(key):
        return a[key]-b[key] if a[key] is not None and b[key] is not None else None
    return {"mix": a, "reference": b, "mix_minus_reference": {
        "lufs": delta("lufs_i"), "crest_db": delta("crest_db"),
        "bands_percentage_points": {k: a["bands_percent"][k]-b["bands_percent"][k] for k in a["bands_percent"]}},
        "note": "Compare matching musical sections. Tonal metrics are gain invariant; listening A/B requires loudness matching."}


def analyze_stems(stems: dict[str, str]) -> dict:
    allowed = {"kick", "808", "vocal", "guitar"}
    if not stems or not set(stems) <= allowed:
        raise ValueError("Use kick, 808, vocal, guitar with separately exported WAVs")
    return {name: analyze(path) for name, path in stems.items()}
