"""Chunked 7-bit ASCII JSON carried by non-commercial SysEx (manufacturer 0x7D)."""
import json
import time

PREFIX = (0x7D, 0x43, 0x4D, 0x41, 1)
CHUNK = 180
MAX_BYTES = 262144


def _number(value, count):
    return [(value >> (7*i)) & 127 for i in range(count)]


def encode(envelope: dict, stream: int) -> list[tuple]:
    if type(stream) is not int or not 1 <= stream < 2**21:
        raise ValueError('Invalid protocol stream')
    data = json.dumps(envelope, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')
    if len(data) > MAX_BYTES:
        raise ValueError('Protocol message too large')
    total = (len(data)+CHUNK-1)//CHUNK
    return [tuple([*PREFIX, *_number(stream,3), *_number(i,2), *_number(total,2), *data[i*CHUNK:(i+1)*CHUNK]]) for i in range(total)]


class Decoder:
    def __init__(self):
        self.pending = {}

    def feed(self, data) -> tuple[int, dict] | None:
        data = tuple(data)
        now = time.monotonic()
        self.pending = {k:v for k,v in self.pending.items() if now-v['time'] < 30}
        if data[:5] != PREFIX:
            return None
        if len(data)<12 or any(type(x) is not int or not 0<=x<128 for x in data):
            raise ValueError('Malformed SysEx frame')
        stream = sum(data[5+i] << (7*i) for i in range(3))
        index = data[8] + (data[9]<<7)
        total = data[10] + (data[11]<<7)
        if not stream or not 1 <= total <= (MAX_BYTES+CHUNK-1)//CHUNK or index >= total or len(data[12:])>CHUNK:
            raise ValueError('Invalid chunk header')
        if len(self.pending)>=8 and stream not in self.pending:
            raise ValueError('Too many incomplete streams')
        item = self.pending.setdefault(stream, {'time':now,'total':total,'parts':{}})
        part = bytes(data[12:])
        if total!=item['total'] or (index in item['parts'] and item['parts'][index]!=part):
            self.pending.pop(stream,None)
            raise ValueError('Conflicting protocol chunks')
        item['parts'][index] = part
        if len(item['parts']) != total:
            return None
        del self.pending[stream]
        body = b''.join(item['parts'][i] for i in range(total))
        if len(body)>MAX_BYTES:
            raise ValueError('Protocol message too large')
        envelope=json.loads(body.decode('ascii'))
        if not isinstance(envelope,dict):
            raise ValueError('Expected protocol object')
        return stream,envelope
