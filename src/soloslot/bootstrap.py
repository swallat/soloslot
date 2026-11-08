"""Set up stem separation for the installed (frozen) app.

The installers do not contain PyTorch/Demucs. On first use the app downloads `uv` (checksum
verified), lets it create a private Python environment in the user's data folder and installs
`soloslot[separate]` there. Separation then runs as `python -m soloslot ...` in that environment
and its console output is streamed to the window.

Qt-free and standard library only, so it is testable.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path

from soloslot.update import Fetch, UpdateError, expected_checksum, fetch_bytes

UV_VERSION = "0.13.5"  # keep in step with mise.toml / CI
PYTHON_VERSION = "3.12"  # what the pinned PyTorch wheels support
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"

Log = Callable[[str], None]


class SetupError(RuntimeError):
    pass


def data_dir(platform: str | None = None, environ: dict[str, str] | None = None) -> Path:
    platform = platform or sys.platform
    env = os.environ if environ is None else environ
    if platform.startswith("win"):
        base = Path(env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "soloslot"


def env_dir() -> Path:
    return data_dir() / "separate-env"


def env_python(root: Path | None = None, platform: str | None = None) -> Path:
    root = root or env_dir()
    if (platform or sys.platform).startswith("win"):
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def is_installed(root: Path | None = None) -> bool:
    """True once the separation environment finished installing."""
    root = root or env_dir()
    return (root / ".installed").is_file() and env_python(root).is_file()


def uv_asset(platform: str | None = None, machine: str | None = None) -> tuple[str, str]:
    """(file name, executable name) of the uv release archive for this machine."""
    platform = platform or sys.platform
    machine = (machine or _machine()).lower()
    arm = machine in ("arm64", "aarch64")
    if platform.startswith("win") and not arm:
        return "uv-x86_64-pc-windows-msvc.zip", "uv.exe"
    if platform == "darwin":
        return f"uv-{'aarch64' if arm else 'x86_64'}-apple-darwin.tar.gz", "uv"
    if platform.startswith("linux") and not arm:
        return "uv-x86_64-unknown-linux-gnu.tar.gz", "uv"
    raise SetupError(f"stem separation setup is not available for {platform}/{machine}")


def _machine() -> str:
    import platform

    return platform.machine()


def ensure_uv(
    folder: Path, *, fetch: Fetch = fetch_bytes, log: Log = print, **asset_args: str
) -> Path:
    """Download uv into `folder` (checksum verified) unless it is already there."""
    name, exe = uv_asset(**asset_args)
    target = folder / exe
    if target.is_file():
        return target
    base = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{name}"
    log(f"Downloading uv {UV_VERSION} ...")
    try:
        data = fetch(base)
        sums = fetch(base + ".sha256").decode("utf-8", "replace")
    except (OSError, UpdateError) as e:
        raise SetupError(f"could not download uv: {e}") from e
    import hashlib

    expected = expected_checksum(sums, name)
    if expected is None:  # the .sha256 file may list a path or only the hash
        words = sums.split()
        expected = words[0].lower() if words else None
    if expected != hashlib.sha256(data).hexdigest():
        raise SetupError("uv download failed its checksum; discarded")
    folder.mkdir(parents=True, exist_ok=True)
    member = _extract(data, name, exe)
    target.write_bytes(member)
    target.chmod(0o755)
    return target


def _extract(data: bytes, archive: str, exe: str) -> bytes:
    if archive.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                if Path(info.filename).name == exe:
                    return z.read(info)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
            for info in t.getmembers():
                if info.isfile() and Path(info.name).name == exe:
                    f = t.extractfile(info)
                    if f is not None:
                        return f.read()
    raise SetupError(f"{exe} not found in {archive}")


def child_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for child processes, undoing what a PyInstaller bundle changes.

    The bundle prepends its own library folder to LD_LIBRARY_PATH / DYLD_LIBRARY_PATH (keeping
    the original in *_ORIG); a child Python or uv would otherwise load the bundled libraries.
    """
    env = dict(os.environ if environ is None else environ)
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.pop(f"{var}_ORIG", None)
        if original is not None:
            env[var] = original
        elif getattr(sys, "frozen", False):
            env.pop(var, None)
    for var in ("PYTHONHOME", "PYTHONPATH"):
        env.pop(var, None)
    env.update(PYTHONUNBUFFERED="1", PYTHONUTF8="1")
    return env


def stream(cmd: Sequence[str | Path], log: Log, *, cwd: Path | None = None) -> int:
    """Run `cmd`, forwarding each output line (progress bars included) to `log`."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window on Windows
    with subprocess.Popen(
        [str(c) for c in cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,  # universal newlines: \r progress updates become lines too
        encoding="utf-8",
        errors="replace",
        env=child_env(),
        cwd=cwd,
        creationflags=flags,
    ) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.strip():
                log(line.rstrip())
        return proc.wait()


def install_separation(
    version: str,
    *,
    root: Path | None = None,
    log: Log = print,
    run: Callable[..., int] = stream,
    fetch: Fetch = fetch_bytes,
) -> Path:
    """Create the environment and install soloslot[separate]. Returns its python."""
    root = root or env_dir()
    if is_installed(root):
        return env_python(root)
    with tempfile.TemporaryDirectory() as tmp:
        uv = ensure_uv(Path(tmp), fetch=fetch, log=log)
        python = env_python(root)
        torch = ["torch", "torchaudio", "--index-url", TORCH_CPU_INDEX]
        steps: list[tuple[str, list[str | Path]]] = [
            (
                f"Creating Python {PYTHON_VERSION} environment ...",
                [uv, "venv", "--python", PYTHON_VERSION, "--clear", root],
            )
        ]
        if sys.platform.startswith("linux"):  # the default Linux wheels bundle CUDA (GBs)
            steps.append(
                (
                    "Installing PyTorch (CPU) ...",
                    [uv, "pip", "install", "--python", python, *torch],
                )
            )
        steps.append(
            (
                f"Installing soloslot[separate]=={version} (this takes a while) ...",
                [uv, "pip", "install", "--python", python, f"soloslot[separate]=={version}"],
            )
        )
        root.parent.mkdir(parents=True, exist_ok=True)
        for message, cmd in steps:
            log(message)
            if run(cmd, log) != 0:
                raise SetupError(f"setup failed in step: {message} See Details for the output.")
    root.mkdir(parents=True, exist_ok=True)
    (root / ".installed").write_text(version, encoding="utf-8")
    log("Stem separation is ready.")
    return python


def run_separation(
    args: Sequence[str], *, log: Log = print, python: Path | None = None, run=stream
) -> bool:
    """Run `python -m soloslot <args>` in the separation environment. True on success."""
    python = python or env_python()
    return run([python, "-m", "soloslot", *args], log) == 0
