"""Command-line interface: ``mml2midi``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .midi_writer import build_midi_multi
from .ocarina_pdf import render_ocarina_tab_pdf
from .parser import MMLParseError


def _read_mml(source: str) -> str:
    """Return MML text for ``source``: either an inline MML string, or a path to read."""
    if "MML@" in source.upper():
        return source
    return Path(source).read_text(encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mml2midi",
        description="Convert Mabinogi Music Language (MML) sheet music into a Standard MIDI File.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="MML",
        help="One or more MML sources: a path to a file containing an 'MML@...;' string, or the "
        "MML string itself. Multiple sources are combined into one MIDI file as separate "
        "instrument voices, each on its own MIDI channel.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output .mid file path. Required unless --ocarina-pdf is given.",
    )
    parser.add_argument(
        "--ocarina-pdf",
        dest="ocarina_pdf",
        type=Path,
        metavar="PATH",
        help="Also (or instead) render the first input's melody as a 12-hole ocarina "
        "fingering tab PDF. Ocarina tabs are single-voice, so only the first input's "
        "melody part is used, transposed as needed to best fit the instrument's A4-F6 "
        "range; notes still out of range after that are marked in red.",
    )
    parser.add_argument(
        "--program",
        dest="programs",
        action="append",
        type=int,
        metavar="N",
        help="General MIDI program number (0-127) for a voice, in the order the inputs are "
        "given. Repeatable. Defaults to 0 (Acoustic Grand Piano) for every voice.",
    )
    parser.add_argument(
        "--keep-check-note",
        action="store_true",
        help="Don't strip a leading 'skill roll check' note (a run of the same note tied to "
        "itself many times, used in-game to show whether the Compose roll succeeded). By "
        "default this is detected and silenced since it isn't part of the music.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.output and not args.ocarina_pdf:
        parser.error("nothing to do: pass -o/--output, --ocarina-pdf, or both")

    try:
        mml_texts = [_read_mml(source) for source in args.inputs]
    except OSError as exc:
        print(f"mml2midi: {exc}", file=sys.stderr)
        return 1

    programs = list(args.programs) if args.programs else [0] * len(mml_texts)
    if len(programs) < len(mml_texts):
        programs += [programs[-1]] * (len(mml_texts) - len(programs))
    strip_check_note = not args.keep_check_note

    if args.output:
        try:
            midi_file = build_midi_multi(mml_texts, programs, strip_check_note=strip_check_note)
        except MMLParseError as exc:
            print(f"mml2midi: {exc}", file=sys.stderr)
            return 1

        args.output.parent.mkdir(parents=True, exist_ok=True)
        midi_file.save(args.output)
        print(f"Wrote {args.output}")

    if args.ocarina_pdf:
        title = Path(args.inputs[0]).stem if Path(args.inputs[0]).is_file() else "Ocarina Tab"
        args.ocarina_pdf.parent.mkdir(parents=True, exist_ok=True)
        try:
            render_ocarina_tab_pdf(
                mml_texts[0], args.ocarina_pdf, title=title, strip_check_note=strip_check_note,
            )
        except MMLParseError as exc:
            print(f"mml2midi: {exc}", file=sys.stderr)
            return 1

        print(f"Wrote {args.ocarina_pdf}")

    return 0
