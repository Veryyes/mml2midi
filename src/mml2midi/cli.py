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
        help="Output .mid file path. Required unless --ocarina6/--ocarina12 is given.",
    )
    parser.add_argument(
        "--ocarina6",
        type=Path,
        metavar="PATH",
        help="Also (or instead) render the first input's melody as a 6-hole ocarina "
        "fingering tab PDF (a small pendant ocarina, C5-E6) at PATH. Ocarina tabs are "
        "single-voice, so only the first input's melody part is used, transposed as "
        "needed to best fit the instrument's range; notes still out of range after that "
        "are marked in red. Combine with --ocarina12 to render both.",
    )
    parser.add_argument(
        "--ocarina12",
        type=Path,
        metavar="PATH",
        help="Same as --ocarina6, but for a 12-hole ocarina ('English pendant', A4-F6).",
    )
    parser.add_argument(
        "--no-octave-fold",
        dest="fold_octaves",
        action="store_false",
        help="For --ocarina6/--ocarina12: don't shift individual out-of-range notes by "
        "whole octaves to make them playable (drawn in blue by default). Leaves them "
        "unplayable (drawn in red) instead.",
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

    if not args.output and not args.ocarina6 and not args.ocarina12:
        parser.error("nothing to do: pass -o/--output, --ocarina6/--ocarina12, or a combination")

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

    title = Path(args.inputs[0]).stem if Path(args.inputs[0]).is_file() else "Ocarina Tab"
    for ocarina_path, hole_count in ((args.ocarina6, 6), (args.ocarina12, 12)):
        if not ocarina_path:
            continue

        ocarina_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            render_ocarina_tab_pdf(
                mml_texts[0], ocarina_path, title=title, strip_check_note=strip_check_note,
                hole_count=hole_count, fold_octaves=args.fold_octaves,
            )
        except MMLParseError as exc:
            print(f"mml2midi: {exc}", file=sys.stderr)
            return 1

        print(f"Wrote {ocarina_path}")

    return 0
