import mido
import pytest
from cubasemixai.midi_track import midi_track_info, draw_midi_track_expression
from cubasemixai.remote import audio_import


def timeline(track):
    tick = 0
    result = []
    for msg in track:
        tick += msg.time
        result.append((tick, msg.copy(time=0)))
    return result


@pytest.fixture
def midi(tmp_path):
    p = tmp_path/'source.mid'
    mid = mido.MidiFile(ticks_per_beat=480)
    mid.tracks = [mido.MidiTrack([mido.MetaMessage('set_tempo',tempo=500000),
                                mido.MetaMessage('set_tempo',tempo=750000,time=960)]),
                  mido.MidiTrack([mido.MetaMessage('track_name', name='Lead'),
                                 mido.Message('control_change', channel=0,control=1,value=30),
                                 mido.Message('note_on',channel=0,note=60,velocity=90),
                                 mido.Message('control_change', channel=0,control=64,value=127,time=480),
                                 mido.Message('control_change', channel=1,control=1,value=80,time=240),
                                 mido.Message('note_off',channel=0,note=60,time=1200)]),
                  mido.MidiTrack([mido.Message('note_on',channel=2,note=64,velocity=80),
                                 mido.Message('note_off',channel=2,note=64,time=1920)])]
    mid.save(p)
    return p, tmp_path/'new.mid'


def draw(paths, **kwargs):
    params = dict(track_index=1, channel=1, start_beat=1, end_beat=3,
                  pitch_curve=[[0,0],[.5,2],[1,0]], modulation_curve=[[0,30],[.5,90],[1,30]])
    params.update(kwargs)
    return draw_midi_track_expression(str(paths[0]),str(paths[1]),**params)


def test_target_track_only_notes_tempo_and_other_controls_preserved(midi):
    src, dst = midi; original = src.read_bytes()
    info = midi_track_info(str(src)); assert info['tracks'][1]['channels'] == [1,2]
    result = draw(midi,expected_sha256=info['sha256'])
    assert src.read_bytes() == original
    before, after = mido.MidiFile(src), mido.MidiFile(dst)
    assert before.tracks[0] == after.tracks[0] and before.tracks[2] == after.tracks[2]
    keep = lambda m: m.type in ('note_on','note_off','track_name','end_of_track') or (m.type=='control_change' and (m.control==64 or m.channel==1))
    assert [(t,m) for t,m in timeline(before.tracks[1]) if keep(m)] == [(t,m) for t,m in timeline(after.tracks[1]) if keep(m)]
    controls = [(t,m) for t,m in timeline(after.tracks[1]) if m.type=='control_change' and m.channel==0 and m.control==1]
    assert controls[-1][0] == 1440 and controls[-1][1].value == 30
    bends = [(t,m.pitch) for t,m in timeline(after.tracks[1]) if m.type=='pitchwheel']
    assert max(v for _,v in bends)==8191 and bends[-1]==(1440,0)
    assert result['cubase_part_modified'] is False


def test_replace_only_requested_controller_and_preserve_boundary(midi):
    with pytest.raises(ValueError, match='already exists'):
        draw(midi,start_beat=0)
    result = draw(midi,start_beat=0,replace_existing=True)
    assert result['replaced_events']==1
    with pytest.raises(ValueError, match='existing'):
        draw(midi)


@pytest.mark.parametrize('args', [dict(channel=0),dict(track_index=20),dict(end_beat=10),dict(pitch_curve=[[0,0],[1,3]]),dict(start_beat=float('nan')),dict(expected_sha256='changed')])
def test_invalid_input_never_writes(midi,args):
    with pytest.raises(ValueError): draw(midi,**args)
    assert not midi[1].exists()


def test_end_state_restores_existing_curve_state(midi):
    src,dst=midi
    mid=mido.MidiFile(src)
    mid.tracks[1].insert(4,mido.Message('pitchwheel',channel=0,pitch=-100,time=0))
    mid.save(src)
    result=draw(midi,replace_existing=True)
    assert result['restored_state']['pitch_bend']==-100
    bends=[m.pitch for m in mido.MidiFile(dst).tracks[1] if m.type=='pitchwheel']
    assert bends[-1]==-100


def test_midi_import_validates_file_and_reports_only_submission(midi,monkeypatch):
    calls=[]
    monkeypatch.setattr(audio_import,'_submit_cubase_file',lambda p,a: calls.append((p,a)) or {'status':'file_submitted','path':str(p)})
    result=audio_import.remote_import_midi(str(midi[0]))
    assert calls[0][1]=='import_midi'
    assert result['cubase_part_modified'] is None
    assert result['status']=='file_submitted'
    bad=midi[0].parent/'bad.mid';bad.write_text('not midi')
    with pytest.raises((ValueError,OSError,EOFError)): audio_import.remote_import_midi(str(bad))
    assert len(calls)==1


def test_midi_file_command_allowlist(monkeypatch):
    from cubasemixai.remote import client
    calls=[]
    class Host:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def request(self,op,args): calls.append((op,args));return {'queued':True}
    monkeypatch.setattr(client,'RemoteClient',Host)
    assert audio_import.remote_midi_file_command('export_midi')['file_completed'] is False
    with pytest.raises(ValueError): audio_import.remote_midi_file_command('record')
    assert len(calls)==1
