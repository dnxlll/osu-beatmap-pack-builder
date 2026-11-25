"""Domain models and constants for osu! beatmap pack building."""

from dataclasses import dataclass

APP_VERSION: str = "1.0.2"
GITHUB_REPO: str = "dnxlll/osu-beatmap-pack-builder"

VALID_PATTERNS: tuple[str, ...] = ("DJ", "CJ", "SJ", "ANCHOR")
AUDIO_EXTENSIONS: tuple[str, ...] = (".mp3", ".ogg", ".wav")
IMAGE_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")

MAX_OSU_FILENAME_LEN: int = 160
MAX_OSU_TAGS_LINE_LEN: int = 850
MAX_OSU_TAGS_BODY_LEN: int = 800

PACK_METADATA_FIELDS: tuple[str, ...] = (
    "Title",
    "TitleUnicode",
    "Artist",
    "ArtistUnicode",
    "Creator",
    "Source",
    "Tags",
    "BeatmapID",
    "BeatmapSetID",
)


@dataclass(frozen=True, slots=True)
class ParsedMapName:
    """Extracted components from an osu! beatmap filename or metadata."""

    artist: str
    first_word: str
    remainder: str
