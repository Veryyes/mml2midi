import mido

from mml2midi.cli import main


def test_cli_writes_midi_file_from_inline_mml(tmp_path):
    output = tmp_path / "out.mid"
    exit_code = main(["MML@cde,,;", "-o", str(output)])

    assert exit_code == 0
    assert output.exists()

    midi_file = mido.MidiFile(output)
    assert len(midi_file.tracks) == 3


def test_cli_reads_mml_from_file(tmp_path):
    mml_file = tmp_path / "song.mml"
    mml_file.write_text("MML@cde,,;")
    output = tmp_path / "out.mid"

    exit_code = main([str(mml_file), "-o", str(output)])

    assert exit_code == 0
    assert output.exists()


def test_cli_reports_parse_errors(tmp_path, capsys):
    output = tmp_path / "out.mid"
    exit_code = main(["not valid mml", "-o", str(output)])

    assert exit_code == 1
    assert not output.exists()
    assert "mml2midi:" in capsys.readouterr().err


def test_cli_combines_multiple_voices_with_programs(tmp_path):
    output = tmp_path / "out.mid"
    exit_code = main([
        "MML@c,,;", "MML@e,,;",
        "-o", str(output),
        "--program", "0", "--program", "40",
    ])

    assert exit_code == 0
    midi_file = mido.MidiFile(output)
    assert len(midi_file.tracks) == 6
    assert midi_file.tracks[0][0].program == 0
    assert midi_file.tracks[3][0].program == 40
