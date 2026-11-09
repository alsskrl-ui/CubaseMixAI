import json
import numpy as np
import pytest
import soundfile as sf
from cubasemixai.engine import integrate, propose_reference
from cubasemixai.analysis import compare, fingerprint
from cubasemixai.listening import score_embeddings, _windows
from cubasemixai.workflow import Workflow


@pytest.fixture
def audio(tmp_path):
    sr=48000;t=np.arange(sr*2)/sr
    ref=.08*np.sin(2*np.pi*100*t)+.04*np.sin(2*np.pi*3000*t)
    mix=.03*np.sin(2*np.pi*100*t)+.09*np.sin(2*np.pi*3000*t)
    a,b=tmp_path/'mix.wav',tmp_path/'ref.wav'
    sf.write(a,mix,sr,subtype='FLOAT');sf.write(b,ref,sr,subtype='FLOAT')
    return str(a),str(b)


def mapping(tmp_path):
    controls={}
    for cc,(suffix,unit,points) in enumerate([
        ('volume','dB',[[-30,1],[0,100],[6,127]]),
        ('eq.bass.gain','dB',[[-12,0],[0,64],[12,127]]),
        ('eq.presence.gain','dB',[[-12,0],[0,64],[12,127]]),
        ('compressor.threshold','dB',[[-40,0],[0,127]]),
        ('compressor.ratio','ratio',[[1,0],[10,127]]),
        ('limiter.ceiling','dB',[[-6,0],[0,127]])],20):
        controls['master.'+suffix]={'channel':1,'cc':cc,'unit':unit,'verified':True,'max_delta':3,'points':points}
    p=tmp_path/'mapping.json';p.write_text(json.dumps({'port':'test','controls':controls}))
    return str(p)


def test_reference_plan_is_pending_and_bounded(audio,tmp_path):
    a,b=audio; mp=mapping(tmp_path)
    result=propose_reference(a,b,mp,{'master.volume':0,'master.eq.bass.gain':0,'master.eq.presence.gain':0,'master.limiter.ceiling':0},mode='master',state_dir=str(tmp_path/'state'))
    p=result['proposal'];assert p['status']=='pending' and not result['midi_sent']
    assert any('eq.' in c['control'] for c in result['candidates'])
    assert all(abs(c['after']-c['before'])<=1.5 for c in result['candidates'])
    w=Workflow(str(tmp_path/'state'))
    with pytest.raises(ValueError): w.apply(p['id'],dry_run=False)
    w.decide(p['id'],True)
    # Previously approved source has changed: never apply stale evidence.
    sf.write(a,np.zeros(48000),48000)
    with pytest.raises(ValueError,match='Source WAV changed'): w.apply(p['id'],dry_run=False)


def test_silent_and_bad_values_rejected(audio,tmp_path):
    a,b=audio;mp=mapping(tmp_path)
    with pytest.raises(ValueError): propose_reference(a,b,mp,{'master.volume':float('nan')},state_dir=str(tmp_path/'state'))
    with pytest.raises(ValueError): propose_reference(a,b,mp,{'master.volume':100},state_dir=str(tmp_path/'state'))
    sf.write(a,np.zeros(48000),48000)
    with pytest.raises(ValueError,match='silent'): propose_reference(a,b,mp,{},state_dir=str(tmp_path/'state'))


def test_embedding_scores_and_input_provenance(audio):
    a,b=audio
    vectors=np.eye(6)
    scores=score_embeddings(vectors[:2],vectors[:2],vectors)
    assert scores['cosine_similarity']==pytest.approx(1)
    assert all(v['mix_minus_reference']==pytest.approx(0) for v in scores['dimensions'].values())
    scores['inputs']={'mix_sha256':fingerprint(a),'reference_sha256':fingerprint(b)}
    assert integrate(compare(a,b),scores)['ai_listening'].startswith('CLAP')
    scores['inputs']['mix_sha256']='bad'
    with pytest.raises(ValueError): integrate(compare(a,b),scores)
    with pytest.raises(ValueError): score_embeddings(np.zeros((2,6)),vectors[:2],vectors)


def test_opposite_phase_clap_not_silent(tmp_path):
    p=tmp_path/'stereo.wav';x=.1*np.sin(np.arange(48000)*.1)
    sf.write(p,np.column_stack([x,-x]),48000,subtype='FLOAT')
    assert np.max(np.abs(_windows(str(p))[0]))>0


def test_full_proposal_to_render_pipeline(audio,tmp_path):
    from cubasemixai.render import create_render_job,finish_render_job
    from cubasemixai.evaluation import export_ab
    a,b=audio;state=str(tmp_path/'state')
    result=propose_reference(a,b,mapping(tmp_path),{'master.volume':0},state_dir=state)
    w=Workflow(state);p=result['proposal'];messages=[]
    w.decide(p['id'],True)
    assert w.apply(p['id'],dry_run=False,sender=lambda port,msg:messages.extend(msg))['sent']
    assert messages
    out=tmp_path/'render.wav';job=create_render_job(a,b,str(out),state)
    x,sr=sf.read(a);sf.write(out,x*.95,sr,subtype='FLOAT')
    final=finish_render_job(job['id'],state_dir=state)
    assert final['evaluation']['verdict']=='requires_human_listening'
    assert export_ab(a,str(out),str(tmp_path/'ab'))['target_lufs']<0
    assert w.restore_proposal(p['id'])['status']=='pending'


def test_clap_conflict_holds_tonal_candidate(audio,tmp_path):
    a,b=audio;mp=mapping(tmp_path)
    current={'master.eq.presence.gain':0}
    baseline=propose_reference(a,b,mp,current,state_dir=str(tmp_path/'baseline'))
    assert any(c['control']=='master.eq.presence.gain' for c in baseline['candidates'])
    listening=score_embeddings(np.eye(6)[:2],np.eye(6)[:2],np.eye(6))
    listening['inputs']={'mix_sha256':fingerprint(a),'reference_sha256':fingerprint(b)}
    listening['dimensions']['brightness'].update(confidence='medium',mix_minus_reference=-.2)
    guarded=propose_reference(a,b,mp,current,listening=listening,state_dir=str(tmp_path/'guarded'))
    assert not any(c['control']=='master.eq.presence.gain' for c in guarded['candidates'])
    assert any('conflicts' in c['reason'] for c in guarded['skipped'])
