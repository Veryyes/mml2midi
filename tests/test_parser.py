import pytest

from mml2midi.events import NoteOff, NoteOn, TempoChange
from mml2midi.parser import MMLParseError, parse_part, parse_score


def test_parse_score_splits_three_parts():
    parts = parse_score("MML@cde,efg,gab;")
    assert parts == ["cde", "efg", "gab"]


def test_parse_score_tolerates_surrounding_text_and_whitespace():
    parts = parse_score("My Song\nMML@ c , d , e ;\nsome trailer")
    assert parts == [" c ", " d ", " e "]


def test_parse_score_requires_mml_header():
    with pytest.raises(MMLParseError):
        parse_score("c,d,e;")


def test_parse_score_requires_terminator():
    with pytest.raises(MMLParseError):
        parse_score("MML@c,d,e")


@pytest.mark.parametrize(
    "body,expected",
    [
        ("c,d", ["c", "d", ""]),  # real-world pastes sometimes drop trailing empty slots
        ("c", ["c", "", ""]),
    ],
)
def test_parse_score_pads_missing_trailing_parts_with_silence(body, expected):
    assert parse_score(f"MML@{body};") == expected


def test_parse_score_rejects_more_than_three_parts():
    with pytest.raises(MMLParseError):
        parse_score("MML@c,d,e,f;")


def test_default_note_is_middle_c_quarter_note():
    events, end_time = parse_part("c")
    assert events == [NoteOn(0, 60, 64), NoteOff(96, 60)]
    assert end_time == 96 + 96  # trailing tail


def test_octave_shift_relative():
    events, _ = parse_part(">c<<c")
    on_notes = [e.note for e in events if isinstance(e, NoteOn)]
    assert on_notes == [72, 48]  # o5 then o3 (clamped no lower than shown)


def test_octave_absolute_and_clamping():
    events, _ = parse_part("o9co0co100c")
    on_notes = [e.note for e in events if isinstance(e, NoteOn)]
    # o9 -> 12*9+0=108 (in range, no wrap); o0 -> 0+12=12; o100 clamps to o9 -> 108 again
    assert on_notes == [108, 12, 108]


def test_sharp_and_flat_accidentals():
    events, _ = parse_part("c+d#e-")
    on_notes = [e.note for e in events if isinstance(e, NoteOn)]
    assert on_notes == [61, 63, 63]  # C#4, D#4, Eb4 (D4=62, E4=64)


def test_rest_advances_time_without_events():
    events, _ = parse_part("cr4c")
    assert events == [
        NoteOn(0, 60, 64),
        NoteOff(96, 60),
        NoteOn(96 + 96, 60, 64),
        NoteOff(96 + 96 + 96, 60),
    ]


def test_dotted_note_extends_length_by_half():
    events, _ = parse_part("c4.")
    assert events == [NoteOn(0, 60, 64), NoteOff(144, 60)]


def test_length_token_sets_default_for_following_notes():
    events, _ = parse_part("l8cd")
    on_times = [e.time for e in events if isinstance(e, NoteOn)]
    assert on_times == [0, 48]


def test_per_note_length_overrides_default_for_that_note_only():
    events, _ = parse_part("l8c4d")
    on_times = [e.time for e in events if isinstance(e, NoteOn)]
    # c4 -> 96 ticks (quarter), then d falls back to default l8 -> 48 ticks
    assert on_times == [0, 96]


def test_tie_sustains_without_retriggering():
    events, _ = parse_part("c4&c4")
    assert events == [NoteOn(0, 60, 64), NoteOff(192, 60)]


def test_tie_breaks_on_pitch_change():
    events, _ = parse_part("c4&d4")
    assert events == [
        NoteOn(0, 60, 64),
        NoteOff(96, 60),
        NoteOn(96, 62, 64),
        NoteOff(192, 62),
    ]


def test_trailing_tie_is_closed_at_end_of_part():
    events, _ = parse_part("c4&")
    assert events == [NoteOn(0, 60, 64), NoteOff(96, 60)]


def test_chromatic_note_uses_absolute_pitch_and_default_duration():
    events, _ = parse_part("l8n60")
    assert events == [NoteOn(0, 72, 64), NoteOff(48, 72)]


def test_chromatic_note_out_of_range_falls_back_to_zero():
    events, _ = parse_part("n200")
    assert events == [NoteOn(0, 12, 64), NoteOff(96, 12)]


def test_volume_sets_velocity_and_clamps():
    events, _ = parse_part("v15cv1cv0cv20c")
    velocities = [e.velocity for e in events if isinstance(e, NoteOn)]
    assert velocities == [120, 8, 8, 120]


def test_tempo_command_emits_tempo_change_event():
    events, _ = parse_part("t180c")
    assert events[0] == TempoChange(0, 180)


def test_invalid_length_value_is_ignored():
    events, _ = parse_part("c300")  # out of 1-192 range -> keeps default quarter
    assert events == [NoteOn(0, 60, 64), NoteOff(96, 60)]


def test_unknown_characters_are_skipped():
    events, _ = parse_part("c ?! @ d")
    on_notes = [e.note for e in events if isinstance(e, NoteOn)]
    assert on_notes == [60, 62]


def test_note_wraps_by_octave_when_out_of_internal_range():
    # o9 + b+ pushes the pre-offset value to 12*9+11+1=120, which wraps down
    # by whole octaves until it fits in [0, 96] before the final +12 offset.
    events, _ = parse_part("o9b+")
    assert events == [NoteOn(0, 12 * 8 + 12, 64), NoteOff(96, 12 * 8 + 12)]


# --- Leading "skill roll check" note ----------------------------------------
# Real Mabinogi scores were sampled in examples/*.txt to derive this pattern:
# the same note tied to itself many times (17-64 repeats observed) at a tiny
# length, right at the start of a part, before any real content.

def test_leading_check_note_is_silenced_but_keeps_its_timing():
    # 8 tied c's (the detection threshold) then a real, differently-pitched note.
    check = "c&" * 8
    events, _ = parse_part(f"l64{check}l8d")
    assert events == [NoteOn(48, 62, 64), NoteOff(96, 62)]


def test_short_tie_below_threshold_is_not_treated_as_a_check_note():
    events, _ = parse_part("c4&c4")  # only 2 repeats -- an ordinary musical tie
    assert events == [NoteOn(0, 60, 64), NoteOff(192, 60)]


def test_strip_check_note_can_be_disabled():
    check = "c&" * 8
    events, _ = parse_part(f"l64{check}l8d", strip_check_note=False)
    assert events == [
        NoteOn(0, 60, 64),
        NoteOff(48, 60),
        NoteOn(48, 62, 64),
        NoteOff(96, 62),
    ]


def test_real_isolated_check_note_produces_no_events():
    # The literal contents of examples/1Sound Check.txt: 17 tied c's, nothing else.
    check_only = "l64" + "c&" * 17
    events, end_time = parse_part(check_only)
    assert events == []
    assert end_time == 17 * 6 + 6  # all silent, but still 108 ticks long


def test_check_note_detection_allows_a_leading_rest_and_control_tokens():
    # Seen in real data ("Crossing Field.txt"): "l32r" precedes the tie chain,
    # and its last repeat isn't tied (the chain closes on its own).
    check = "c&" * 7 + "c"  # 8 repeats total, last one untied
    events, _ = parse_part(f"l32r{check}l8d")
    # l32 -> 12 ticks/note: 1 rest + 8 (silenced) check notes = 9*12 = 108 ticks
    # before l8 takes over and the real note plays.
    assert events == [NoteOn(108, 62, 64), NoteOff(156, 62)]
