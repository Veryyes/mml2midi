# mml2midi

Convert Mabinogi Music Language (MML) sheet music into Standard MIDI Files.

MML is the text format the in-game Compose skill produces: a score is
`MML@<melody>,<harmony 1>,<harmony 2>;`, three parts that play at once.
This library parses that format and writes a real `.mid` file, so a
score can be previewed, arranged, or played back outside the game.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## CLI usage

```bash
# Inline MML string
mml2midi "MML@cdefgab>c;,,;" -o scale.mid

# From a file
mml2midi examples/scale.mml -o scale.mid

# Multiple parts as separate instrument voices in one file
mml2midi part1.mml part2.mml -o duet.mid --program 0 --program 40
```

`--program` takes a General MIDI program number (0-127); pass it once per
input to give each voice its own instrument. Run `mml2midi --help` for
the full option list.

## Library usage

```python
from mml2midi import build_midi, write_midi_file

midi_file = build_midi("MML@cdefgab>c;,,;")  # a mido.MidiFile
write_midi_file("MML@cdefgab>c;,,;", "scale.mid")
```

## MML grammar

Each of the three comma-separated parts is its own sequence of tokens.
MML is case-insensitive and ignores whitespace.

| Token | Meaning |
|---|---|
| `a`-`g` | Play that note in the current octave. |
| `+` / `#` | Sharp, attached to a note (`c+`, `d#`). |
| `-` | Flat, attached to a note (`e-`). |
| `r` | Rest. |
| `n<0-96>` | Play an absolute chromatic pitch directly (bypasses octave/accidentals). The number is a pitch, not a length — duration is whatever the current default length is. |
| `<note><1-192>` | Set that note's/rest's length to 1/*n* of a whole note (`c4` = quarter note). Overrides the default for just that token. |
| `.` | Attached to a note/rest, extends its length by 50%. |
| `&` | Attached to a note, ties it to the next occurrence of the same pitch (sustain without re-striking). |
| `o<0-9>` | Set the current octave outright. Default is 4 (`o4c` = middle C). |
| `<` / `>` | Shift the current octave down/up by one (clamped to 0-9). |
| `l<1-192>` | Set the default length used by notes/rests that don't specify their own. |
| `t<bpm>` | Set the tempo in BPM from this point on. |
| `v<1-15>` | Set the volume (mapped to MIDI velocity = volume × 8). |

Unrecognised characters are skipped. A part left empty (`MML@c,,;`) is valid
and just produces a silent track. A score with fewer than 3 comma-separated
parts (`MML@melody;`, `MML@melody,harmony1;`) is also accepted -- missing
trailing parts are treated as silence, since real-world pastes sometimes
drop them instead of writing them out empty.

### Skill-roll check note

Composing in Mabinogi is a skill roll, and some real scores open a part with
the same note tied to itself many times over at a tiny length (e.g.
`l64c&c&c&c&c&c&c&c&...&c`) purely so the performer can see or hear whether
that roll succeeded before the actual song plays -- it isn't part of the
music. This is detected structurally (the same pitch tied to itself 8+
times in a row, right at the start of a part) and silenced by default: it
still occupies its original duration, so the part stays in sync with the
rest of the score, but produces no note. Pass `strip_check_note=False` to
the library functions, or `--keep-check-note` to the CLI, to keep it.

This pattern and the `>=8` threshold were derived empirically from a batch
of 60+ real player-composed scores: genuine musical ties never repeat the
same tied pitch more than twice, while every real check note found repeated
17-64 times, leaving a wide, unambiguous gap to set the threshold in.

### A quirk worth knowing about

Notes are computed relative to octave 0 and folded into a 0-96 window
*before* the final offset to a MIDI note number — so a note built from an
extreme octave/accidental combination (e.g. `o9b+`) wraps down by whole
octaves instead of clipping or overflowing. This isn't a generic MML rule;
it's a real characteristic of Mabinogi's own note calculation, preserved
here on purpose so this converter's output matches what the game actually
produces (see `MMLParseError`-adjacent comments in `parser.py` for the
exact arithmetic).

## How this was verified

There's no single official MML spec document, so the grammar and tick/note
arithmetic in `parser.py` were cross-checked against multiple independent
sources rather than guessed:

- the [Mabinogi World Wiki's MML page](https://wiki.mabinogiworld.com/view/MML)
- [rajephon/YKSConverter](https://github.com/rajephon/YKSConverter), a C++/Rust
  Mabinogi MML→MIDI converter (itself a port of
  [logue/PSGConverter](https://github.com/logue/PSGConverter))

`build_midi` was smoke-tested against the scale example above and produces
the same note numbers, octave shifts, and tempo as those reference
implementations.

## Tests

```bash
pytest
```
