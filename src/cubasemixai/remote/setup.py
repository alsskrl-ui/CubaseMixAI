"""Export the original driver without changing existing Cubase files."""
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from .client import config_path


def setup_remote(scripts_dir: str) -> dict:
    base=Path(scripts_dir).resolve()
    destination=base/'Local'/'CubaseMixAI'/'DirectBridge'/'CubaseMixAI_DirectBridge.js'
    config=config_path()
    if destination.exists() or config.exists():
        raise ValueError('Driver/config already exists; back it up and choose explicit update paths instead of overwriting')
    script=files('cubasemixai.remote').joinpath('CubaseMixAI_DirectBridge.js').read_text(encoding='utf-8')
    destination.parent.mkdir(parents=True,exist_ok=True)
    config.parent.mkdir(parents=True,exist_ok=True)
    created=[]
    try:
        for path,body in [(destination,script),(config,json.dumps({'output_port':'CubaseMixAI To Cubase','input_port':'CubaseMixAI From Cubase','timeout':15},indent=2))]:
            with path.open('x',encoding='utf-8') as f:f.write(body)
            created.append(path)
    except Exception:
        for path in created:path.unlink()
        raise
    return {'driver':str(destination),'config':str(config),'driver_sha256':hashlib.sha256(script.encode()).hexdigest(),
            'instructions':['Create both loopMIDI ports before starting Cubase 15',
                            'Load the MIDI Remote script and connect command input / feedback output',
                            'Edit Python port names in remote.json if ports reports suffixes',
                            'Run remote-status; capabilities and a real Cubase read are required before proposing changes'],
            'validation':'driver exported; not a Cubase live validation'}
