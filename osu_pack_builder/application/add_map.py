"""Use case: add a selected beatmap difficulty to pack.json."""

from pathlib import Path

from osu_pack_builder.domain.models import AUDIO_EXTENSIONS
from osu_pack_builder.domain.naming import normalize_pattern
from osu_pack_builder.domain.osu_file import extract_audio_filename
from osu_pack_builder.infrastructure.pack_repository import PackRepository


def build_pack_entry(
    folder: Path,
    selected_osu: Path,
    patron: str = "",
    custom_version: str = "",
) -> dict:
    """
    Build a pack.json entry dictionary for a selected .osu difficulty,
    keeping only its referenced audio, image assets, pattern tag, and custom version.
    """
    mapa: dict = {}

    for archivo in folder.iterdir():
        if archivo.is_file() and archivo.suffix != ".osu":
            mapa[archivo.name] = str(archivo.absolute())

    mapa[selected_osu.name] = str(selected_osu.absolute())

    norm_patron = normalize_pattern(patron)
    if norm_patron:
        mapa["__pattern__"] = norm_patron

    if custom_version and custom_version.strip():
        mapa["__custom_version__"] = custom_version.strip()

    cancion = extract_audio_filename(selected_osu.read_text(encoding="utf-8", errors="ignore"))
    for clave in list(mapa.keys()):
        if clave.endswith(AUDIO_EXTENSIONS) and clave != cancion:
            del mapa[clave]

    return mapa


def add_map_to_pack(
    folder: Path,
    selected_osu: Path,
    repository: PackRepository,
    patron: str = "",
    custom_version: str = "",
) -> tuple[str, dict]:
    """Register a selected .osu difficulty in pack.json."""
    mapa = build_pack_entry(
        folder=folder,
        selected_osu=selected_osu,
        patron=patron,
        custom_version=custom_version,
    )
    pack = repository.load()
    nuevo_indice = repository.next_index(pack)
    pack[nuevo_indice] = mapa
    repository.save(pack)

    return nuevo_indice, pack
