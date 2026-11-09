from pathlib import Path

import mido
import pytest

from cubasemixai.midi_expression import add_midi_expression


def _make_midi(path: Path):
    mid = mido.MidiFile(ticks_per_beat=480)
    tempo = mido.MidiTrack([mido.MetaMessage('set_tempo', tempo=500_000, time=0)])
    notes = mido.MidiTrack([
        mido.Message('note_on', channel=0, note=60, velocity=90, time=0),
        mido.Message('note_off', channel=0, note=60, velocity=0, time=960),
        mido.Message('note_on', channel=0, note=64, velocity=90, time=0),
        mido.Message('note_off', channel=0, note=64, velocity=0, time=960),
    ])
    mid.tracks.extend([tempo, notes])
    mid.save(path)


def test_creates_new_bounded_expression_copy(tmp_path):
    source, output = tmp_path / 'source.mid', tmp_path / 'expressive.mid'
    _make_midi(source)
    source_bytes = source.read_bytes()
    result = add_midi_expression(str(source), str(output), pitch_wander_cents=10,
                                 modulation_depth=32, aftertouch_depth=24, seed=42)
    assert source.read_bytes() == source_bytes
    assert result['notes'] == 2 and result['channel'] == 1
    messages = [msg for track in mido.MidiFile(output).tracks for msg in track]
    bends = [m.pitch for m in messages if m.type == 'pitchwheel']
    mod = [m.value for m in messages if m.type == 'control_change' and m.control == 1]
    pressure = [m.value for m in messages if m.type == 'aftertouch']
    assert bends and max(abs(x) for x in bends) <= round(10 / 200 * 8192)
    assert mod and max(mod) <= 32 and mod[-1] == 0
    assert pressure and max(pressure) <= 24 and pressure[-1] == 0
    assert bends[-1] == 0


def test_refuses_overwrite_and_existing_expression(tmp_path):
    source, output = tmp_path / 'source.mid', tmp_path / 'expressive.mid'
    _make_midi(source)
    with pytest.raises(ValueError, match='never overwritten'):
        add_midi_expression(str(source), str(source))
    add_midi_expression(str(source), str(output))
    with pytest.raises(ValueError, match='already exists'):
        add_midi_expression(str(source), str(output))

    expressive_source = tmp_path / 'has_pitch.mid'
    mid = mido.MidiFile()
    mid.tracks.append(mido.MidiTrack([
        mido.Message('pitchwheel', channel=0, pitch=20, time=0),
        mido.Message('note_on', channel=0, note=60, velocity=80, time=0),
        mido.Message('note_off', channel=0, note=60, velocity=0, time=480),
    ]))
    mid.save(expressive_source)
    with pytest.raises(ValueError, match='already contains pitch-bend'):
        add_midi_expression(str(expressive_source), str(tmp_path / 'out.mid'))
