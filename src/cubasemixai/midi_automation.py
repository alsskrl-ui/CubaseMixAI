"""Generate standalone, controller-only MIDI automation in musical bar time."""
import math
from pathlib import Path

import mido


def create_midi_automation(
    output_midi: str,
    cc_number: int,
    start_bar: int,
    end_bar: int,
    curve: str = 'linear',
    start_value: int = 0,
    end_value: int = 127,
    channel: int = 1,
    tempo_bpm: float = 120.0,
    numerator: int = 4,
    denominator: int = 4,
    steps_per_beat: int = 32,
    exponent: float = 2.0,
    cycles: float = 1.0,
    ticks_per_beat: int = 480,
) -> dict:
    """Create a NEW .mid containing CC automation, without notes or live Cubase edits.

    Bars are 1-based; end_bar is EXCLUSIVE (start=5,end=9 covers bars 5..8).
    Positions are absolute from bar 1, with one constant time signature and tempo.
    channel is 1..16; cc_number and values are 0..127. linear interpolates endpoints;
    exponential uses t**exponent (supports zero and descending ramps); sine oscillates
    from start_value toward end_value and back using (1-cos(2*pi*cycles*t))/2.
    steps_per_beat is samples per QUARTER NOTE, not per denominator beat.
    Final CC is emitted at end_bar; it holds until another MIDI event changes it.
    Import at project origin to preserve bar placement. Cubase import may create a
    new track: confirm routing and tempo options. No existing file is overwritten.
    """
    def integer(value, low, high, name):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{name} must be an integer in {low}..{high}')
    integer(start_bar, 1, 1000000, 'start_bar')
    integer(end_bar, 2, 1000000, 'end_bar')
    if end_bar <= start_bar:
        raise ValueError('end_bar must be greater than start_bar (exclusive end)')
    integer(cc_number, 0, 127, 'cc_number')
    integer(channel, 1, 16, 'channel')
    integer(start_value, 0, 127, 'start_value')
    integer(end_value, 0, 127, 'end_value')
    integer(numerator, 1, 32, 'numerator')
    if type(denominator) is not int or denominator not in {1, 2, 4, 8, 16, 32}:
        raise ValueError('denominator must be 1,2,4,8,16,32')
    integer(steps_per_beat, 1, 128, 'steps_per_beat')
    integer(ticks_per_beat, 24, 32767, 'ticks_per_beat')
    for value, low, high, name in ((tempo_bpm, 4, 1000, 'tempo_bpm'),
                                   (exponent, .1, 16, 'exponent'), (cycles, .01, 1000, 'cycles')):
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{name} must be finite and in {low}..{high}')
    if curve not in {'linear', 'exponential', 'sine'}:
        raise ValueError('curve must be linear, exponential or sine')
    beats_per_bar = numerator * 4 / denominator
    duration_beats = (end_bar-start_bar)*beats_per_bar
    steps = math.ceil(duration_beats*steps_per_beat)
    if steps+1 > 100000:
        raise ValueError('Curve exceeds 100000 events; reduce range or density')
    if curve == 'sine' and steps < 8*cycles:
        raise ValueError('Sine requires at least 8 samples per cycle; increase density')
    start_tick = round((start_bar-1)*beats_per_bar*ticks_per_beat)
    end_tick = round((end_bar-1)*beats_per_bar*ticks_per_beat)
    if end_tick > 0x0FFFFFFF:
        raise ValueError('Absolute MIDI range exceeds the supported tick limit')
    if curve == 'sine' and (end_tick-start_tick) < 8*cycles:
        raise ValueError('Insufficient tick resolution for sine cycles')
    destination = Path(output_midi).expanduser().resolve()
    if destination.suffix.lower() not in {'.mid', '.midi'} or destination.exists():
        raise ValueError('Choose a new .mid/.midi output path')
    mid = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    mid.tracks.append(mido.MidiTrack([
        mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo_bpm)),
        mido.MetaMessage('time_signature', numerator=numerator, denominator=denominator),
        mido.MetaMessage('end_of_track', time=end_tick),
    ]))
    track = mido.MidiTrack([mido.MetaMessage('track_name', name=f'CC{cc_number} {curve}')])
    by_tick = {}
    for i in range(steps+1):
        t = i/steps
        weight = t if curve == 'linear' else t**exponent if curve == 'exponential' else (1-math.cos(2*math.pi*cycles*t))/2
        value = max(0, min(127, round(start_value+(end_value-start_value)*weight)))
        by_tick[round(start_tick+(end_tick-start_tick)*t)] = value
    previous = 0
    for tick, value in sorted(by_tick.items()):
        track.append(mido.Message('control_change', channel=channel-1, control=cc_number, value=value, time=tick-previous))
        previous = tick
    track.append(mido.MetaMessage('end_of_track'))
    mid.tracks.append(track)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        mid.save(file=stream)
    return {'output': str(destination), 'curve': curve, 'cc_number': cc_number, 'channel': channel,
            'start_bar': start_bar, 'end_bar_exclusive': end_bar, 'start_tick': start_tick, 'end_tick': end_tick,
            'event_count': len(by_tick), 'first_value': by_tick[start_tick], 'last_value': by_tick[end_tick],
            'time_signature': f'{numerator}/{denominator}', 'tempo_bpm': tempo_bpm,
            'cubase_part_modified': False,
            'next': 'Import at project origin via remote_import_midi; confirm instrument routing and tempo/meter options. Final CC value is held.'}
