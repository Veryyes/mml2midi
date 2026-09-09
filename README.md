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

# Also (or instead) export the melody as an ocarina fingering tab PDF
mml2midi examples/scale.mml -o scale.mid --ocarina12 scale-tab.pdf
mml2midi examples/scale.mml --ocarina12 scale-tab.pdf   # PDF only, 12-hole
mml2midi examples/scale.mml --ocarina6 scale-tab.pdf    # PDF only, 6-hole
mml2midi examples/scale.mml --ocarina6 tab6.pdf --ocarina12 tab12.pdf  # both
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
render_ocarina_tab_pdf("MML@cdefgab>c;,,;", "scale-tab-6h.pdf", title="Scale", hole_count=6)
```

## Ocarina tabs

`--ocarina6 PATH` / `--ocarina12 PATH` render a melody as fingering diagrams
for a real ocarina in the key of C -- the same format used by real ocarina
fingering charts, not a game-specific notation. Pass one, the other, or
both (each writes its own file). Since a physical ocarina is monophonic,
only the first input's melody part is used; the whole part is transposed
by whichever octave shift fits the most notes into the instrument's
playable range.

Any note that still doesn't fit (common when a song's overall range is
wider than the instrument's) is, by default, individually shifted by
whole octaves to make it playable -- drawn in **blue** with an `↑`/`↓`
marker so you can see it'll sound an octave off from the rest of the
song. Pass `--no-octave-fold` (or `fold_octaves=False` in the library) to
leave such notes unplayable and drawn in **red** instead. See
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
