"""Check GitHub Releases for a newer version and download its installer (verified by SHA256).

Pure standard library and Qt-free, so it is testable. One request per check, no tracking.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO = "swallat/soloslot"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
CHECKSUMS = "SHA256SUMS"
_TIMEOUT = 10

Fetch = Callable[[str], bytes]


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Update:
    version: str
    notes: str
    page: str  # release page
    asset_name: str | None  # installer for this platform, if the release has one
    asset_url: str | None
    checksums_url: str | None


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.2.3' -> (1, 2, 3). Pre-release suffixes are ignored; garbage gives ()."""
    match = re.match(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(p) for p in match.group(1).split(".")) if match else ()


def is_newer(candidate: str, current: str) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    return bool(a) and bool(b) and a > b


def platform_suffix(platform: str | None = None, machine: str | None = None) -> str | None:
    """File name ending of this platform's installer in a release."""
    platform = platform or sys.platform
    if platform.startswith("win"):
        return "-windows-setup.exe"
    if platform == "darwin":
        return "-macos-arm64.dmg"
    if platform.startswith("linux"):
        return "-linux-x86_64.AppImage"
    return None


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "soloslot-update-check"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return response.read()


def check_for_update(
    current: str, *, fetch: Fetch = fetch_bytes, suffix: str | None = None
) -> Update | None:
    """The latest release if it is newer than `current`, else None."""
    try:
        release = json.loads(fetch(LATEST_URL))
    except (OSError, ValueError) as e:
        raise UpdateError(f"update check failed: {e}") from e
    tag = str(release.get("tag_name", ""))
    if not is_newer(tag, current):
        return None
    suffix = suffix if suffix is not None else platform_suffix()
    # Only trust downloads that come from this repository's releases.
    assets = {
        a["name"]: a["browser_download_url"]
        for a in release.get("assets", [])
        if str(a.get("browser_download_url", "")).startswith(DOWNLOAD_PREFIX)
    }
    name = next((n for n in assets if suffix and n.endswith(suffix)), None)
    return Update(
        version=tag.lstrip("v"),
        notes=str(release.get("body") or ""),
        page=str(release.get("html_url") or f"https://github.com/{REPO}/releases"),
        asset_name=name,
        asset_url=assets.get(name) if name else None,
        checksums_url=assets.get(CHECKSUMS),
    )


def expected_checksum(sums: str, name: str) -> str | None:
    """Look up `name` in sha256sum output ('<hash>  <file>' per line)."""
    for line in sums.splitlines():
        digest, _, file = line.strip().partition(" ")
        if file.strip().lstrip("*") == name:
            return digest.lower()
    return None


def download_update(update: Update, folder: Path, *, fetch: Fetch = fetch_bytes) -> Path:
    """Download the installer into `folder` and verify its SHA256. Returns the file path."""
    if not (update.asset_name and update.asset_url):
        raise UpdateError(f"release {update.version} has no installer for this platform")
    if not update.checksums_url:
        raise UpdateError("release has no SHA256SUMS; refusing to install an unverified file")
    try:
        data = fetch(update.asset_url)
        sums = fetch(update.checksums_url).decode("utf-8", "replace")
    except OSError as e:
        raise UpdateError(f"download failed: {e}") from e
    expected = expected_checksum(sums, update.asset_name)
    actual = hashlib.sha256(data).hexdigest()
    if expected is None or expected != actual:
        raise UpdateError("checksum mismatch; the download was discarded")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / update.asset_name
    target.write_bytes(data)
    if not sys.platform.startswith("win"):
        target.chmod(0o755 if target.suffix == ".AppImage" else 0o644)
    return target
