"""Post-render objective comparison and loudness-matched listening exports."""
import html
import json
import math
from pathlib import Path
import numpy as np
import soundfile as sf
from .analysis import analyze, compare


def _distance(a, b):
    pairs = [(a[k], b[k]) for k in a if min(a[k], b[k]) >= .1]
    if not pairs:
        return None
    return float(np.sqrt(np.mean([(10*math.log10(x/y))**2 for x, y in pairs])))


def evaluate_render(before: str, after: str, reference: str, listening_before: dict | None = None,
                    listening_after: dict | None = None) -> dict:
    initial, final = compare(before, reference), compare(after, reference)
    a, b, ref = initial['mix'], final['mix'], final['reference']
    for key in ('sample_rate', 'channels'):
        if a[key] != b[key]:
            raise ValueError(f'Before/after {key} must match')
    if abs(a['duration']-b['duration']) > 1/a['sample_rate']:
        raise ValueError('Before/after duration must match within one sample; export the same locators')
    if any(x['lufs_i'] is None for x in (a, b, ref)):
        raise ValueError('Cannot judge silent renders')
    metrics = {}
    values = {
        'loudness_reference_error_lu': (abs(a['lufs_i']-ref['lufs_i']), abs(b['lufs_i']-ref['lufs_i'])),
        'tonal_distance_db': (_distance(a['bands_percent'],ref['bands_percent']), _distance(b['bands_percent'],ref['bands_percent'])),
        'crest_reference_error_db': (abs(a['crest_db']-ref['crest_db']), abs(b['crest_db']-ref['crest_db'])),
        'peak_excess_above_minus1_db': (max(0, a['true_peak_estimate_dbtp']+1), max(0, b['true_peak_estimate_dbtp']+1)),
    }
    for name, (old, new) in values.items():
        status = 'unavailable' if old is None or new is None else 'unchanged' if abs(old-new)<.05 else 'closer_to_target' if new < old else 'farther_from_target'
        metrics[name] = {'before': old, 'after': new, 'direction': status}
    listening_result = None
    if (listening_before is None) != (listening_after is None):
        raise ValueError('Supply both listening reports or neither')
    if listening_before is not None:
        from .engine import integrate
        integrate(initial, listening_before); integrate(final, listening_after)
        listening_result = {'before': listening_before, 'after': listening_after,
                            'similarity_delta': listening_after['cosine_similarity']-listening_before['cosine_similarity'],
                            'interpretation': 'Higher semantic similarity does not demonstrate better mix quality'}
    return {'metrics': metrics, 'before': a, 'after': b, 'reference': ref, 'listening': listening_result,
            'verdict': 'requires_human_listening',
            'limitation': 'Matching reference statistics is not proof of improvement; verify alignment and loudness-matched A/B'}


def compare_sections(mix: str, reference: str, sections: list[dict]) -> dict:
    """Named chorus/drop comparisons with independent reference locator ranges."""
    if not sections or len(sections) > 100:
        raise ValueError('Need 1–100 named sections')
    result = {}
    for s in sections:
        name = str(s['name']).strip()
        if not name or name in result:
            raise ValueError('Section names must be unique and nonempty')
        if not all(k in s for k in ('start','end','reference_start','reference_end')):
            raise ValueError('Each section requires explicit mix and reference ranges')
        result[name] = compare(mix, reference, s['start'], s['end'], s['reference_start'], s['reference_end'])
    return result


def export_ab(first: str, second: str, destination: str) -> dict:
    a, b = analyze(first), analyze(second)
    if a['lufs_i'] is None or b['lufs_i'] is None:
        raise ValueError('Cannot loudness-match silent audio')
    if a['sample_rate'] != b['sample_rate'] or a['channels'] != b['channels'] or abs(a['duration']-b['duration']) > 1/a['sample_rate']:
        raise ValueError('A/B export requires matching format and duration')
    target = min(a['lufs_i'], b['lufs_i'])
    gains = [target-x['lufs_i'] for x in (a,b)]
    peak = max(x['true_peak_estimate_dbtp']+g for x,g in zip((a,b),gains))
    attenuation = max(0, peak+1.0)
    gains = [g-attenuation for g in gains]
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=False)
    for name, path, gain in zip(('A.wav','B.wav'), (first,second), gains):
        x, sr = sf.read(path, always_2d=True, dtype='float64')
        sf.write(out/name, x*10**(gain/20), sr, subtype='FLOAT')
    manifest = {'A': a, 'B': b, 'gain_db': dict(zip(('A','B'),gains)),
                'target_lufs': target-attenuation,
                'note': 'Level-matched copies only; no EQ, compression, limiting, or dithering. Not final masters.'}
    (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2),encoding='utf-8')
    return {'directory': str(out.resolve()), **manifest}


def export_report(report: dict, output: str) -> dict:
    """Standalone HTML with escaped data, no remote scripts or resources."""
    body = html.escape(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    page = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>CubaseMixAI report</title><style>body{font:15px system-ui;max-width:1100px;margin:40px auto;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{color:#253f76}</style><h1>CubaseMixAI 분석 보고서</h1><p>측정과 제안을 직접 검토하고 레벨을 맞춰 청취하세요.</p><pre>'+body+'</pre></html>'
    with Path(output).open('x',encoding='utf-8') as f:
        f.write(page)
    return {'report': str(Path(output).resolve())}
