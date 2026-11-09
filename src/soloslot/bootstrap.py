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
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path

from soloslot.update import Fetch, UpdateError, expected_checksum, fetch_bytes

UV_VERSION = "0.13.5"  # keep in step with mise.toml / CI
PYTHON_VERSION = "3.13"  # newest with wheels for torch, lameenc and sphn on all supported systems
INTEL_MAC_PYTHON_VERSION = "3.12"  # demucs needs torch<2.3 on Intel Macs; no wheels beyond 3.12
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


def installed_version(root: Path | None = None) -> str:
    """The soloslot version the separation environment was set up with ('' if unknown)."""
    try:
        return ((root or env_dir()) / ".installed").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


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


def python_version(platform: str | None = None, machine: str | None = None) -> str:
    platform = platform or sys.platform
    machine = (machine or _machine()).lower()
    if platform == "darwin" and machine not in ("arm64", "aarch64"):
        return INTEL_MAC_PYTHON_VERSION
    return PYTHON_VERSION


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


def remove_stale_python_links(python_dir: Path) -> None:
    """Delete `cpython-3.13-...` links uv left behind that can no longer be traversed.

    A previous run may have created the minor-version link (a junction on Windows) that Windows
    then refuses to follow (os error 448); uv would trip over it when looking for a Python.
    """
    if not python_dir.is_dir():
        return
    for entry in python_dir.glob("cpython-*"):
        if re.match(r"cpython-\d+\.\d+-", entry.name) and not entry.exists():
            for remove in (os.rmdir, os.unlink):  # a junction is a dir, a symlink a file
                try:
                    remove(entry)
                    break
                except OSError:
                    continue


def find_managed_python(python_dir: Path, version: str, platform: str | None = None) -> Path | None:
    """The interpreter of the newest `cpython-<version>.<patch>-...` uv unpacked, or None.

    It is addressed by its real (patch version) folder, never through the minor-version link.
    """
    windows = (platform or sys.platform).startswith("win")
    exe = Path("python.exe") if windows else Path("bin") / "python"
    found: list[tuple[int, Path]] = []
    for entry in python_dir.glob(f"cpython-{version}.*-*"):
        match = re.match(rf"cpython-{re.escape(version)}\.(\d+)-", entry.name)
        if match and (entry / exe).is_file():
            found.append((int(match.group(1)), entry / exe))
    return max(found)[1] if found else None


def is_link_error(output: str) -> bool:
    """True if uv's output shows Windows refusing to create the Python link (os error 448)."""
    text = output.lower()
    return "os error 448" in text or "untrusted mount point" in text


def uv_env(
    environ: dict[str, str] | None = None,
    root: Path | None = None,
    python_dir: Path | None = None,
) -> dict[str, str]:
    """child_env() plus settings that isolate uv from the user's own Python/uv setup.

    uv would otherwise find e.g. a scoop/pyenv/system Python (which may be unusable, like a
    junction on Windows) or read the user's uv.toml. Python and cache live in our data folder.
    """
    base = root or data_dir()
    env = child_env(environ)
    # Drop user settings that select/steer Python. Of the managed/preference/no-managed
    # options only one may be set: uv rejects e.g. UV_MANAGED_PYTHON together with
    # UV_PYTHON_PREFERENCE ("cannot be used with --python-preference").
    for var in (
        "UV_PYTHON",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON_PREFERENCE",
        "UV_NO_MANAGED_PYTHON",
        "UV_SYSTEM_PYTHON",
    ):
        env.pop(var, None)
    env.update(
        UV_PYTHON_INSTALL_DIR=str(python_dir or base / "python"),
        UV_CACHE_DIR=str(base / "uv-cache"),
        UV_MANAGED_PYTHON="1",  # only uv's own Python; never scoop/pyenv/system ones
        UV_PYTHON_DOWNLOADS="automatic",
        UV_NO_CONFIG="1",
    )
    return env


def stream(
    cmd: Sequence[str | Path],
    log: Log,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run `cmd`, forwarding each output line (progress bars included) to `log`."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window on Windows
    with subprocess.Popen(
        [str(c) for c in cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,  # universal newlines: \r progress updates become lines too
        encoding="utf-8",
        errors="replace",
        env=env if env is not None else child_env(),
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
        if installed_version(root) == version:
            return env_python(root)
        return _upgrade_soloslot(version, root, log, run, fetch)
    with tempfile.TemporaryDirectory() as tmp:
        uv = ensure_uv(Path(tmp), fetch=fetch, log=log)
        python = env_python(root)
        py_version = python_version()
        torch = ["torch", "torchaudio", "--index-url", TORCH_CPU_INDEX]
        steps: list[tuple[str, list[str | Path]]] = [
            (
                f"Creating Python {py_version} environment ...",
                [uv, "venv", "--python", py_version, "--clear", root],
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
        python_dir = root.parent / "python"
        isolated = uv_env(root=root.parent, python_dir=python_dir)
        for index, (message, cmd) in enumerate(steps):
            log(message)
            if index == 0:  # creating the venv installs Python, which can hit os error 448
                code = _run_venv_step(cmd, log, run, isolated, python_dir, py_version, root)
            else:
                code = run(cmd, log, env=isolated)
            if code != 0:
                raise SetupError(f"setup failed in step: {message} See Details for the output.")
    root.mkdir(parents=True, exist_ok=True)
    (root / ".installed").write_text(version, encoding="utf-8")
    log("Stem separation is ready.")
    return python


def _upgrade_soloslot(
    version: str, root: Path, log: Log, run: Callable[..., int], fetch: Fetch
) -> Path:
    """The app was updated: bring soloslot in the existing environment to the same version.

    Only soloslot is reinstalled; PyTorch and Demucs stay, so this is quick. Without it the
    environment would run an old command line that does not know new options.
    """
    python = env_python(root)
    with tempfile.TemporaryDirectory() as tmp:
        uv = ensure_uv(Path(tmp), fetch=fetch, log=log)
        message = f"Updating soloslot in the separation environment to {version} ..."
        log(message)
        isolated = uv_env(root=root.parent, python_dir=root.parent / "python")
        cmd = [uv, "pip", "install", "--python", python, f"soloslot[separate]=={version}"]
        if run(cmd, log, env=isolated) != 0:
            raise SetupError(f"setup failed in step: {message} See Details for the output.")
    (root / ".installed").write_text(version, encoding="utf-8")
    return python


def _run_venv_step(
    cmd: Sequence[str | Path],
    log: Log,
    run: Callable[..., int],
    env: dict[str, str],
    python_dir: Path,
    py_version: str,
    root: Path,
) -> int:
    """Create the venv. If Windows refuses uv's Python link (os error 448), use the unpacked Python.

    uv downloads and unpacks Python completely before it creates the minor-version link, so
    after that failure the real `cpython-<patch>` folder is intact. Retry with its exact path and
    downloads off, so nothing is read through a link.
    """
    python_dir.mkdir(parents=True, exist_ok=True)
    remove_stale_python_links(python_dir)
    seen: list[str] = []

    def tee(line: str) -> None:
        seen.append(line)
        log(line)

    code = run(cmd, tee, env=env)
    if code == 0 or not is_link_error("\n".join(seen)):
        return code
    remove_stale_python_links(python_dir)
    python = find_managed_python(python_dir, py_version)
    if python is None:
        return code
    log(f"Windows refused uv's Python link; using {python} directly ...")
    direct = [*cmd]
    direct[direct.index(py_version)] = str(python)
    return run(direct, log, env={**env, "UV_PYTHON_DOWNLOADS": "never"})


def run_separation(
    args: Sequence[str], *, log: Log = print, python: Path | None = None, run=stream
) -> bool:
    """Run `python -m soloslot <args>` in the separation environment. True on success."""
    python = python or env_python()
    return run([python, "-m", "soloslot", *args], log) == 0
