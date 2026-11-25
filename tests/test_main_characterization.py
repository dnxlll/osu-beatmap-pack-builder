import json
from pathlib import Path

from PIL import Image

from main import (
    _load_pack,
    _next_index,
    _save_pack,
    add_map_to_pack,
    detectar_patron_sugerido,
    init_create_map,
    limpiar_bpm_od,
)


class TestLimpiarBpmOd:
    def test_preserves_text_without_bpm_or_od(self) -> None:
        assert limpiar_bpm_od("[Extra]") == "[Extra]"
        assert limpiar_bpm_od("1.1x [Challenge]") == "1.1x [Challenge]"

    def test_removes_bpm_and_od_in_brackets_and_parens(self) -> None:
        assert limpiar_bpm_od("Artist - Song (180 BPM) [Extra]") == "Artist - Song [Extra]"
        assert limpiar_bpm_od("Extra [180-200bpm, OD 8.5]") == "Extra"
        assert limpiar_bpm_od("Challenge 1.2x (OD: 9) [~190 BPM]") == "Challenge 1.2x"

    def test_removes_standalone_bpm_and_od_preserving_rate(self) -> None:
        assert limpiar_bpm_od("1.35x 210bpm OD8") == "1.35x"


class TestDetectarPatronSugerido:
    def test_detects_known_patterns(self) -> None:
        assert detectar_patron_sugerido("Song [DJ] [Extra].osu") == "DJ"
        assert detectar_patron_sugerido("Song (Dense Jack).osu") == "DJ"
        assert detectar_patron_sugerido("Song [CJ Challenge].osu") == "CJ"
        assert detectar_patron_sugerido("Song Speed Jacks.osu") == "SJ"
        assert detectar_patron_sugerido("Song [ANCHOR].osu") == "ANCHOR"

    def test_returns_empty_when_no_pattern(self) -> None:
        assert detectar_patron_sugerido("Artist - Title [Normal].osu") == ""


class TestPackPersistence:
    def test_load_missing_and_corrupt_pack(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.json"
        assert _load_pack(missing) == {}

        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{not valid json", encoding="utf-8")
        assert _load_pack(corrupt) == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        pack_file = tmp_path / "pack.json"
        data = {"1": {"map.osu": "C:/Songs/map.osu"}, "invalid": "ignored"}
        _save_pack(data, pack_file)
        loaded = _load_pack(pack_file)
        assert loaded == {"1": {"map.osu": "C:/Songs/map.osu"}}

    def test_next_index_handles_gaps(self) -> None:
        assert _next_index({}) == "1"
        assert _next_index({"1": {}, "4": {}}) == "5"


class TestAddMapAndInitCreateMap:
    def test_add_map_to_pack_filters_unused_audio(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "12345 Artist - Title"
        song_dir.mkdir()
        osu_file = song_dir / "Artist - Title (Mapper) [Extra].osu"
        osu_file.write_text(
            "osu file format v14\n[General]\nAudioFilename: main.mp3\n",
            encoding="utf-8",
        )
        (song_dir / "main.mp3").write_bytes(b"audio")
        (song_dir / "unused.mp3").write_bytes(b"other")
        (song_dir / "bg.jpg").write_bytes(b"img")

        pack_file = tmp_path / "pack.json"
        idx, pack = add_map_to_pack(
            song_dir,
            osu_file,
            patron="cj",
            custom_version="",
            pack_file=pack_file,
        )

        assert idx == "1"
        entry = pack["1"]
        assert "main.mp3" in entry
        assert "unused.mp3" not in entry
        assert "bg.jpg" in entry
        assert entry["__pattern__"] == "CJ"
        assert json.loads(pack_file.read_text(encoding="utf-8")) == pack

    def test_init_create_map_generates_osu_and_optimizes_bg(self, tmp_path: Path) -> None:
        pack_out = tmp_path / "PackFolder"
        pack_out.mkdir()
        init_file = pack_out / "Various Artists - My Pack (Creator) [delete].osu"
        long_tags = " ".join(f"tag{i}" for i in range(250))
        init_file.write_text(
            "\n".join([
                "osu file format v14",
                "[General]",
                "AudioFilename: old.mp3",
                "[Metadata]",
                "Title: My Pack",
                "Artist: Various Artists",
                "Creator: Creator",
                "Version: delete",
                f"Tags:{long_tags}",
                "BeatmapID:9999",
                "[Events]",
                "//Background and Video events",
            ]),
            encoding="utf-8",
        )

        song_dir = tmp_path / "999 Kobaryo - Bookmaker"
        song_dir.mkdir()
        osu_src = song_dir / "Kobaryo - Bookmaker (Rachel) [Extra 180BPM].osu"
        osu_src.write_text(
            "\n".join([
                "osu file format v14",
                "[General]",
                "AudioFilename: track.mp3",
                "[Metadata]",
                "Artist: Kobaryo",
                "Title: Bookmaker",
                "Version: Extra 180BPM",
                "[Events]",
                "//Background and Video events",
                '0,0,"original_bg.png",0,0',
                "[HitObjects]",
                "64,192,1000,1,0,0:0:0:0:",
            ]),
            encoding="utf-8",
        )
        (song_dir / "track.mp3").write_bytes(b"mp3data")
        img_path = song_dir / "original_bg.png"
        Image.new("RGB", (2560, 1440), color=(10, 20, 30)).save(img_path)

        pack_file = tmp_path / "pack.json"
        add_map_to_pack(song_dir, osu_src, patron="DJ", pack_file=pack_file)

        out_dir, count = init_create_map(init_file, pack_file=pack_file)
        assert out_dir == pack_out.resolve()
        assert count == 1

        generated_osu = pack_out / (
            "Various Artists - My Pack (Creator) [[DJ] Kobaryo - Bookmaker (Rachel) [Extra]].osu"
        )
        assert generated_osu.exists()
        raw_bytes = generated_osu.read_bytes()
        assert b"\r\n" in raw_bytes
        content = raw_bytes.decode("utf-8")
        assert "BeatmapID: 0" in content
        assert "AudioFilename: BOOKMAKER.mp3" in content
        assert '0,0,"BOOKMAKER_bg.jpg",0,0' in content
        assert (pack_out / "BOOKMAKER.mp3").exists()
        with Image.open(pack_out / "BOOKMAKER_bg.jpg") as bg_out:
            assert bg_out.size == (1920, 1080)

        tags_line = next(line for line in content.splitlines() if line.startswith("Tags:"))
        assert len(tags_line) <= 850
