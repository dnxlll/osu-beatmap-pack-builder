"""Use case: generate adapted .osu beatmap pack files from pack.json."""

import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from osu_pack_builder.domain.models import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MAX_OSU_FILENAME_LEN,
)
from osu_pack_builder.domain.naming import (
    build_pack_prefix,
    build_version_name,
    normalize_pattern,
    parse_osu_filename,
    sanitize_filename_part,
)
from osu_pack_builder.domain.osu_file import (
    build_adapted_osu_content,
    extract_background_filename,
    extract_pack_header_metadata,
    parse_osu_metadata,
)
from osu_pack_builder.infrastructure.media_processor import copy_audio, optimize_background
from osu_pack_builder.infrastructure.pack_repository import PackRepository

logger = logging.getLogger(__name__)

ParaphraseCallback = Callable[[str, str, str, str], str]


def _resolve_background_path(archivos_mapa: dict, source_content: str | None) -> Path | None:
    """Prefer the background declared in [Events], falling back to the first image in the entry."""
    if source_content:
        declared_bg = extract_background_filename(source_content)
        if declared_bg and declared_bg in archivos_mapa:
            return Path(archivos_mapa[declared_bg])

    clave_imagen = next(
        (k for k in archivos_mapa if k.lower().endswith(IMAGE_EXTENSIONS)),
        None,
    )
    return Path(archivos_mapa[clave_imagen]) if clave_imagen else None


def _copy_unique_audio(
    ruta_audio: Path | None,
    carpeta_salida: Path,
    base_name: str,
    indice: str,
    audios_usados: dict[str, Path],
) -> str | None:
    """Copy audio with collision-free uppercase naming."""
    if not (ruta_audio and ruta_audio.exists()):
        return None

    ext = ruta_audio.suffix.lower()
    proposed = f"{base_name.upper()}{ext}"
    if proposed in audios_usados and audios_usados[proposed] != ruta_audio:
        proposed = f"{base_name.upper()}_{indice}{ext}"

    audios_usados[proposed] = ruta_audio
    copy_audio(ruta_audio, carpeta_salida, proposed)
    return proposed


def _copy_unique_background(
    ruta_imagen: Path | None,
    carpeta_salida: Path,
    base_name: str,
    indice: str,
    imagenes_usadas: dict[str, Path],
) -> str | None:
    """Optimize and copy background image with collision-free naming."""
    if not (ruta_imagen and ruta_imagen.exists()):
        return None

    proposed = f"{base_name.upper()}_bg.jpg"
    if proposed in imagenes_usadas and imagenes_usadas[proposed] != ruta_imagen:
        proposed = f"{base_name.upper()}_bg_{indice}.jpg"

    imagenes_usadas[proposed] = ruta_imagen
    optimize_background(ruta_imagen, carpeta_salida, proposed)
    return proposed


def generate_pack(
    init_file: Path,
    repository: PackRepository,
    callback_parafraseo: ParaphraseCallback | None = None,
    default_creator: str = "",
    title_words: int | None = 1,
) -> tuple[Path, int]:
    """
    Generate all adapted .osu files, optimized backgrounds, and renamed audio files
    into the folder containing init_file.
    """
    extracted_metadata = extract_pack_header_metadata(
        init_file.read_text(encoding="utf-8", errors="ignore")
    )
    carpeta_salida = init_file.resolve().parent

    pack_datos = repository.load()
    if not pack_datos:
        return carpeta_salida, 0

    prefix_base_limpio = build_pack_prefix(init_file.stem, extracted_metadata, default_creator)
    total_generados = 0
    pack_dirty = False
    audios_usados: dict[str, Path] = {}
    imagenes_usadas: dict[str, Path] = {}

    for indice, archivos_mapa in pack_datos.items():
        if not isinstance(archivos_mapa, dict):
            continue

        clave_osu = next((k for k in archivos_mapa if k.endswith(".osu")), None)
        if not clave_osu:
            continue

        ruta_osu = Path(archivos_mapa[clave_osu])
        clave_audio = next((k for k in archivos_mapa if k.lower().endswith(AUDIO_EXTENSIONS)), None)
        ruta_audio = Path(archivos_mapa[clave_audio]) if clave_audio else None

        source_content = (
            ruta_osu.read_text(encoding="utf-8", errors="ignore") if ruta_osu.exists() else None
        )
        ruta_imagen = _resolve_background_path(archivos_mapa, source_content)

        meta_original = parse_osu_metadata(source_content) if source_content is not None else {}
        parsed_name = parse_osu_filename(clave_osu, meta_original, title_words=title_words)
        first_token = parsed_name.first_word.split()[0] if parsed_name.first_word.split() else ""
        safe_first_word = sanitize_filename_part(first_token) or f"SONG_{indice}"

        patron_tag = normalize_pattern(archivos_mapa.get("__pattern__") or archivos_mapa.get("patron"))
        custom_version = archivos_mapa.get("__custom_version__") or ""
        version_final = build_version_name(
            parsed_name,
            pattern=patron_tag,
            custom_version=custom_version,
        )

        nombre_audio_destino = _copy_unique_audio(
            ruta_audio, carpeta_salida, safe_first_word, indice, audios_usados
        )
        nombre_imagen_destino = _copy_unique_background(
            ruta_imagen, carpeta_salida, safe_first_word, indice, imagenes_usadas
        )

        version_limpia = sanitize_filename_part(version_final)
        nombre_nuevo = f"{prefix_base_limpio} [{version_limpia}].osu"

        if len(nombre_nuevo) > MAX_OSU_FILENAME_LEN and callback_parafraseo:
            version_parafraseada = callback_parafraseo(
                indice, clave_osu, version_final, prefix_base_limpio
            )
            if version_parafraseada and version_parafraseada.strip():
                version_final = version_parafraseada.strip()
                version_limpia = sanitize_filename_part(version_final)
                nombre_nuevo = f"{prefix_base_limpio} [{version_limpia}].osu"
                archivos_mapa["__custom_version__"] = version_final
                pack_dirty = True

        simple = carpeta_salida / nombre_nuevo
        if init_file.resolve() != simple.resolve():
            shutil.copyfile(init_file, simple)

        contenido_final = build_adapted_osu_content(
            base_content=simple.read_text(encoding="utf-8", errors="ignore"),
            source_content=source_content,
            version=version_final,
            audio_filename=nombre_audio_destino,
            bg_filename=nombre_imagen_destino,
        )
        simple.write_text(contenido_final, encoding="utf-8")
        total_generados += 1

    if pack_dirty:
        try:
            repository.save(pack_datos)
        except OSError as exc:
            logger.warning("No se pudo persistir versiones parafraseadas en pack.json: %s", exc)

    return carpeta_salida, total_generados
