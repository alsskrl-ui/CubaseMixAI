import json
from pathlib import Path

import numpy as np
import soundfile as sf


class AgentHost:
    def __init__(self):
        self.hello = {"driver": "CubaseMixAI/1", "capabilities": {"direct_access": True}}
        self.targets = [
            {"session": "session-1", "object_id": 10, "unique_id": "kick-id", "unique_name": "AudioChannel", "title": "Kick"},
            {"session": "session-1", "object_id": 20, "unique_id": "out-id", "unique_name": "OutputChannel", "title": "Stereo Out"},
        ]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def request(self, operation, args):
        if operation == "tracks":
            return {"tracks": self.targets}
        if operation == "channel_fader":
            return {"parameter": {"title": "Volume", "tag": 1, "unit": "dB", "plain": -6.0,
                                   "normalized": 0.9, "display": "-6.00 dB"}}
        raise AssertionError(operation)


def _wav(path: Path, amplitude: float):
    rate = 16000
    t = np.arange(rate) / rate
    sf.write(path, amplitude * np.sin(2 * np.pi * 220 * t), rate)


def test_agent_context_discovers_reports_stems_and_live_cubase_state(tmp_path, monkeypatch):
    import cubasemixai.remote.agent as agent

    (tmp_path / "analysis").mkdir()
    (tmp_path / "stems/mix").mkdir(parents=True)
    (tmp_path / "stems/reference").mkdir(parents=True)
    _wav(tmp_path / "reference.wav", .12)
    _wav(tmp_path / "mix.wav", .06)
    _wav(tmp_path / "stems/mix/kick.wav", .05)
    _wav(tmp_path / "stems/reference/kick.wav", .1)
    (tmp_path / "analysis/reference.json").write_text(json.dumps({"lufs_i": -14}), encoding="utf-8")
    (tmp_path / "cubasemixai-session.json").write_text(
        json.dumps({"track_map": {"kick": "kick-id"}}), encoding="utf-8")
    monkeypatch.setattr(agent, "RemoteClient", AgentHost)

    result = agent.remote_agent_context(str(tmp_path))

    assert result["analysis"]["mix"]["path"].endswith("mix.wav")
    assert result["analysis_files"][0]["report"] == {"lufs_i": -14}
    assert result["stem_comparisons"]["kick"]["mix_minus_reference"]["lufs"] is not None
    assert result["cubase"]["tracks"][0]["fader"]["plain"] == -6
    assert result["cubase"]["tracks"][1]["is_output"] is True
    assert result["unresolved_track_map"] == {}


def test_agent_context_does_not_guess_track_name_associations(tmp_path, monkeypatch):
    import cubasemixai.remote.agent as agent

    (tmp_path / "analysis").mkdir()
    _wav(tmp_path / "reference.wav", .12)
    _wav(tmp_path / "mix.wav", .06)
    (tmp_path / "cubasemixai-session.json").write_text(
        json.dumps({"track_map": {"kick": "missing-id"}}), encoding="utf-8")
    monkeypatch.setattr(agent, "RemoteClient", AgentHost)

    result = agent.remote_agent_context(str(tmp_path))
    assert result["unresolved_track_map"] == {"kick": "missing-id"}
    assert result["stem_comparisons"] == {}
