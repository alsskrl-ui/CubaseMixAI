import time
import pytest
from fastapi import HTTPException
from cubasemixai.workflow import Workflow
from cubasemixai.ui import create_app


def test_auto_includes_existing_and_approved_excludes_terminal_and_expired(tmp_path):
    w=Workflow(str(tmp_path)); ids={}
    for status in ('pending','approved','verified','sent','rejected','uncertain','sending','expired'):
        p=w.store({'reason':'test'});ids[status]=p['id']
        with w.connect() as con:
            con.execute('UPDATE proposals SET status=?,created=? WHERE id=?',
                        ('pending' if status=='expired' else status,time.time()-(1000 if status=='expired' else 10),p['id']))
    app=create_app(w,'secret')
    routes={route.path:route.endpoint for route in app.routes}
    with pytest.raises(HTTPException) as exc: routes['/auto/queue'](None)
    assert exc.value.status_code==403
    assert routes['/auto/start']('secret')['includes_existing']
    result=routes['/auto/queue']('secret')
    assert {r['id'] for r in result}=={ids['pending'],ids['approved']}
    p=w.store({'reason':'new'})
    assert p['id'] in {r['id'] for r in routes['/auto/queue']('secret')}
