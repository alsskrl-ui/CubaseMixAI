import copy
import pytest
from cubasemixai.remote import insert_chain as c
from cubasemixai.workflow import Workflow


@pytest.fixture
def chain(tmp_path, monkeypatch):
    monkeypatch.setenv('CUBASEMIXAI_STATE_DIR', str(tmp_path))
    target = dict(unique_id='track', object_id=1, session='s')
    slot = dict(object_id=2, unique_id='slot')
    plugin = dict(object_id=3, unique_id='instance', title='Compressor')
    param = dict(tag=10, title='Threshold', plain=-12., normalized=.5, unit='dB')
    class Host:
        current = plugin
        calls = []
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def request(self, op, args):
            self.calls.append(op)
            if op == 'inspect':
                if args['object_id'] == 2:
                    return {'object': slot, 'children': [self.current]}
                return {'object': self.current, 'parameters': [param], 'next_offset': None}
            if op == 'preview':
                return {'plan': {'kind': 'parameter', 'target': target, 'object': self.current,
                                 'before': param, 'request': args, 'after_normalized': .45}}
            raise AssertionError(op)
    host = Host()
    monkeypatch.setattr(c, 'RemoteClient', lambda: host)
    w = Workflow()
    p = w.store({'backend':'midi_remote', 'kind':'plugin',
                 'plan': {'target':target, 'object':slot, 'plugin':{'uid':'plugin-type'}},
                 'receipt': {'observed': {'children':[plugin]}}})
    return w, p['id'], host


def verified(w, ident):
    with w.connect() as con: con.execute("UPDATE proposals SET status='verified' WHERE id=?", (ident,))


def change(**kw):
    return dict(name='Threshold', after=-13., value_kind='plain', unit='dB', max_delta=1., **kw)


def test_pending_insertion_cannot_tune(chain):
    w, ident, host = chain
    with pytest.raises(ValueError, match='verified'): c.remote_insert_parameters(ident)
    with pytest.raises(ValueError, match='verified'): c.remote_configure_insert(ident, [change()], 'measured')
    assert not host.calls


def test_verified_insert_mapping_then_pending_tuning(chain):
    w, ident, host = chain; verified(w, ident)
    assert c.remote_insert_parameters(ident)['parameters'][0]['tag'] == 10
    result = c.remote_configure_insert(ident, [change()], 'Reduce measured crest')
    assert result['status'] == 'pending'
    assert result['payload']['plans'][0]['request']['after'] == -13
    assert result['payload']['evidence']['insert_proposal_id'] == ident
    assert 'apply' not in host.calls


def test_replaced_instance_is_rejected(chain):
    w, ident, host = chain; verified(w, ident)
    host.current = {**host.current, 'unique_id':'replacement'}
    with pytest.raises(ValueError, match='changed'): c.remote_configure_insert(ident, [change()], 'test')


@pytest.mark.parametrize('bad', [dict(name='Missing'), dict(unit='ms'), dict(after=-30), dict(after=float('nan')), dict(max_delta=4)])
def test_bad_settings_never_store(chain, bad):
    w, ident, host = chain; verified(w, ident)
    edit = change(); edit.update(bad)
    with pytest.raises(ValueError): c.remote_configure_insert(ident, [edit], 'test')
    assert len(w.history()) == 1


def test_duplicates_and_explicit_tag(chain):
    w, ident, host = chain; verified(w, ident)
    with pytest.raises(ValueError, match='Duplicate'): c.remote_configure_insert(ident, [change(),change()], 'test')
    edit = change(); del edit['name']; edit['parameter_tag'] = 10
    assert c.remote_configure_insert(ident, [edit], 'test')['status'] == 'pending'
