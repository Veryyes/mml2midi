"""12-hole ocarina fingering data and MML -> tab conversion.

Maps MIDI note numbers to which of a 12-hole ("English pendant") ocarina's
holes are covered, so a melody can be rendered as fingering tabs instead of
(or alongside) MIDI.

Hole numbering, layout, and the note-to-fingering table below are not
guesswork: they're taken from the ``GLYPH_MAP``/``KEY_MAPS`` fingering data in
Mathias Panzenböck's `Open 12 Hole Ocarina font and tab creator
<https://github.com/panzi/ocarina_tabs>`_ (fonts/data licensed under the SIL
Open Font License 1.1; per that license's own terms, documents produced using
the font/data -- like the PDFs this module generates -- are not themselves
subject to it), cross-checked against Imperial City Ocarina's published
12-hole "Key of C" fingering charts. Holes are numbered 1-12: 1-7 and 10 are
the 8 main top finger holes, 8 and 9 are the thumb holes (played from
underneath), and 11-12 are the two small "subholes" that extend the range
down a further two notes.

A 12-hole ocarina in the key of C covers 21 chromatic notes, A4 to F6.
"""

from __future__ import annotations

from dataclasses import dataclass

from .events import NoteOff, NoteOn, TempoChange
from .parser import DEFAULT_TEMPO_BPM, parse_part

# --- Fingering data ----------------------------------------------------------
# Hole sets per fingering letter (see module docstring for provenance).
# Holes are 1-12; a covered hole lowers the pitch.
_HOLES_BY_LETTER: dict[str, frozenset[int]] = {
    "A": frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}),
    "B": frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}),
    "C": frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12}),
    "D": frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10}),
    "E": frozenset({2, 3, 4, 5, 6, 7, 8, 9, 10, 12}),
    "F": frozenset({2, 3, 4, 5, 6, 7, 8, 9, 10}),
    "G": frozenset({3, 4, 5, 6, 7, 8, 9, 10, 12}),
    "H": frozenset({3, 4, 5, 6, 7, 8, 9, 10}),
    "I": frozenset({4, 5, 6, 7, 8, 9, 10}),
    "J": frozenset({2, 5, 6, 7, 8, 9, 10}),
    "K": frozenset({5, 6, 7, 8, 9, 10}),
    "L": frozenset({2, 6, 7, 8, 9, 10}),
    "M": frozenset({6, 7, 8, 9, 10}),
    "N": frozenset({2, 7, 8, 9, 10}),
    "O": frozenset({7, 8, 9, 10}),
    "P": frozenset({8, 9, 10}),
    "Q": frozenset({2, 9, 10}),
    "R": frozenset({9, 10}),
    "S": frozenset({2, 10}),
    "T": frozenset({10}),
    "U": frozenset(),
}

# Letters A..U, in strict alphabetical order, correspond to ascending
# chromatic pitch starting at A4 (MIDI 69): A=A4, B=A#4, C=B4, ..., U=F6.
MIN_MIDI_NOTE = 69  # A4
MAX_MIDI_NOTE = MIN_MIDI_NOTE + (ord("U") - ord("A"))  # F6 (89)

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

MAIN_HOLES = frozenset({1, 2, 3, 4, 5, 6, 7, 10})
THUMB_HOLES = frozenset({8, 9})
SUBHOLES = frozenset({11, 12})


def note_name(midi_note: int) -> str:
    """e.g. 69 -> 'A4' (using the same octave numbering as parser.py, C4=60)."""
    name = NOTE_NAMES[midi_note % 12]
    octave = midi_note // 12 - 1
    return f"{name}{octave}"


def holes_for_note(midi_note: int) -> frozenset[int] | None:
    """Covered holes for ``midi_note``, or None if it's outside A4-F6."""
    if not (MIN_MIDI_NOTE <= midi_note <= MAX_MIDI_NOTE):
        return None
    letter = chr(ord("A") + (midi_note - MIN_MIDI_NOTE))
    return _HOLES_BY_LETTER[letter]


@dataclass(frozen=True)
class TabNote:
    """One entry in an ocarina tab: either a note (with its original pitch,
    the pitch actually played after transposition, and its covered holes --
    or ``None`` for holes if it's out of range even after transposing) or a
    rest (``midi_note is None``)."""

    midi_note: int | None
    transposed_note: int | None
    holes: frozenset[int] | None
    duration_ticks: int


def best_transposition(midi_notes: list[int]) -> int:
    """Pick the octave shift (a multiple of 12 semitones) that fits the most
    notes into the ocarina's A4-F6 range."""
    if not midi_notes:
        return 0

    best_shift = 0
    best_in_range = -1
    for octaves in range(-7, 8):
        shift = octaves * 12
        in_range = sum(
            1 for n in midi_notes if MIN_MIDI_NOTE <= n + shift <= MAX_MIDI_NOTE
        )
        if in_range > best_in_range or (
            in_range == best_in_range and abs(shift) < abs(best_shift)
        ):
            best_in_range = in_range
            best_shift = shift
    return best_shift


def build_tab(
    mml_part_text: str, strip_check_note: bool = True
) -> tuple[list[TabNote], int, int]:
    """Parse one MML part into a sequence of :class:`TabNote` entries.

    Returns ``(tab_notes, transposition, tempo_bpm)``. Notes and rests are
    emitted in time order; a gap between the end of one event and the start
    of the next (or before the first note) becomes an explicit rest.
    """
    events, _end_time = parse_part(mml_part_text, strip_check_note=strip_check_note)
    tempo_bpm = next((e.bpm for e in events if isinstance(e, TempoChange)), DEFAULT_TEMPO_BPM)

    # A single part is monophonic (ties are already collapsed by the parser),
    # so at most one note is ever "on" at a time -- pair each NoteOn with the
    # next NoteOff by sequence position, not by time value (which could
    # coincide across unrelated notes).
    pairs: list[tuple[NoteOn, NoteOff]] = []
    pending: NoteOn | None = None
    for event in events:
        if isinstance(event, NoteOn):
            pending = event
        elif isinstance(event, NoteOff) and pending is not None:
            pairs.append((pending, event))
            pending = None

    transposition = best_transposition([on.note for on, _off in pairs])

    tab: list[TabNote] = []
    cursor = 0
    for on, off in pairs:
        if on.time > cursor:
            tab.append(TabNote(None, None, None, on.time - cursor))
        duration = off.time - on.time
        transposed = on.note + transposition
        tab.append(TabNote(on.note, transposed, holes_for_note(transposed), duration))
        cursor = off.time

    return tab, transposition, tempo_bpm
