"""Opt-in integration smoke test using real local CLAP weights and synthetic WAVs."""
import argparse
import json
import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from cubasemixai.listening import clap_compare

parser=argparse.ArgumentParser()
parser.add_argument('model_dir')
parser.add_argument('--output')
args=parser.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    sr=48000
    t=np.arange(sr*3)/sr
    x=.1*np.sin(2*np.pi*440*t)+.02*np.sin(2*np.pi*1000*t)
    a,b=Path(tmp)/'a.wav',Path(tmp)/'b.wav'
    sf.write(a,x,sr,subtype='FLOAT');sf.write(b,x*.5,sr,subtype='FLOAT')
    report=clap_compare(str(a),str(b),args.model_dir)
    assert report['cosine_similarity'] > .99, report
    assert set(report['dimensions'])=={'brightness','punch','space'}
    assert all(np.isfinite(d['mix_minus_reference']) for d in report['dimensions'].values())
    report['validation']='real model + synthetic gain-paired audio; not human perceptual validation'
    text=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)
    if args.output: Path(args.output).write_text(text,encoding='utf-8')
    print(text)
