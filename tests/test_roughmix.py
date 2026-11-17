import copy
import json
import numpy as np
import pytest
import soundfile as sf
from cubasemixai import roughmix as r
from cubasemixai.remote.workflow import RemoteWorkflow


class Host:
    def __init__(self, count=2):
        self.tracks = [dict(unique_id=str(i), object_id=i, session='s', unique_name='AudioChannel', title=str(i)) for i in range(count)]
        self.tracks.append(dict(unique_id='master', object_id=9999, session='s', unique_name='OutputChannel', title='Stereo Out'))
        self.master = .8
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def request(self, op, args):
        self.calls.append(op)
        p = dict(tag=1, normalized=self.master if args.get('target', {}).get('unique_id') == 'master' else .7, plain=-6., unit='dB')
        if op == 'tracks': return {'tracks': self.tracks}
        if op == 'channel_fader': return {'parameter': p}
        if op == 'inspect': return {'object': {'object_id': args['object_id'], 'unique_id': str(args['object_id'])}, 'parameters': [p], 'next_offset': None}
        if op == 'preview':
            return {'plan': dict(kind='parameter', target=args['target'], object={'object_id': args['object_id']}, before=p,
                                 after_normalized=.6, request=args)}
        raise AssertionError(op)


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setenv('CUBASEMIXAI_STATE_DIR', str(tmp_path/'state'))
    sr = 8000; t = np.arange(sr)/sr
    for name, freq, amp in [('low', 120, .2), ('high', 2500, .04), ('mix', 120, .3), ('reference', 2500, .2)]:
        sf.write(tmp_path/f'{name}.wav', amp*np.sin(2*np.pi*freq*t), sr)
    cfg = {'mix_wav': 'mix.wav', 'reference_wav': 'reference.wav', 'tracks': [
        {'unique_id': '0', 'wav': 'low.wav', 'controls': {}}, {'unique_id': '1', 'wav': 'high.wav', 'controls': {}}]}
    path = tmp_path/'roughmix.json'; path.write_text(json.dumps(cfg))
    host = Host(); monkeypatch.setattr(r, 'RemoteClient', lambda: host)
    return path, host, cfg


def test_nonuniform_measured_balance_and_no_writes(session):
    path, host, _ = session
    report = r.roughmix_analyze(str(path), target_peak_dbfs=-10.5)
    page = r.roughmix_review(report['report_id'])
    a, b = [t['volume_delta_db'] for t in page['tracks']]
    assert a < b  # excessive bass reduced relative to the high-frequency track
    proposal = r.roughmix_propose(report['report_id'])['proposal']
    assert proposal['status'] == 'pending'
    assert all(p['target']['unique_id'] != 'master' for p in proposal['payload']['plans'])
    assert 'apply' not in host.calls
    host.master = .9
    with pytest.raises(ValueError, match='Master'):
        r.roughmix_propose(report['report_id'])


def test_master_and_duplicate_tracks_rejected(session):
    path, _, cfg = session
    cfg['tracks'][0]['unique_id'] = 'master'; path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='output'):
        r.roughmix_analyze(str(path))
    cfg['tracks'][0]['unique_id'] = '1'; path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='Duplicate'):
        r.roughmix_analyze(str(path))


def test_changed_audio_rejected(session):
    path, _, _ = session
    report = r.roughmix_analyze(str(path))
    sf.write(path.parent/'low.wav', np.zeros(8000), 8000)
    with pytest.raises(ValueError, match='changed'):
        r.roughmix_review(report['report_id'])


def test_all_effect_categories_and_bounds(session):
    path, _, cfg = session
    cfg['tracks'][0]['controls'] = {name: dict(category=name, object_id=20+i, parameter_tag=1,
        value_kind='plain', unit='dB', max_delta=1.) for i, name in enumerate(r.CATEGORIES)}
    path.write_text(json.dumps(cfg))
    report = r.roughmix_analyze(str(path))
    changes = [dict(unique_id='0', control=name, delta=-.5, reason='Measured candidate, listening required') for name in r.CATEGORIES]
    result = r.roughmix_propose(report['report_id'], changes=changes)
    assert len(result['proposal']['payload']['plans']) == 5
    changes[0]['delta'] = 2
    with pytest.raises(ValueError, match='limit'):
        r.roughmix_propose(report['report_id'], changes=changes)


def test_300_track_pagination(session, monkeypatch):
    path, _, cfg = session
    cfg['tracks'] = [dict(unique_id=str(i), wav='low.wav', controls={}) for i in range(300)]
    path.write_text(json.dumps(cfg)); host = Host(300)
    monkeypatch.setattr(r, 'RemoteClient', lambda: host)
    original = r.analyze
    cached = {str(path.parent/f'{name}.wav'): original(str(path.parent/f'{name}.wav')) for name in ('low', 'mix', 'reference')}
    monkeypatch.setattr(r, 'analyze', lambda p: copy.deepcopy(cached[p]))
    report = r.roughmix_analyze(str(path))
    assert report['track_count'] == 300
    assert r.roughmix_review(report['report_id'], 288)['next_offset'] is None
    result = r.roughmix_propose(report['report_id'], offset=288)
    assert len(result['proposal']['payload']['plans']) == 12
    assert result['next_offset'] is None


def test_master_guard_checks_nonfinite(session):
    _, host, _ = session
    guards = [{'target': host.tracks[-1], 'parameter': {'tag': 1, 'normalized': .8}}]
    host.master = float('nan')
    with pytest.raises(ValueError): RemoteWorkflow.check_master_guards(host, guards)


def test_guard_enforced_at_approval_and_application(session, monkeypatch):
    path, host, _ = session
    report = r.roughmix_analyze(str(path))
    proposal = r.roughmix_propose(report['report_id'])['proposal']
    w = r.Workflow()
    remote = RemoteWorkflow(w, client_factory=lambda: host)
    host.master = .9
    with pytest.raises(ValueError, match='Master'):
        remote.decide(proposal['id'], True)
    assert w.get(proposal['id'])['status'] == 'pending'
    with w.connect() as con:
        con.execute("UPDATE proposals SET status='approved' WHERE id=?", (proposal['id'],))
    with pytest.raises(ValueError, match='Master'):
        remote.apply(proposal['id'], False)
    assert 'apply' not in host.calls


def test_evaluation_requires_new_matching_render(session):
    path, host, _ = session
    report = r.roughmix_analyze(str(path))
    with pytest.raises(ValueError, match='new WAV'):
        r.roughmix_evaluate(report['report_id'], str(path.parent/'mix.wav'))
    t = np.arange(8000)/8000
    sf.write(path.parent/'after.wav', 10**(-6/20)*np.sin(2*np.pi*120*t), 8000, subtype='FLOAT')
    result = r.roughmix_evaluate(report['report_id'], str(path.parent/'after.wav'))
    assert result['peak_within_tolerance'] and result['master_unchanged']
    assert not result['audio_quality_verified']
