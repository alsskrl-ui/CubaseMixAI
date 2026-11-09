import copy
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from cubasemixai.remote.protocol import encode, Decoder, PREFIX
from cubasemixai.remote.client import port_lock, RemoteError
from cubasemixai.remote.setup import setup_remote
from cubasemixai.workflow import Workflow


def test_protocol_unicode_chunks_and_conflicts():
    message={'title':'킥 / ボーカル 🎵','parameters':list(range(300))}
    frames=encode(message,42);assert len(frames)>1
    decoder=Decoder();result=None
    for frame in reversed(frames):
        assert max(frame)<128
        result=decoder.feed(frame) or result
    assert result==(42,message)
    assert decoder.feed((1,2,3)) is None
    with pytest.raises(ValueError):decoder.feed((*PREFIX,1))
    decoder=Decoder();decoder.feed(frames[0])
    bad=list(frames[0]);bad[-1]=ord('X')
    with pytest.raises(ValueError,match='Conflicting'):decoder.feed(bad)
    with pytest.raises(ValueError):encode({'x':float('nan')},1)


def test_port_pair_lock():
    config={'input_port':'test feedback','output_port':'test commands'}
    with port_lock(config):
        with pytest.raises(RemoteError,match='busy'):
            with port_lock(config):pass


def test_setup_no_overwrite(tmp_path,monkeypatch):
    monkeypatch.setenv('CUBASEMIXAI_STATE_DIR',str(tmp_path/'state'))
    result=setup_remote(str(tmp_path/'Scripts'))
    assert Path(result['driver']).is_file()
    assert json.loads(Path(result['config']).read_text())['input_port']=='CubaseMixAI From Cubase'
    with pytest.raises(ValueError,match='exists'):setup_remote(str(tmp_path/'Scripts'))


class Host:
    def __init__(self):
        self.current=.8;self.writes=0;self.session='epoch-1';self.fail_after_write=False;self.calls=[]
        self.target={'session':self.session,'object_id':10,'unique_id':'kick','unique_name':'Audio','title':'Kick'}
        self.object={k:v for k,v in self.target.items() if k!='session'}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def request(self,op,args):
        self.calls.append(op)
        if op=='preview':
            if args['target']['session']!=self.session:raise RemoteError('STALE_SESSION')
            return {'plan':{'kind':'parameter','target':copy.deepcopy(self.target),'object':copy.deepcopy(self.object),
                            'before':{'normalized':self.current,'tag':1,'title':'Volume','unit':'dB','display':'-12 dB'},
                            'after_normalized':args['after'],'request':copy.deepcopy(args)}}
        plan=args['plan']
        if plan['target']['session']!=self.session:raise RemoteError('STALE_SESSION')
        if op in {'check','apply'} and abs(plan['before']['normalized']-self.current)>1e-6:raise RemoteError('STALE_CURRENT_VALUE')
        if op=='check':return {'plan':plan}
        if op=='apply':
            self.writes+=1;self.current=plan['after_normalized']
            if self.fail_after_write:raise OSError('lost feedback after dispatch')
            return {'mutation_sent':True}
        if op=='read':return {'parameter':{'normalized':self.current}}
        raise AssertionError(op)


@pytest.fixture
def host_workflow(tmp_path,monkeypatch):
    import cubasemixai.remote.workflow as remote
    host=Host();monkeypatch.setattr(remote,'RemoteClient',lambda:host)
    w=Workflow(str(tmp_path/'state'));modern=remote.RemoteWorkflow(w)
    p=modern.propose(host.target,10,1,.75,'Bring kick back slightly')
    return host,w,modern,p


def test_remote_approval_readback_and_fresh_restore(host_workflow):
    host,w,modern,p=host_workflow
    assert host.writes==0
    with pytest.raises(ValueError):w.apply(p['id'],dry_run=False)
    w.decide(p['id'],True)
    assert w.apply(p['id'])['dry_run'] and host.writes==0
    result=w.apply(p['id'],dry_run=False)
    assert result['acknowledged_by_cubase'] and result['proposal']['status']=='verified'
    assert host.writes==1
    with pytest.raises(ValueError):w.apply(p['id'],dry_run=False)
    restored=w.restore_proposal(p['id'])
    assert restored['status']=='pending'
    assert restored['payload']['plan']['before']['normalized']==.75
    assert restored['payload']['plan']['after_normalized']==.8
    assert host.writes==1


def test_remote_current_drift_reactivation_and_rejection(host_workflow):
    host,w,modern,p=host_workflow
    host.current=.7
    with pytest.raises(RemoteError,match='STALE_CURRENT'):w.decide(p['id'],True)
    assert host.writes==0
    assert w.decide(p['id'],False)['status']=='rejected'
    host.current=.8;p=modern.propose(host.target,10,1,.75,'test');w.decide(p['id'],True)
    host.session='epoch-2'
    with pytest.raises(RemoteError,match='STALE_SESSION'):w.apply(p['id'],dry_run=False)
    assert host.writes==0


def test_remote_partial_failure_is_never_replayed(host_workflow):
    host,w,modern,p=host_workflow
    w.decide(p['id'],True);host.fail_after_write=True
    with pytest.raises(OSError):w.apply(p['id'],dry_run=False)
    assert w.get(p['id'])['status']=='uncertain' and host.writes==1
    with pytest.raises(ValueError):w.apply(p['id'],dry_run=False)
    assert host.writes==1


def test_driver_contract_with_node():
    node=shutil.which('node')
    assert node,'Node is required to validate the actual driver script'
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([node,str(root/'tests'/'remote_driver_contract.cjs'),str(root/'src'/'cubasemixai'/'remote'/'CubaseMixAI_DirectBridge.js')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr


def test_python_to_actual_js_driver_wire_roundtrip(tmp_path,monkeypatch):
    """Actual Python SysEx codec/client/workflow <-> actual JS driver, fake DA host only."""
    import queue
    import threading
    import mido
    from cubasemixai.remote.client import RemoteClient
    import cubasemixai.remote.workflow as modern
    root=Path(__file__).resolve().parents[1]
    process=subprocess.Popen([shutil.which('node'),str(root/'tests'/'remote_driver_contract.cjs'),str(root/'src'/'cubasemixai'/'remote'/'CubaseMixAI_DirectBridge.js'),'--wire'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
    incoming=queue.Queue()
    def read():
        for line in process.stdout:
            for frame in json.loads(line):incoming.put(mido.Message('sysex',data=frame[1:-1]))
    thread=threading.Thread(target=read,daemon=True);thread.start()
    class Port:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def send(self,message):
            process.stdin.write(json.dumps(list(message.data))+'\n');process.stdin.flush()
        def iter_pending(self):
            while True:
                try:yield incoming.get_nowait()
                except queue.Empty:return
    config={'input_port':'wire-test feedback','output_port':'wire-test commands','timeout':5}
    monkeypatch.setattr(mido,'get_input_names',lambda:[config['input_port']])
    monkeypatch.setattr(mido,'get_output_names',lambda:[config['output_port']])
    monkeypatch.setattr(mido,'open_input',lambda name:Port())
    monkeypatch.setattr(mido,'open_output',lambda name:Port())
    monkeypatch.setattr(modern,'RemoteClient',lambda:RemoteClient(config))
    try:
        with RemoteClient(config) as host:
            target=host.request('tracks',{})['tracks'][0]
            assert target['title']=='Kick'
        w=Workflow(str(tmp_path/'state'))
        p=modern.RemoteWorkflow(w).propose(target,10,1,-13,'One dB kick A/B','plain','dB',1)
        assert p['payload']['plan']['before']['plain']==-12
        w.decide(p['id'],True)
        result=w.apply(p['id'],dry_run=False)
        assert result['proposal']['status']=='verified'
        assert result['proposal']['payload']['receipt']['observed']['parameter']['display']=='-13.00 dB'
        reverse=w.restore_proposal(p['id'])
        w.decide(reverse['id'],True)
        assert w.apply(reverse['id'],dry_run=False)['proposal']['status']=='verified'
        # Empty-slot insertion is also verified by actual JS object identity readback.
        plugin=modern.RemoteWorkflow(w).propose_plugin(target,14,'A'*32,'Insert test EQ into empty slot')
        w.decide(plugin['id'],True)
        assert w.apply(plugin['id'],dry_run=False)['proposal']['status']=='verified'
        with pytest.raises(ValueError,match='manual'):w.restore_proposal(plugin['id'])
    finally:
        process.stdin.close()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        thread.join(timeout=2)


def test_remote_ui_uses_shared_history_and_local_approval(host_workflow):
    from fastapi.testclient import TestClient
    from cubasemixai.ui import create_app
    host,w,modern,old=host_workflow
    client=TestClient(create_app(w,'secret'),base_url='http://127.0.0.1:8765')
    headers={'X-Review-Token':'secret'}
    result=client.post('/run/remote_propose',headers=headers,json={'target':host.target,'object_id':10,'parameter_tag':1,'after':.75,'reason':'UI remote test','value_kind':'normalized','max_delta':.1})
    assert result.status_code==200,result.text
    p=result.json();assert w.get(p['id'])['status']=='pending'
    assert client.post('/apply/'+p['id'],headers=headers,json={'dry_run':False,'confirmed':True}).status_code==400
    assert host.writes==0
    assert client.post('/decision/'+p['id'],headers=headers,json={'approve':True,'confirmed':True}).status_code==200
    applied=client.post('/apply/'+p['id'],headers=headers,json={'dry_run':False,'confirmed':True})
    assert applied.status_code==200 and applied.json()['proposal']['status']=='verified'
    assert client.post('/restore/'+p['id'],headers=headers,json={}).json()['status']=='pending'


class BatchHost:
    def __init__(self):
        self.values={10:-12.0,11:-14.0,20:-10.0};self.writes=0;self.fail_at=None
    @staticmethod
    def norm(db):return (db+60)/60
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def target(self,object_id):
        return {'session':'batch-session','object_id':object_id,'unique_id':f'id-{object_id}',
                'unique_name':'Audio','title':f'Track {object_id}'}
    def request(self,op,args):
        if op=='inspect':
            object_id=args['object_id']
            return {'object':{k:v for k,v in self.target(object_id).items() if k!='session'},
                    'parameters':[{'tag':1,'title':'Volume','unit':'dB','plain':self.values[object_id],
                                   'normalized':self.norm(self.values[object_id])}], 'next_offset':None}
        if op=='preview':
            object_id=args['object_id'];current=self.values[object_id];after=args['after']
            if abs(after-current)>args['max_delta']+1e-6:raise RemoteError('DELTA')
            target=self.target(object_id);obj={k:v for k,v in target.items() if k!='session'}
            return {'plan':{'kind':'parameter','target':target,'object':obj,
                'before':{'normalized':self.norm(current),'plain':current,'tag':1,'title':'Volume','unit':'dB'},
                'after_normalized':self.norm(after),'after_plain':after,'request':copy.deepcopy(args)}}
        plan=args['plan'];object_id=plan['object']['object_id']
        if op=='read':return {'parameter':{'normalized':self.norm(self.values[object_id]),'plain':self.values[object_id]}}
        if abs(self.norm(self.values[object_id])-plan['before']['normalized'])>1e-6:
            raise RemoteError('STALE_CURRENT_VALUE')
        if op=='check':return {'plan':plan}
        if op=='apply':
            self.values[object_id]=plan['after_plain'];self.writes+=1
            if self.fail_at==self.writes:raise OSError('lost feedback after batch write')
            return {'mutation_sent':True}
        raise AssertionError(op)


def test_reference_volume_batch_requires_one_local_approval_and_verifies_each_fader(tmp_path,monkeypatch):
    import numpy as np
    import soundfile as sf
    import cubasemixai.remote.workflow as remote
    import cubasemixai.remote.tools as tools
    from cubasemixai.remote.tools import remote_propose_reference_volumes
    sr=48000;t=np.arange(sr*2)/sr;dry=.05*np.sin(2*np.pi*220*t)
    mix=tmp_path/'mix-stem.wav';reference=tmp_path/'reference-stem.wav'
    sf.write(mix,dry,sr);sf.write(reference,dry*2,sr)
    host=BatchHost();monkeypatch.setattr(remote,'RemoteClient',lambda:host);monkeypatch.setattr(tools,'RemoteClient',lambda:host)
    w=Workflow(str(tmp_path/'state'))
    pairs=[{'target':host.target(i),'object_id':i,'parameter_tag':1,'mix_wav':str(mix),'reference_wav':str(reference)} for i in (10,11)]
    result=remote_propose_reference_volumes(pairs,state_dir=str(tmp_path/'state'))
    proposal=result['proposal'];plans=proposal['payload']['plans']
    assert len(plans)==2 and [p['after_plain'] for p in plans]==[-11.0,-13.0]
    assert host.writes==0
    with pytest.raises(ValueError):w.apply(proposal['id'],dry_run=False)
    w.decide(proposal['id'],True)
    assert w.apply(proposal['id'])['dry_run'] and host.writes==0
    applied=w.apply(proposal['id'],dry_run=False)
    assert applied['proposal']['status']=='verified' and host.writes==2
    assert len(applied['proposal']['payload']['batch_receipts'])==2
    restore=w.restore_proposal(proposal['id'])
    assert restore['payload']['kind']=='batch_parameter' and len(restore['payload']['plans'])==2


def test_reference_volume_batch_partial_failure_is_uncertain_and_single_use(tmp_path,monkeypatch):
    import numpy as np
    import soundfile as sf
    import cubasemixai.remote.workflow as remote
    import cubasemixai.remote.tools as tools
    from cubasemixai.remote.tools import remote_propose_reference_volumes
    sr=48000;t=np.arange(sr*2)/sr;dry=.05*np.sin(2*np.pi*220*t)
    mix=tmp_path/'mix.wav';reference=tmp_path/'ref.wav'
    sf.write(mix,dry,sr);sf.write(reference,dry*2,sr)
    host=BatchHost();host.fail_at=2;monkeypatch.setattr(remote,'RemoteClient',lambda:host);monkeypatch.setattr(tools,'RemoteClient',lambda:host)
    w=Workflow(str(tmp_path/'state'))
    pairs=[{'target':host.target(i),'object_id':i,'parameter_tag':1,'mix_wav':str(mix),'reference_wav':str(reference)} for i in (10,11)]
    proposal=remote_propose_reference_volumes(pairs,state_dir=str(tmp_path/'state'))['proposal']
    w.decide(proposal['id'],True)
    with pytest.raises(OSError,match='lost feedback'):
        w.apply(proposal['id'],dry_run=False)
    saved=w.get(proposal['id'])
    assert saved['status']=='uncertain' and len(saved['payload']['batch_receipts'])==1
    with pytest.raises(ValueError):w.apply(proposal['id'],dry_run=False)
    assert host.writes==2


def test_master_peak_proposal_uses_exported_wav_and_fader_unit(tmp_path,monkeypatch):
    import numpy as np
    import soundfile as sf
    import cubasemixai.remote.workflow as remote
    import cubasemixai.remote.tools as tools
    from cubasemixai.remote.tools import remote_propose_master_peak
    sr=48000;t=np.arange(sr*2)/sr;rendered=.05*np.sin(2*np.pi*220*t)
    wav=tmp_path/'master-after-track-adjustments.wav';sf.write(wav,rendered,sr)
    host=BatchHost();monkeypatch.setattr(remote,'RemoteClient',lambda:host);monkeypatch.setattr(tools,'RemoteClient',lambda:host)
    w=Workflow(str(tmp_path/'state'))
    result=remote_propose_master_peak(host.target(20),20,1,str(wav),state_dir=str(tmp_path/'state'))
    proposal=result['proposal']
    assert result['master']['peak_metric']=='sample_peak_dbfs'
    assert result['master']['target_peak_db']==-6
    assert result['master']['proposed_fader_step_db']==3
    assert proposal['payload']['plan']['after_plain']==-7
    w.decide(proposal['id'],True)
    assert w.apply(proposal['id'],dry_run=False)['proposal']['status']=='verified'
    assert host.values[20]==-7
