"""Turn parsed MML events into a Standard MIDI File via :mod:`mido`."""

from __future__ import annotations

import mido

from .events import NoteOff, NoteOn, TempoChange
from .parser import DEFAULT_TEMPO_BPM, parse_part, parse_score

TICKS_PER_BEAT = 96  # matches the tick arithmetic in parser.py
DEFAULT_PROGRAM = 0  # General MIDI: Acoustic Grand Piano


def _build_track(
    part_text: str, program: int, channel: int, want_default_tempo: bool, strip_check_note: bool
) -> mido.MidiTrack:
    events, _end_time = parse_part(part_text, strip_check_note=strip_check_note)

    track = mido.MidiTrack()
    track.append(mido.Message("program_change", program=program, channel=channel, time=0))

    has_leading_tempo = any(isinstance(e, TempoChange) and e.time == 0 for e in events)
    if want_default_tempo and not has_leading_tempo:
        track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(DEFAULT_TEMPO_BPM), time=0))

    ordered: list[tuple[int, mido.Message | mido.MetaMessage]] = []
    for event in events:
        if isinstance(event, TempoChange):
            ordered.append((event.time, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(event.bpm))))
        elif isinstance(event, NoteOn):
            ordered.append(
                (event.time, mido.Message("note_on", note=event.note, velocity=event.velocity, channel=channel))
            )
        elif isinstance(event, NoteOff):
            ordered.append((event.time, mido.Message("note_off", note=event.note, velocity=0, channel=channel)))

    ordered.sort(key=lambda pair: pair[0])  # stable: ties keep insertion order

    last_time = 0
    for time, message in ordered:
        message.time = time - last_time
        track.append(message)
        last_time = time

    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def build_midi_multi(
    mml_texts: list[str], programs: list[int], strip_check_note: bool = True
) -> mido.MidiFile:
    """Convert several ``MML@...;`` voices into one multi-track MIDI file.

    Each voice becomes 3 MIDI tracks (melody, harmony 1, harmony 2) sharing
    one MIDI channel (voices cycle through channels 0-15). ``programs[i]``
    is the General MIDI program number used for voice ``i``.

    ``strip_check_note`` (default true) silences a leading "skill roll
    check" run in any part -- see :func:`mml2midi.parser.parse_part`.
    """
    if len(mml_texts) != len(programs):
        raise ValueError("mml_texts and programs must have the same length")

    midi_file = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)

    is_first_track = True
    for voice_index, (mml_text, program) in enumerate(zip(mml_texts, programs)):
        parts_text = parse_score(mml_text)
        channel = voice_index % 16
        for part_text in parts_text:
            track = _build_track(
                part_text, program, channel, want_default_tempo=is_first_track,
                strip_check_note=strip_check_note,
            )
            midi_file.tracks.append(track)
            is_first_track = False

    return midi_file


def build_midi(
    mml_text: str, program: int = DEFAULT_PROGRAM, strip_check_note: bool = True
) -> mido.MidiFile:
    """Convert a single ``MML@...;`` string into a 3-track MIDI file."""
    return build_midi_multi([mml_text], [program], strip_check_note=strip_check_note)


def write_midi_file(
    mml_text: str, output_path, program: int = DEFAULT_PROGRAM, strip_check_note: bool = True
) -> None:
    """Convert ``mml_text`` and save it to ``output_path``."""
    build_midi(mml_text, program=program, strip_check_note=strip_check_note).save(output_path)
