import subprocess

import mido
import pytest

from mml2midi.cli import main


def _pdf_text(path) -> str:
    """Extract text from a PDF for assertions (reportlab compresses content
    streams by default, so a raw byte search won't find embedded text)."""
    return subprocess.run(
        ["pdftotext", str(path), "-"], capture_output=True, check=True, text=True
    ).stdout


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


def test_cli_writes_ocarina12_pdf(tmp_path):
    output = tmp_path / "tab.pdf"
    exit_code = main(["MML@cde,,;", "--ocarina12", str(output)])

    assert exit_code == 0
    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")
    assert "12-hole" in _pdf_text(output)


def test_cli_writes_ocarina6_pdf(tmp_path):
    output = tmp_path / "tab.pdf"
    exit_code = main(["MML@cde,,;", "--ocarina6", str(output)])

    assert exit_code == 0
    assert output.exists()
    assert "6-hole" in _pdf_text(output)


def test_cli_can_write_midi_and_both_ocarina_pdfs_together(tmp_path):
    midi_out = tmp_path / "out.mid"
    pdf6_out = tmp_path / "tab6.pdf"
    pdf12_out = tmp_path / "tab12.pdf"
    exit_code = main([
        "MML@cde,,;", "-o", str(midi_out),
        "--ocarina6", str(pdf6_out), "--ocarina12", str(pdf12_out),
    ])

    assert exit_code == 0
    assert midi_out.exists()
    assert pdf6_out.exists()
    assert pdf12_out.exists()
    assert "6-hole" in _pdf_text(pdf6_out)
    assert "12-hole" in _pdf_text(pdf12_out)


def test_cli_octave_folds_out_of_range_notes_by_default(tmp_path):
    output = tmp_path / "tab.pdf"
    # Spans 2 octaves -- wider than the 6-hole's ~1.4 octave range.
    exit_code = main(["MML@o3co6c,,;", "--ocarina6", str(output)])

    assert exit_code == 0
    text = _pdf_text(output)
    assert "Blue" in text
    assert "Red" not in text


def test_cli_no_octave_fold_leaves_notes_unplayable(tmp_path):
    output = tmp_path / "tab.pdf"
    exit_code = main(["MML@o3co6c,,;", "--ocarina6", str(output), "--no-octave-fold"])

    assert exit_code == 0
    text = _pdf_text(output)
    assert "Red" in text
    assert "Blue" not in text


def test_cli_ocarina_pdf_uses_only_the_first_input(tmp_path):
    # A second voice with completely different content shouldn't affect the tab.
    # (Byte-for-byte content should match; only reportlab's embedded creation
    # timestamp can legitimately differ between the two calls, and that's a
    # fixed-width field, so a size match is a reliable proxy here.)
    output_a = tmp_path / "a.pdf"
    output_b = tmp_path / "b.pdf"
    main(["MML@cde,,;", "MML@gab,,;", "--ocarina12", str(output_a)])
    main(["MML@cde,,;", "--ocarina12", str(output_b)])

    assert len(output_a.read_bytes()) == len(output_b.read_bytes())
