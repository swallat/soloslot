<p align="center">
  <img src="https://raw.githubusercontent.com/swallat/soloslot/main/docs/logo.svg" alt="soloslot logo" width="420">
</p>

<h1 align="center">soloslot</h1>

<p align="center"><strong>Make room for your solo.</strong><br>
Turn any song into a play-along backing track in one command.</p>

<p align="center">
  <a href="https://github.com/swallat/soloslot/actions/workflows/ci.yml"><img src="https://github.com/swallat/soloslot/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
</p>

You know the song. You want to play the guitar part, the piano solo, the sax line. But the
record has the original player on it, right where you want to jump in.

soloslot takes the song, finds the instruments you name, and takes them **out of the solo
section only**. The band keeps playing, the song stays whole before and after, and the gap is
yours.

```bash
soloslot "Blue Bossa.mp3" --solo 1:05-2:40 --mute guitar
```

That is the whole workflow: one song in, one backing track out.

## Why soloslot

- **Practice with the real recording.** No more generic backing tracks or MIDI band-in-a-box.
  You play with the actual band, the actual groove, the actual song.
- **Only the solo is muted.** Intro, theme and outro stay intact, so you play the song the way
  it goes, from the top, and step into the gap at the right moment.
- **Start from a plain MP3.** Drop in an MP3, WAV or FLAC. soloslot splits it into stems with
  [Demucs](https://github.com/adefossez/demucs), a state-of-the-art open-source separator. No
  stems? No problem.
- **Or bring your own stems.** Already have stems from Moises, Demucs or your DAW? soloslot works
  on those directly and needs no separation, no PyTorch and no GPU.
- **Say what goes, or what stays.** `--mute guitar` removes one instrument. `--hear
  piano,bass,drums` keeps only the rhythm section. Pick whichever is shorter to type.
- **Several solos, one run.** Repeat `--solo` for every section you want to play over.
- **Click-free edits.** Short fades at the edges of each gap, so there are no pops or abrupt
  cuts where the instrument leaves and returns.
- **Fast to try again.** The separation is cached. Change the solo region, mute another
  instrument, re-run: the song is not split twice.
- **Safe for your files.** Your originals are never modified. Everything goes to a separate
  output folder, and soloslot refuses to write over your input.
- **Private and offline.** Everything runs on your computer. Your recordings are never uploaded.
  Only the Demucs model is downloaded, once.
- **Lossless output.** WAV or FLAC, with the bit depth of your source preserved (MP3 input is
  written as 24 bit).
- **Plain-text config for repeat use.** Describe a song, or a whole repertoire, in a small TOML
  file. Give solos as timestamps or as bar numbers.

## What you get

For every song, an output folder with:

| File | What it is |
| --- | --- |
| `<song> - Backing Track.wav` | The finished play-along track: the whole song with your chosen instruments missing in the solo. Load it into your player and go. |
| `drums.wav`, `bass.wav`, `guitar.wav`, ... | The individual stems, each with the same mute applied. Handy for DAWs, for loops, or for mixing your own balance. Skip them with `--backing-only`. |
| `separated/<model>/` | The untouched stems from separation, kept so the next run is instant. |

## Install

You need [uv](https://docs.astral.sh/uv/). It fetches a suitable Python (3.12 or newer) for you.

```bash
# with stem separation (pulls in PyTorch, a large download)
uv tool install "soloslot[separate] @ git+https://github.com/swallat/soloslot.git"

# without it, if you only work on stems you already have
uv tool install git+https://github.com/swallat/soloslot.git

soloslot --help
```

Update with `uv tool upgrade soloslot`.

The first separation downloads the Demucs model (about 50 to 100 MB) and caches it. Separation
runs on an NVIDIA GPU if PyTorch finds one, otherwise on the CPU, where a song takes a few
minutes.

## Quick start

```bash
# The guitar drops out between 1:05 and 2:40
soloslot song.mp3 --solo 1:05-2:40 --mute guitar

# Only piano, bass and drums stay in the solo
soloslot song.flac --solo 2:15-3:40 --hear piano,bass,drums

# Two solos, two instruments gone
soloslot song.mp3 --solo 1:05-2:40 --solo 4:10-5:02 --mute guitar,piano

# Look first, write nothing
soloslot song.mp3 --solo 2:15-3:40 --mute guitar --dry-run
```

| Option | Meaning |
| --- | --- |
| `--solo START-END` | A solo region. Repeat it for several. Times like `135.5`, `2:15`, `1:02:15.5`. |
| `--mute STEMS` | Silence these stems in the solo; everything else stays. |
| `--hear STEMS` | The opposite: only these stems stay in the solo. Use one of the two. |
| `--model` | Demucs model. Default `htdemucs_6s` splits into **drums, bass, guitar, piano, vocals, other**. `htdemucs` and `htdemucs_ft` give drums, bass, vocals, other, and are a bit cleaner at that. |
| `--backing-only` | Write only the backing track. |
| `--format flac` | Write FLAC instead of WAV. |
| `-o, --output DIR` | Output folder. Default: `out/<song>/` next to the song. |
| `--dry-run` | Show what would happen and write nothing. |

## Desktop window (optional)

```
uv tool install 'soloslot[gui,separate]'
soloslot-gui
```

Choose a song (or a folder with stems), enter the solo regions (`2:15-3:40`, one per line),
tick the stems to mute, pick an output folder and press the button. The console output
(including Demucs progress) is under the collapsible **Details** section.

Prebuilt installers (Windows `.exe`, macOS `.dmg`, Linux `.AppImage`) are attached to each
[release](https://github.com/swallat/soloslot/releases). They are not code-signed yet:
Windows SmartScreen shows "unknown publisher" (More info, Run anyway), and on macOS you open
the app once with right-click, Open.

The installers are slim and do not contain PyTorch, so splitting full songs with Demucs inside
the installed app is not available yet (use a stems folder, or install with
`uv tool install 'soloslot[gui,separate]'`).

The window checks for a newer release at startup and offers to download the installer
(checksum verified). Set `SOLOSLOT_NO_UPDATE_CHECK=1` to turn that off.

## Working with stems you already have

Put each song's stems (WAV, FLAC or MP3) in their own folder and describe the solo in a
`solo.toml` next to them (see `solo.example.toml`):

```toml
hear  = ["piano", "bass", "drums"]   # stems that stay audible in the solo
skip  = ["visualizer"]               # ignore the full mix
solos = [ { start = "2:15", end = "3:40" } ]
```

```bash
cd stems/Interplay
soloslot                  # uses ./solo.toml
soloslot --dry-run        # show what would happen, write nothing
```

The song name defaults to the folder name and the result goes to `./out/`. You can also pass
several configs at once, for example `soloslot stems/*/solo.toml`.

### A whole repertoire in one file

Copy `songs.example.toml` to `songs.toml` and list your songs as `[[song]]` tables:

```toml
[defaults]
hear = ["piano", "bass", "drums"]   # shared by all songs

[[song]]
name   = "Interplay"
folder = "stems/Interplay"
bpm    = 113
solos  = [ { start_bar = 36, end_bar = 97 } ]

[[song]]
name   = "Blue Bossa"
input  = "Blue Bossa.mp3"            # a full song: split it first
mute   = ["guitar"]
solos  = [ { start = "1:05", end = "2:40" } ]
```

```bash
soloslot songs.toml                    # all songs
soloslot songs.toml --song Interplay   # one song
```

Output goes to `out/<song>/`, next to the config file. Defaults live in `[defaults]` and any
song can override them.

## Configuration reference

- **`input`**: a full song to split into stems first, instead of `folder`. The song name
  defaults to the file name.
- **`model`**: Demucs model for `input`, default `htdemucs_6s`.
- **`hear`**: stems that stay audible in the solo; every other stem is silenced there. Matching
  is a case-insensitive substring of the stem name (`"piano"` matches `Grand Piano`). Stems a
  song does not have are ignored. A `hear` entry that matches nothing is reported as a warning,
  so a typo cannot silently mute the wrong thing.
- **`mute`**: the opposite of `hear`. Use either one per song.
- **`skip`**: files or stems to ignore, such as a full mix (`["visualizer"]`).
- **`solos`**: one or more solo regions, see below.
- **`format`**: `"wav"` (default) or `"flac"`. FLAC is lossless and smaller; float or 32 bit
  input becomes 24 bit there.
- **`stems`**: `stems = false` writes only the backing track.
- **`fade_ms`**, **`mixdown`**, **`output`**: see `songs.example.toml`.
- Relative paths are resolved against the directory of the config file.

### Solo regions: timestamps or bars

```toml
# Timestamps: no tempo needed
solos = [ { start = "2:15", end = "3:40" } ]

# Several solos, mixing seconds and mm:ss
solos = [ { start = 135.5, end = "3:40" }, { start = "4:10.5", end = "5:02" } ]

# Bars: needs bpm on the song
bpm   = 113
solos = [ { start_bar = 36, end_bar = 97 } ]
```

- **Timestamps** are seconds from the start of the file: `135.5`, `"2:15"` or `"1:02:15.5"`.
  Read them off your player or DAW.
- **Bars** count from 1, bar 1 starts at the beginning of the file, and `end_bar` is the bar
  where the solo is over again. Use `beats_per_bar` (default 4) for other meters and `offset`
  if the file has a lead-in before bar 1.
- Bars assume a constant tempo. For live recordings with a drifting tempo, use timestamps.

Stem names are read from Moises file names (`<title>-<Stem>-<key>-<tempo>bpm-<hz>hz.wav`);
other names are matched on the whole file name.

## Your audio

soloslot only processes files you provide, on your own computer. It includes no recordings and
downloads none; only the Demucs model is fetched. Make sure you have the right to use your
recordings. The output keeps the copyright status of the original. That is why `*.wav`,
`*.mp3` and `*.flac` are git-ignored and the tests use synthetic audio only.

## Develop

[mise](https://mise.jdx.dev) provides `uv`; `uv` manages Python and packages.

```bash
mise install      # uv
mise run install  # uv sync
mise run check    # ruff + pytest
mise tasks        # all tasks
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute, [CHANGELOG.md](CHANGELOG.md) for changes
and [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

[MIT](LICENSE) © 2026 Sebastian Wallat.

soloslot installs these libraries, which keep their own licenses: click (BSD-3-Clause), NumPy
(BSD-3-Clause and other permissive licenses) and python-soundfile (BSD-3-Clause), whose binary
wheels include libsndfile (LGPL-2.1-or-later). The `separate` extra adds Demucs (MIT) and
PyTorch (BSD-3-Clause).
