import argparse
import json
from .analysis import analyze, compare
from .workflow import Workflow


def main():
    parser = argparse.ArgumentParser(prog="cubasemixai")
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze"); a.add_argument("wav"); a.add_argument("--start", type=float, default=0); a.add_argument("--end", type=float)
    c = sub.add_parser("compare"); c.add_argument("mix"); c.add_argument("reference")
    sub.add_parser("ports")
    sub.add_parser("ui")
    sub.add_parser("history")
    p = sub.add_parser("propose"); p.add_argument("mapping"); p.add_argument("changes", help="JSON file containing a list of control/before/after/unit objects"); p.add_argument("--reason", required=True)
    a = sub.add_parser("apply"); a.add_argument("id"); a.add_argument("--live", action="store_true")
    r = sub.add_parser("restore"); r.add_argument("id")
    ai = sub.add_parser("listen"); ai.add_argument("mix"); ai.add_argument("reference"); ai.add_argument("checkpoint")
    args = parser.parse_args()
    try:
        if args.cmd == "analyze": result = analyze(args.wav, args.start, args.end)
        elif args.cmd == "compare": result = compare(args.mix, args.reference)
        elif args.cmd == "ports":
            import mido
            result = mido.get_output_names()
        elif args.cmd == "ui":
            import uvicorn
            from .ui import create_app
            app = create_app(Workflow())
            print("Local review: http://127.0.0.1:8765", flush=True)
            print("Review token (do not share with an AI agent): " + app.state.token, flush=True)
            uvicorn.run(app, host="127.0.0.1", port=8765)
            return
        elif args.cmd == "history": result = Workflow().history()
        elif args.cmd == "propose":
            from pathlib import Path
            result = Workflow().create(args.mapping, json.loads(Path(args.changes).read_text(encoding="utf-8")), args.reason)
        elif args.cmd == "apply": result = Workflow().apply(args.id, dry_run=not args.live)
        elif args.cmd == "restore": result = Workflow().restore_proposal(args.id)
        elif args.cmd == "listen":
            from .listening import clap_compare
            result = clap_compare(args.mix, args.reference, args.checkpoint)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")
