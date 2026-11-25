"""GitHub Releases update checker, downloader, and Windows self-updater."""

import json
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from packaging.version import InvalidVersion, Version

from osu_pack_builder.domain.models import APP_VERSION, GITHUB_REPO


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    """Metadata for an available newer GitHub release."""

    version: str
    tag_name: str
    html_url: str
    download_url: str | None
    notes: str


def _parse_version(raw: str) -> Version | None:
    cleaned = raw.strip().lstrip("vV")
    try:
        return Version(cleaned)
    except InvalidVersion:
        return None


def check_latest_release(
    repo: str = GITHUB_REPO,
    current_version: str = APP_VERSION,
    timeout: float = 8.0,
) -> ReleaseInfo | None:
    """
    Query GitHub's latest release endpoint and return ReleaseInfo if a newer
    version is available, or None if already up to date.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "osu-beatmap-pack-builder",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    tag_name = str(data.get("tag_name") or "").strip()
    remote_ver = _parse_version(tag_name)
    local_ver = _parse_version(current_version)
    if remote_ver is None or local_ver is None or remote_ver <= local_ver:
        return None

    download_url: str | None = None
    for asset in data.get("assets", []):
        name = str(asset.get("name") or "").lower()
        asset_url = str(asset.get("browser_download_url") or "")
        if name.endswith(".exe") and asset_url.startswith("https://"):
            download_url = asset_url
            break

    return ReleaseInfo(
        version=str(remote_ver),
        tag_name=tag_name,
        html_url=str(data.get("html_url") or f"https://github.com/{repo}/releases"),
        download_url=download_url,
        notes=str(data.get("body") or "").strip(),
    )


def download_release_asset(
    download_url: str,
    dest_path: Path,
    on_progress: Callable[[int, int], None] | None = None,
    timeout: float = 30.0,
) -> Path:
    """Download an HTTPS release asset to dest_path, reporting byte progress."""
    if not download_url.startswith("https://"):
        raise ValueError("La URL de descarga debe usar HTTPS.")

    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": "osu-beatmap-pack-builder"},
    )
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        with open(dest_path, "wb") as out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if on_progress is not None:
                    on_progress(downloaded, total)
    return dest_path


def launch_windows_self_replace(new_exe: Path, current_exe: Path | None = None) -> None:
    """
    Spawn a detached helper script that waits briefly for this process to exit,
    replaces the running .exe with new_exe, and relaunches the updated app.
    """
    target = current_exe or Path(sys.executable)
    bat_path = Path(tempfile.gettempdir()) / "osu_beatmap_pack_update.bat"
    script = (
        "@echo off\n"
        "timeout /t 2 /nobreak >nul\n"
        f'move /y "{new_exe}" "{target}"\n'
        f'start "" "{target}"\n'
        'del "%~f0"\n'
    )
    bat_path.write_text(script, encoding="utf-8")

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "DETACHED_PROCESS", 0
    )
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat_path)],
        creationflags=creation_flags,
        close_fds=True,
    )
