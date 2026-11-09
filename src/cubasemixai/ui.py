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
        return '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>CubaseMixAI 승인</title>
<style>body{font:16px system-ui;max-width:1000px;margin:40px auto;background:#111827;color:#e5e7eb}input,button{padding:10px;margin:6px}pre{white-space:pre-wrap;background:#1f2937;padding:20px}article{border:1px solid #475569;padding:20px;margin:20px 0}</style>
<h1>CubaseMixAI 로컬 승인</h1><p>Cubase 프로젝트를 백업하고 트랙·현재 값·포트를 직접 확인하세요. 승인은 15분 이내 한 번만 사용할 수 있습니다.</p>
<input id="token" type="password" placeholder="터미널의 승인 토큰"><button id="refresh">내역 조회</button><p id="message"></p><main id="list"></main>
<script>
const token=document.querySelector('#token');
async function api(path,body){const r=await fetch(path,{method:body?'POST':'GET',headers:{'X-Review-Token':token.value,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(d.detail);return d;}
async function refresh(){try{const data=await api('/history');const list=document.querySelector('#list');list.replaceChildren();for(const p of data){const box=document.createElement('article'),pre=document.createElement('pre');pre.textContent=JSON.stringify(p,null,2);box.append(pre);if(p.status==='pending'){const check=document.createElement('input');check.type='checkbox';box.append(check,document.createTextNode('백업 완료, 현재 값과 매핑 및 변경 내용을 직접 확인했습니다.'));for(const approve of [true,false]){const b=document.createElement('button');b.textContent=approve?'승인':'거절';b.onclick=async()=>{try{if(approve&&!check.checked)throw Error('직접 확인 후 체크하세요');await api('/decision/'+p.id,{approve,confirmed:check.checked});await refresh();}catch(e){document.querySelector('#message').textContent=e.message}};box.append(b)}}list.append(box)}}catch(e){document.querySelector('#message').textContent=e.message}}
document.querySelector('#refresh').onclick=refresh;
</script></html>'''

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
        except (ValueError, KeyError) as exc:
            raise HTTPException(400, str(exc)) from exc
    return app
