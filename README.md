# stem-solo-gap

[![CI](https://github.com/swallat/stem-solo-gap/actions/workflows/ci.yml/badge.svg)](https://github.com/swallat/stem-solo-gap/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Clear a solo section out of stem files to build play-along backing tracks.

You split a recording into stems (Moises, Demucs, ...), say where the solo is and which
stems should stay audible in it. The tool silences everything else in that region
(with short fades against clicks) and writes the stems and a finished backing track.

## Install

Needs [uv](https://docs.astral.sh/uv/), which fetches a suitable Python (3.12 or newer) itself.

```bash
uv tool install git+https://github.com/swallat/stem-solo-gap.git
stem-solo-gap --help
```

Update with `uv tool upgrade stem-solo-gap`. Or install from a checkout:

```bash
uv tool install .
```

## Use

Put the stems of each song (WAV, FLAC or MP3) in their own folder, then describe the solo in
a TOML file. There are two ways to organise that.

### One config per song (run it inside the stems folder)

Save a `solo.toml` next to the stems of the song (see `solo.example.toml`):

```toml
hear  = ["piano", "bass", "drums"]   # stems that stay audible in the solo
skip  = ["visualizer"]               # ignore the full mix
solos = [ { start = "2:15", end = "3:40" } ]
```

and run the tool in that folder:

```bash
cd stems/Interplay
stem-solo-gap                  # uses ./solo.toml
stem-solo-gap --dry-run        # show what would happen, write nothing
```

The song name defaults to the folder name, the result goes to `./out/`. You can also pass
several configs at once, e.g. `stem-solo-gap stems/*/solo.toml`.

### One config for many songs

Copy `songs.example.toml` to `songs.toml` and list the songs as `[[song]]` tables:

```toml
[defaults]
hear = ["piano", "bass", "drums"]   # shared by all songs

[[song]]
name   = "Interplay"
folder = "stems/Interplay"
bpm    = 113
solos  = [ { start_bar = 36, end_bar = 97 } ]
```

```bash
stem-solo-gap songs.toml                    # all songs
stem-solo-gap songs.toml --song Interplay   # one song
```

Here the output goes to `out/<song>/`, next to the config file.

In both layouts every stem is written with the same name as WAV or FLAC (set `format = "flac"`
for FLAC; the default is WAV). MP3 input becomes 24 bit, WAV/FLAC input keeps its bit depth. You
also get `<song> - Backing Track.wav` or `.flac` (the sum of all processed stems, 24 bit). The
`out/` folder is not read as input on the next run.

**Your original files are never modified.** Everything is written to the output folder; if
`output` would resolve to the stems folder itself, the tool refuses and writes nothing.

### Config

- **`hear`**: stems that stay audible in the solo; every other stem is silenced there.
  Matching is a case-insensitive substring of the stem name (`"piano"` matches
  `Grand Piano`). Stems a song does not have are ignored. A `hear` entry that matches
  nothing is reported as a warning, so a typo cannot silently mute a stem.
- **`skip`**: files/stems to ignore, e.g. the full mix (`["visualizer"]`).
- **`solos`**: one or more solo regions, see below.
- **`format`**: output format, `"wav"` (default) or `"flac"`. Applies to the stems and the backing
  track. FLAC is lossless and smaller; float or 32 bit input becomes 24 bit there.
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

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute, [CHANGELOG.md](CHANGELOG.md) for
changes and [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

[MIT](LICENSE) © 2026 Sebastian Wallat.

The tool installs these libraries, which keep their own licenses: click (BSD-3-Clause),
NumPy (BSD-3-Clause and other permissive licenses) and python-soundfile (BSD-3-Clause), whose
binary wheels include the libsndfile library (LGPL-2.1-or-later).

## Your audio

The tool only processes files you provide. It does not include, download or split any
recordings. Make sure you have the right to use your recordings and stems; the output keeps
the copyright status of the original. For that reason, `*.wav`, `*.mp3` and `*.flac` are
git-ignored and the tests use synthetic audio only.
