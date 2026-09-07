"""Render an ocarina tab (see :mod:`mml2midi.ocarina`) to a PDF."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from .ocarina import MAIN_HOLES, SUBHOLES, THUMB_HOLES, TabNote, build_tab, note_name
from .parser import parse_score

# Hole centers in a fixed 0-667 x 0-640 design space (see ocarina.py's
# docstring for where this layout comes from), scaled to whatever size an
# icon is drawn at.
_DESIGN_W = 667.2
_DESIGN_H = 639.6
_HOLE_CENTERS: dict[int, tuple[float, float]] = {
    1: (550.6, 97.1),
    2: (488.9, 165.2),
    3: (435.5, 236.3),
    4: (388.7, 313.0),
    5: (258.0, 247.6),
    6: (180.7, 300.2),
    7: (90.6, 329.2),
    8: (141.8, 513.5),
    9: (436.1, 513.5),
    10: (319.7, 178.6),
    11: (222.0, 351.6),
    12: (384.1, 196.6),
}
_HOLE_RADIUS: dict[int, float] = {h: (20.0 if h in SUBHOLES else 35.0) for h in range(1, 13)}

# The ocarina body outline, as a sequence of cubic Bezier curve segments in
# the same design space as the hole centers above. This is the real body
# silhouette (translated into this module's coordinate space) from Mathias
# Panzenböck's Open 12 Hole Ocarina font/tab creator (see ocarina.py's
# docstring for the full attribution) -- not a freehand approximation.
_BODY_START = (227.72, 594.69)
_BODY_CURVES: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]] = [
    ((232.33, 569.37), (242.43, 545.8), (242.02, 519.99)),
    ((241.59, 492.9), (233.06, 463.77), (213.94, 445.37)),
    ((178.23, 411.02), (99.51, 399.4), (59.57, 389.37)),
    ((46.57, 386.1), (20.64, 377.35), (15.45, 365.15)),
    ((6.27, 343.53), (43.12, 299.12), (69.31, 276.59)),
    ((150.64, 206.66), (244.51, 162.75), (339.6, 120.57)),
    ((437.28, 77.24), (604.12, 18.71), (638.61, 14.1)),
    ((648.27, 12.8), (656.0, 24.9), (652.15, 32.2)),
    ((639.41, 56.34), (595.85, 117.57), (564.6, 159.14)),
    ((511.15, 230.23), (456.46, 299.75), (410.61, 375.46)),
    ((380.27, 425.56), (353.53, 478.04), (330.97, 532.09)),
    ((320.08, 558.2), (314.85, 586.42), (304.25, 612.63)),
    ((301.03, 620.6), (292.77, 625.56), (286.19, 625.57)),
    ((271.77, 625.59), (252.09, 621.32), (237.4, 614.21)),
    ((230.76, 610.99), (226.32, 602.42), (227.72, 594.69)),
]


def _draw_ocarina(
    c: canvas.Canvas, x: float, y: float, size: float,
    holes: frozenset[int] | None, out_of_range: bool = False,
) -> None:
    """Draw one ocarina icon with (x, y) as its bottom-left corner."""
    scale = size / _DESIGN_W

    def to_page(px: float, py: float) -> tuple[float, float]:
        return x + px * scale, y + (_DESIGN_H - py) * scale  # flip: SVG y-down -> PDF y-up

    body_color = colors.Color(0.85, 0.25, 0.25) if out_of_range else colors.Color(0.2, 0.2, 0.2)

    c.setLineWidth(max(1.0, size / 80))
    c.setStrokeColor(body_color)
    p = c.beginPath()
    px, py = to_page(*_BODY_START)
    p.moveTo(px, py)
    for cp1, cp2, end in _BODY_CURVES:
        x1, y1 = to_page(*cp1)
        x2, y2 = to_page(*cp2)
        x3, y3 = to_page(*end)
        p.curveTo(x1, y1, x2, y2, x3, y3)
    p.close()
    c.drawPath(p, stroke=1, fill=0)

    for hole in range(1, 13):
        hx, hy = to_page(*_HOLE_CENTERS[hole])
        r = _HOLE_RADIUS[hole] * scale
        covered = holes is not None and hole in holes
        c.setLineWidth(max(0.75, size / 120))
        c.setStrokeColor(body_color)
        if covered:
            c.setFillColor(body_color)
            c.circle(hx, hy, r, stroke=1, fill=1)
        else:
            c.setFillColor(colors.white)
            c.circle(hx, hy, r, stroke=1, fill=1)


_DURATIONS = [
    (384, "1"), (288, "1/2."), (192, "1/2"), (144, "1/4."), (96, "1/4"),
    (72, "1/8."), (48, "1/8"), (36, "1/16."), (24, "1/16"), (18, "1/32."), (12, "1/32"),
]


def _duration_label(ticks: int) -> str:
    # 96 ticks/quarter note (see parser.py). Exact match if one exists (dots
    # included), else the nearest common note value at or below it.
    for denom, name in _DURATIONS:
        if ticks == denom:
            return name
    for denom, name in _DURATIONS:
        if ticks >= denom:
            return "~" + name
    return "~1/32"


def render_ocarina_tab_pdf(
    mml_text: str, output_path, title: str = "Ocarina Tab", strip_check_note: bool = True,
) -> None:
    """Render the melody part of ``mml_text`` as a 12-hole ocarina tab PDF."""
    melody_text = parse_score(mml_text)[0]
    tab, transposition, tempo_bpm = build_tab(melody_text, strip_check_note=strip_check_note)

    c = canvas.Canvas(str(output_path), pagesize=LETTER)
    page_w, page_h = LETTER
    margin = 0.5 * inch

    def draw_header(page_num: int) -> float:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, page_h - margin, title)
        c.setFont("Helvetica", 9)
        info = f"12-hole ocarina (Key of C, A4-F6) · tempo {tempo_bpm} BPM"
        if transposition:
            direction = "up" if transposition > 0 else "down"
            info += f" · transposed {direction} {abs(transposition)} semitones to fit range"
        c.drawString(margin, page_h - margin - 16, info)
        if page_num > 1:
            c.setFont("Helvetica", 8)
            c.drawRightString(page_w - margin, margin / 2, f"page {page_num}")
        return page_h - margin - 40

    icon_size = 0.62 * inch
    col_gap = 0.18 * inch
    row_gap = 0.38 * inch
    label_h = 0.30 * inch
    cols = int((page_w - 2 * margin) // (icon_size + col_gap))

    page_num = 1
    cursor_y = draw_header(page_num)
    col = 0
    any_out_of_range = False

    for entry in tab:
        if col == 0 and cursor_y - icon_size - label_h < margin:
            c.showPage()
            page_num += 1
            cursor_y = draw_header(page_num)

        x = margin + col * (icon_size + col_gap)
        y = cursor_y - icon_size

        out_of_range = entry.midi_note is not None and entry.holes is None
        any_out_of_range = any_out_of_range or out_of_range
        if entry.midi_note is not None:  # leave rests as a blank space, no icon
            _draw_ocarina(c, x, y, icon_size, entry.holes, out_of_range=out_of_range)

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 7.5)
        if entry.midi_note is None:
            label = "rest"
        else:
            label = note_name(entry.transposed_note)
        c.drawCentredString(x + icon_size / 2, y - 9, label)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(x + icon_size / 2, y - 18, _duration_label(entry.duration_ticks))

        col += 1
        if col >= cols:
            col = 0
            cursor_y -= icon_size + label_h + row_gap

    if any_out_of_range:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.Color(0.85, 0.25, 0.25))
        c.drawString(
            margin, margin / 2,
            "Red = outside this ocarina's playable range (A4-F6), even after transposing "
            "the whole song -- there's no fingering for it on this instrument.",
        )

    c.save()
