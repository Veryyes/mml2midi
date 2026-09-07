"""Parser for Mabinogi Music Language (MML).

MML is the text format the in-game Compose skill turns sheet music into. A
full score looks like::

    MML@<melody>,<harmony 1>,<harmony 2>;

The three comma-separated parts play simultaneously; each is its own
sequence of tokens:

===============  ============================================================
Token            Meaning
===============  ============================================================
``a``-``g``      Play that note in the current octave (case-insensitive).
``+`` / ``#``    Sharp, attached to a note (``c+``, ``d#``).
``-``            Flat, attached to a note (``e-``).
``r``            Rest.
``n<0-96>``      Play an absolute chromatic pitch directly, bypassing octave
                 and accidentals (duration is still the current default
                 length -- the number here is a pitch, not a length).
``<number>``     Attached to a note/rest, sets its length as 1/number of a
                 whole note (``c4`` = quarter note), overriding the default
                 for that token only. Valid range is 1-192.
``.``            Attached to a note/rest, extends its length by 50%.
``&``            Attached to a note, ties it to the next occurrence of the
                 same pitch (sustain without re-striking).
``o<0-9>``       Set the current octave outright (default 4, i.e. middle C
                 is ``o4c``).
``<`` / ``>``    Shift the current octave down/up by one, clamped to 0-9.
``l<number>``    Set the default note length used by notes/rests that don't
                 specify their own (``.`` is honoured here too).
``t<number>``    Set the tempo in BPM from this point on.
``v<1-15>``      Set the volume/velocity used by subsequent notes.
===============  ============================================================

Whitespace is ignored, MML is case-insensitive, and unrecognised characters
are simply skipped.

This grammar and the arithmetic below (tick values, the octave-wrap rule,
tie handling, ``n`` semantics) were cross-checked against the Mabinogi World
Wiki's MML page and against two independent open-source Mabinogi MML->MIDI
converters (rajephon/YKSConverter, itself a port of logue/PSGConverter) to
make sure this implementation matches real Mabinogi output, not just a
generic MML dialect.
"""

from __future__ import annotations

import re

from .events import NoteOff, NoteOn, TempoChange

# --- Timing -----------------------------------------------------------------
# 96 ticks per quarter note keeps every length in the 1-192 range (including
# dotted lengths) an exact integer number of ticks.
TICKS_PER_WHOLE_NOTE = 384
TICKS_PER_HALF_NOTE = 192
TICKS_PER_QUARTER_NOTE = 96
MAX_LENGTH_VALUE = TICKS_PER_HALF_NOTE  # largest denominator 'l'/note lengths accept

# --- Octave -------------------------------------------------------------
DEFAULT_OCTAVE = 4
MIN_OCTAVE = 0
MAX_OCTAVE = 9

# --- Volume / velocity --------------------------------------------------
DEFAULT_VOLUME = 8
MIN_VOLUME = 1
MAX_VOLUME = 15
VELOCITY_MULTIPLIER = 8

# --- Note range -----------------------------------------------------------
# Notes are computed relative to octave 0 and then wrapped into this window
# before a final +12 offset is applied. This mirrors a real quirk of
# Mabinogi's own tone generator: a note built from an out-of-range octave or
# accidental doesn't get clipped, it wraps by octaves until it lands back in
# range.
NOTE_RANGE_MIN = 0
NOTE_RANGE_MAX = 96
FINAL_NOTE_OFFSET = 12

DEFAULT_TEMPO_BPM = 120

SEMITONES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

# --- "Skill roll" check note ------------------------------------------------
# Composing in Mabinogi is a skill roll, and the roll's outcome affects the
# piece's quality. Some real scores open a part with the same note tied to
# itself many times over at a tiny length (e.g. "l64c&c&c&...&c") purely so
# the performer can see/hear whether that roll succeeded before the actual
# song plays -- it's a UI convenience, not music. Real compositions have no
# reason to ever tie an identical pitch to itself this many times in a row
# (a single longer note length says the same thing), so requiring a long run
# safely tells this apart from a genuine short tie like "c4&c4".
MIN_CHECK_NOTE_REPEATS = 8

_TOKEN_RE = re.compile(r"[A-GNOTLVR<>][+\-#]?[0-9]*\.?&?", re.IGNORECASE)
_CONTROL_RE = re.compile(r"^([LOTV<>])([1-9][0-9]*|0)?(\.?)(&?)$", re.IGNORECASE)
_NOTE_RE = re.compile(r"^([A-GN])([+\-#]?)([0-9]*)(\.?)(&?)$", re.IGNORECASE)
_REST_RE = re.compile(r"^R([0-9]*)(\.?)$", re.IGNORECASE)


class MMLParseError(ValueError):
    """Raised when a string isn't well-formed MML."""


def parse_score(text: str) -> list[str]:
    """Split an ``MML@<melody>,<harmony1>,<harmony2>;`` string into its parts.

    Surrounding text (e.g. a title line copied along with the score) is
    tolerated -- only the ``MML@...;`` substring is used.
    """
    header = re.search(r"MML@", text, re.IGNORECASE)
    if not header:
        raise MMLParseError("no 'MML@' header found")

    rest = text[header.end():]
    terminator = rest.find(";")
    if terminator == -1:
        raise MMLParseError("missing terminating ';'")

    parts = rest[:terminator].split(",")
    if len(parts) > 3:
        raise MMLParseError(
            "expected at most 3 comma-separated parts (melody, harmony 1, harmony 2), "
            f"got {len(parts)}"
        )
    # Real-world pastes sometimes drop trailing empty harmony slots entirely
    # (e.g. "MML@melody;" or "MML@melody,harmony1;") rather than writing them
    # out as "MML@melody,,;" -- treat a missing part as silence.
    parts += [""] * (3 - len(parts))
    return parts


def _wrap_note(note: int) -> int:
    """Fold ``note`` into [NOTE_RANGE_MIN, NOTE_RANGE_MAX] by octave steps."""
    if note < NOTE_RANGE_MIN:
        steps = -(-(NOTE_RANGE_MIN - note) // 12)  # ceil division
        note += 12 * steps
    elif note > NOTE_RANGE_MAX:
        steps = -(-(note - NOTE_RANGE_MAX) // 12)
        note -= 12 * steps
    return note


def _length_to_ticks(length_str: str, dot: str, current_default: int) -> int:
    ticks = current_default
    if length_str:
        value = int(length_str)
        if 1 <= value <= MAX_LENGTH_VALUE:
            ticks = TICKS_PER_WHOLE_NOTE // value
    if dot:
        ticks = int(ticks * 1.5)
    return ticks


def _find_leading_check_note(tokens: list[str]) -> tuple[int, int]:
    """Find a leading skill-roll check run in ``tokens``.

    Returns ``(start, end)`` token indices to suppress (``(0, 0)`` if there's
    no qualifying run). Only pure control tokens (``l``/``o``/``v``/``t``/
    ``<``/``>``) and rests may precede the run -- the first real note found
    either starts a long enough identical tied-note run, or the part has no
    check note at all.
    """
    i = 0
    while i < len(tokens) and (_CONTROL_RE.match(tokens[i]) or _REST_RE.match(tokens[i])):
        i += 1
    start = i
    if start >= len(tokens):
        return 0, 0

    first = _NOTE_RE.match(tokens[start])
    if not first or first.group(1).lower() == "n":
        return 0, 0
    key = (first.group(1).lower(), first.group(2))

    end = start
    j = start
    while j < len(tokens):
        m = _NOTE_RE.match(tokens[j])
        if not m or (m.group(1).lower(), m.group(2)) != key:
            break
        end = j + 1
        tied = bool(m.group(5))
        j += 1
        if not tied:
            break  # the tie chain closes here; a repeat right after would be a new, coincidental run

    if end - start < MIN_CHECK_NOTE_REPEATS:
        return 0, 0
    return start, end


def parse_part(
    text: str, strip_check_note: bool = True
) -> tuple[list[NoteOn | NoteOff | TempoChange], int]:
    """Parse one melody/harmony part into a time-ordered list of events.

    Returns ``(events, end_time)``; ``end_time`` is the tick position after
    the last note/rest plus one trailing default-length tick, which is a
    convenient track length for a MIDI writer.

    If ``strip_check_note`` is true (the default), a leading "skill roll
    check" run (see :data:`MIN_CHECK_NOTE_REPEATS`) is silenced: it still
    takes up its original duration, so the rest of the part -- and the other
    parts of the score -- stay in sync, but it produces no MIDI note.
    """
    clean = re.sub(r"\s+", "", text)
    tokens = _TOKEN_RE.findall(clean)
    check_start, check_end = _find_leading_check_note(tokens) if strip_check_note else (0, 0)

    length_ticks = TICKS_PER_QUARTER_NOTE
    octave = DEFAULT_OCTAVE
    volume = DEFAULT_VOLUME
    tied_note: int | None = None

    events: list[NoteOn | NoteOff | TempoChange] = []
    time = 0

    for index, token in enumerate(tokens):
        control = _CONTROL_RE.match(token)
        if control:
            op, value_str, dot, _tie = control.groups()
            op = op.lower()
            value = int(value_str) if value_str else 0

            if op == "l":
                if 0 < value <= MAX_LENGTH_VALUE:
                    length_ticks = TICKS_PER_WHOLE_NOTE // value
                    if dot:
                        length_ticks = int(length_ticks * 1.5)
            elif op == "o":
                octave = min(max(value, MIN_OCTAVE), MAX_OCTAVE)
            elif op == "t":
                if value > 0:
                    events.append(TempoChange(time, value))
            elif op == "v":
                volume = min(max(value, MIN_VOLUME), MAX_VOLUME)
            elif op == "<":
                octave = max(octave - 1, MIN_OCTAVE)
            elif op == ">":
                octave = min(octave + 1, MAX_OCTAVE)
            continue

        note_match = _NOTE_RE.match(token)
        if note_match:
            letter, accidental, length_str, dot, tie = note_match.groups()
            letter = letter.lower()

            if letter == "n":
                # The trailing number is a raw chromatic pitch (0-96), not a
                # length -- duration stays at the current default.
                note = 0
                if length_str:
                    candidate = int(length_str)
                    if 0 <= candidate <= NOTE_RANGE_MAX:
                        note = candidate
                duration = length_ticks
            else:
                duration = _length_to_ticks(length_str, dot, length_ticks)
                note = 12 * octave + SEMITONES[letter]
                if accidental in ("+", "#"):
                    note += 1
                elif accidental == "-":
                    note -= 1

            note = _wrap_note(note) + FINAL_NOTE_OFFSET

            if check_start <= index < check_end:
                # Part of a detected skill-roll check run: keep its timing so
                # the part (and its siblings) don't drift, emit no sound.
                time += duration
                continue

            if tied_note is not None and note != tied_note:
                events.append(NoteOff(time, tied_note))
                tied_note = None

            if tied_note is None:
                events.append(NoteOn(time, note, volume * VELOCITY_MULTIPLIER))

            time += duration

            if tie:
                tied_note = note
            else:
                events.append(NoteOff(time, note))
                tied_note = None
            continue

        rest_match = _REST_RE.match(token)
        if rest_match:
            length_str, dot = rest_match.groups()
            time += _length_to_ticks(length_str, dot, length_ticks)
            continue

        # _TOKEN_RE only ever matches text that one of the three patterns
        # above also matches, so this point is unreachable.
        raise AssertionError(f"unclassifiable MML token: {token!r}")

    if tied_note is not None:
        events.append(NoteOff(time, tied_note))
        time_end = time
    else:
        time_end = time

    time_end += length_ticks  # trailing tail so a track isn't cut off abruptly
    return events, time_end
