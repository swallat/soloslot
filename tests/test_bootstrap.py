import hashlib
import io
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from soloslot import bootstrap
from soloslot.bootstrap import (
    SetupError,
    child_env,
    data_dir,
    ensure_uv,
    env_python,
    find_managed_python,
    install_separation,
    is_link_error,
    remove_stale_python_links,
    run_separation,
    stream,
    uv_asset,
    uv_env,
)


def test_data_dir():
    assert data_dir("win32", {"LOCALAPPDATA": "C:/L"}) == Path("C:/L/soloslot")
    assert data_dir("linux", {"XDG_DATA_HOME": "/x"}) == Path("/x/soloslot")
    assert data_dir("linux", {}).parts[-3:] == (".local", "share", "soloslot")
    assert data_dir("darwin", {}).parts[-3:] == ("Library", "Application Support", "soloslot")


def test_env_python():
    assert env_python(Path("e"), "linux") == Path("e/bin/python")
    assert env_python(Path("e"), "win32") == Path("e/Scripts/python.exe")


def test_uv_asset():
    assert uv_asset("win32", "AMD64") == ("uv-x86_64-pc-windows-msvc.zip", "uv.exe")
    assert uv_asset("darwin", "arm64")[0] == "uv-aarch64-apple-darwin.tar.gz"
    assert uv_asset("linux", "x86_64")[0] == "uv-x86_64-unknown-linux-gnu.tar.gz"
    with pytest.raises(SetupError):
        uv_asset("linux", "aarch64")


def _tar(exe: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        info = tarfile.TarInfo("uv-x86_64-unknown-linux-gnu/uv")
        info.size = len(exe)
        t.addfile(info, io.BytesIO(exe))
    return buf.getvalue()


def test_ensure_uv_verifies_and_extracts(tmp_path):
    archive = _tar(b"binary")
    name = "uv-x86_64-unknown-linux-gnu.tar.gz"
    digest = hashlib.sha256(archive).hexdigest()

    def fetch(url):
        return f"{digest}  {name}\n".encode() if url.endswith(".sha256") else archive

    uv = ensure_uv(tmp_path, fetch=fetch, log=lambda _: None, platform="linux", machine="x86_64")
    assert uv.read_bytes() == b"binary"

    def bad(url):
        return b"0" * 64 if url.endswith(".sha256") else archive

    with pytest.raises(SetupError, match="checksum"):
        ensure_uv(tmp_path / "x", fetch=bad, log=lambda _: None, platform="linux", machine="x86_64")


def test_zip_extraction():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("uv.exe", b"exe")
    assert bootstrap._extract(buf.getvalue(), "uv.zip", "uv.exe") == b"exe"


def test_stream_forwards_lines():
    lines = []
    code = stream([sys.executable, "-c", "print('a'); print('b')"], lines.append)
    assert code == 0
    assert lines == ["a", "b"]


def test_install_separation_runs_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ensure_uv", lambda folder, **kw: Path("uv"))
    calls = []

    envs = []

    def run(cmd, log, env=None):
        calls.append([str(c) for c in cmd])
        envs.append(env)
        return 0

    root = tmp_path / "env"
    install_separation("1.2.3", root=root, log=lambda _: None, run=run)
    assert calls[0][1:3] == ["venv", "--python"]
    assert any("soloslot[separate]==1.2.3" in c for call in calls for c in call)
    assert (root / ".installed").read_text() == "1.2.3"
    assert all(e["UV_NO_CONFIG"] == "1" for e in envs)
    assert envs[0]["UV_PYTHON_INSTALL_DIR"] == str(tmp_path / "python")


def test_install_separation_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ensure_uv", lambda folder, **kw: Path("uv"))
    with pytest.raises(SetupError, match="failed"):
        install_separation(
            "1.2.3", root=tmp_path / "env", log=lambda _: None, run=lambda cmd, log, env=None: 1
        )
    assert not (tmp_path / "env" / ".installed").exists()


def test_run_separation():
    seen = []
    ok = run_separation(["a.mp3"], python=Path("py"), run=lambda cmd, log: seen.append(cmd) or 0)
    assert ok
    assert [str(c) for c in seen[0]] == ["py", "-m", "soloslot", "a.mp3"]


def test_child_env_undoes_bundle_changes():
    env = child_env(
        {
            "LD_LIBRARY_PATH": "/bundle",
            "LD_LIBRARY_PATH_ORIG": "/usr/lib",
            "PYTHONHOME": "/bundle",
            "PATH": "/bin",
        }
    )
    assert env["LD_LIBRARY_PATH"] == "/usr/lib"
    assert "LD_LIBRARY_PATH_ORIG" not in env
    assert "PYTHONHOME" not in env
    assert env["PATH"] == "/bin"
    assert env["PYTHONUTF8"] == "1"


def test_uv_env_isolates_user_python(tmp_path):
    user = {
        "UV_PYTHON": "x",
        "VIRTUAL_ENV": "v",
        "UV_PYTHON_PREFERENCE": "system",
        "UV_NO_MANAGED_PYTHON": "1",
        "UV_SYSTEM_PYTHON": "1",
        "UV_PYTHON_INSTALL_DIR": "C:/elsewhere",
        "PATH": "/bin",
    }
    env = uv_env(user, root=tmp_path)
    assert "UV_PYTHON" not in env and "VIRTUAL_ENV" not in env
    # uv rejects UV_MANAGED_PYTHON together with a python preference
    assert "UV_PYTHON_PREFERENCE" not in env and "UV_NO_MANAGED_PYTHON" not in env
    assert "UV_SYSTEM_PYTHON" not in env
    assert env["UV_PYTHON_INSTALL_DIR"] == str(tmp_path / "python")
    assert env["UV_MANAGED_PYTHON"] == "1"
    assert env["UV_CACHE_DIR"] == str(tmp_path / "uv-cache")


def test_python_version():
    assert bootstrap.python_version("win32", "AMD64") == "3.13"
    assert bootstrap.python_version("linux", "x86_64") == "3.13"
    assert bootstrap.python_version("darwin", "arm64") == "3.13"
    assert bootstrap.python_version("darwin", "x86_64") == "3.12"


def test_is_link_error():
    assert is_link_error(
        "error: Failed to create Python minor version link directory (os error 448)"
    )
    assert is_link_error("... nicht vertrauenswürdigen Bereitstellungspunkt ... os error 448")
    assert not is_link_error("error: something else")


def _fake_python(python_dir, name, windows=False):
    exe = python_dir / name / ("python.exe" if windows else "bin/python")
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    return exe


def test_find_managed_python_ignores_link_and_picks_newest(tmp_path):
    (tmp_path / "cpython-3.13-linux-x86_64-gnu").mkdir()  # the minor-version link, no python
    _fake_python(tmp_path, "cpython-3.13.9-linux-x86_64-gnu")
    newest = _fake_python(tmp_path, "cpython-3.13.17-linux-x86_64-gnu")
    _fake_python(tmp_path, "cpython-3.12.4-linux-x86_64-gnu")
    assert find_managed_python(tmp_path, "3.13", "linux") == newest
    assert find_managed_python(tmp_path, "3.11", "linux") is None
    win = _fake_python(tmp_path, "cpython-3.14.1-windows-x86_64-none", windows=True)
    assert find_managed_python(tmp_path, "3.14", "win32") == win


def test_remove_stale_python_links(tmp_path):
    target = tmp_path / "cpython-3.13.1-linux-x86_64-gnu"
    target.mkdir()
    broken = tmp_path / "cpython-3.13-linux-x86_64-gnu"
    try:
        broken.symlink_to(tmp_path / "missing", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    good = tmp_path / "cpython-3.12-linux-x86_64-gnu"
    good.symlink_to(target, target_is_directory=True)
    remove_stale_python_links(tmp_path)
    assert not broken.is_symlink()
    assert good.is_symlink() and target.is_dir()


def test_install_separation_uses_unpacked_python_after_link_error(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ensure_uv", lambda folder, **kw: Path("uv"))
    monkeypatch.setattr(bootstrap, "python_version", lambda *a, **kw: "3.13")
    calls = []
    root = tmp_path / "env"

    def run(cmd, log, env=None):
        calls.append(([str(c) for c in cmd], env))
        if len(calls) == 1:
            _fake_python(tmp_path / "python", "cpython-3.13.17-linux-x86_64-gnu")
            log("error: Failed to create Python minor version link directory (os error 448)")
            return 2
        return 0

    install_separation("1.2.3", root=root, log=lambda _: None, run=run)
    first, second = calls[0], calls[1]
    assert "3.13" in first[0]
    assert second[0][1:3] == ["venv", "--python"]
    assert second[0][3].endswith("bin/python") and "cpython-3.13.17" in second[0][3]
    assert second[1]["UV_PYTHON_DOWNLOADS"] == "never"
    assert (root / ".installed").exists()


def test_install_separation_no_unpacked_python_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ensure_uv", lambda folder, **kw: Path("uv"))

    def run(cmd, log, env=None):
        log("error: ... (os error 448)")
        return 2

    with pytest.raises(SetupError):
        install_separation("1.2.3", root=tmp_path / "env", log=lambda _: None, run=run)
