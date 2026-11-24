"""Use case: update an existing beatmap entry in pack.json (difficulty, pattern, version)."""

from pathlib import Path

from osu_pack_builder.application.add_map import build_pack_entry
from osu_pack_builder.domain.naming import normalize_pattern
from osu_pack_builder.infrastructure.pack_repository import PackRepository


def update_map_in_pack(
    index: str,
    repository: PackRepository,
    patron: str = "",
    custom_version: str = "",
    folder: Path | None = None,
    selected_osu: Path | None = None,
) -> dict:
    """
    Update an existing entry in pack.json in-place.
    If folder and selected_osu are provided, rebuilds assets (.osu, audio, images)
    for the new difficulty; otherwise updates only pattern and custom version.
    """
    pack = repository.load()
    if index not in pack or not isinstance(pack[index], dict):
        raise KeyError(f"No existe el mapa con índice '{index}' en pack.json")

    if folder is not None and selected_osu is not None:
        pack[index] = build_pack_entry(
            folder=folder,
            selected_osu=selected_osu,
            patron=patron,
            custom_version=custom_version,
        )
    else:
        entry = dict(pack[index])
        norm_patron = normalize_pattern(patron)
        entry.pop("patron", None)
        if norm_patron:
            entry["__pattern__"] = norm_patron
        else:
            entry.pop("__pattern__", None)

        if custom_version and custom_version.strip():
            entry["__custom_version__"] = custom_version.strip()
        else:
            entry.pop("__custom_version__", None)
        pack[index] = entry

    repository.save(pack)
    return pack


def clear_custom_versions(repository: PackRepository) -> dict:
    """Remove __custom_version__ from all pack entries so the title cutter applies to all maps."""
    pack = repository.load()
    changed = False
    for entry in pack.values():
        if isinstance(entry, dict) and "__custom_version__" in entry:
            del entry["__custom_version__"]
            changed = True
    if changed:
        repository.save(pack)
    return pack
