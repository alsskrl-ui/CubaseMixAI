"""One owner of the port pair across UI/MCP processes; no write retries."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
import uuid
from .protocol import encode, Decoder


class RemoteError(ValueError):
    pass


def config_path():
    state=Path(os.environ.get('CUBASEMIXAI_STATE_DIR','.cubasemixai')).resolve()
    return Path(os.environ.get('CUBASEMIXAI_REMOTE_CONFIG',str(state/'remote.json')))


def load_config():
    p=config_path()
    if not p.is_file():
        raise RemoteError(f'Create remote config first: {p}')
    data=json.loads(p.read_text(encoding='utf-8'))
    if not all(isinstance(data.get(k),str) and data[k] for k in ('input_port','output_port')) or data['input_port']==data['output_port']:
        raise RemoteError('Use two different MIDI ports for command and feedback')
    data['timeout']=float(data.get('timeout',15))
    if not 1<=data['timeout']<=60:
        raise RemoteError('timeout must be 1–60 seconds')
    return data


@contextlib.contextmanager
def port_lock(config):
    key=hashlib.sha256((config['input_port']+'\n'+config['output_port']).encode()).hexdigest()[:24]
    path=Path(tempfile.gettempdir())/('cubasemixai-midi-'+key+'.lock')
    f=path.open('a+b')
    try:
        if f.tell()==0:
            f.write(b'0');f.flush()
        f.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise RemoteError('MIDI Remote is busy in another UI/MCP operation') from exc
        try:
            yield
        finally:
            f.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(f.fileno(),fcntl.LOCK_UN)
    finally:
        f.close()


class RemoteClient:
    def __init__(self,config=None):
        self.config=config or load_config()
        self.stack=contextlib.ExitStack()
        self.session=None

    def __enter__(self):
        import mido
        try:
            self.stack.enter_context(port_lock(self.config))
            if self.config['input_port'] not in mido.get_input_names() or self.config['output_port'] not in mido.get_output_names():
                raise RemoteError('Remote MIDI port pair not found; check loopMIDI names')
            self.input=self.stack.enter_context(mido.open_input(self.config['input_port']))
            self.output=self.stack.enter_context(mido.open_output(self.config['output_port']))
            self.hello=self.request('hello',{})
            self.session=self.hello['session']
            if self.hello.get('driver')!='CubaseMixAI/1':
                raise RemoteError('Unexpected MIDI Remote driver identity')
            return self
        except Exception:
            self.stack.close()
            raise

    def __exit__(self,*args):
        self.stack.close()

    def request(self,operation,args):
        import mido
        ident=uuid.uuid4().hex
        stream=secrets.randbelow(2**21-1)+1
        packet={'id':ident,'session':self.session,'op':operation,'args':args}
        decoder=Decoder()
        for frame in encode(packet,stream):
            self.output.send(mido.Message('sysex',data=frame))
            time.sleep(.001)
        deadline=time.monotonic()+self.config['timeout']
        while time.monotonic()<deadline:
            for message in self.input.iter_pending():
                if message.type!='sysex':continue
                result=decoder.feed(message.data)
                if result is None or result[0]!=stream:continue
                response=result[1]
                if response.get('id')!=ident or response.get('kind')!='response':continue
                if not response.get('ok'):
                    raise RemoteError(response.get('error','Unknown host error'))
                body=response['result']
                if self.session and body.get('session')!=self.session:
                    raise RemoteError('Host session changed; create a fresh proposal')
                return body
            time.sleep(.005)
        raise RemoteError('Host response timeout; a dispatched write may have applied. Never resend automatically.')
