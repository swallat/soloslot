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
    install_separation,
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
    env = uv_env({"UV_PYTHON": "x", "VIRTUAL_ENV": "v", "PATH": "/bin"}, root=tmp_path)
    assert "UV_PYTHON" not in env and "VIRTUAL_ENV" not in env
    assert env["UV_PYTHON_PREFERENCE"] == "only-managed"
    assert env["UV_MANAGED_PYTHON"] == "1"
    assert env["UV_CACHE_DIR"] == str(tmp_path / "uv-cache")


def test_python_version():
    assert bootstrap.python_version("win32", "AMD64") == "3.13"
    assert bootstrap.python_version("linux", "x86_64") == "3.13"
    assert bootstrap.python_version("darwin", "arm64") == "3.13"
    assert bootstrap.python_version("darwin", "x86_64") == "3.12"
