"""Opt-in local browser smoke test. Uses simulated mappings; never sends MIDI."""
import json
import tempfile
import threading
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import uvicorn
from playwright.sync_api import sync_playwright
from cubasemixai.ui import create_app
from cubasemixai.workflow import Workflow

Path('.cubasemixai').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);sr=48000;t=np.arange(sr)/sr
    a,b=root/'mix.wav',root/'reference.wav'
    sf.write(a,.1*np.sin(2*np.pi*440*t),sr,subtype='FLOAT')
    sf.write(b,.05*np.sin(2*np.pi*440*t),sr,subtype='FLOAT')
    mapping=root/'mapping.json'
    mapping.write_text(json.dumps({'simulation':True,'port':'SIMULATION','controls':{'master.volume':{'channel':1,'cc':20,'unit':'dB','verified':True,'max_delta':3,'points':[[-20,0],[0,100],[6,127]]}}}))
    app=create_app(Workflow(str(root/'state')),'browser-test-token')
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8765,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    deadline=time.monotonic()+10
    while not server.started:
        if time.monotonic()>deadline: raise RuntimeError('UI server did not start')
        time.sleep(.05)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1280,'height':900})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8765')
            page.locator('#token').fill('browser-test-token')
            page.select_option('#operation','compare')
            page.locator('#f-mix').fill(str(a));page.locator('#f-reference').fill(str(b))
            page.locator('#run').click()
            page.wait_for_function("document.querySelector('#result').textContent.includes('lufs_i')")
            page.select_option('#operation','propose_reference')
            page.locator('#f-mix').fill(str(a));page.locator('#f-reference').fill(str(b))
            page.locator('#f-mapping_path').fill(str(mapping));page.locator('#f-current_values').fill('{"master.volume":0}')
            page.locator('#run').click()
            page.get_by_role('button',name='승인',exact=True).wait_for()
            page.locator('#list input[type=checkbox]').check()
            page.get_by_role('button',name='승인',exact=True).click()
            page.get_by_role('button',name='승인된 변경 실제 전송',exact=True).wait_for()
            page.get_by_role('button',name='MIDI 미리보기',exact=True).click()
            page.wait_for_function("document.querySelector('#result').textContent.includes('dry_run')")
            result=json.loads(page.locator('#result').text_content())
            assert result['dry_run'] and not result['sent']
            page.on('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='승인된 변경 실제 전송',exact=True).click()
            page.wait_for_function("document.querySelector('#message').textContent.includes('Simulation mapping')")
            page.locator('#token').fill('')
            page.screenshot(path='.cubasemixai/browser-validation.png',full_page=True)
            assert not errors,errors
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            print('Browser: analysis → proposal → approval → dry-run; simulation live blocked; desktop/mobile layout passed')
            browser.close()
    finally:
        server.should_exit=True;thread.join(timeout=5)
