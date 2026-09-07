import mido

from mml2midi.midi_writer import DEFAULT_PROGRAM, TICKS_PER_BEAT, build_midi, build_midi_multi


def test_build_midi_basic_structure():
    midi_file = build_midi("MML@c,,;")

    assert midi_file.type == 1
    assert midi_file.ticks_per_beat == TICKS_PER_BEAT
    assert len(midi_file.tracks) == 3  # melody, harmony 1, harmony 2


def test_melody_track_has_expected_messages():
    midi_file = build_midi("MML@c,,;")
    melody = midi_file.tracks[0]

    kinds = [msg.type for msg in melody]
    assert kinds[0] == "program_change"
    assert "set_tempo" in kinds  # default tempo written on the first track
    assert "note_on" in kinds
    assert "note_off" in kinds
    assert kinds[-1] == "end_of_track"


def test_empty_harmony_parts_still_produce_valid_tracks():
    midi_file = build_midi("MML@c,,;")
    for track in midi_file.tracks[1:]:
        assert track[-1].type == "end_of_track"


def test_program_change_uses_requested_program():
    midi_file = build_midi("MML@c,,;", program=40)
    for track in midi_file.tracks:
        assert track[0].type == "program_change"
        assert track[0].program == 40


def test_default_program_is_acoustic_grand_piano():
    assert DEFAULT_PROGRAM == 0


def test_explicit_tempo_command_overrides_default():
    midi_file = build_midi("MML@t200c,,;")
    melody = midi_file.tracks[0]
    tempo_messages = [msg for msg in melody if msg.type == "set_tempo"]
    assert len(tempo_messages) == 1
    assert mido.tempo2bpm(tempo_messages[0].tempo) == 200


def test_note_on_note_off_pair_roundtrips_through_mido(tmp_path):
    output = tmp_path / "out.mid"
    midi_file = build_midi("MML@cde,,;")
    midi_file.save(output)

    reloaded = mido.MidiFile(output)
    melody = reloaded.tracks[0]
    note_ons = [msg for msg in melody if msg.type == "note_on"]
    note_offs = [msg for msg in melody if msg.type == "note_off"]

    assert [m.note for m in note_ons] == [60, 62, 64]
    assert [m.note for m in note_offs] == [60, 62, 64]


def test_build_midi_multi_assigns_one_channel_per_voice():
    midi_file = build_midi_multi(["MML@c,,;", "MML@e,,;"], [0, 40])

    assert len(midi_file.tracks) == 6  # 3 tracks per voice

    voice0_channels = {msg.channel for msg in midi_file.tracks[0] if hasattr(msg, "channel")}
    voice1_channels = {msg.channel for msg in midi_file.tracks[3] if hasattr(msg, "channel")}
    assert voice0_channels == {0}
    assert voice1_channels == {1}


def test_build_midi_multi_only_writes_default_tempo_once():
    midi_file = build_midi_multi(["MML@c,,;", "MML@e,,;"], [0, 0])
    tempo_events = [
        msg for track in midi_file.tracks for msg in track if msg.type == "set_tempo"
    ]
    assert len(tempo_events) == 1


def test_build_midi_multi_requires_matching_lengths():
    import pytest

    with pytest.raises(ValueError):
        build_midi_multi(["MML@c,,;"], [0, 1])
