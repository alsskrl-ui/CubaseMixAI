"""Read-only local installation checks; hardware status is never inferred."""
import importlib.util
import platform
import shutil
import subprocess
import sys
from .workflow import Workflow


def doctor(mapping_path: str | None = None) -> dict:
    tools={}
    for name in ('git','node','codex'):
        path=shutil.which(name)
        if not path:
            tools[name]={'installed':False}
            continue
        try:
            # Windows npm shims may be .cmd files; use cmd explicitly with a fixed executable.
            command=[path,'--version']
            if sys.platform=='win32' and path.lower().endswith(('.cmd','.bat')):
                command=['cmd.exe','/d','/c',path,'--version']
            r=subprocess.run(command,capture_output=True,text=True,timeout=10)
            tools[name]={'installed':r.returncode==0,'version':r.stdout.strip()[:200]}
        except (OSError,subprocess.TimeoutExpired) as exc:
            tools[name]={'installed':False,'error':str(exc)}
    try:
        import mido
        ports={'outputs':mido.get_output_names()}
    except Exception as exc:
        ports={'error':str(exc),'outputs':[]}
    mapping=None
    if mapping_path:
        from .control import load_mapping
        try:
            data,digest=load_mapping(mapping_path)
            mapping={'valid':True,'sha256':digest,'port_present':data['port'] in ports['outputs'],
                     'simulation':bool(data.get('simulation'))}
        except (ValueError,KeyError,OSError,TypeError) as exc:
            mapping={'valid':False,'error':str(exc)}
    return {'platform':platform.platform(),'python':sys.version.split()[0],
            'python_supported':sys.version_info>=(3,11),'tools':tools,'midi':ports,'mapping':mapping,
            'ai_dependencies':{name:importlib.util.find_spec(name) is not None for name in ('torch','transformers','librosa')},
            'state_dir':str(Workflow().root),
            'requires_manual_verification':['Cubase project backup and consolidated external media',
                'Generic Remote routing and actual parameter response','CLAP checkpoint and real-audio listening']}
