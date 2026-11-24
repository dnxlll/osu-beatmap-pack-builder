"""Media file adapters for audio copying, background optimization, and thumbnails."""

import logging
import shutil
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


def copy_audio(source: Path, dest_dir: Path, target_name: str) -> Path:
    """Copy a beatmap audio file to the pack output directory."""
    dest = dest_dir / target_name
    shutil.copyfile(source, dest)
    return dest


def optimize_background(
    source: Path,
    dest_dir: Path,
    target_name: str,
    max_size: tuple[int, int] = (1920, 1080),
    quality: int = 85,
) -> Path:
    """
    Convert and resize a background image to optimized JPEG (max 1080p)
    to stay under osu!'s 100 MB pack limit. Falls back to raw copy on error.
    """
    dest = dest_dir / target_name
    try:
        with Image.open(source) as im:
            im_rgb = im.convert("RGB")
            w, h = im_rgb.size
            if w > max_size[0] or h > max_size[1]:
                im_rgb.thumbnail(max_size, Image.Resampling.LANCZOS)
            im_rgb.save(dest, format="JPEG", quality=quality, optimize=True)
    except Exception as exc:
        logger.warning("No se pudo optimizar imagen %s: %s", source, exc)
        shutil.copyfile(source, dest)
    return dest


def load_thumbnail(source: Path, size: tuple[int, int] = (96, 60)) -> Image.Image | None:
    """Load and center-crop an image to a uniform thumbnail size, or None on error."""
    if not source.exists():
        return None
    try:
        with Image.open(source) as im:
            return ImageOps.fit(im.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    except Exception as exc:
        logger.debug("No se pudo cargar miniatura %s: %s", source, exc)
        return None
