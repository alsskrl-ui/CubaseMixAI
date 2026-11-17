"""Assemble an analysis workspace and live Cubase state for an agentic mix pass."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .client import RemoteClient


MAX_REPORT_FILES = 16
MAX_REPORT_BYTES = 2 * 1024 * 1024
MAX_TRACKS = 512


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve(root: Path, value: str | None, fallback: str | None = None) -> Path | None:
    raw = value if value is not None else fallback
    if raw is None:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path.resolve(strict=False)


def _report_files(root: Path, config: dict) -> list[dict]:
    configured = config.get("analysis_files")
    if configured is not None and (not isinstance(configured, list) or len(configured) > MAX_REPORT_FILES):
        raise ValueError(f"analysis_files must be a list with at most {MAX_REPORT_FILES} JSON files")
    if configured is None:
        folder = _resolve(root, config.get("analysis_dir"), "analysis")
        paths = sorted(folder.glob("*.json")) if folder and folder.is_dir() else []
    else:
        paths = [_resolve(root, item) for item in configured]
    if len(paths) > MAX_REPORT_FILES:
        raise ValueError(f"Found more than {MAX_REPORT_FILES} analysis JSON files")
    reports = []
    total = 0
    for path in paths:
        if path is None or path.suffix.lower() != ".json" or not path.is_file():
            raise ValueError("Analysis reports must be existing JSON files")
        size = path.stat().st_size
        total += size
        if size > MAX_REPORT_BYTES or total > MAX_REPORT_BYTES * 2:
            raise ValueError("Analysis reports exceed the local read limit")
        digest = _digest(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid analysis JSON: {path.name}") from exc
        if _digest(path) != digest:
            raise ValueError(f"Analysis report changed while reading: {path.name}")
        reports.append({"name": path.name, "path": str(path), "sha256": digest, "report": data})
    return reports


def _stem_pairs(root: Path, config: dict) -> dict[str, tuple[Path, Path]]:
    configured = config.get("stems")
    if configured is None:
        current_dir = _resolve(root, config.get("mix_stems_dir"), "stems/mix")
        reference_dir = _resolve(root, config.get("reference_stems_dir"), "stems/reference")
        current = {p.stem: p.resolve() for p in current_dir.glob("*.wav")} if current_dir and current_dir.is_dir() else {}
        reference = {p.stem: p.resolve() for p in reference_dir.glob("*.wav")} if reference_dir and reference_dir.is_dir() else {}
        return {name: (current[name], reference[name]) for name in sorted(current.keys() & reference.keys())}
    if not isinstance(configured, dict) or len(configured) > 32:
        raise ValueError("stems must map at most 32 role names to mix/reference WAV paths")
    pairs = {}
    for name, pair in configured.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(pair, dict):
            raise ValueError("Each stem entry needs a role name and a mix/reference object")
        if set(pair) != {"mix", "reference"}:
            raise ValueError(f"Stem {name!r} must specify exactly mix and reference paths")
        mix = _resolve(root, pair["mix"])
        reference = _resolve(root, pair["reference"])
        if not mix.is_file() or not reference.is_file() or mix.suffix.lower() != ".wav" or reference.suffix.lower() != ".wav":
            raise ValueError("Stem comparisons require WAV files")
        pairs[name] = (mix, reference)
    return pairs


def remote_agent_context(session_dir: str) -> dict:
    """Read the optional session manifest/assets and current Cubase track/fader state.

    Standard layout: cubasemixai-session.json, reference.wav, mix.wav,
    analysis/*.json, stems/mix/*.wav, stems/reference/*.wav. Stem pairing is
    exact by basename; Cubase track association is never guessed.
    """
    from ..analysis import analyze, compare

    root = Path(session_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("session_dir must be a folder")
    manifest_path = root / "cubasemixai-session.json"
    config = {}
    if manifest_path.exists():
        if manifest_path.stat().st_size > 1024 * 1024:
            raise ValueError("Session manifest exceeds 1 MB")
        try:
            config = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid cubasemixai-session.json") from exc
        if not isinstance(config, dict):
            raise ValueError("Session manifest must contain a JSON object")

    reference = (_resolve(root, config["reference_wav"]) if "reference_wav" in config
                 else ((root / "reference.wav").resolve() if (root / "reference.wav").is_file() else None))
    mix = (_resolve(root, config["mix_wav"]) if "mix_wav" in config
           else ((root / "mix.wav").resolve() if (root / "mix.wav").is_file() else None))
    analysis = compare(str(mix), str(reference)) if mix and reference else None
    if mix and not reference:
        analysis = {"mix": analyze(str(mix)), "reference": None,
                    "note": "No reference_wav was found; this is current-mix analysis only."}
    reports = _report_files(root, config)
    pairs = _stem_pairs(root, config)
    stem_reports = {}
    if pairs:
        for role, (mix_stem, reference_stem) in pairs.items():
            stem_reports[role] = compare(str(mix_stem), str(reference_stem))

    with RemoteClient() as host:
        hello = host.hello
        track_result = host.request("tracks", {})
        all_tracks = track_result.get("tracks", [])
        tracks = all_tracks[:MAX_TRACKS]
        live_tracks = []
        for target in tracks:
            item = {"target": target, "is_output": target.get("unique_name", "").startswith("OutputChannel")}
            try:
                item["fader"] = host.request("channel_fader", {"target": target})["parameter"]
            except (KeyError, OSError, RuntimeError, ValueError) as exc:
                item["fader_error"] = str(exc)
            live_tracks.append(item)

    track_map = config.get("track_map", {})
    if not isinstance(track_map, dict):
        raise ValueError("track_map must map stem role names to Cubase unique_id values")
    valid_ids = {t["target"].get("unique_id") for t in live_tracks}
    unknown = {name: ident for name, ident in track_map.items() if ident not in valid_ids}
    return {
        "session_dir": str(root),
        "manifest": str(manifest_path) if manifest_path.is_file() else None,
        "analysis": analysis,
        "analysis_files": reports,
        "stem_comparisons": stem_reports,
        "cubase": {"driver": hello, "tracks": live_tracks,
                   "track_count": len(all_tracks), "tracks_truncated": len(all_tracks) > MAX_TRACKS},
        "track_map": track_map,
        "unresolved_track_map": unknown,
        "next": "Use these live unique_id targets with remote_batch_volume or create a bounded, reviewable parameter proposal."
    }
