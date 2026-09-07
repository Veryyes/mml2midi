# mml2midi

Convert Mabinogi Music Language (MML) sheet music into Standard MIDI Files.

## Install

```bash
pip install -e .
```
## CLI usage

```bash
# Inline MML string
mml2midi "MML@cdefgab>c;,,;" -o scale.mid

# From a file
mml2midi examples/scale.mml -o scale.mid

# Multiple parts as separate instrument voices in one file
mml2midi part1.mml part2.mml -o duet.mid --program 0 --program 40

# Also (or instead) export the melody as a 12-hole ocarina fingering tab PDF
mml2midi examples/scale.mml -o scale.mid --ocarina-pdf scale-tab.pdf
mml2midi examples/scale.mml --ocarina-pdf scale-tab.pdf  # PDF only
```

`--program` takes a General MIDI program number (0-127); pass it once per
input to give each voice its own instrument. Run `mml2midi --help` for
the full option list.

## Library usage

```python
from mml2midi import build_midi, write_midi_file, render_ocarina_tab_pdf

midi_file = build_midi("MML@cdefgab>c;,,;")  # a mido.MidiFile
write_midi_file("MML@cdefgab>c;,,;", "scale.mid")
render_ocarina_tab_pdf("MML@cdefgab>c;,,;", "scale-tab.pdf", title="Scale")
```

## Ocarina tabs

`--ocarina-pdf` renders a melody as fingering diagrams for a 12-hole
("English pendant") ocarina in the key of C -- the same format used by
real ocarina fingering charts, not a game-specific notation. Since a
physical ocarina is monophonic, only the first input's melody part is
used; the whole part is transposed by whichever octave shift fits the
most notes into the instrument's playable range (A4-F6), and any note
still out of range after that is drawn in red. See
[MML_GRAMMAR.md](MML_GRAMMAR.md#ocarina-tab-fingering-data) for where the
fingering data comes from.

## MML grammar

See [MML_GRAMMAR.md](MML_GRAMMAR.md) for the full token reference, the
skill-roll check note behavior, the octave-wrap quirk, and how the grammar
was verified against real Mabinogi output.

## Tests

```bash
pytest
```
