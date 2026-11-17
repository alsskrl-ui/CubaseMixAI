"""Measured, iterative rough-mix tools. Never infer controls from track names."""
import json
import math
import uuid
from pathlib import Path

import numpy as np
from scipy.optimize import lsq_linear

from .analysis import analyze, fingerprint
from .workflow import Workflow
from .remote.client import RemoteClient
from .remote.workflow import RemoteWorkflow

CATEGORIES = {'pan', 'eq', 'compressor', 'reverb', 'delay'}


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('A finite number is required')
    return float(value)


def _path(w, ident):
    if len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
        raise ValueError('Invalid roughmix report ID')
    return w.root / 'roughmix' / (ident + '.json')


def _load(ident):
    w = Workflow()
    report = json.loads(_path(w, ident).read_text(encoding='utf-8'))
    w._check_sources({'evidence': {'source_files': report['sources']}})
    return w, report


def _distance(a, b):
    return float(np.mean([abs(a['bands_percent'][k] - b['bands_percent'][k]) for k in a['bands_percent']]))


def _volume_candidates(measurements, mix, reference, target_peak, max_step):
    """Regularized power-spectrum fit; phase/routing effects require a fresh render."""
    if mix['sample_peak_dbfs'] is None or reference['rms_dbfs'] is None:
        raise ValueError('Mix and reference must contain measurable audio')
    bands = list(reference['bands_percent'])
    energies = np.array([0 if m['rms_dbfs'] is None else 10**(m['rms_dbfs']/10) for m in measurements])
    matrix = np.array([[m['bands_percent'][k]/100 for m in measurements] for k in bands]) * energies
    total = matrix.sum()
    if total <= 0:
        return [0.0] * len(measurements)
    matrix /= total
    goal = np.array([reference['bands_percent'][k] for k in bands], dtype=float)
    goal /= max(goal.sum(), 1e-12)
    n = len(measurements)
    # Penalize large per-track moves; an underdetermined stereo reference has no unique solution.
    regularizer = .03 * np.eye(n)
    fit = lsq_linear(np.vstack((matrix, regularizer)), np.concatenate((goal, .03*np.ones(n))),
                     bounds=(10**(-max_step/10), 10**(max_step/10)))
    if not fit.success:
        raise ValueError('Spectral balance solver did not converge')
    tonal = 10*np.log10(fit.x)
    tonal -= np.average(tonal, weights=np.maximum(energies, 1e-20))
    headroom = target_peak - mix['sample_peak_dbfs']
    return [0.0 if energies[i] == 0 else round(float(np.clip(v + headroom, -max_step, max_step)), 4)
            for i, v in enumerate(tonal)]


def _read_binding(host, target, binding):
    offset = 0
    while True:
        page = host.request('inspect', {'target': target, 'object_id': binding['object_id'], 'parameter_offset': offset})
        parameter = next((p for p in page['parameters'] if p['tag'] == binding['parameter_tag']), None)
        if parameter is not None:
            return {'object': page['object'], 'parameter': parameter}
        offset = page['next_offset']
        if offset is None:
            raise ValueError('Mapped parameter not exposed')


def roughmix_analyze(manifest_path: str, target_peak_dbfs: float = -6.0,
                     max_volume_step_db: float = 2.0) -> dict:
    """Measure up to 512 explicitly mapped track WAVs and a stereo reference; save an agent worklist.

    Manifest: reference_wav, mix_wav, tracks [{unique_id, wav, controls: {name:
    {category, object_id, parameter_tag, value_kind, unit, max_delta}}}].
    WAVs must be same-section post-fader exports from the current Cubase state.
    Existing output faders are protected. No Cubase values are changed here.
    """
    target_peak_dbfs = _number(target_peak_dbfs)
    max_volume_step_db = _number(max_volume_step_db)
    if not -24 <= target_peak_dbfs <= -1 or not 0 < max_volume_step_db <= 3:
        raise ValueError('Peak target must be -24..-1 dBFS; volume step must be 0..3 dB')
    manifest = Path(manifest_path).resolve(strict=True)
    if manifest.stat().st_size > 4*1024*1024:
        raise ValueError('Manifest exceeds 4 MB')
    manifest_hash = fingerprint(str(manifest))
    cfg = json.loads(manifest.read_text(encoding='utf-8'))
    entries = cfg['tracks']
    if not isinstance(entries, list) or not 1 <= len(entries) <= 512:
        raise ValueError('Supply 1..512 track entries')
    ids = [e['unique_id'] for e in entries]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate track IDs')
    def wav(path):
        return str((manifest.parent / path).resolve(strict=True))
    mix, reference = analyze(wav(cfg['mix_wav'])), analyze(wav(cfg['reference_wav']))
    sources = [{'path': str(manifest), 'sha256': manifest_hash},
               *[{k: m[k] for k in ('path', 'sha256')} for m in (mix, reference)]]
    with RemoteClient() as host:
        tracks = host.request('tracks', {})['tracks']
        if len({t['unique_id'] for t in tracks}) != len(tracks):
            raise ValueError('Ambiguous Cubase identities')
        by_id = {t['unique_id']: t for t in tracks}
        guards = []
        for t in tracks:
            if t['unique_name'].startswith('OutputChannel'):
                parameter = host.request('channel_fader', {'target': t})['parameter']
                _number(parameter['normalized'])
                guards.append({'target': t, 'parameter': parameter})
        if not guards:
            raise ValueError('Cannot protect master: no output channel found')
        work = []
        for entry in entries:
            t = by_id.get(entry['unique_id'])
            if not t or t['unique_name'].startswith('OutputChannel'):
                raise ValueError('Unknown or output channel in roughmix tracks')
            controls = entry.get('controls', {})
            for name, binding in controls.items():
                if name == 'volume' or binding['category'] not in CATEGORIES:
                    raise ValueError('Invalid control category or reserved volume name')
                kind = binding['value_kind']
                limit = _number(binding['max_delta'])
                if kind not in ('plain', 'normalized') or not 0 < limit <= (.25 if kind == 'normalized' else 3):
                    raise ValueError('Binding exceeds DirectAccess per-step limits')
                binding['observed'] = _read_binding(host, t, binding)
            fader = host.request('channel_fader', {'target': t})['parameter']
            if fader['unit'] != 'dB':
                raise ValueError('Volume requires a dB fader')
            _number(fader['plain'])
            work.append({'target': t, 'fader': fader, 'controls': controls, 'wav': wav(entry['wav'])})
    # Analyze one WAV at a time: memory does not grow with track count.
    for item in work:
        m = analyze(item['wav'])
        if m['sample_rate'] != mix['sample_rate'] or abs(m['duration'] - mix['duration']) > 1/mix['sample_rate']:
            raise ValueError('Track exports must match mix sample rate and full locator duration')
        item['measurement'] = m
        sources.append({k: m[k] for k in ('path', 'sha256')})
    deltas = _volume_candidates([i['measurement'] for i in work], mix, reference,
                               target_peak_dbfs, max_volume_step_db)
    for item, delta in zip(work, deltas):
        item['volume_delta_db'] = delta
        item['review'] = {'eq': 'Use measured band differences; map actual EQ parameters before proposing.',
                          'compressor': 'Compare crest and block RMS range; reference mastering can affect both.',
                          'pan': 'Use arrangement and stereo measurement; stereo reference does not reveal individual pan.',
                          'reverb_delay': 'Agent/listening decision required; do not derive wet/time from spectral percentages.'}
    sources = list({s['path']: s for s in sources}.values())
    w = Workflow()
    report = {'id': uuid.uuid4().hex, 'target_peak_dbfs': target_peak_dbfs, 'max_volume_step_db': max_volume_step_db,
              'mix': mix, 'reference': reference, 'tracks': work, 'sources': sources, 'master_guards': guards,
              'status': 'measured_candidates_require_render',
              'limitations': ['Independent track power is only a heuristic, not a phase-aware summed output prediction.',
                             'Only use same-locator post-fader stems from the measured current session.',
                             'Do not include both a group bus and its child stems; map leaf tracks explicitly.',
                             'Master peak is confirmed only by a new Cubase render; master faders are never proposed.',
                             'Plugin and send bindings must be explicitly inspected; agent selects their changes.']}
    w._check_sources({'evidence': {'source_files': sources}})
    path = _path(w, report['id']); path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    return {'report_id': report['id'], 'path': str(path), 'track_count': len(work),
            'target_peak_dbfs': target_peak_dbfs, 'mix_peak_dbfs': mix['sample_peak_dbfs'],
            'tonal_distance': _distance(mix, reference), 'limitations': report['limitations'],
            'next': 'roughmix_review pages, then roughmix_propose pages; approve/apply, render, roughmix_evaluate.'}


def roughmix_review(report_id: str, offset: int = 0, limit: int = 32) -> dict:
    """Page through measured tracks, volume candidates and explicit effect bindings."""
    _, r = _load(report_id)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 32:
        raise ValueError('Use nonnegative offset and limit 1..32')
    end = min(offset + limit, len(r['tracks']))
    return {'report_id': report_id, 'tracks': r['tracks'][offset:end],
            'next_offset': end if end < len(r['tracks']) else None,
            'mix': r['mix'], 'reference': r['reference']}


def roughmix_propose(report_id: str, offset: int = 0, changes: list[dict] | None = None) -> dict:
    """Create one approved-workflow batch, never directly apply.

    Without changes, propose the next 32 measured volume candidates. Explicit changes:
    [{unique_id, control, delta, reason}], up to 32, support mapped pan/EQ/compressor/reverb/delay.
    Use actual units from bindings; normalized deltas are not dB/ms/percent.
    """
    w, r = _load(report_id)
    if type(offset) is not int or offset < 0:
        raise ValueError('Invalid offset')
    automatic = changes is None
    if automatic:
        changes = [{'unique_id': i['target']['unique_id'], 'control': 'volume', 'delta': i['volume_delta_db'],
                    'reason': 'Measured reference spectral fit and rendered mix peak; tentative rough balance.'}
                   for i in r['tracks'][offset:offset+32] if abs(i['volume_delta_db']) >= .01]
    if not changes:
        return {'proposal': None, 'next_offset': offset+32 if offset+32 < len(r['tracks']) else None}
    if len(changes) > 32:
        raise ValueError('Create at most 32 parameter changes per page')
    tracks = {t['target']['unique_id']: t for t in r['tracks']}
    plans = []
    with RemoteClient() as host:
        RemoteWorkflow.check_master_guards(host, r['master_guards'])
        for change in changes:
            item = tracks[change['unique_id']]
            target = item['target']
            if not isinstance(change['reason'], str) or not change['reason'].strip():
                raise ValueError('Each change needs a reason based on the measurements/listening')
            delta = _number(change['delta'])
            control = change['control']
            if control == 'volume':
                binding = {'object_id': target['object_id'], 'parameter_tag': item['fader']['tag'],
                           'value_kind': 'channel_db', 'unit': 'dB', 'max_delta': r['max_volume_step_db']}
                current = host.request('channel_fader', {'target': target})['parameter']
                if abs(current['normalized'] - item['fader']['normalized']) > 1e-5:
                    raise ValueError('Fader changed since measurement; render/analyze again')
            else:
                binding = item['controls'][control]
                observed = _read_binding(host, target, binding)
                expected = binding['observed']
                current = observed['parameter']
                if (observed['object'] != expected['object']
                    or current.get('title') != expected['parameter'].get('title')
                    or current.get('unit') != expected['parameter'].get('unit')
                    or abs(_number(current['normalized']) - expected['parameter']['normalized']) > 1e-5):
                    raise ValueError('Mapped effect changed since analysis; refresh the session')
            if not 0 < abs(delta) <= binding['max_delta']:
                raise ValueError('Change exceeds the configured per-step limit')
            field = 'normalized' if binding['value_kind'] == 'normalized' else 'plain'
            before = _number(current[field])
            args = {k: binding[k] for k in ('object_id', 'parameter_tag', 'value_kind', 'unit', 'max_delta')}
            args.update(target=target, after=before+delta)
            plan = host.request('preview', args)['plan']
            if abs(plan['before'][field]-before) > 1e-5:
                raise ValueError('Parameter changed during preparation')
            plans.append(plan)
    evidence = {'source_files': r['sources'], 'master_guards': r['master_guards'],
                'roughmix_report': report_id, 'decisions': changes}
    proposal = RemoteWorkflow(w).propose_batch(plans, 'Reference-guided roughmix; master fixed', evidence)
    return {'proposal': proposal, 'next_offset': offset+32 if automatic and offset+32 < len(r['tracks']) else None,
            'next': 'Approve/apply once; stop on uncertain batches. Re-render before the next mix pass.'}


def roughmix_evaluate(report_id: str, rendered_wav: str, tolerance_db: float = .5) -> dict:
    """Measure the new Cubase export; never claim a simulated peak is an actual output measurement."""
    _, r = _load(report_id)
    if not 0 < _number(tolerance_db) <= 2:
        raise ValueError('Tolerance must be 0..2 dB')
    if Path(rendered_wav).resolve() in {Path(s['path']) for s in r['sources']}:
        raise ValueError('Export to a new WAV path')
    after = analyze(rendered_wav)
    before = r['mix']
    if after['sample_rate'] != before['sample_rate'] or after['channels'] != before['channels'] or abs(after['duration']-before['duration']) > 1/before['sample_rate']:
        raise ValueError('New render must match original format and locator duration')
    with RemoteClient() as host:
        RemoteWorkflow.check_master_guards(host, r['master_guards'])
    error = None if after['sample_peak_dbfs'] is None else after['sample_peak_dbfs']-r['target_peak_dbfs']
    return {'after': after, 'peak_error_db': error, 'peak_within_tolerance': error is not None and abs(error) <= tolerance_db,
            'tonal_distance_before': _distance(before, r['reference']),
            'tonal_distance_after': _distance(after, r['reference']), 'master_unchanged': True,
            'audio_quality_verified': False,
            'next': 'Listen level-matched; keep or restore proposals. Refresh post-fader stems and analyze for another pass.'}
