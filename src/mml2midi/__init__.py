"""mml2midi: convert Mabinogi Music Language (MML) into Standard MIDI Files."""

from .midi_writer import build_midi, build_midi_multi, write_midi_file
from .parser import MMLParseError, parse_part, parse_score

__all__ = [
    "MMLParseError",
    "parse_score",
    "parse_part",
    "build_midi",
    "build_midi_multi",
    "write_midi_file",
]

__version__ = "0.1.0"
