"""Ocarina fingering data and MML -> tab conversion.

Maps MIDI note numbers to which holes of an ocarina are covered, so a
melody can be rendered as fingering tabs instead of (or alongside) MIDI.
Two instruments are supported, selected by ``hole_count`` on :func:`build_tab`:

- **12-hole** ("English pendant"), the default. Hole numbering, layout, and
  the note-to-fingering table are not guesswork: they're taken from the
  ``GLYPH_MAP``/``KEY_MAPS`` fingering data in Mathias Panzenböck's
  `Open 12 Hole Ocarina font and tab creator
  <https://github.com/panzi/ocarina_tabs>`_ (fonts/data licensed under the
  SIL Open Font License 1.1; per that license's own terms, documents
  produced using the font/data -- like the PDFs this module generates --
  are not themselves subject to it), cross-checked against Imperial City
  Ocarina's published 12-hole "Key of C" fingering charts. Holes are
  numbered 1-12: 1-7 and 10 are the 8 main top finger holes, 8 and 9 are
  the thumb holes (played from underneath), and 11-12 are the two small
  "subholes" that extend the range down a further two notes. Covers 21
  chromatic notes, A4 to F6.

- **6-hole**, a small pendant instrument reaching an octave plus a major
  third from 6 holes (4 in a top cluster, 2 more below/underneath), using
  half-covered holes for two of its notes. The fingering table is
  transcribed directly from `OcarinaSongbook.com's Six Hole Ocarina
  Fingering Chart <https://ocarinasongbook.com/fingering-charts/six-hole/>`_.
  Holes are numbered 1-4 for the top-left/top-right/bottom-left/bottom-right
  cluster and 5-6 for the two holes below it, matching that chart's own
  diagram layout, so a generated tab can be cross-checked directly against
  it. That chart doesn't name an absolute octave (small pendant ocarinas
  vary by maker), so this module treats its 17-note range as C5-E6 -- a
  reasonable default; the *pattern* of which holes to cover for the Nth
  note of the scale is what's authoritative, not the exact octave number
  printed under each icon.
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


# --- 6-hole fingering data ---------------------------------------------------
# Fill fraction per hole: 1.0 = fully covered, 0.5 = half-covered, and a hole
# absent from the dict is fully open. Holes are numbered 1=top-left,
# 2=top-right, 3=bottom-left, 4=bottom-right (the main 2x2 cluster), and
# 5/6 for the two holes below/underneath it, matching the reference chart's
# own diagram layout (see module docstring for provenance). Transcribed by
# visually reading that chart's fingering icons note by note, not guessed.
_HOLES_BY_LETTER_6H: dict[str, dict[int, float]] = {
    "A": {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0},  # C
    "B": {1: 1.0, 2: 0.5, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0},  # C#/Db
    "C": {1: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0},          # D
    "D": {1: 1.0, 2: 1.0, 3: 1.0, 4: 0.5, 5: 1.0, 6: 1.0},  # D#/Eb
    "E": {1: 1.0, 2: 1.0, 3: 1.0, 5: 1.0, 6: 1.0},          # E
    "F": {1: 1.0, 3: 1.0, 5: 1.0, 6: 1.0},                  # F
    "G": {2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0},          # F#/Gb
    "H": {3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0},                  # G
    "I": {2: 1.0, 3: 1.0, 5: 1.0, 6: 1.0},                  # G#/Ab
    "J": {3: 1.0, 5: 1.0, 6: 1.0},                          # A
    "K": {4: 1.0, 5: 1.0, 6: 1.0},                          # A#/Bb
    "L": {2: 1.0, 5: 1.0, 6: 1.0},                          # B
    "M": {5: 1.0, 6: 1.0},                                  # C (an octave up)
    "N": {4: 1.0, 5: 1.0},                                  # C#/Db (up)
    "O": {5: 1.0},                                          # D (up)
    "P": {4: 1.0},                                          # D#/Eb (up)
    "Q": {},                                                # E (up)
}

# Letters A..Q, in strict alphabetical order, correspond to ascending
# chromatic pitch starting at C5 (MIDI 72) -- see module docstring for why
# this octave is a default rather than a verified absolute pitch.
MIN_MIDI_NOTE_6H = 72  # C5
MAX_MIDI_NOTE_6H = MIN_MIDI_NOTE_6H + (ord("Q") - ord("A"))  # E6 (88)


def holes_for_note_6h(midi_note: int) -> dict[int, float] | None:
    """Fill fraction per hole for ``midi_note`` on a 6-hole ocarina, or None
    if it's outside C5-E6."""
    if not (MIN_MIDI_NOTE_6H <= midi_note <= MAX_MIDI_NOTE_6H):
        return None
    letter = chr(ord("A") + (midi_note - MIN_MIDI_NOTE_6H))
    return _HOLES_BY_LETTER_6H[letter]


@dataclass(frozen=True)
class TabNote:
    """One entry in an ocarina tab: either a note (with its original pitch,
    the pitch actually played after transposition, and a hole -> fill
    fraction map -- 1.0 covered, 0.5 half-covered, absent means open; or
    ``None`` if it's out of range even after transposing and octave-folding)
    or a rest (``midi_note is None``).

    ``octave_shift`` is nonzero when this note didn't fit the song's overall
    transposition and was individually moved by whole octaves to make it
    playable (see :func:`fold_into_range`) -- e.g. 1 means it now sounds an
    octave higher than the rest of the song's transposition would put it.
    """

    midi_note: int | None
    transposed_note: int | None
    holes: dict[int, float] | None
    duration_ticks: int
    octave_shift: int = 0


def best_transposition(
    midi_notes: list[int], min_midi: int = MIN_MIDI_NOTE, max_midi: int = MAX_MIDI_NOTE
) -> int:
    """Pick the octave shift (a multiple of 12 semitones) that fits the most
    notes into an instrument's [min_midi, max_midi] range (default: the
    12-hole ocarina's A4-F6)."""
    if not midi_notes:
        return 0

    best_shift = 0
    best_in_range = -1
    for octaves in range(-7, 8):
        shift = octaves * 12
        in_range = sum(1 for n in midi_notes if min_midi <= n + shift <= max_midi)
        if in_range > best_in_range or (
            in_range == best_in_range and abs(shift) < abs(best_shift)
        ):
            best_in_range = in_range
            best_shift = shift
    return best_shift


def fold_into_range(note: int, min_midi: int, max_midi: int) -> tuple[int, int] | None:
    """If ``note`` is outside [min_midi, max_midi], find the octave shift that
    brings it in. Returns ``(folded_note, octaves_shifted)``, or None if no
    whole-octave shift fits (only possible if the range is narrower than an
    octave, which no supported ocarina's is -- every pitch class appears at
    least once in each instrument's range)."""
    if min_midi <= note <= max_midi:
        return note, 0
    for octaves in range(1, 8):
        for direction in (1, -1):
            shift = direction * octaves * 12
            candidate = note + shift
            if min_midi <= candidate <= max_midi:
                return candidate, direction * octaves
    return None


def build_tab(
    mml_part_text: str, hole_count: int = 12, strip_check_note: bool = True,
    fold_octaves: bool = True,
) -> tuple[list[TabNote], int, int]:
    """Parse one MML part into a sequence of :class:`TabNote` entries.

    ``hole_count`` selects the instrument: 12 (the default, "English
    pendant") or 6 (a small pendant with 2 holes half-covered for two notes).

    A single transposition is chosen for the whole part to fit as many notes
    as possible into the instrument's range. Any note that still falls
    outside it (common when a song's range is wider than the instrument's)
    is, by default (``fold_octaves=True``), individually shifted by whole
    octaves until it fits -- see :func:`fold_into_range` and
    :attr:`TabNote.octave_shift`. Pass ``fold_octaves=False`` to leave such
    notes unplayable (``holes is None``) instead.

    Returns ``(tab_notes, transposition, tempo_bpm)``. Notes and rests are
    emitted in time order; a gap between the end of one event and the start
    of the next (or before the first note) becomes an explicit rest.
    """
    if hole_count == 12:
        min_midi, max_midi = MIN_MIDI_NOTE, MAX_MIDI_NOTE

        def lookup(note: int) -> dict[int, float] | None:
            holes = holes_for_note(note)
            return None if holes is None else {hole: 1.0 for hole in holes}
    elif hole_count == 6:
        min_midi, max_midi = MIN_MIDI_NOTE_6H, MAX_MIDI_NOTE_6H
        lookup = holes_for_note_6h
    else:
        raise ValueError(f"unsupported ocarina hole_count: {hole_count} (expected 6 or 12)")

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

    transposition = best_transposition([on.note for on, _off in pairs], min_midi, max_midi)

    tab: list[TabNote] = []
    cursor = 0
    for on, off in pairs:
        if on.time > cursor:
            tab.append(TabNote(None, None, None, on.time - cursor))
        duration = off.time - on.time
        transposed = on.note + transposition
        holes = lookup(transposed)
        octave_shift = 0

        if holes is None and fold_octaves:
            folded = fold_into_range(transposed, min_midi, max_midi)
            if folded is not None:
                transposed, octave_shift = folded
                holes = lookup(transposed)

        tab.append(TabNote(on.note, transposed, holes, duration, octave_shift))
        cursor = off.time

    return tab, transposition, tempo_bpm
