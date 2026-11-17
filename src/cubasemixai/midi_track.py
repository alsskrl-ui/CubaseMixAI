"""Track-scoped MIDI controller editing via non-destructive Standard MIDI Files."""
import math
from pathlib import Path

import mido

from .analysis import fingerprint
from .midi_expression import _validate_curve, _curve_value


def _read(path):
    path = Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower() not in {'.mid', '.midi'} or path.stat().st_size > 64*1024*1024:
        raise ValueError('Use a MIDI file no larger than 64 MB')
    digest = fingerprint(str(path))
    mid = mido.MidiFile(path)
    if mid.type not in (0, 1) or not 1 <= mid.ticks_per_beat <= 32767:
        raise ValueError('Only type 0/1 MIDI with PPQN timing is supported')
    if fingerprint(str(path)) != digest:
        raise ValueError('MIDI source changed while reading')
    return path, digest, mid


def midi_track_info(input_midi: str) -> dict:
    """List file track indices, channels (1..16), lengths and existing expression before editing."""
    path, digest, mid = _read(input_midi)
    tracks = []
    for index, track in enumerate(mid.tracks):
        counts = {'pitch_bend': 0, 'modulation': 0, 'aftertouch': 0}
        channels = set()
        for msg in track:
            if hasattr(msg, 'channel'): channels.add(msg.channel+1)
            control = _control(msg)
            if control: counts[control] += 1
        tracks.append({'track_index': index, 'name': track.name, 'channels': sorted(channels),
                       'duration_beats': sum(msg.time for msg in track)/mid.ticks_per_beat,
                       'note_count': sum(msg.type == 'note_on' and msg.velocity > 0 for msg in track),
                       'expression_counts': counts})
    return {'path': str(path), 'sha256': digest, 'type': mid.type, 'ticks_per_beat': mid.ticks_per_beat,
            'tracks': tracks, 'timing': 'Zero-based quarter-note beats from the exported MIDI file origin, not Cubase bar numbers.'}


def _control(msg):
    if msg.type == 'pitchwheel': return 'pitch_bend'
    if msg.type == 'aftertouch': return 'aftertouch'
    if msg.type == 'control_change' and msg.control == 1: return 'modulation'
    return None


def draw_midi_track_expression(input_midi: str, output_midi: str, track_index: int,
                               channel: int, start_beat: float, end_beat: float,
                               pitch_curve: list[list[float]] | None = None,
                               modulation_curve: list[list[float]] | None = None,
                               aftertouch_curve: list[list[float]] | None = None,
                               pitch_bend_range_semitones: float = 2.0,
                               steps_per_beat: int = 32, replace_existing: bool = False,
                               expected_sha256: str | None = None) -> dict:
    """Draw curves into ONE exported MIDI track/channel and save a new file, never edit a live Cubase part.

    channel is 1..16; track_index is zero-based from midi_track_info. Beats are zero-based
    quarter notes relative to the MIDI file, preserving tempo/time-signature maps.
    Curves: [[0,value],...,[1,value]]; pitch values are SEMITONES, CC1/pressure 0..127.
    Only requested controllers in [start_beat,end_beat) are replaced when explicitly enabled.
    The prior controller state is restored at end_beat, preserving subsequent material.
    Instrument bend range must match; no RPN or instrument setting is changed.
    """
    source, digest, mid = _read(input_midi)
    dest = Path(output_midi).expanduser().resolve()
    if dest == source or dest.exists() or dest.suffix.lower() not in {'.mid', '.midi'}:
        raise ValueError('Choose a new .mid/.midi output; never overwrite the original or an existing file')
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('MIDI source no longer matches the inspected hash')
    if type(track_index) is not int or not 0 <= track_index < len(mid.tracks):
        raise ValueError('Invalid track_index')
    if type(channel) is not int or not 1 <= channel <= 16:
        raise ValueError('Channel must be 1..16')
    if type(steps_per_beat) is not int or not 1 <= steps_per_beat <= 128:
        raise ValueError('steps_per_beat must be 1..128')
    if type(replace_existing) is not bool:
        raise ValueError('replace_existing must be boolean')
    for value in (start_beat, end_beat, pitch_bend_range_semitones):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Timing and bend range must be finite')
    if not 0 <= start_beat < end_beat or not 1 <= pitch_bend_range_semitones <= 48:
        raise ValueError('Invalid range; bend range must be 1..48 semitones')
    curves = {'pitch_bend': _validate_curve(pitch_curve, 'pitch_curve', -pitch_bend_range_semitones, pitch_bend_range_semitones),
              'modulation': _validate_curve(modulation_curve, 'modulation_curve', 0, 127),
              'aftertouch': _validate_curve(aftertouch_curve, 'aftertouch_curve', 0, 127)}
    curves = {k: v for k, v in curves.items() if v is not None}
    if not curves: raise ValueError('Specify at least one curve')
    track = mid.tracks[track_index]
    duration = sum(m.time for m in track)
    start, end = round(start_beat*mid.ticks_per_beat), round(end_beat*mid.ticks_per_beat)
    if not 0 <= start < end <= duration:
        raise ValueError('Range exceeds selected track duration or is shorter than one tick')
    channel -= 1
    if not any(getattr(m, 'channel', None) == channel for m in track):
        raise ValueError('Selected track has no events on this channel')
    samples = math.ceil((end_beat-start_beat)*steps_per_beat)
    if (samples+65)*len(curves) > 100000:
        raise ValueError('Curve exceeds 100000-event limit; shorten range or reduce density')
    original, tick, removed = [], 0, 0
    restore = {name: 0 for name in curves}
    for order, msg in enumerate(track):
        tick += msg.time
        control = _control(msg) if getattr(msg, 'channel', None) == channel else None
        if control in curves and tick <= end:
            restore[control] = msg.pitch if control == 'pitch_bend' else msg.value
        if control in curves and start <= tick < end:
            if not replace_existing:
                raise ValueError('Requested controller already exists in range; explicitly enable replace_existing')
            removed += 1
            continue
        if msg.type != 'end_of_track': original.append((tick, 2, order, msg.copy()))
    events = []
    for name, points in curves.items():
        positions = {i/samples for i in range(samples+1)} | {x for x, _ in points}
        by_tick = {}
        for x in sorted(positions):
            # The final point occupies the last tick; boundary restores old state.
            when = min(end-1, start+round(x*(end-start)))
            value = _curve_value(points, x)
            if name == 'pitch_bend':
                raw = max(-8192, min(8191, round(value/pitch_bend_range_semitones*8192)))
                msg = mido.Message('pitchwheel', channel=channel, pitch=raw)
            else:
                msg = (mido.Message('control_change', channel=channel, control=1, value=round(value))
                       if name == 'modulation' else mido.Message('aftertouch', channel=channel, value=round(value)))
            by_tick[when] = msg
        for when, msg in sorted(by_tick.items()): events.append((when, 0, len(events), msg))
        reset = (mido.Message('pitchwheel', channel=channel, pitch=restore[name]) if name == 'pitch_bend' else
                 mido.Message('control_change', channel=channel, control=1, value=restore[name]) if name == 'modulation' else
                 mido.Message('aftertouch', channel=channel, value=restore[name]))
        events.append((end, 1, len(events), reset))
    rebuilt, previous = mido.MidiTrack(), 0
    for tick, _, _, msg in sorted(original+events, key=lambda e: e[:3]):
        rebuilt.append(msg.copy(time=tick-previous)); previous = tick
    rebuilt.append(mido.MetaMessage('end_of_track', time=duration-previous))
    mid.tracks[track_index] = rebuilt
    if fingerprint(str(source)) != digest:
        raise ValueError('MIDI source changed during editing')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('xb') as output: mid.save(file=output)
    return {'input': str(source), 'input_sha256': digest, 'output': str(dest), 'output_sha256': fingerprint(str(dest)),
            'track_index': track_index, 'channel': channel+1, 'start_beat': start_beat, 'end_beat': end_beat,
            'created_events': len(events), 'replaced_events': removed, 'restored_state': restore,
            'pitch_bend_range_semitones_assumed': pitch_bend_range_semitones,
            'cubase_part_modified': False,
            'next': 'Use remote_import_midi to submit the file; verify placement/routing and avoid duplicate notes in Cubase.',
            'warning': 'Controllers affect all notes on their routed MIDI channel. Match instrument bend range; CC1/pressure support depends on the instrument.'}
