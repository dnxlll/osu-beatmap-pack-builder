from pathlib import Path

import pytest
from PIL import Image

from osu_pack_builder.infrastructure.media_processor import copy_audio, load_thumbnail, optimize_background
from osu_pack_builder.infrastructure.pack_repository import PackRepository
from osu_pack_builder.infrastructure.songs_scanner import filter_song_folders, list_song_folders


class TestPackRepository:
    def test_load_missing_and_corrupt(self, tmp_path: Path) -> None:
        repo = PackRepository(tmp_path / "pack.json")
        assert repo.load() == {}

        repo.pack_file.write_text("{broken", encoding="utf-8")
        assert repo.load() == {}

    def test_atomic_save_and_clear(self, tmp_path: Path) -> None:
        repo = PackRepository(tmp_path / "nested" / "pack.json")
        repo.save({"1": {"a.osu": "x"}, "bad": "ignored"})
        assert repo.load() == {"1": {"a.osu": "x"}}
        assert list(repo.pack_file.parent.glob("*.tmp")) == []

        repo.clear()
        assert repo.load() == {}

    def test_save_preserves_existing_file_on_serialization_error(self, tmp_path: Path) -> None:
        repo = PackRepository(tmp_path / "pack.json")
        repo.save({"1": {"ok": "yes"}})

        with pytest.raises(TypeError):
            repo.save({"1": {"bad": object()}})

        assert repo.load() == {"1": {"ok": "yes"}}
        assert list(tmp_path.glob("*.tmp")) == []

    def test_next_index(self) -> None:
        assert PackRepository.next_index({}) == "1"
        assert PackRepository.next_index({"2": {}, "7": {}}) == "8"


class TestMediaProcessor:
    def test_copy_audio(self, tmp_path: Path) -> None:
        src = tmp_path / "src.mp3"
        src.write_bytes(b"mp3")
        out = copy_audio(src, tmp_path, "OUT.mp3")
        assert out.exists()
        assert out.read_bytes() == b"mp3"

    def test_optimize_background_resizes_and_falls_back(self, tmp_path: Path) -> None:
        big = tmp_path / "big.png"
        Image.new("RGB", (3840, 2160), color=(255, 0, 0)).save(big)
        dest = optimize_background(big, tmp_path, "out_bg.jpg")
        with Image.open(dest) as im:
            assert im.size == (1920, 1080)

        broken = tmp_path / "broken.png"
        broken.write_bytes(b"not an image")
        fallback_dest = optimize_background(broken, tmp_path, "fallback_bg.jpg")
        assert fallback_dest.read_bytes() == b"not an image"



    def test_load_thumbnail_crops_and_handles_missing(self, tmp_path: Path) -> None:
        src = tmp_path / "bg.png"
        Image.new("RGB", (400, 200), color=(0, 128, 255)).save(src)
        thumb = load_thumbnail(src, size=(96, 60))
        assert thumb is not None
        assert thumb.size == (96, 60)

        assert load_thumbnail(tmp_path / "missing.png") is None

class TestSongsScanner:
    def test_list_and_filter_folders(self, tmp_path: Path) -> None:
        (tmp_path / "123 Kobaryo - Bookmaker").mkdir()
        (tmp_path / "456 Camellia - Ghost").mkdir()
        (tmp_path / "readme.txt").write_text("hi", encoding="utf-8")

        folders = list_song_folders(tmp_path)
        assert len(folders) == 2

        matches = filter_song_folders(folders, "kobaryo book")
        assert [f.name for f in matches] == ["123 Kobaryo - Bookmaker"]
        assert filter_song_folders(folders, "   ") == []
