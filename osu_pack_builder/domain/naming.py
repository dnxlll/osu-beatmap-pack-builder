"""Pure naming, pattern detection, and filename sanitization rules."""

import re

from osu_pack_builder.domain.models import ParsedMapName

_INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/*?:"<>|]')
_PATTERN_PREFIX_RE = re.compile(r"^\[(DJ|CJ|SJ|ANCHOR)\]\s*", flags=re.IGNORECASE)


def sanitize_filename_part(text: str) -> str:
    """Remove characters forbidden in Windows/osu! filenames and trim whitespace."""
    return _INVALID_FILENAME_CHARS_RE.sub("", text).strip()


def normalize_pattern(pattern: str | None) -> str:
    """Normalize pattern tag, returning empty string for empty or 'NINGUNO'."""
    if not pattern:
        return ""
    cleaned = pattern.strip().upper()
    return "" if cleaned == "NINGUNO" else cleaned


def limpiar_bpm_od(texto: str) -> str:
    """
    Elimina menciones de BPM y OD del nombre o dificultad del mapa,
    conservando rates (ej. 1.1x, 0.95x) y nombres propios de dificultad.
    """
    if not re.search(r"bpm|\bod\s*:?\s*\d", texto, flags=re.IGNORECASE):
        return texto

    texto = re.sub(
        r"\(\s*(?:~?\s*\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*bpm"
        r"|\bod\s*:?\s*\d+(?:\.\d+)?)[^)]*\)",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    texto = re.sub(
        r"\[\s*(?:~?\s*\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*bpm"
        r"|\bod\s*:?\s*\d+(?:\.\d+)?)[^\]]*\]",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    texto = re.sub(
        r"(?<!\w)~?\s*\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*bpm\b",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    texto = re.sub(r"\bod\s*:?\s*\d+(?:\.\d+)?\b", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\(\s*[,;\s–—\-/|]*\)", "", texto)
    texto = re.sub(r"[\s,;–—\-/|]+\]", "]", texto)
    texto = re.sub(r"[\s,;–—\-/|]+\)", ")", texto)
    texto = re.sub(r"\[[\s,;–—\-/|]+", "[", texto)
    texto = re.sub(r"\([\s,;–—\-/|]+", "(", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    texto = re.sub(r"[\s,;–—\-/|]+$", "", texto).strip()
    texto = re.sub(r"^[\s,;–—\-/|]+", "", texto).strip()

    return texto


def detectar_patron_sugerido(texto: str) -> str:
    """Detecta automáticamente patrones conocidos (DJ, CJ, SJ, ANCHOR) en un nombre."""
    texto_upper = texto.upper()
    if re.search(r"\b(ANCHOR|ANCHORS)\b", texto_upper) or "[ANCHOR]" in texto_upper:
        return "ANCHOR"
    if re.search(r"\b(SPEED\s*JACKS?|SJ)\b", texto_upper) or "[SJ]" in texto_upper:
        return "SJ"
    if re.search(r"\b(CHORD\s*JACKS?|CJ)\b", texto_upper) or "[CJ]" in texto_upper:
        return "CJ"
    if re.search(r"\b(DENSE\s*JACKS?|DJ)\b", texto_upper) or "[DJ]" in texto_upper:
        return "DJ"
    return ""


def _slice_title_words(title: str, title_words: int | None) -> str:
    """Keep the first N words of title, or the full title when title_words is None."""
    cleaned = _PATTERN_PREFIX_RE.sub("", title).strip()
    if title_words is None or title_words <= 0:
        return cleaned
    words = cleaned.split()
    return " ".join(words[:title_words]) if words else cleaned


def parse_osu_filename(
    clave_osu: str,
    meta_original: dict[str, str] | None = None,
    title_words: int | None = 1,
) -> ParsedMapName:
    """
    Extract artist, sliced song title (1/2/3 words or full), and difficulty remainder
    from an .osu filename, falling back to internal [Metadata] when needed.
    """
    meta = meta_original or {}
    stem = clave_osu[:-4] if clave_osu.lower().endswith(".osu") else clave_osu

    match = re.match(
        r"^(.*?)\s+-\s+(.*?)\s*((?:\([^)]*\)\s*)?\[.*\])\.osu$",
        clave_osu,
    ) or re.match(
        r"^(.*?)\s*-\s*(.*?)\s*((?:\([^)]*\)\s*)?\[.*\])\.osu$",
        clave_osu,
    )
    if match:
        artist = match.group(1).strip()
        raw_title = match.group(2).strip()
        remainder = match.group(3).strip()
    else:
        match_parens = re.match(
            r"^(.*?)\s+-\s+(.*?)\s*(\([^)]*\))\s*\.osu$",
            clave_osu,
        ) or re.match(
            r"^(.*?)\s*-\s*(.*?)\s*(\([^)]*\))\s*\.osu$",
            clave_osu,
        )
        if match_parens:
            artist = match_parens.group(1).strip()
            raw_title = match_parens.group(2).strip()
            remainder = f"[{match_parens.group(3).strip('()')}]"
        else:
            match_short = re.match(r"^(.*?)\s*-\s*(\([^)]*\))\s*\.osu$", clave_osu)
            if match_short:
                artist = match_short.group(1).strip()
                diff = match_short.group(2).strip("()")
                raw_title = diff or artist
                remainder = f"[{diff}]"
            else:
                artist = meta.get("Artist", "").strip() or "Unknown"
                raw_title = meta.get("Title", "").strip() or stem or "Unknown"
                remainder = f"[{meta.get('Version', stem)}]"

    artist = _PATTERN_PREFIX_RE.sub("", artist).strip()
    sliced_title = _slice_title_words(raw_title, title_words)

    return ParsedMapName(artist=artist, first_word=sliced_title, remainder=remainder)


def build_version_name(
    parsed: ParsedMapName,
    pattern: str = "",
    custom_version: str = "",
) -> str:
    """Build the adapted osu! Version string, applying BPM/OD cleanup and optional pattern tag."""
    if custom_version and custom_version.strip():
        return custom_version.strip()

    clean_remainder = limpiar_bpm_od(parsed.remainder)
    norm_pattern = normalize_pattern(pattern)
    if norm_pattern:
        raw = f"[{norm_pattern}] {parsed.artist} - {parsed.first_word} {clean_remainder}"
    else:
        raw = f"{parsed.artist} - {parsed.first_word} {clean_remainder}"
    return limpiar_bpm_od(raw)


def build_pack_prefix(
    init_stem: str,
    extracted_metadata: dict[str, str],
    default_creator: str = "",
) -> str:
    """Build the sanitized base filename prefix for generated pack .osu files."""
    prefix_base = re.sub(r"\s*\[.*\]$", "", init_stem).strip()
    if not prefix_base:
        artist = sanitize_filename_part(extracted_metadata.get("Artist", "Various Artists"))
        title = sanitize_filename_part(extracted_metadata.get("Title", "Pack"))
        creator = sanitize_filename_part(extracted_metadata.get("Creator", default_creator))
        prefix_base = f"{artist} - {title} ({creator})" if creator else f"{artist} - {title}"
    return sanitize_filename_part(prefix_base)
