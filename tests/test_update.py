import hashlib
import json

import pytest

from soloslot.update import (
    DOWNLOAD_PREFIX,
    UpdateError,
    check_for_update,
    download_update,
    expected_checksum,
    is_newer,
    parse_version,
    platform_suffix,
)

SUFFIX = "-linux-x86_64.AppImage"


def _release(tag="v0.2.0", names=(f"soloslot-0.2.0{SUFFIX}", "SHA256SUMS")):
    return json.dumps(
        {
            "tag_name": tag,
            "body": "notes",
            "html_url": "https://example/release",
            "assets": [
                {"name": n, "browser_download_url": f"{DOWNLOAD_PREFIX}v0.2.0/{n}"} for n in names
            ],
        }
    ).encode()


def test_versions():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("1.10") == (1, 10)
    assert parse_version("nope") == ()
    assert is_newer("v0.10.0", "0.9.0")
    assert not is_newer("v0.1.0", "0.1.0")
    assert not is_newer("garbage", "0.1.0")


def test_platform_suffix():
    assert platform_suffix("win32").endswith("setup.exe")
    assert platform_suffix("darwin").endswith(".dmg")
    assert platform_suffix("linux").endswith(".AppImage")
    assert platform_suffix("freebsd") is None


def test_no_update_when_current():
    assert check_for_update("0.2.0", fetch=lambda url: _release(), suffix=SUFFIX) is None


def test_update_found():
    update = check_for_update("0.1.0", fetch=lambda url: _release(), suffix=SUFFIX)
    assert update.version == "0.2.0"
    assert update.asset_name == f"soloslot-0.2.0{SUFFIX}"
    assert update.checksums_url.endswith("SHA256SUMS")


def test_update_without_installer_for_platform():
    update = check_for_update("0.1.0", fetch=lambda url: _release(names=()), suffix=SUFFIX)
    assert update.asset_url is None
    with pytest.raises(UpdateError, match="no installer"):
        download_update(update, None)


def test_network_error_is_wrapped():
    def boom(url):
        raise OSError("offline")

    with pytest.raises(UpdateError):
        check_for_update("0.1.0", fetch=boom)


def test_expected_checksum():
    sums = "abc123  a.exe\nDEF456 *b.dmg\n"
    assert expected_checksum(sums, "a.exe") == "abc123"
    assert expected_checksum(sums, "b.dmg") == "def456"
    assert expected_checksum(sums, "c") is None


def test_download_verifies(tmp_path):
    payload = b"installer"
    name = f"soloslot-0.2.0{SUFFIX}"
    digest = hashlib.sha256(payload).hexdigest()

    def fetch(url):
        return payload if url.endswith(name) else f"{digest}  {name}\n".encode()

    update = check_for_update("0.1.0", fetch=lambda url: _release(), suffix=SUFFIX)
    path = download_update(update, tmp_path, fetch=fetch)
    assert path.read_bytes() == payload

    def tampered(url):
        return b"evil" if url.endswith(name) else f"{digest}  {name}\n".encode()

    with pytest.raises(UpdateError, match="checksum"):
        download_update(update, tmp_path / "x", fetch=tampered)
    assert not (tmp_path / "x").exists()


def test_download_requires_checksums(tmp_path):
    update = check_for_update(
        "0.1.0", fetch=lambda url: _release(names=(f"soloslot-0.2.0{SUFFIX}",)), suffix=SUFFIX
    )
    with pytest.raises(UpdateError, match="SHA256SUMS"):
        download_update(update, tmp_path, fetch=lambda url: b"")


def test_foreign_download_urls_are_ignored():
    release = json.dumps(
        {
            "tag_name": "v0.2.0",
            "assets": [
                {"name": f"x{SUFFIX}", "browser_download_url": f"https://evil.example/x{SUFFIX}"}
            ],
        }
    ).encode()
    update = check_for_update("0.1.0", fetch=lambda url: release, suffix=SUFFIX)
    assert update.asset_url is None
