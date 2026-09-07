from mml2midi.ocarina import (
    MAX_MIDI_NOTE,
    MIN_MIDI_NOTE,
    TabNote,
    best_transposition,
    build_tab,
    holes_for_note,
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


def test_build_tab_marks_unplayable_notes_after_transposition():
    # A very wide-ranging part: most fits after transposition, some doesn't.
    tab, shift, _bpm = build_tab("o0co9c")  # a note far below range, one far above
    playable = [t for t in tab if t.midi_note is not None]
    assert any(t.holes is None for t in playable)  # at least one stays unplayable


def test_build_tab_strips_check_note_like_parse_part_does():
    check = "c&" * 8
    tab, _shift, _bpm = build_tab(f"l64{check}l8d")
    # The check run becomes a silent rest (keeps its timing), then the real note.
    assert [t.midi_note for t in tab] == [None, 62]
