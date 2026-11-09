import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from cubasemixai.workflow import Workflow
from cubasemixai.ui import create_app


def test_dashboard_actions_auth_and_no_hidden_send(tmp_path):
    w=Workflow(str(tmp_path/'state'));client=TestClient(create_app(w,'secret'),base_url='http://127.0.0.1:8765')
    assert 'CubaseMixAI' in client.get('/').text
    assert client.post('/run/compare',json={}).status_code==403
    headers={'X-Review-Token':'secret'}
    assert client.post('/run/send_cc',headers=headers,json={}).status_code==404
    assert client.post('/apply/missing',headers=headers,json={'dry_run':False}).status_code==400
    assert client.get('/history',headers={**headers,'Host':'attacker.example'}).status_code==403
    p=tmp_path/'a.wav';sf.write(p,np.sin(np.arange(48000)*.1)*.1,48000)
    r=client.post('/run/compare',headers=headers,json={'mix':str(p),'reference':str(p)})
    assert r.status_code==200 and r.json()['mix_minus_reference']['lufs']==0
    assert not w.history()


def test_shared_state_directory(tmp_path,monkeypatch):
    monkeypatch.setenv('CUBASEMIXAI_STATE_DIR',str(tmp_path/'shared'))
    assert Workflow().root==tmp_path/'shared'
