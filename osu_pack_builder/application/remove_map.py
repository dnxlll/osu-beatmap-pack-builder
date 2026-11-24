"""Use case: remove a single beatmap entry from pack.json."""

from osu_pack_builder.infrastructure.pack_repository import PackRepository


def remove_map_from_pack(index: str, repository: PackRepository) -> dict:
    """Remove the entry with the given index from pack.json and persist atomically."""
    pack = repository.load()
    if index in pack:
        del pack[index]
        repository.save(pack)
    return pack
