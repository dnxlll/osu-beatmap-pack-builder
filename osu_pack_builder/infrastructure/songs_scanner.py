"""Filesystem scanner for locating and filtering osu! Songs directories."""

from pathlib import Path


def detect_songs_dir() -> Path:
    """Detect the default osu! Songs directory, falling back to CWD."""
    candidates = [
        Path.home() / "AppData" / "Local" / "osu!" / "Songs",
        Path(r"C:\osu!\Songs"),
        Path(r"D:\osu!\Songs"),
    ]
    for path in candidates:
        if path.exists() and path.is_dir():
            return path
    return Path.cwd()


def list_song_folders(songs_dir: Path) -> list[Path]:
    """Return immediate subdirectories in the given Songs directory."""
    if not (songs_dir.exists() and songs_dir.is_dir()):
        return []
    return [entry for entry in songs_dir.iterdir() if entry.is_dir()]


def filter_song_folders(folders: list[Path], query: str, limit: int = 8) -> list[Path]:
    """Filter song folders using case-insensitive multi-word AND matching."""
    words = query.strip().lower().split()
    if not words:
        return []
    return [f for f in folders if all(w in f.name.lower() for w in words)][:limit]
