import pytest

from mml2midi.ocarina import (
    MAX_MIDI_NOTE,
    MAX_MIDI_NOTE_6H,
    MIN_MIDI_NOTE,
    MIN_MIDI_NOTE_6H,
    TabNote,
    best_transposition,
    build_tab,
    holes_for_note,
    holes_for_note_6h,
    note_name,
)


def test_range_is_a4_to_f6():
    assert note_name(MIN_MIDI_NOTE) == "A4"
    assert note_name(MAX_MIDI_NOTE) == "F6"
    assert MAX_MIDI_NOTE - MIN_MIDI_NOTE == 20  # 21 chromatic notes


def test_lowest_note_covers_all_twelve_holes():
    assert holes_for_note(MIN_MIDI_NOTE) == frozenset(range(1, 13))


def test_highest_note_covers_no_holes():
    assert holes_for_note(MAX_MIDI_NOTE) == frozenset()


def test_scale_opens_holes_in_the_standard_order():
    # C5 (all main holes + both thumb holes, no subholes) up through B5,
    # opening main holes 1 by 1 -- the standard diatonic fingering sequence.
    c5 = holes_for_note(72)
    d5 = holes_for_note(74)
    assert c5 == frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10})
    assert d5 == frozenset({2, 3, 4, 5, 6, 7, 8, 9, 10})
    assert c5 - d5 == {1}  # only hole 1 opens going from C5 to D5


def test_out_of_range_returns_none():
    assert holes_for_note(MIN_MIDI_NOTE - 1) is None
    assert holes_for_note(MAX_MIDI_NOTE + 1) is None


def test_best_transposition_picks_octave_shift_that_maximizes_in_range_notes():
    # A middle-C major scale (60-72) is mostly below A4=69; shifting up an
    # octave puts all of it inside A4-F6.
    notes = [60, 62, 64, 65, 67, 69, 71, 72]
    assert best_transposition(notes) == 12


def test_best_transposition_prefers_smaller_shift_on_a_tie():
    assert best_transposition([]) == 0


def test_build_tab_inserts_explicit_rests_for_gaps():
    tab, shift, bpm = build_tab("l8crc")  # note, rest, note
    assert [t.midi_note for t in tab] == [60, None, 60]
    assert bpm == 120


def test_build_tab_folds_out_of_range_notes_by_default():
    # A very wide-ranging part: the two notes are 8 octaves apart, so no
    # single global transposition can fit both -- but octave-folding brings
    # the loser into range individually instead of leaving it unplayable.
    tab, shift, _bpm = build_tab("o0co9c")  # a note far below range, one far above
    playable = [t for t in tab if t.midi_note is not None]
    assert all(t.holes is not None for t in playable)
    assert any(t.octave_shift != 0 for t in playable)


def test_build_tab_can_disable_octave_folding():
    tab, shift, _bpm = build_tab("o0co9c", fold_octaves=False)
    playable = [t for t in tab if t.midi_note is not None]
    assert any(t.holes is None for t in playable)  # at least one stays unplayable
    assert all(t.octave_shift == 0 for t in playable)  # never adjusted when disabled


def test_fold_into_range_returns_shift_in_octaves():
    from mml2midi.ocarina import fold_into_range

    # 36 (C3) is below A4-F6; folding up 3 octaves (36 semitones) lands at 72.
    assert fold_into_range(36, MIN_MIDI_NOTE, MAX_MIDI_NOTE) == (72, 3)
    # Already in range: no shift needed.
    assert fold_into_range(72, MIN_MIDI_NOTE, MAX_MIDI_NOTE) == (72, 0)


def test_build_tab_strips_check_note_like_parse_part_does():
    check = "c&" * 8
    tab, _shift, _bpm = build_tab(f"l64{check}l8d")
    # The check run becomes a silent rest (keeps its timing), then the real note.
    assert [t.midi_note for t in tab] == [None, 62]


def test_build_tab_rejects_unsupported_hole_count():
    with pytest.raises(ValueError):
        build_tab("c", hole_count=4)


# --- 6-hole ocarina ----------------------------------------------------
# Fingering data transcribed from OcarinaSongbook.com's Six Hole Ocarina
# Fingering Chart (see ocarina.py's docstring); holes are 1=top-left,
# 2=top-right, 3=bottom-left, 4=bottom-right for the main cluster, 5/6 for
# the two below it, matching that chart.


def test_6h_range_is_c5_to_e6():
    assert note_name(MIN_MIDI_NOTE_6H) == "C5"
    assert note_name(MAX_MIDI_NOTE_6H) == "E6"
    assert MAX_MIDI_NOTE_6H - MIN_MIDI_NOTE_6H == 16  # 17 chromatic notes


def test_6h_lowest_note_covers_all_six_holes():
    assert holes_for_note_6h(MIN_MIDI_NOTE_6H) == {
        1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0,
    }


def test_6h_highest_note_covers_no_holes():
    assert holes_for_note_6h(MAX_MIDI_NOTE_6H) == {}


def test_6h_half_covered_holes():
    # C#5 and D#5 are the two notes needing a half-covered hole on this chart.
    assert holes_for_note_6h(MIN_MIDI_NOTE_6H + 1) == {
        1: 1.0, 2: 0.5, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0,
    }
    assert holes_for_note_6h(MIN_MIDI_NOTE_6H + 3) == {
        1: 1.0, 2: 1.0, 3: 1.0, 4: 0.5, 5: 1.0, 6: 1.0,
    }


def test_6h_out_of_range_returns_none():
    assert holes_for_note_6h(MIN_MIDI_NOTE_6H - 1) is None
    assert holes_for_note_6h(MAX_MIDI_NOTE_6H + 1) is None


def test_build_tab_6h_uses_the_six_hole_range():
    tab, shift, _bpm = build_tab("cdefgab>c4.", hole_count=6)
    on_notes = [t.transposed_note for t in tab]
    assert all(MIN_MIDI_NOTE_6H <= n <= MAX_MIDI_NOTE_6H for n in on_notes)
    assert tab[0].holes == {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0}  # C, all covered
    assert tab[-1].holes == {5: 1.0, 6: 1.0}  # the octave C: only the two lower holes stay covered
