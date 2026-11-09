"""Conservative, traceable reference proposals. All changes need local approval."""
import math
from .analysis import compare
from .control import load_mapping, validate_change
from .proposals import recommend
from .workflow import Workflow


def integrate(report: dict, listening: dict | None = None) -> dict:
    result = recommend(report)
    result['listening'] = listening
    result['uncertainty'] = ['DSP does not isolate arrangement from mix choices',
                             'Confidence labels are heuristic, not calibrated probabilities']
    if listening is None:
        result['ai_listening'] = 'Not run'
    else:
        expected = {'mix_sha256': report['mix']['sha256'], 'reference_sha256': report['reference']['sha256']}
        if listening.get('inputs') != expected:
            raise ValueError('Listening report must reference the same source WAV hashes')
        result['ai_listening'] = 'CLAP prompt affinity; human validation required'
        for name, values in listening['dimensions'].items():
            result['findings'].append({'parameter': f'listening.{name}',
                                      'reason': f"Prompt margin difference {values['mix_minus_reference']:+.4f}; window spread {values['window_spread']:.4f}",
                                      'confidence': values['confidence'],
                                      'risk': 'Semantic model scores may reflect instruments and arrangement, not mix quality'})
    return result


def propose_reference(mix: str, reference: str, mapping_path: str, current_values: dict[str, float],
                      target: str = 'master', mode: str = 'mix', listening: dict | None = None,
                      state_dir: str | None = None) -> dict:
    """Generate bounded EQ/volume/compressor/limiter candidates for measured controls.

    Name controls <target>.volume, .eq.<band>.gain, .compressor.threshold,
    .compressor.ratio, .limiter.ceiling. Only supplied current values are touched.
    The result is pending; MIDI is never sent here.
    """
    if mode not in {'mix', 'master'} or not target.strip():
        raise ValueError('Use mode mix/master and a target control prefix')
    report = compare(mix, reference)
    if report['mix']['lufs_i'] is None or report['reference']['lufs_i'] is None:
        raise ValueError('Cannot propose changes for silent audio')
    mapping, _ = load_mapping(mapping_path)
    integrated = integrate(report, listening)
    candidates, skipped = [], []
    dimensions = (listening or {}).get('dimensions', {})
    def candidate(suffix, delta, unit, reason, confidence='low'):
        name = target + '.' + suffix
        if name not in mapping['controls'] or name not in current_values:
            skipped.append({'control': name, 'reason': 'Requires calibrated mapping and manually confirmed current value'})
            return
        c = mapping['controls'][name]
        if c['unit'] != unit:
            raise ValueError(f'Unexpected unit for {name}: expected {unit}')
        before = float(current_values[name])
        if not math.isfinite(before):
            raise ValueError('Current values must be finite')
        # Strict range check, including before; no extrapolation.
        from .control import value_to_cc
        value_to_cc(c, before)
        limit = min(c['max_delta'], 1.5 if mode == 'master' else 3.0)
        bounded = max(-limit, min(limit, float(delta)))
        after = max(c['points'][0][0], min(c['points'][-1][0], before+bounded))
        change = {'control': name, 'before': before, 'after': after, 'unit': unit}
        message = validate_change(mapping, change)
        if message['before_cc'] == message['value']:
            skipped.append({'control': name, 'reason': 'No effective change at measured MIDI resolution'})
            return
        candidates.append({**change, 'reason': reason, 'confidence': confidence,
                           'risk': 'Reference matching may harm the intended sound; loudness-match and audition'})
    loudness_delta = report['reference']['lufs_i']-report['mix']['lufs_i']
    peak = report['mix']['true_peak_estimate_dbtp']
    gain = min(loudness_delta, -1.0-peak) if peak is not None else loudness_delta
    candidate('volume', gain, 'dB', 'LUFS reference difference, capped by estimated -1 dBTP headroom', 'medium')
    for band, actual in report['mix']['bands_percent'].items():
        desired = report['reference']['bands_percent'][band]
        if min(actual, desired) < .1:
            skipped.append({'control': f'{target}.eq.{band}.gain', 'reason': 'Band energy too low for a stable ratio'})
            continue
        db_ratio = 10*math.log10(desired/actual)
        if abs(db_ratio) >= 1.0:
            brightness = dimensions.get('brightness', {})
            if band in {'presence', 'air'} and brightness.get('confidence') == 'medium' and abs(brightness['mix_minus_reference']) > .02 and db_ratio*brightness['mix_minus_reference'] > 0:
                skipped.append({'control': f'{target}.eq.{band}.gain', 'reason': 'DSP tonal correction conflicts with CLAP brightness evidence; hold for human listening'})
                continue
            candidate(f'eq.{band}.gain', max(-1, min(1, .25*db_ratio)), 'dB',
                      f'{band} relative energy ratio {db_ratio:+.2f} dB; quarter correction capped at 1 dB')
    crest_delta = report['mix_minus_reference']['crest_db']
    punch = dimensions.get('punch', {})
    compression_conflict = (punch.get('confidence') == 'medium' and punch.get('mix_minus_reference', 0) < -.02)
    if crest_delta is not None and crest_delta > 2 and compression_conflict:
        skipped.append({'control': target+'.compressor', 'reason': 'DSP suggests more compression but CLAP suggests less punch than reference; hold for human listening'})
    elif crest_delta is not None and crest_delta > 2:
        candidate('compressor.threshold', -1.0, 'dB', f'Crest exceeds reference by {crest_delta:.2f} dB; audition gentle compression')
        candidate('compressor.ratio', .2, 'ratio', 'Small ratio increase; attack/release remain manually configured')
    elif crest_delta is not None and crest_delta < -2:
        candidate('compressor.threshold', 1.0, 'dB', f'Crest is {abs(crest_delta):.2f} dB below reference; audition less compression')
    if mode == 'master':
        name = target+'.limiter.ceiling'
        if name in current_values:
            candidate('limiter.ceiling', min(0, -1.0-float(current_values[name])), 'dB', 'Conservative -1 dBTP ceiling candidate; confirm plugin true-peak mode')
    evidence = {'source_files': [{'path': report[k]['path'], 'sha256': report[k]['sha256']} for k in ('mix', 'reference')],
                'analysis': report, 'integrated': integrated, 'candidates': candidates,
                'method': 'bounded DSP heuristics with CLAP conflict guards; conflicting tonal/compression candidates are held for human review'}
    proposal = None
    if candidates:
        proposal = Workflow(state_dir).create(mapping_path, candidates,
                    f'{mode} reference candidates for {target}; numerical confidence is uncalibrated', evidence=evidence)
    return {'proposal': proposal, 'candidates': candidates, 'skipped': skipped, 'evidence': evidence,
            'midi_sent': False, 'requires': 'Review exact values, current Cubase state, project backup and local approval'}
