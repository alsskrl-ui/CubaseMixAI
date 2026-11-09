import argparse
import json
import os
from pathlib import Path
from .analysis import analyze, compare, analyze_stems
from .workflow import Workflow


def main():
    parser = argparse.ArgumentParser(prog='cubasemixai')
    parser.add_argument('--state-dir', help='Shared absolute state directory for CLI, UI and MCP')
    sub = parser.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('analyze'); a.add_argument('wav'); a.add_argument('--start',type=float,default=0); a.add_argument('--end',type=float)
    c = sub.add_parser('compare'); c.add_argument('mix'); c.add_argument('reference')
    s = sub.add_parser('stems'); s.add_argument('manifest')
    s = sub.add_parser('sections'); s.add_argument('mix'); s.add_argument('reference'); s.add_argument('manifest')
    d = sub.add_parser('doctor'); d.add_argument('--mapping')
    sub.add_parser('ports'); sub.add_parser('ui'); sub.add_parser('history')
    p = sub.add_parser('propose'); p.add_argument('mapping'); p.add_argument('changes'); p.add_argument('--reason',required=True)
    p = sub.add_parser('reference-plan'); p.add_argument('mix'); p.add_argument('reference'); p.add_argument('mapping'); p.add_argument('current_values'); p.add_argument('--target',default='master'); p.add_argument('--mode',choices=['mix','master'],default='mix'); p.add_argument('--model-dir')
    a = sub.add_parser('apply'); a.add_argument('id'); a.add_argument('--live',action='store_true')
    r = sub.add_parser('restore'); r.add_argument('id')
    ai = sub.add_parser('listen'); ai.add_argument('mix'); ai.add_argument('reference'); ai.add_argument('model_dir')
    ai = sub.add_parser('setup-ai'); ai.add_argument('output')
    for name in ('backup','restore-project'):
        p = sub.add_parser(name); p.add_argument('source'); p.add_argument('destination')
    p = sub.add_parser('verify-backup'); p.add_argument('source')
    p = sub.add_parser('calibrate'); p.add_argument('measurements'); p.add_argument('output'); p.add_argument('--confirmed-measured',action='store_true')
    p = sub.add_parser('calibration-check'); p.add_argument('mapping'); p.add_argument('observations')
    p = sub.add_parser('master-chain'); p.add_argument('mapping'); p.add_argument('--target',default='master')
    p = sub.add_parser('evaluate'); p.add_argument('before'); p.add_argument('after'); p.add_argument('reference'); p.add_argument('--model-dir')
    p = sub.add_parser('ab'); p.add_argument('first'); p.add_argument('second'); p.add_argument('destination')
    p = sub.add_parser('render-start'); p.add_argument('before'); p.add_argument('reference'); p.add_argument('output')
    p = sub.add_parser('render-finish'); p.add_argument('id'); p.add_argument('--model-dir')
    p = sub.add_parser('report'); p.add_argument('input_json'); p.add_argument('output_html')
    args = parser.parse_args()
    if args.state_dir:
        os.environ['CUBASEMIXAI_STATE_DIR'] = str(Path(args.state_dir).resolve())
    def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
    try:
        if args.cmd == 'doctor':
            from .doctor import doctor
            result=doctor(args.mapping)
        elif args.cmd == 'analyze': result = analyze(args.wav,args.start,args.end)
        elif args.cmd == 'compare': result = compare(args.mix,args.reference)
        elif args.cmd == 'stems': result = analyze_stems(read(args.manifest))
        elif args.cmd == 'sections':
            from .evaluation import compare_sections
            result = compare_sections(args.mix,args.reference,read(args.manifest))
        elif args.cmd == 'ports':
            import mido
            result = mido.get_output_names()
        elif args.cmd == 'ui':
            import uvicorn
            from .ui import create_app
            app = create_app(Workflow())
            print('Local review: http://127.0.0.1:8765',flush=True)
            print('State directory: '+str(Workflow().root),flush=True)
            print('Review token (do not share with an AI agent): '+app.state.token,flush=True)
            uvicorn.run(app,host='127.0.0.1',port=8765)
            return
        elif args.cmd == 'history': result = Workflow().history()
        elif args.cmd == 'propose': result = Workflow().create(args.mapping,read(args.changes),args.reason)
        elif args.cmd == 'reference-plan':
            from .engine import propose_reference
            listening = None
            if args.model_dir:
                from .listening import clap_compare
                listening = clap_compare(args.mix,args.reference,args.model_dir)
            result = propose_reference(args.mix,args.reference,args.mapping,read(args.current_values),args.target,args.mode,listening)
        elif args.cmd == 'apply': result = Workflow().apply(args.id,dry_run=not args.live)
        elif args.cmd == 'restore': result = Workflow().restore_proposal(args.id)
        elif args.cmd == 'listen':
            from .listening import clap_compare
            result = clap_compare(args.mix,args.reference,args.model_dir)
        elif args.cmd == 'setup-ai':
            from .listening import setup_ai
            result = setup_ai(args.output)
        elif args.cmd in {'backup','verify-backup','restore-project'}:
            from .backup import backup_project,verify_backup,restore_project
            if args.cmd=='verify-backup': result=verify_backup(args.source)
            else: result=(backup_project if args.cmd=='backup' else restore_project)(args.source,args.destination)
        elif args.cmd == 'calibrate':
            from .calibration import build_mapping
            data=read(args.measurements)
            result=build_mapping(data['port'],data['controls'],args.output,args.confirmed_measured)
        elif args.cmd == 'calibration-check':
            from .calibration import calibration_report
            result=calibration_report(args.mapping,read(args.observations))
        elif args.cmd == 'master-chain':
            from .mastering import master_chain
            result=master_chain(args.mapping,args.target)
        elif args.cmd == 'evaluate':
            from .evaluation import evaluate_render
            listening=[None,None]
            if args.model_dir:
                from .listening import clap_compare
                listening=[clap_compare(p,args.reference,args.model_dir) for p in (args.before,args.after)]
            result=evaluate_render(args.before,args.after,args.reference,*listening)
        elif args.cmd == 'ab':
            from .evaluation import export_ab
            result=export_ab(args.first,args.second,args.destination)
        elif args.cmd == 'render-start':
            from .render import create_render_job
            result=create_render_job(args.before,args.reference,args.output)
        elif args.cmd == 'render-finish':
            from .render import finish_render_job
            result=finish_render_job(args.id,args.model_dir)
        elif args.cmd == 'report':
            from .evaluation import export_report
            result=export_report(read(args.input_json),args.output_html)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    except (ValueError,KeyError,TypeError,OSError,ImportError,RuntimeError) as exc:
        parser.exit(2,f'Error: {exc}\n')
