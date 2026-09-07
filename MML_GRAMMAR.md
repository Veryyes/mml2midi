# MML grammar

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

## Skill-Check

Often times players will add a skill-check sequence of notes at the begnning of a score (e.g. `l64c&c&c&c&c&c&c&c&...&c`).
This is to quicky check if the player will play the song correctly without error

This is detected structurally (the same pitch tied to itself 8+
times in a row, right at the start of a part) and silenced by default: it
still occupies its original duration, so the part stays in sync with the
rest of the score, but produces no note. Pass `strip_check_note=False` to
the library functions, or `--keep-check-note` to the CLI, to keep it.

## A quirk worth knowing about

Notes are computed relative to octave 0 and folded into a 0-96 window
*before* the final offset to a MIDI note number — so a note built from an
extreme octave/accidental combination (e.g. `o9b+`) wraps down by whole
octaves instead of clipping or overflowing. This isn't a generic MML rule;
it's a real characteristic of Mabinogi's own note calculation, preserved
here on purpose so this converter's output matches what the game actually
produces (see `MMLParseError`-adjacent comments in `parser.py` for the
exact arithmetic).
