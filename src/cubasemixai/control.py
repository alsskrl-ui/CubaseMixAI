"""Validated Generic Remote mapping, including measured dB conversion."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np


def load_mapping(path: str) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if not data.get("port") or not isinstance(data.get("controls"), dict):
        raise ValueError("Mapping needs a port and controls")
    addresses = set()
    for key, c in data["controls"].items():
        if type(c.get("channel")) is not int or not 1 <= c["channel"] <= 16 or type(c.get("cc")) is not int or not 0 <= c["cc"] <= 127:
            raise ValueError(f"Invalid MIDI address: {key}")
        address = (c["channel"], c["cc"])
        if address in addresses:
            raise ValueError("Duplicate MIDI address")
        addresses.add(address)
        points = c.get("points", [])
        if len(points) < 2 or c.get("verified") is not True:
            raise ValueError(f"Calibration is not verified: {key}")
        vals, ccs = zip(*points)
        if not all(type(v) in (int, float) and math.isfinite(v) for v in vals):
            raise ValueError("Nonfinite calibration")
        if not all(type(v) is int and 0 <= v <= 127 for v in ccs):
            raise ValueError("Invalid calibrated CC values")
        if any(b <= a for a, b in zip(vals, vals[1:])) or any(b <= a for a, b in zip(ccs, ccs[1:])):
            raise ValueError("Calibration must be strictly increasing")
        if not c.get("unit") or not math.isfinite(c.get("max_delta", float("nan"))) or c["max_delta"] <= 0:
            raise ValueError("Unit and positive max_delta required")
    return data, hashlib.sha256(raw).hexdigest()


def value_to_cc(control: dict, value: float) -> int:
    points = control["points"]
    if not math.isfinite(value) or not points[0][0] <= value <= points[-1][0]:
        raise ValueError("Value outside calibrated range")
    return int(round(np.interp(value, [p[0] for p in points], [p[1] for p in points])))


def validate_change(mapping: dict, change: dict) -> dict:
    c = mapping["controls"][change["control"]]
    before, after = float(change["before"]), float(change["after"])
    if abs(after-before) > c["max_delta"]:
        raise ValueError("Change exceeds configured max_delta")
    if change.get("unit") != c["unit"]:
        raise ValueError("Unit mismatch")
    return {"channel": c["channel"]-1, "control": c["cc"],
            "value": value_to_cc(c, after), "before_cc": value_to_cc(c, before)}


def send_cc(port_name: str, messages: list[dict]) -> None:
    import mido
    if port_name not in mido.get_output_names():
        raise ValueError(f"MIDI output not found: {port_name}")
    with mido.open_output(port_name) as port:
        for m in messages:
            port.send(mido.Message("control_change", channel=m["channel"], control=m["control"], value=m["value"]))
