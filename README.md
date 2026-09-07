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

See [MML_GRAMMAR.md](MML_GRAMMAR.md) for the full token reference, the
skill-roll check note behavior, the octave-wrap quirk, and how the grammar
was verified against real Mabinogi output.

## Tests

```bash
pytest
```
