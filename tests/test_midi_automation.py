import asyncio
import math
import mido
import pytest
from cubasemixai.midi_automation import create_midi_automation


def generate(tmp_path, **kwargs):
    path=tmp_path/'cc.mid'
    args=dict(output_midi=str(path), cc_number=1,start_bar=5,end_bar=9)
    args.update(kwargs)
    result=create_midi_automation(**args)
    mid=mido.MidiFile(path)
    tick=0;events=[]
    for msg in mid.tracks[1]:
        tick+=msg.time
        if msg.type=='control_change':events.append((tick,msg))
    return result,mid,events


@pytest.mark.parametrize('curve,midvalue,last', [('linear',64,127),('exponential',32,127),('sine',127,0)])
def test_curves_absolute_bars_and_channel(tmp_path,curve,midvalue,last):
    result,mid,events=generate(tmp_path,curve=curve,channel=16)
    assert events[0][0]==16*480 and events[-1][0]==32*480
    assert events[len(events)//2][1].value==midvalue
    assert events[-1][1].value==last
    assert all(m.channel==15 and m.control==1 for _,m in events)
    assert all(m.type!='note_on' for t in mid.tracks for m in t)
    assert result['event_count']==513


def test_meter_tempo_and_descending_exponential(tmp_path):
    _,mid,events=generate(tmp_path,numerator=6,denominator=8,tempo_bpm=90,curve='exponential',start_value=127,end_value=0)
    assert events[0][0]==12*480 and events[-1][0]==24*480
    assert events[0][1].value==127 and events[-1][1].value==0
    assert all(a[1].value>=b[1].value for a,b in zip(events,events[1:]))
    assert mid.tracks[0][0].tempo==mido.bpm2tempo(90)
    assert mid.tracks[0][1].denominator==8


@pytest.mark.parametrize('kw', [dict(end_bar=5),dict(start_bar=0),dict(channel=0),dict(cc_number=128),dict(curve='bad'),dict(tempo_bpm=float('nan')),dict(denominator=3),dict(exponent=0),dict(curve='sine',cycles=1000),dict(end_bar=100000),dict(channel=True)])
def test_bad_inputs_no_output(tmp_path,kw):
    with pytest.raises(ValueError): generate(tmp_path,**kw)
    assert not (tmp_path/'cc.mid').exists()


def test_no_overwrite_and_fractional_cycle(tmp_path):
    _,_,events=generate(tmp_path,curve='sine',cycles=.5)
    assert events[-1][1].value==127
    original=(tmp_path/'cc.mid').read_bytes()
    with pytest.raises(ValueError):generate(tmp_path)
    assert (tmp_path/'cc.mid').read_bytes()==original


def test_mcp_registration_and_execution(tmp_path):
    from cubasemixai.mcp_server import server
    async def run():
        tools=await server.list_tools()
        assert 'create_midi_automation' in {t.name for t in tools}
        result=await server.call_tool('create_midi_automation',dict(output_midi=str(tmp_path/'tool.mid'),cc_number=11,start_bar=1,end_bar=2))
        assert (tmp_path/'tool.mid').is_file()
    asyncio.run(run())
