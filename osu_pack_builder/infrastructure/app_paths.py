"""Application data path resolution for both source and frozen (.exe) runs."""

import os
import sys
from pathlib import Path

APP_DIR_NAME = "osu-beatmap-pack-builder"


def get_app_data_dir(app_name: str = APP_DIR_NAME) -> Path:
    """
    Return the writable directory for persistent runtime files (pack.json, logs).
    Uses %LOCALAPPDATA%\\<app_name> when frozen as an .exe, or project root in dev.
    """
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        data_dir = base / app_name
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    return Path(__file__).resolve().parents[2]


def get_pack_file() -> Path:
    """Return the path to pack.json."""
    return get_app_data_dir() / "pack.json"


def get_log_file() -> Path:
    """Return the path to beatmappack.log."""
    return get_app_data_dir() / "beatmappack.log"
