from osu_pack_builder.domain.models import ParsedMapName
from osu_pack_builder.domain.naming import (
    build_pack_prefix,
    build_version_name,
    detectar_patron_sugerido,
    limpiar_bpm_od,
    normalize_pattern,
    parse_osu_filename,
    sanitize_filename_part,
)
from osu_pack_builder.domain.osu_file import (
    build_adapted_osu_content,
    extract_audio_filename,
    extract_background_filename,
    parse_osu_metadata,
    truncate_tags_line,
)


class TestNamingDomain:
    def test_sanitize_filename_part(self) -> None:
        assert sanitize_filename_part('  foo/bar:baz*?"<>|  ') == "foobarbaz"

    def test_normalize_pattern(self) -> None:
        assert normalize_pattern(None) == ""
        assert normalize_pattern("ninguno") == ""
        assert normalize_pattern("  dj ") == "DJ"

    def test_parse_osu_filename_standard_and_fallback(self) -> None:
        parsed = parse_osu_filename("Kobaryo - Bookmaker (Rachel) [Extra].osu")
        assert parsed == ParsedMapName(
            artist="Kobaryo",
            first_word="Bookmaker",
            remainder="(Rachel) [Extra]",
        )

        fallback = parse_osu_filename(
            "weird_name.osu",
            meta_original={"Artist": "A", "Title": "My Song", "Version": "Hard"},
        )
        assert fallback == ParsedMapName(
            artist="A",
            first_word="My",
            remainder="[Hard]",
        )

    def test_build_version_name_with_pattern_and_custom(self) -> None:
        parsed = ParsedMapName(artist="Kobaryo", first_word="Bookmaker", remainder="[Extra 200BPM]")
        assert build_version_name(parsed, pattern="DJ") == "[DJ] Kobaryo - Bookmaker [Extra]"
        assert build_version_name(parsed, pattern="DJ", custom_version="Custom") == "Custom"

    def test_build_pack_prefix(self) -> None:
        assert build_pack_prefix("Artist - Pack (Creator) [delete]", {}) == "Artist - Pack (Creator)"
        assert (
            build_pack_prefix(
                "[delete]",
                {"Artist": "Various", "Title": "Pack", "Creator": "Alejo"},
            )
            == "Various - Pack (Alejo)"
        )

    def test_limpiar_and_detectar_compat(self) -> None:
        assert limpiar_bpm_od("Song (190 BPM) 1.1x") == "Song 1.1x"
        assert detectar_patron_sugerido("Map [SJ]") == "SJ"



    def test_parse_osu_filename_title_words_slicing(self) -> None:
        name = "Envy - Little Poor Me (2024 Rework) (awowuspro) [1.35x].osu"
        assert parse_osu_filename(name, title_words=1).first_word == "Little"
        assert parse_osu_filename(name, title_words=2).first_word == "Little Poor"
        assert parse_osu_filename(name, title_words=3).first_word == "Little Poor Me"
        assert parse_osu_filename(name, title_words=None).first_word == "Little Poor Me (2024 Rework)"

        single = "Kobaryo - Bookmaker (Rachel) [Extra].osu"
        assert parse_osu_filename(single, title_words=2).first_word == "Bookmaker"
        assert parse_osu_filename(single, title_words=3).first_word == "Bookmaker"

class TestOsuFileDomain:
    def test_extract_audio_and_background(self) -> None:
        content = (
            "[General]\nAudioFilename: song.ogg\n"
            "[Metadata]\nTitle: Hello\nArtist: World\n"
            '[Events]\n0,0,"bg.png",0,0\n'
        )
        assert extract_audio_filename(content) == "song.ogg"
        assert parse_osu_metadata(content) == {"Title": "Hello", "Artist": "World"}
        assert extract_background_filename(content) == "bg.png"

    def test_truncate_tags_line(self) -> None:
        short = "Tags:a b c"
        assert truncate_tags_line(short) == short

        long_tags = "Tags:" + " ".join(f"tag{i}" for i in range(250))
        truncated = truncate_tags_line(long_tags)
        assert truncated.startswith("Tags:")
        assert len(truncated) <= 850

    def test_build_adapted_osu_content_inserts_bg_when_missing(self) -> None:
        base = "osu file format v14\n[Metadata]\nBeatmapID:123\nVersion:old\n[Events]\n"
        src = "[Events]\n//bg\n[HitObjects]\n1,2,3,4,0\n"
        result = build_adapted_osu_content(
            base_content=base,
            source_content=src,
            version="NewDiff",
            audio_filename="AUDIO.mp3",
            bg_filename="AUDIO_bg.jpg",
        )
        assert "\r\n" in result
        assert "BeatmapID: 0" in result
        assert "Version: NewDiff" in result
        assert '0,0,"AUDIO_bg.jpg",0,0' in result
