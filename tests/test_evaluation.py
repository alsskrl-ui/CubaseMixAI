import json
import numpy as np
import pytest
import soundfile as sf
from cubasemixai.analysis import analyze
from cubasemixai.evaluation import evaluate_render,export_ab,compare_sections,export_report
from cubasemixai.render import create_render_job,finish_render_job
from cubasemixai.calibration import build_mapping,calibration_report


@pytest.fixture
def wavs(tmp_path):
    sr=48000;t=np.arange(sr*2)/sr;x=.1*np.sin(2*np.pi*440*t)
    paths=[tmp_path/(name+'.wav') for name in ('before','after','reference')]
    for p,gain in zip(paths,(1,.5,.5)): sf.write(p,x*gain,sr,subtype='FLOAT')
    return [str(p) for p in paths]


def test_post_render_metrics_and_ab(wavs,tmp_path):
    a,b,ref=wavs;r=evaluate_render(a,b,ref)
    assert r['metrics']['loudness_reference_error_lu']['direction']=='closer_to_target'
    assert r['verdict']=='requires_human_listening'
    out=tmp_path/'ab';export_ab(a,b,str(out))
    one,two=analyze(str(out/'A.wav')),analyze(str(out/'B.wav'))
    assert one['lufs_i']==pytest.approx(two['lufs_i'],abs=.01)
    assert max(one['true_peak_estimate_dbtp'],two['true_peak_estimate_dbtp'])<=-1+.01
    with pytest.raises(FileExistsError): export_ab(a,b,str(out))
    sf.write(b,np.zeros(48000),48000)
    with pytest.raises(ValueError,match='duration'): evaluate_render(a,b,ref)


def test_sections_and_html(wavs,tmp_path):
    a,b,_=wavs
    sections=[{'name':'chorus','start':.1,'end':1,'reference_start':.2,'reference_end':1.1}]
    result=compare_sections(a,b,sections)
    assert 'chorus' in result
    with pytest.raises(ValueError): compare_sections(a,b,sections*2)
    out=tmp_path/'report.html';export_report({'evil':'<script>alert(1)</script>'},str(out))
    assert '<script>' not in out.read_text()
    with pytest.raises(FileExistsError): export_report({},str(out))


def test_render_handoff(wavs,tmp_path):
    a,b,ref=wavs;target=tmp_path/'new-render.wav';state=str(tmp_path/'state')
    job=create_render_job(a,ref,str(target),state)
    with pytest.raises(FileNotFoundError): finish_render_job(job['id'],state_dir=state)
    x,sr=sf.read(b);sf.write(target,x,sr,subtype='FLOAT')
    finished=finish_render_job(job['id'],state_dir=state)
    assert finished['status']=='evaluated_requires_listening'
    with pytest.raises(ValueError): finish_render_job(job['id'],state_dir=state)
    with pytest.raises(ValueError): create_render_job(a,ref,str(target),state)
    with pytest.raises(ValueError): finish_render_job('../bad',state_dir=state)


def test_calibration_build_and_holdout(tmp_path):
    controls={'vocal.volume':{'channel':1,'cc':20,'unit':'dB','max_delta':3,'points':[[-12,20],[0,100],[6,127]]}}
    out=tmp_path/'mapping.json'
    with pytest.raises(ValueError): build_mapping('test',controls,str(out))
    build_mapping('test',controls,str(out),True)
    r=calibration_report(str(out),[{'control':'vocal.volume','requested':-2,'observed':-2.1,'tolerance':.2}])
    assert r['passed']
    r=calibration_report(str(out),[{'control':'vocal.volume','requested':-2,'observed':-3,'tolerance':.2}])
    assert not r['passed']
