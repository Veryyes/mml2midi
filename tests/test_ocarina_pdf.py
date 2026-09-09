import pytest

from mml2midi.ocarina_pdf import render_ocarina_tab_pdf


def test_renders_12_hole_pdf_by_default(tmp_path):
    output = tmp_path / "tab.pdf"
    render_ocarina_tab_pdf("MML@cde,,;", output, title="Test")

    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")


def test_renders_6_hole_pdf(tmp_path):
    output = tmp_path / "tab.pdf"
    render_ocarina_tab_pdf("MML@cde,,;", output, title="Test", hole_count=6)

    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")


def test_rejects_unsupported_hole_count(tmp_path):
    output = tmp_path / "tab.pdf"
    with pytest.raises(ValueError):
        render_ocarina_tab_pdf("MML@cde,,;", output, hole_count=4)

    assert not output.exists()
