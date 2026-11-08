<p align="center">
  <img src="docs/logo.svg" alt="soloslot logo" width="420">
</p>

# soloslot

[![CI](https://github.com/swallat/soloslot/actions/workflows/ci.yml/badge.svg)](https://github.com/swallat/soloslot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Make room for your solo: turn any song into a play-along backing track.

Give it a song (MP3, WAV, FLAC, ...), say where the solo is and which instruments should drop
out there (or which ones stay). soloslot splits the song into stems with
[Demucs](https://github.com/adefossez/demucs), mutes the chosen stems in the solo (with short
fades against clicks) and writes the stems plus a finished backing track. If you already have
stems (Moises, Demucs, ...), it works on those directly.

```bash
soloslot "Blue Bossa.mp3" --solo 1:05-2:40 --mute guitar
soloslot "Interplay.flac" --solo 2:15-3:40 --hear piano,bass,drums
```

## Install

Needs [uv](https://docs.astral.sh/uv/), which fetches a suitable Python (3.12 or newer) itself.

```bash
# with stem separation (pulls in PyTorch, a large download)
uv tool install "soloslot[separate] @ git+https://github.com/swallat/soloslot.git"

# without, if you only work on stems you already have
uv tool install git+https://github.com/swallat/soloslot.git

soloslot --help
```

Update with `uv tool upgrade soloslot`. Or install from a checkout: `uv tool install ".[separate]"`.

The first separation downloads the Demucs model (about 50 to 100 MB) and caches it. Separation
runs on an NVIDIA GPU if PyTorch finds one, otherwise on the CPU, where a song takes a few
minutes.

## Use

### A song, straight from the command line

```bash
soloslot song.mp3 --solo 2:15-3:40 --mute guitar            # guitar drops out in the solo
soloslot song.mp3 --solo 2:15-3:40 --hear piano,bass,drums  # only these stay in the solo
soloslot song.mp3 --solo 1:05-2:40 --solo 4:10-5:02 --mute guitar,piano
soloslot song.mp3 --solo 2:15-3:40 --mute guitar --dry-run  # show what would happen
```

- `--solo START-END`: timestamps as in the config (`135.5`, `2:15`, `1:02:15.5`); repeat it
  for several solos.
- `--mute STEMS` mutes the named stems in the solo, everything else stays. `--hear STEMS` is
  the opposite: only the named stems stay. Use one of the two.
- `--model`: the Demucs model, default `htdemucs_6s`, which splits into **drums, bass, guitar,
  piano, vocals and other**. `htdemucs` and `htdemucs_ft` give drums, bass, vocals and other,
  and are a bit cleaner for those.
- `--format flac`, `-o/--output DIR`: see below. The default output is `out/<song>/` next to the
  song.

You get `drums.wav`, `bass.wav`, ... with the solo muted where you asked, plus
`<song> - Backing Track.wav`. The untouched separated stems are kept in `separated/<model>/` in
the output folder and are reused on the next run, so trying another solo region does not split
the song again.

### Stems you already have

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
soloslot                  # uses ./solo.toml
soloslot --dry-run        # show what would happen, write nothing
```

The song name defaults to the folder name, the result goes to `./out/`. You can also pass
several configs at once, e.g. `soloslot stems/*/solo.toml`.

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
soloslot songs.toml                    # all songs
soloslot songs.toml --song Interplay   # one song
```

Here the output goes to `out/<song>/`, next to the config file.

In both layouts every stem is written with the same name as WAV or FLAC (set `format = "flac"`
for FLAC; the default is WAV). MP3 input becomes 24 bit, WAV/FLAC input keeps its bit depth. You
also get `<song> - Backing Track.wav` or `.flac` (the sum of all processed stems, 24 bit). The
`out/` folder is not read as input on the next run.

**Your original files are never modified.** Everything is written to the output folder; if
`output` would resolve to the stems folder itself, the tool refuses and writes nothing.

### Config

- **`input`**: a full song to split into stems first (instead of `folder`), e.g.
  `input = "Interplay.flac"`. The song name defaults to the file name.
- **`model`**: Demucs model for `input`, default `htdemucs_6s` (see above).
- **`hear`**: stems that stay audible in the solo; every other stem is silenced there.
  Matching is a case-insensitive substring of the stem name (`"piano"` matches
  `Grand Piano`). Stems a song does not have are ignored. A `hear` entry that matches
  nothing is reported as a warning, so a typo cannot silently mute a stem.
- **`mute`**: the opposite of `hear`: stems that are silenced in the solo; every other stem
  stays. Use either `hear` or `mute` for a song.
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
binary wheels include the libsndfile library (LGPL-2.1-or-later). The `separate` extra adds
Demucs (MIT) and PyTorch (BSD-3-Clause); the Demucs models are downloaded on first use.

## Your audio

The tool only processes files you provide, on your own computer. It does not include or
download any recordings; only the Demucs model is downloaded. Make sure you have the right to use your recordings and stems; the output keeps
the copyright status of the original. For that reason, `*.wav`, `*.mp3` and `*.flac` are
git-ignored and the tests use synthetic audio only.
