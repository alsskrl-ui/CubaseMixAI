"""Build measured mapping files without sending any MIDI."""
import json
from pathlib import Path
from .control import load_mapping, value_to_cc


def build_mapping(port: str, controls: dict, output: str, confirmed_measured: bool = False) -> dict:
    if not confirmed_measured:
        raise ValueError('Confirm that all calibration points were physically measured')
    result = {'port': port, 'controls': {name: {**c, 'verified': True} for name, c in controls.items()}}
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Never destroy an existing mapping or accidentally approve example values in place.
    with out.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
    try:
        load_mapping(str(out))
    except Exception:
        out.unlink()
        raise
    return {'mapping': str(out.resolve()), 'controls': len(controls), 'midi_sent': False}


def calibration_report(mapping_path: str, observations: list[dict]) -> dict:
    """Hold-out measurements: requested physical value vs actual Cubase display value."""
    mapping, digest = load_mapping(mapping_path)
    rows = []
    for row in observations:
        c = mapping['controls'][row['control']]
        requested, observed, tolerance = float(row['requested']), float(row['observed']), float(row['tolerance'])
        import math
        if not all(math.isfinite(v) for v in (requested, observed, tolerance)) or tolerance <= 0:
            raise ValueError('Finite observations and positive tolerance required')
        cc = value_to_cc(c, requested)
        error = abs(observed-requested)
        rows.append({**row, 'cc': cc, 'absolute_error': error, 'passed': error <= tolerance})
    if not rows:
        raise ValueError('Need at least one independent observation')
    return {'mapping_sha256': digest, 'observations': rows, 'passed': all(r['passed'] for r in rows),
            'limitation': 'Observations are entered by the user, not MIDI readback'}
