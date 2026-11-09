import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from cubasemixai.workflow import Workflow
from cubasemixai.ui import create_app


@pytest.fixture
def setup(tmp_path):
    mapping = tmp_path/'mapping.json'
    mapping.write_text(json.dumps({'port':'test','controls':{'vocal.volume':{'channel':1,'cc':20,'unit':'dB','verified':True,'max_delta':3,'points':[[-12,20],[0,100],[6,127]]}}}))
    w = Workflow(str(tmp_path/'state'))
    p = w.create(str(mapping), [{'control':'vocal.volume','before':0,'after':-2,'unit':'dB'}], 'test headroom')
    return w, p, mapping


def test_no_send_without_local_approval(setup):
    w, p, _ = setup
    sent = []
    assert w.apply(p['id'])['sent'] is False
    with pytest.raises(ValueError): w.apply(p['id'], dry_run=False, sender=lambda *a: sent.append(a))
    assert not sent
    client = TestClient(create_app(w, 'secret'), base_url='http://127.0.0.1:8765')
    url = '/decision/'+p['id']
    assert client.post(url, json={'approve':True,'confirmed':True}).status_code == 403
    headers = {'X-Review-Token':'secret'}
    assert client.post(url, headers={**headers,'Origin':'https://evil.example'}, json={'approve':True,'confirmed':True}).status_code == 403
    assert client.post(url, headers=headers, json={'approve':True}).status_code == 400
    assert client.post(url, headers=headers, json={'approve':True,'confirmed':True}).status_code == 200
    result = w.apply(p['id'], dry_run=False, sender=lambda *a: sent.append(a))
    assert result['sent'] and len(sent)==1
    assert (w.root/f"{p['id']}.before.json").exists()
    with pytest.raises(ValueError): w.apply(p['id'], dry_run=False, sender=lambda *a: sent.append(a))
    reverse = w.restore_proposal(p['id'])
    assert reverse['status']=='pending'
    assert reverse['payload']['changes'][0]['after']==0


def test_mapping_tampering_and_expiry(setup):
    w,p,mapping = setup
    w.decide(p['id'],True)
    mapping.write_text(mapping.read_text()+'\n')
    with pytest.raises(ValueError, match='Mapping changed'): w.apply(p['id'],dry_run=False)
    with w.connect() as con: con.execute('UPDATE proposals SET created=0 WHERE id=?',(p['id'],))
    with pytest.raises(ValueError): w.decide(p['id'],True)


def test_partial_failure_never_retries(setup):
    w,p,_ = setup
    w.decide(p['id'],True)
    def fail(*args): raise OSError('device disconnected after partial send')
    with pytest.raises(OSError): w.apply(p['id'],dry_run=False,sender=fail)
    assert w.get(p['id'])['status']=='uncertain'
    with pytest.raises(ValueError): w.apply(p['id'],dry_run=False,sender=fail)


def test_only_one_concurrent_send(setup):
    w,p,_ = setup
    w.decide(p['id'],True)
    sent=[]
    def attempt():
        try: return w.apply(p['id'],dry_run=False,sender=lambda *args:sent.append(args))
        except ValueError: return None
    with ThreadPoolExecutor(2) as pool: list(pool.map(lambda _:attempt(),range(2)))
    assert len(sent)==1


def test_calibration_limits(setup):
    w,p,mapping=setup
    for value in [float('nan'),float('inf'),4,50]:
        with pytest.raises(ValueError): w.create(str(mapping),[{'control':'vocal.volume','before':0,'after':value,'unit':'dB'}],'bad')
    data=json.loads(mapping.read_text());data['controls']['vocal.volume']['verified']=False
    mapping.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='not verified'): w.create(str(mapping),p['payload']['changes'],'bad')


def test_expired_live_and_stale_rejection(setup):
    w,p,_=setup
    w.decide(p['id'],True)
    with w.connect() as con: con.execute('UPDATE proposals SET created=0 WHERE id=?',(p['id'],))
    with pytest.raises(ValueError,match='unexpired'): w.apply(p['id'],dry_run=False,sender=lambda *a:None)
    with w.connect() as con: con.execute("UPDATE proposals SET status='pending' WHERE id=?",(p['id'],))
    assert w.decide(p['id'],False)['status']=='rejected'


def test_simulation_never_sends(setup):
    w,p,mapping=setup
    data=json.loads(mapping.read_text());data['simulation']=True;mapping.write_text(json.dumps(data))
    p=w.create(str(mapping),p['payload']['changes'],'simulation')
    w.decide(p['id'],True)
    assert not w.apply(p['id'])['sent']
    with pytest.raises(ValueError,match='Simulation'): w.apply(p['id'],dry_run=False,sender=lambda *a:None)
