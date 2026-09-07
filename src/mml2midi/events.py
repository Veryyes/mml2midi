"""Intermediate, MIDI-library-agnostic event types produced by the parser.

Keeping these separate from :mod:`mido` means :mod:`mml2midi.parser` has no
dependency on the MIDI-writing layer and can be tested (and reused) on its
own.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NoteOn:
    """A note begins sounding at ``time`` ticks from the start of the part."""

    time: int
    note: int
    velocity: int


@dataclass(frozen=True)
class NoteOff:
    """A note stops sounding at ``time`` ticks from the start of the part."""

    time: int
    note: int


@dataclass(frozen=True)
class TempoChange:
    """A ``t`` command: from ``time`` onward the part plays at ``bpm``."""

    time: int
    bpm: int
