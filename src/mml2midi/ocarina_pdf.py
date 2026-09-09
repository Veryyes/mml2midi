"""Render an ocarina tab (see :mod:`mml2midi.ocarina`) to a PDF."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from .ocarina import SUBHOLES, TabNote, build_tab, note_name
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


# --- 6-hole layout -----------------------------------------------------
# A small pendant ocarina reads clearly as a simple rounded oval body with a
# short spout, unlike the 12-hole's more complex "wing" shape -- so this one
# is an original simple drawing, not traced from any source. Hole numbering
# (1=top-left, 2=top-right, 3=bottom-left, 4=bottom-right for the main
# cluster, 5/6 for the two below it) matches the fingering chart in
# ocarina.py's docstring, so a reader can cross-check. The mouthpiece points
# down (toward the two lower holes), not up, matching how these are actually
# held.
_DESIGN_W_6H = 400.0
_DESIGN_H_6H = 480.0
_BODY_ELLIPSE_6H = (50.0, 40.0, 350.0, 340.0)  # (x1, y1, x2, y2) bounding box
_SPOUT_6H = [(170.0, 415.0), (230.0, 415.0), (200.0, 470.0)]  # points down
_HOLE_CENTERS_6H: dict[int, tuple[float, float]] = {
    1: (150.0, 150.0),
    2: (250.0, 150.0),
    3: (150.0, 230.0),
    4: (250.0, 230.0),
    5: (150.0, 390.0),
    6: (250.0, 390.0),
}
_HOLE_RADIUS_6H = 35.0


def _draw_hole(c: canvas.Canvas, hx: float, hy: float, r: float, fraction: float, body_color) -> None:
    """Draw one hole: fraction 0.0 open, 0.5 half-covered (right half filled,
    matching the reference 4-hole chart's convention), 1.0 fully covered."""
    c.setStrokeColor(body_color)
    c.setFillColor(colors.white)
    c.circle(hx, hy, r, stroke=1, fill=1)
    if fraction >= 1.0:
        c.setFillColor(body_color)
        c.circle(hx, hy, r, stroke=1, fill=1)
    elif fraction >= 0.5:
        c.setFillColor(body_color)
        c.wedge(hx - r, hy - r, hx + r, hy + r, -90, 180, stroke=0, fill=1)
        c.setStrokeColor(body_color)
        c.circle(hx, hy, r, stroke=1, fill=0)


NORMAL_COLOR = colors.Color(0.2, 0.2, 0.2)
OUT_OF_RANGE_COLOR = colors.Color(0.85, 0.25, 0.25)  # red: unplayable, no fingering exists
OCTAVE_SHIFTED_COLOR = colors.Color(0.15, 0.4, 0.75)  # blue: playable, but an octave off


def _draw_ocarina_12h(
    c: canvas.Canvas, x: float, y: float, size: float,
    holes: dict[int, float] | None, body_color=NORMAL_COLOR,
) -> None:
    """Draw one 12-hole ocarina icon with (x, y) as its bottom-left corner."""
    scale = size / _DESIGN_W

    def to_page(px: float, py: float) -> tuple[float, float]:
        return x + px * scale, y + (_DESIGN_H - py) * scale  # flip: SVG y-down -> PDF y-up

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

    c.setLineWidth(max(0.75, size / 120))
    for hole in range(1, 13):
        hx, hy = to_page(*_HOLE_CENTERS[hole])
        r = _HOLE_RADIUS[hole] * scale
        fraction = (holes or {}).get(hole, 0.0)
        _draw_hole(c, hx, hy, r, fraction, body_color)


def _draw_ocarina_6h(
    c: canvas.Canvas, x: float, y: float, size: float,
    holes: dict[int, float] | None, body_color=NORMAL_COLOR,
) -> None:
    """Draw one 6-hole ocarina icon with (x, y) as its bottom-left corner."""
    scale = size / _DESIGN_W_6H

    def to_page(px: float, py: float) -> tuple[float, float]:
        return x + px * scale, y + (_DESIGN_H_6H - py) * scale

    c.setLineWidth(max(1.0, size / 80))
    c.setStrokeColor(body_color)
    x1, y1 = to_page(_BODY_ELLIPSE_6H[0], _BODY_ELLIPSE_6H[1])
    x2, y2 = to_page(_BODY_ELLIPSE_6H[2], _BODY_ELLIPSE_6H[3])
    c.ellipse(x1, min(y1, y2), x2, max(y1, y2), stroke=1, fill=0)

    p = c.beginPath()
    sx, sy = to_page(*_SPOUT_6H[0])
    p.moveTo(sx, sy)
    for px, py in _SPOUT_6H[1:]:
        qx, qy = to_page(px, py)
        p.lineTo(qx, qy)
    p.close()
    c.drawPath(p, stroke=1, fill=0)

    c.setLineWidth(max(0.75, size / 120))
    for hole in range(1, 7):
        hx, hy = to_page(*_HOLE_CENTERS_6H[hole])
        r = _HOLE_RADIUS_6H * scale
        fraction = (holes or {}).get(hole, 0.0)
        _draw_hole(c, hx, hy, r, fraction, body_color)


def _draw_ocarina(
    c: canvas.Canvas, x: float, y: float, size: float, hole_count: int,
    holes: dict[int, float] | None, body_color=NORMAL_COLOR,
) -> None:
    if hole_count == 6:
        _draw_ocarina_6h(c, x, y, size, holes, body_color=body_color)
    else:
        _draw_ocarina_12h(c, x, y, size, holes, body_color=body_color)


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
    hole_count: int = 12, fold_octaves: bool = True,
) -> None:
    """Render the melody part of ``mml_text`` as an ocarina tab PDF.

    ``hole_count`` selects the instrument: 12 (default, "English pendant",
    A4-F6) or 6 (a small pendant ocarina, C5-E6 -- see ocarina.py's
    docstring for why that octave is a default rather than a verified pitch).

    ``fold_octaves`` (default true): a note that doesn't fit the song's
    overall transposition is individually shifted by whole octaves to make
    it playable rather than left unplayable -- drawn in blue with an
    up/down marker rather than red. Pass false to disable and just mark
    such notes unplayable in red.
    """
    if hole_count not in (6, 12):
        raise ValueError(f"unsupported ocarina hole_count: {hole_count} (expected 6 or 12)")

    melody_text = parse_score(mml_text)[0]
    tab, transposition, tempo_bpm = build_tab(
        melody_text, hole_count=hole_count, strip_check_note=strip_check_note,
        fold_octaves=fold_octaves,
    )

    c = canvas.Canvas(str(output_path), pagesize=LETTER)
    page_w, page_h = LETTER
    margin = 0.5 * inch
    range_label = "A4-F6" if hole_count == 12 else "C5-E6"
    aspect = (_DESIGN_H_6H / _DESIGN_W_6H) if hole_count == 6 else (_DESIGN_H / _DESIGN_W)

    def draw_header(page_num: int) -> float:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, page_h - margin, title)
        c.setFont("Helvetica", 9)
        info = f"{hole_count}-hole ocarina (Key of C, {range_label}) · tempo {tempo_bpm} BPM"
        if transposition:
            direction = "up" if transposition > 0 else "down"
            info += f" · transposed {direction} {abs(transposition)} semitones to fit range"
        c.drawString(margin, page_h - margin - 16, info)
        if page_num > 1:
            c.setFont("Helvetica", 8)
            c.drawRightString(page_w - margin, margin / 2, f"page {page_num}")
        return page_h - margin - 40

    icon_size = 0.62 * inch  # icon width; height follows the instrument's own aspect ratio
    icon_h = icon_size * aspect
    col_gap = 0.18 * inch
    row_gap = 0.38 * inch
    label_h = 0.30 * inch
    cols = int((page_w - 2 * margin) // (icon_size + col_gap))

    page_num = 1
    cursor_y = draw_header(page_num)
    col = 0
    any_out_of_range = False
    any_octave_shifted = False

    for entry in tab:
        if col == 0 and cursor_y - icon_h - label_h < margin:
            c.showPage()
            page_num += 1
            cursor_y = draw_header(page_num)

        x = margin + col * (icon_size + col_gap)
        y = cursor_y - icon_h

        out_of_range = entry.midi_note is not None and entry.holes is None
        octave_shifted = entry.octave_shift != 0
        any_out_of_range = any_out_of_range or out_of_range
        any_octave_shifted = any_octave_shifted or octave_shifted

        if out_of_range:
            body_color = OUT_OF_RANGE_COLOR
        elif octave_shifted:
            body_color = OCTAVE_SHIFTED_COLOR
        else:
            body_color = NORMAL_COLOR

        if entry.midi_note is not None:  # leave rests as a blank space, no icon
            _draw_ocarina(c, x, y, icon_size, hole_count, entry.holes, body_color=body_color)

        c.setFillColor(body_color)
        c.setFont("Helvetica", 7.5)
        if entry.midi_note is None:
            label = "rest"
        else:
            label = note_name(entry.transposed_note)
            if octave_shifted:
                label += " ↑" * entry.octave_shift if entry.octave_shift > 0 else " ↓" * -entry.octave_shift
        c.drawCentredString(x + icon_size / 2, y - 9, label)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(x + icon_size / 2, y - 18, _duration_label(entry.duration_ticks))

        col += 1
        if col >= cols:
            col = 0
            cursor_y -= icon_h + label_h + row_gap

    if any_octave_shifted:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(OCTAVE_SHIFTED_COLOR)
        c.drawString(
            margin, margin / 2 + (10 if any_out_of_range else 0),
            "Blue (↑/↓) = shifted by whole octaves from the song's overall transposition "
            "to make it playable -- it'll sound an octave off from the rest of the song.",
        )
    if any_out_of_range:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(OUT_OF_RANGE_COLOR)
        c.drawString(
            margin, margin / 2,
            f"Red = outside this ocarina's playable range ({range_label}) even after "
            "transposing -- there's no fingering for it on this instrument.",
        )

    c.save()
