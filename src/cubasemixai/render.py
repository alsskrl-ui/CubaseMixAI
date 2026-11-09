"""Persistent manual-export handoff. Never pretends to drive Cubase GUI."""
import json
import uuid
from pathlib import Path
from .analysis import analyze, fingerprint
from .evaluation import evaluate_render
from .workflow import Workflow


def _job_path(workflow, job_id):
    if len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id):
        raise ValueError('Invalid render job ID')
    return workflow.root/'renders'/(job_id+'.json')


def create_render_job(before: str, reference: str, output: str, state_dir: str | None = None) -> dict:
    w = Workflow(state_dir)
    a, b = analyze(before), analyze(reference)
    out = Path(output).resolve()
    if out.suffix.lower() != '.wav' or out.exists():
        raise ValueError('Choose a new WAV export path; existing files are not accepted')
    ident = uuid.uuid4().hex
    result = {'id': ident, 'status': 'awaiting_cubase_export', 'before': a, 'reference': b, 'output': str(out),
              'instructions': ['In Cubase, select the same locators as the before render',
                               f"Export Audio Mixdown as mono/stereo WAV, {a['sample_rate']} Hz, {a['channels']} channels",
                               f'Export to {out}; finish export before importing the result',
                               'Run render-finish with this job ID; inspect loudness-matched A/B']}
    path = _job_path(w, ident)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def finish_render_job(job_id: str, model_dir: str | None = None, state_dir: str | None = None) -> dict:
    w = Workflow(state_dir)
    path = _job_path(w, job_id)
    job = json.loads(path.read_text(encoding='utf-8'))
    if job['status'] != 'awaiting_cubase_export':
        raise ValueError('Render job already completed')
    for name in ('before','reference'):
        if fingerprint(job[name]['path']) != job[name]['sha256']:
            raise ValueError('Before/reference changed since render job creation')
    out = Path(job['output'])
    stat = out.stat()
    digest = fingerprint(str(out))
    listening = [None,None]
    if model_dir:
        from .listening import clap_compare
        listening = [clap_compare(job[k]['path'],job['reference']['path'],model_dir) if k=='before'
                     else clap_compare(str(out),job['reference']['path'],model_dir) for k in ('before','after')]
    report = evaluate_render(job['before']['path'], str(out), job['reference']['path'], *listening)
    if stat.st_size != out.stat().st_size or stat.st_mtime_ns != out.stat().st_mtime_ns or fingerprint(str(out)) != digest:
        raise ValueError('Export file is still changing; retry after Cubase finishes rendering')
    job.update(status='evaluated_requires_listening', evaluation=report)
    temp = path.with_suffix('.tmp-'+uuid.uuid4().hex)
    temp.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)
    return job
