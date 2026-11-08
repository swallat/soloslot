# stem-solo-gap

Clear a solo section out of stem WAVs to build play-along backing tracks.

You split a recording into stems (Moises, Demucs, ...), say where the solo is and which
stems should stay audible in it. The tool silences everything else in that region
(with short fades against clicks) and writes the stems and a finished backing track.

## Install

```bash
uv tool install git+ssh://git@github.com/swallat/stem-solo-gap.git
stem-solo-gap --help
```

Or from a checkout:

```bash
uv tool install .
```

## Use

1. Put the stems of each song (WAV, FLAC or MP3) in their own folder, e.g. `stems/Interplay/`.
2. Copy `songs.example.toml` to `songs.toml` and describe your songs:

   ```toml
   [defaults]
   hear = ["piano", "bass", "drums"]   # stems that stay audible in the solo

   [[song]]
   name   = "Interplay"
   folder = "stems/Interplay"
   bpm    = 113
   solos  = [ { start_bar = 36, end_bar = 97 } ]
   ```

3. Run it:

   ```bash
   stem-solo-gap songs.toml             # all songs
   stem-solo-gap songs.toml --song Interplay
   stem-solo-gap songs.toml --dry-run   # show what would happen, write nothing
   ```

Output goes to `out/<song>/`: every stem as WAV with the same name (MP3 input becomes 24 bit; WAV/FLAC keep their bit depth), plus
`<song> - Backing Track.wav` (the sum of all processed stems, 24 bit).

### Config

- **`hear`**: stems that stay audible in the solo; every other stem is silenced there.
  Matching is a case-insensitive substring of the stem name (`"piano"` matches
  `Grand Piano`). Stems a song does not have are ignored. A `hear` entry that matches
  nothing is reported as a warning, so a typo cannot silently mute a stem.
- **`skip`**: files/stems to ignore, e.g. the full mix (`["visualizer"]`).
- **`solos`**: one or more solo regions, see below.
- **`fade_ms`**, **`mixdown`**, **`output`**: see `songs.example.toml`.
- Defaults live in `[defaults]` and can be overridden per song.
- Relative paths are resolved against the directory of the config file.

### Solo regions

Give each region either as **timestamps** or as **bars**:

```toml
# Timestamps: no bpm needed
solos = [ { start = "2:15", end = "3:40" } ]

# Several solos in one song, mixing seconds and mm:ss
solos = [ { start = 135.5, end = "3:40" }, { start = "4:10.5", end = "5:02" } ]

# Bars: needs bpm on the song
bpm   = 113
solos = [ { start_bar = 36, end_bar = 97 } ]
```

- **Timestamps** are seconds from the start of the file: `135.5`, `"2:15"` (mm:ss) or
  `"1:02:15.5"` (h:mm:ss). Fractions of a second are allowed.
- **Bars** are counted from 1, bar 1 starts at the beginning of the file, and `end_bar` is the
  bar where the solo is over again (the solo covers `start_bar` up to, not including, `end_bar`).
  Optional per song: `beats_per_bar` (default 4) for other meters, and `offset` (a timestamp)
  if the file has a lead-in before bar 1.
- Use only one of the two forms per region.

Bars are converted to seconds with a constant tempo. For live recordings with a drifting
tempo, **use timestamps**. You can read them from the timeline of your player or DAW; in
Ableton Live, a locator at `36|1` is bar 36.

To convert a time into a bar number: `bar = seconds × bpm ÷ (60 × beats_per_bar) + 1`.

Stem names are read from Moises file names (`<title>-<Stem>-<key>-<tempo>bpm-<hz>hz.wav`);
other names are matched on the whole file name.

## Develop

[mise](https://mise.jdx.dev) provides `uv`; `uv` manages Python and packages.

```bash
mise install      # uv
mise run install  # uv sync
mise run check    # ruff + pytest
mise tasks        # all tasks
```

## License

MIT
