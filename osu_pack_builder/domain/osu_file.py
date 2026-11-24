"""Pure .osu file parsing and content transformation rules."""

import re

from osu_pack_builder.domain.models import (
    MAX_OSU_TAGS_BODY_LEN,
    MAX_OSU_TAGS_LINE_LEN,
    PACK_METADATA_FIELDS,
)


def extract_audio_filename(content: str) -> str:
    """Return the AudioFilename value from .osu content, or empty string if absent."""
    for line in content.splitlines():
        if line.startswith("AudioFilename:"):
            return line.split(":", 1)[1].strip()
    return ""


def extract_pack_header_metadata(content: str) -> dict[str, str]:
    """Extract pack-level metadata fields from the base init .osu content."""
    extracted: dict[str, str] = {}
    for line in content.splitlines():
        for field in PACK_METADATA_FIELDS:
            if line.startswith(f"{field}:"):
                extracted[field] = line.split(":", 1)[1].strip()
    return extracted


def parse_osu_metadata(content: str) -> dict[str, str]:
    """Parse key-value pairs inside the [Metadata] section of an .osu file."""
    meta: dict[str, str] = {}
    in_meta = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line == "[Metadata]":
            in_meta = True
            continue
        if in_meta:
            if line.startswith("["):
                break
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
    return meta


def extract_background_filename(content: str) -> str | None:
    """Extract the background image filename declared in the [Events] section, if any."""
    in_events = False
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if stripped == "[Events]":
            in_events = True
            continue
        if in_events:
            if stripped.startswith("["):
                break
            match = re.match(r'^\s*0\s*,\s*0\s*,\s*"?([^",]+)"?', raw_line)
            if match:
                return match.group(1).strip()
    return None


def truncate_tags_line(
    line: str,
    max_line_len: int = MAX_OSU_TAGS_LINE_LEN,
    max_body_len: int = MAX_OSU_TAGS_BODY_LEN,
) -> str:
    """Truncate Tags: line to prevent osu! MySQL 'Data too long for column tags' errors."""
    if not line.startswith("Tags:") or len(line) <= max_line_len:
        return line

    raw_tags = line.split(":", 1)[1].split()
    cleaned_tags: list[str] = []
    cur_len = 0
    for tag in raw_tags:
        if cur_len + len(tag) + 1 <= max_body_len:
            cleaned_tags.append(tag)
            cur_len += len(tag) + 1
    return f"Tags:{' '.join(cleaned_tags)}"


def build_adapted_osu_content(
    base_content: str,
    source_content: str | None,
    version: str,
    audio_filename: str | None = None,
    bg_filename: str | None = None,
    beatmap_id: str = "0",
) -> str:
    """
    Combine the pack base header (up to [Events]) with the source map body (from [Events]),
    updating BeatmapID, Version, AudioFilename, Tags length, and background image reference.
    """
    overrides: dict[str, str] = {
        "BeatmapID": beatmap_id,
        "Version": version,
    }
    if audio_filename:
        overrides["AudioFilename"] = audio_filename

    header_lines: list[str] = []
    for line in base_content.splitlines():
        if line.strip() == "[Events]":
            break

        line = truncate_tags_line(line)

        replaced = False
        for field, value in overrides.items():
            if line.startswith(f"{field}:"):
                header_lines.append(f"{field}: {value}")
                replaced = True
                break
        if not replaced:
            header_lines.append(line)

    body_lines: list[str] = []
    if source_content is not None:
        in_events = False
        bg_updated = False
        for line in source_content.splitlines():
            if line.strip() == "[Events]":
                in_events = True
                body_lines.append(line)
                continue
            if in_events:
                if bg_filename and re.match(r"^\s*0\s*,\s*0\s*,", line):
                    line = re.sub(
                        r'^(\s*0\s*,\s*0\s*,\s*)"?[^",]+"?(.*)$',
                        rf'\1"{bg_filename}"\2',
                        line,
                    )
                    bg_updated = True
                body_lines.append(line)

        if bg_filename and not bg_updated and in_events:
            idx_events = body_lines.index("[Events]")
            body_lines.insert(idx_events + 1, f'0,0,"{bg_filename}",0,0')

    return "\r\n".join(header_lines + body_lines)
