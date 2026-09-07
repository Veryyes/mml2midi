import mido
import pytest

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


def test_cli_requires_an_output_of_some_kind(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["MML@cde,,;"])

    assert exc_info.value.code == 2
    assert "nothing to do" in capsys.readouterr().err


def test_cli_writes_ocarina_pdf(tmp_path):
    output = tmp_path / "tab.pdf"
    exit_code = main(["MML@cde,,;", "--ocarina-pdf", str(output)])

    assert exit_code == 0
    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")


def test_cli_can_write_both_midi_and_ocarina_pdf_together(tmp_path):
    midi_out = tmp_path / "out.mid"
    pdf_out = tmp_path / "tab.pdf"
    exit_code = main(["MML@cde,,;", "-o", str(midi_out), "--ocarina-pdf", str(pdf_out)])

    assert exit_code == 0
    assert midi_out.exists()
    assert pdf_out.exists()


def test_cli_ocarina_pdf_uses_only_the_first_input(tmp_path):
    # A second voice with completely different content shouldn't affect the tab.
    # (Byte-for-byte content should match; only reportlab's embedded creation
    # timestamp can legitimately differ between the two calls, and that's a
    # fixed-width field, so a size match is a reliable proxy here.)
    output_a = tmp_path / "a.pdf"
    output_b = tmp_path / "b.pdf"
    main(["MML@cde,,;", "MML@gab,,;", "--ocarina-pdf", str(output_a)])
    main(["MML@cde,,;", "--ocarina-pdf", str(output_b)])

    assert len(output_a.read_bytes()) == len(output_b.read_bytes())
