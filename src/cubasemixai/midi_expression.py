"""Create a non-destructive MIDI copy with bounded performance expression."""
from __future__ import annotations

import math
import random
from pathlib import Path

import mido


def _timeline(mid: mido.MidiFile):
    """Return tempo-aware tick/second converters for a type 0/1 MIDI file."""
    changes = [(0, 500_000)]
    for track in mid.tracks:
        absolute = 0
        for msg in track:
            absolute += msg.time
            if msg.type == "set_tempo":
                changes.append((absolute, msg.tempo))
    changes.sort(key=lambda item: item[0])
    compact = []
    for tick, tempo in changes:
        if compact and compact[-1][0] == tick:
            compact[-1] = (tick, tempo)
        else:
            compact.append((tick, tempo))

    segments = []
    seconds = 0.0
    last_tick = 0
    tempo = 500_000
    for tick, next_tempo in compact:
        if tick > last_tick:
            segments.append((last_tick, tick, seconds, tempo))
            seconds += mido.tick2second(tick - last_tick, mid.ticks_per_beat, tempo)
            last_tick = tick
        tempo = next_tempo
    segments.append((last_tick, math.inf, seconds, tempo))

    def tick_to_seconds(tick: int) -> float:
        for start, end, base_sec, use_tempo in segments:
            if start <= tick < end or math.isinf(end):
                return base_sec + mido.tick2second(tick - start, mid.ticks_per_beat, use_tempo)
        raise ValueError("Cannot convert MIDI tick")

    def seconds_to_tick(value: float) -> int:
        for start, end, base_sec, use_tempo in segments:
            end_sec = math.inf if math.isinf(end) else base_sec + mido.tick2second(end - start, mid.ticks_per_beat, use_tempo)
            if base_sec <= value < end_sec or math.isinf(end_sec):
                return start + int(round(mido.second2tick(value - base_sec, mid.ticks_per_beat, use_tempo)))
        raise ValueError("Cannot convert MIDI time")

    return tick_to_seconds, seconds_to_tick


def add_midi_expression(
    input_midi: str,
    output_midi: str,
    *,
    channel: int = 0,
    pitch_wander_cents: float = 6.0,
    pitch_bend_range_semitones: float = 2.0,
    modulation_depth: int = 0,
    aftertouch_depth: int = 0,
    rate_hz: float = 8.0,
    seed: int = 1,
) -> dict:
    """Add deterministic, smoothed pitch/CC1/channel-pressure motion to a copy.

    The output is for manual import/routing in a DAW. MIDI pitch bend and
    channel pressure affect every sounding note on the selected channel.
    """
    source = Path(input_midi).expanduser().resolve()
    destination = Path(output_midi).expanduser().resolve()
    if source == destination:
        raise ValueError("Output must be a new file; the source MIDI is never overwritten")
    if not source.is_file():
        raise ValueError("Input MIDI file does not exist")
    if source.suffix.lower() not in {".mid", ".midi"} or destination.suffix.lower() not in {".mid", ".midi"}:
        raise ValueError("Input and output must use .mid or .midi filenames")
    if destination.exists():
        raise ValueError("Output already exists; choose a new filename")
    if not 0 <= channel <= 15:
        raise ValueError("MIDI channel must be 0–15")
    if not math.isfinite(pitch_wander_cents) or not 0 <= pitch_wander_cents <= 20:
        raise ValueError("Pitch wander must be between 0 and 20 cents")
    if not math.isfinite(pitch_bend_range_semitones) or not 1 <= pitch_bend_range_semitones <= 48:
        raise ValueError("Configured instrument pitch-bend range must be 1–48 semitones")
    if not 0 <= modulation_depth <= 127 or not 0 <= aftertouch_depth <= 127:
        raise ValueError("Modulation and aftertouch depths must be 0–127")
    if not math.isfinite(rate_hz) or not 2 <= rate_hz <= 20:
        raise ValueError("Expression rate must be between 2 and 20 Hz")

    mid = mido.MidiFile(source)
    tick_to_seconds, seconds_to_tick = _timeline(mid)
    for track in mid.tracks:
        for msg in track:
            if msg.type in {"pitchwheel", "aftertouch"} and msg.channel == channel:
                raise ValueError("Selected channel already contains pitch-bend or channel-pressure events")
            if msg.type == "control_change" and msg.channel == channel and msg.control == 1:
                raise ValueError("Selected channel already contains CC1 modulation events")
    track_notes: list[tuple[int, int, int]] = []
    chosen_track = None
    for track_index, track in enumerate(mid.tracks):
        absolute = 0
        active: dict[tuple[int, int], list[int]] = {}
        notes = []
        for msg in track:
            absolute += msg.time
            if msg.type in {"note_on", "note_off"} and msg.channel == channel:
                key = (msg.channel, msg.note)
                if msg.type == "note_on" and msg.velocity > 0:
                    active.setdefault(key, []).append(absolute)
                else:
                    starts = active.get(key)
                    if not starts:
                        raise ValueError("Selected track has an unmatched note-off")
                    notes.append((starts.pop(0), absolute, msg.note))
        if active and any(active.values()):
            raise ValueError("Selected track has an unmatched note-on")
        if notes:
            if chosen_track is not None:
                raise ValueError("Selected channel has notes in multiple tracks; combine/select one MIDI track first")
            chosen_track = track_index
            track_notes = notes
    if chosen_track is None:
        raise ValueError("No notes found on the selected MIDI channel")
    if pitch_wander_cents == 0 and modulation_depth == 0 and aftertouch_depth == 0:
        raise ValueError("Set at least one non-zero expression depth")

    intervals = [(tick_to_seconds(start), tick_to_seconds(end)) for start, end, _ in track_notes]
    duration = max(end for _, end in intervals)
    rng = random.Random(seed)
    step = 1.0 / rate_hz
    smooth = 0.0
    events: list[tuple[int, int, mido.Message]] = []
    point_count = int(math.ceil(duration / step)) + 1
    for i in range(point_count):
        when = min(i * step, duration)
        active = any(start <= when < end for start, end in intervals)
        if not active:
            continue
        smooth = 0.72 * smooth + 0.28 * rng.uniform(-1.0, 1.0)
        tick = seconds_to_tick(when)
        if pitch_wander_cents:
            cents = smooth * pitch_wander_cents
            raw = int(round(cents / (pitch_bend_range_semitones * 100.0) * 8192))
            events.append((tick, 1, mido.Message("pitchwheel", channel=channel, pitch=max(-8192, min(8191, raw)))))
        if modulation_depth:
            value = int(round((smooth + 1.0) * 0.5 * modulation_depth))
            events.append((tick, 2, mido.Message("control_change", channel=channel, control=1, value=max(0, min(127, value)))))
        if aftertouch_depth:
            value = int(round((smooth + 1.0) * 0.5 * aftertouch_depth))
            events.append((tick, 3, mido.Message("aftertouch", channel=channel, value=max(0, min(127, value)))) )

    def reset_expression(tick: int) -> None:
        if pitch_wander_cents:
            events.append((tick, 0, mido.Message("pitchwheel", channel=channel, pitch=0)))
        if modulation_depth:
            events.append((tick, 0, mido.Message("control_change", channel=channel, control=1, value=0)))
        if aftertouch_depth:
            events.append((tick, 0, mido.Message("aftertouch", channel=channel, value=0)))

    # Clear expression at the edges of sounding regions so a following note
    # does not inherit the previous note's final bend/pressure value.
    for start, end in intervals:
        sounding_before = any(other_start < start < other_end for other_start, other_end in intervals)
        sounding_after = any(other_start <= end < other_end for other_start, other_end in intervals)
        if not sounding_before:
            reset_expression(seconds_to_tick(start))
        if not sounding_after:
            reset_expression(seconds_to_tick(end))
    track = mid.tracks[chosen_track]
    original = []
    absolute = 0
    for order, msg in enumerate(track):
        absolute += msg.time
        original.append((absolute, 10 + order, msg.copy()))
    merged = sorted(original + events, key=lambda item: (item[0], item[1]))
    rebuilt = []
    previous = 0
    for tick, _, msg in merged:
        msg.time = tick - previous
        rebuilt.append(msg)
        previous = tick
    mid.tracks[chosen_track] = mido.MidiTrack(rebuilt)
    destination.parent.mkdir(parents=True, exist_ok=True)
    mid.save(destination)
    return {
        "input": str(source), "output": str(destination), "track_index": chosen_track,
        "channel": channel + 1, "notes": len(track_notes), "expression_events": len(events),
        "pitch_wander_cents_max": pitch_wander_cents,
        "pitch_bend_range_semitones_assumed": pitch_bend_range_semitones,
        "modulation_depth_max": modulation_depth, "aftertouch_depth_max": aftertouch_depth,
        "rate_hz": rate_hz, "seed": seed,
        "warning": "Pitch bend, CC1 and channel aftertouch affect all simultaneous notes on this MIDI channel; import and audition the new file before replacing anything.",
    }
