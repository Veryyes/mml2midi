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

## Ocarina tab fingering data

`--ocarina-pdf` targets one of two real instruments in the key of C,
selected with `--ocarina12` (the default) or `--ocarina6`. Neither
fingering table is guesswork -- both were transcribed from real published
charts.

**12-hole** ("English pendant"), 21 chromatic notes, A4-F6. The hole
numbering and note-to-fingering table in `ocarina.py` come from the
`GLYPH_MAP`/`KEY_MAPS` fingering data in Mathias Panzenböck's
[Open 12 Hole Ocarina font and tab creator](https://github.com/panzi/ocarina_tabs)
(font/data licensed under the SIL Open Font License 1.1 -- per that
license's own terms, a document produced *using* the font/data, like the
PDFs this module generates, isn't itself subject to it), cross-checked
against [Imperial City Ocarina](https://www.imperialcityocarina.com/)'s
published 12-hole "Key of C" fingering charts. The on-page ocarina body
silhouette is also adapted from Panzenböck's project (its real outline,
not a freehand approximation), under the same license terms.

**6-hole**, a small pendant instrument reaching 17 chromatic notes (an
octave plus a major third). The fingering table -- including which two
notes need a half-covered hole -- was transcribed directly from
[OcarinaSongbook.com's Six Hole Ocarina Fingering Chart](https://ocarinasongbook.com/fingering-charts/six-hole/)
by reading its fingering diagrams pixel by pixel, not from an automated
text extraction (which loses the half-covered-hole distinction). That
chart doesn't name an absolute octave -- small pendant ocarinas vary by
maker -- so this module's 17-note range is labeled C5-E6 as a reasonable
default; the *pattern* of which holes to cover for the Nth note of the
scale is what's authoritative, not the exact octave number. The 6-hole
body silhouette is this project's own simple original drawing (a small
rounded pendant shape with the mouthpiece pointing down toward the two
lower holes), not traced from any source.

A song is transposed by whichever octave shift fits the most notes into
the target instrument's range; any note still outside that range
afterward is drawn in red, since one physical ocarina simply can't play
everything a full MML score can.
