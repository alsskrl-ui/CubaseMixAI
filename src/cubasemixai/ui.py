"""Loopback-only review UI with per-launch secret and origin checking."""
import secrets
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from .workflow import Workflow


def create_app(workflow: Workflow, token: str | None = None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = token or secrets.token_urlsafe(32)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "")
        if host not in {"127.0.0.1:8765", "localhost:8765"}:
            return HTMLResponse("Invalid host", status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
            return HTMLResponse("Invalid origin", status_code=403)
        return await call_next(request)

    def authorize(value):
        if not value or not secrets.compare_digest(value, app.state.token):
            raise HTTPException(403, "Enter the token printed by the local UI process")

    @app.get("/", response_class=HTMLResponse)
    def home():
        from importlib.resources import files
        return files("cubasemixai").joinpath("dashboard.html").read_text(encoding="utf-8")

    @app.get("/history")
    def history(x_review_token: str | None = Header(default=None)):
        authorize(x_review_token)
        return workflow.history()

    class Decision(BaseModel):
        approve: bool
        confirmed: bool = False

    @app.post("/decision/{ident}")
    def decision(ident: str, body: Decision, x_review_token: str | None = Header(default=None)):
        authorize(x_review_token)
        if body.approve and not body.confirmed:
            raise HTTPException(400, "Backup and current-value confirmation required")
        try:
            return workflow.decide(ident, body.approve)
        except (ValueError, KeyError, OSError, RuntimeError) as exc:
            raise HTTPException(400, str(exc)) from exc
    class ApplyBody(BaseModel):
        dry_run: bool = True
        confirmed: bool = False

    @app.post("/apply/{ident}")
    def apply(ident: str, body: ApplyBody, x_review_token: str | None = Header(default=None)):
        authorize(x_review_token)
        if not body.dry_run and not body.confirmed:
            raise HTTPException(400, "Confirm current Cubase values before live MIDI")
        try:
            return workflow.apply(ident, dry_run=body.dry_run)
        except (ValueError, KeyError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/restore/{ident}")
    def restore(ident: str, x_review_token: str | None = Header(default=None)):
        authorize(x_review_token)
        try:
            return workflow.restore_proposal(ident)
        except (ValueError, KeyError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/run/{operation}")
    def run(operation: str, body: dict, x_review_token: str | None = Header(default=None)):
        authorize(x_review_token)
        from .analysis import compare, analyze_stems
        from .engine import propose_reference
        from .evaluation import compare_sections, evaluate_render, export_ab
        from .backup import backup_project, verify_backup, restore_project
        from .listening import clap_compare
        from .calibration import calibration_report
        from .mastering import master_chain
        from .render import create_render_job, finish_render_job
        from .remote.tools import remote_status, remote_tracks, remote_inspect, remote_plugins, remote_propose, remote_propose_plugin
        functions = {f.__name__: f for f in (compare, analyze_stems, propose_reference, compare_sections,
                     evaluate_render, export_ab, backup_project, verify_backup, restore_project, clap_compare,
                     calibration_report, master_chain, create_render_job, finish_render_job,
                     remote_status, remote_tracks, remote_inspect, remote_plugins, remote_propose, remote_propose_plugin)}
        if operation not in functions:
            raise HTTPException(404, "Unknown operation")
        if operation in {"propose_reference", "create_render_job", "finish_render_job"}:
            body["state_dir"] = str(workflow.root)
        try:
            if operation in {"remote_propose", "remote_propose_plugin"}:
                from .remote.workflow import RemoteWorkflow
                modern = RemoteWorkflow(workflow)
                return (modern.propose if operation == "remote_propose" else modern.propose_plugin)(**body)
            return functions[operation](**body)
        except (ValueError, KeyError, OSError, TypeError, ImportError, RuntimeError) as exc:
            raise HTTPException(400, str(exc)) from exc
    return app
