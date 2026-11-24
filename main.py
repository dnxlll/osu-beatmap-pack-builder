"""
osu! BeatmapPack Builder
Composition root and backwards-compatible entry point.
"""

import logging
from pathlib import Path

import customtkinter as ctk

from osu_pack_builder.application.add_map import add_map_to_pack as _app_add_map_to_pack
from osu_pack_builder.application.generate_pack import generate_pack as _app_generate_pack
from osu_pack_builder.domain.naming import detectar_patron_sugerido, limpiar_bpm_od
from osu_pack_builder.infrastructure.pack_repository import PackRepository
from osu_pack_builder.ui.app import BeatmapPackApp

PACK_FILE: Path = Path(__file__).parent / "pack.json"
DEFAULT_CREATOR: str = ""

__all__ = [
    "BeatmapPackApp",
    "PACK_FILE",
    "DEFAULT_CREATOR",
    "add_map_to_pack",
    "detectar_patron_sugerido",
    "init_create_map",
    "limpiar_bpm_od",
]


def _load_pack(pack_file: Path = PACK_FILE) -> dict:
    """Compatibilidad: carga pack.json mediante PackRepository."""
    return PackRepository(pack_file).load()


def _save_pack(pack: dict, pack_file: Path = PACK_FILE) -> None:
    """Compatibilidad: escribe pack.json de forma atómica."""
    PackRepository(pack_file).save(pack)


def _next_index(pack: dict) -> str:
    """Compatibilidad: calcula el próximo índice incremental."""
    return PackRepository.next_index(pack)


def add_map_to_pack(
    folder: Path,
    selected_osu: Path,
    patron: str = "",
    custom_version: str = "",
    pack_file: Path = PACK_FILE,
) -> tuple[str, dict]:
    """Compatibilidad: delega al caso de uso AddMapToPack."""
    return _app_add_map_to_pack(
        folder=folder,
        selected_osu=selected_osu,
        repository=PackRepository(pack_file),
        patron=patron,
        custom_version=custom_version,
    )


def init_create_map(
    init_file: Path,
    callback_parafraseo=None,
    pack_file: Path = PACK_FILE,
) -> tuple[Path, int]:
    """Compatibilidad: delega al caso de uso GeneratePack."""
    return _app_generate_pack(
        init_file=init_file,
        repository=PackRepository(pack_file),
        callback_parafraseo=callback_parafraseo,
        default_creator=DEFAULT_CREATOR,
    )


def main() -> None:
    """Configure logging and CustomTkinter, wire dependencies, and run the GUI."""
    logging.basicConfig(
        filename=str(Path(__file__).parent / "beatmappack.log"),
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    repository = PackRepository(PACK_FILE)
    app = BeatmapPackApp(repository=repository, default_creator=DEFAULT_CREATOR)
    app.mainloop()


if __name__ == "__main__":
    main()
