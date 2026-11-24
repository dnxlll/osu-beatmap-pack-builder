from pathlib import Path

from PIL import Image

from osu_pack_builder.application.add_map import add_map_to_pack
from osu_pack_builder.application.generate_pack import generate_pack
from osu_pack_builder.application.remove_map import remove_map_from_pack
from osu_pack_builder.application.update_map import clear_custom_versions, update_map_in_pack
from osu_pack_builder.infrastructure.pack_repository import PackRepository


class TestApplicationUseCases:
    def test_generate_pack_prefers_events_background_and_persists_paraphrase(
        self,
        tmp_path: Path,
    ) -> None:
        pack_out = tmp_path / "PackOut"
        pack_out.mkdir()
        init_file = pack_out / (
            "Various Artists - Very Long Pack Title For Testing Limits (MapperName) [delete].osu"
        )
        init_file.write_text(
            "osu file format v14\n[General]\nAudioFilename: x.mp3\n[Metadata]\nVersion: delete\n[Events]\n",
            encoding="utf-8",
        )

        song_dir = tmp_path / "100 Artist - LongTitle"
        song_dir.mkdir()
        osu_src = song_dir / (
            "Artist - LongSongTitleWithManyWords (VeryLongMapperName) [Extremely Long Difficulty Name].osu"
        )
        osu_src.write_text(
            "\n".join([
                "osu file format v14",
                "[General]",
                "AudioFilename: main.mp3",
                "[Events]",
                '0,0,"real_bg.png",0,0',
            ]),
            encoding="utf-8",
        )
        (song_dir / "main.mp3").write_bytes(b"audio")
        Image.new("RGB", (100, 100), color=(0, 0, 255)).save(song_dir / "aaa_unrelated.png")
        Image.new("RGB", (100, 100), color=(0, 255, 0)).save(song_dir / "real_bg.png")

        repo = PackRepository(tmp_path / "pack.json")
        add_map_to_pack(song_dir, osu_src, repository=repo, patron="SJ")

        called: list[str] = []

        def fake_paraphrase(idx: str, clave: str, orig: str, prefix: str) -> str:
            called.append(orig)
            return "[SJ] Short"

        out_dir, count = generate_pack(init_file, repository=repo, callback_parafraseo=fake_paraphrase)
        assert out_dir == pack_out.resolve()
        assert count == 1
        assert len(called) == 1
        assert repo.load()["1"]["__custom_version__"] == "[SJ] Short"

        bg_out = pack_out / "LONGSONGTITLEWITHMANYWORDS_bg.jpg"
        assert bg_out.exists()
        with Image.open(bg_out) as im:
            # Verify the green real_bg.png was chosen over aaa_unrelated.png
            r, g, b = im.getpixel((50, 50))
            assert g > 200 and b < 50

    def test_remove_map_from_pack(self, tmp_path: Path) -> None:
        repo = PackRepository(tmp_path / "pack.json")
        repo.save({"1": {"a.osu": "x"}, "2": {"b.osu": "y"}})

        updated = remove_map_from_pack("1", repo)
        assert "1" not in updated
        assert "2" in updated
        assert repo.load() == {"2": {"b.osu": "y"}}


    def test_update_map_in_pack_changes_difficulty_audio_and_pattern(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "200 Artist - Song"
        song_dir.mkdir()
        osu_1 = song_dir / "Artist - Song [Easy].osu"
        osu_1.write_text("[General]\nAudioFilename: normal.mp3\n", encoding="utf-8")
        osu_2 = song_dir / "Artist - Song [1.2x].osu"
        osu_2.write_text("[General]\nAudioFilename: spedup.mp3\n", encoding="utf-8")
        (song_dir / "normal.mp3").write_bytes(b"n")
        (song_dir / "spedup.mp3").write_bytes(b"s")
        (song_dir / "bg.jpg").write_bytes(b"img")

        repo = PackRepository(tmp_path / "pack.json")
        idx, _ = add_map_to_pack(song_dir, osu_1, repository=repo, patron="DJ")
        assert idx == "1"

        updated = update_map_in_pack(
            index="1",
            repository=repo,
            patron="SJ",
            custom_version="[SJ] Short 1.2x",
            folder=song_dir,
            selected_osu=osu_2,
        )
        entry = updated["1"]
        assert "Artist - Song [1.2x].osu" in entry
        assert "Artist - Song [Easy].osu" not in entry
        assert "spedup.mp3" in entry
        assert "normal.mp3" not in entry
        assert "bg.jpg" in entry
        assert entry["__pattern__"] == "SJ"
        assert entry["__custom_version__"] == "[SJ] Short 1.2x"

    def test_update_map_in_pack_metadata_only_when_offline(self, tmp_path: Path) -> None:
        repo = PackRepository(tmp_path / "pack.json")
        repo.save({"1": {"a.osu": "G:/missing/a.osu", "__pattern__": "DJ"}})

        updated = update_map_in_pack(
            index="1",
            repository=repo,
            patron="ANCHOR",
            custom_version="Custom",
        )
        assert updated["1"]["__pattern__"] == "ANCHOR"
        assert updated["1"]["__custom_version__"] == "Custom"

    def test_clear_custom_versions_removes_manual_overrides(self, tmp_path: Path) -> None:
        repo = PackRepository(tmp_path / "pack.json")
        repo.save({
            "1": {"a.osu": "x", "__custom_version__": "Manual 1"},
            "2": {"b.osu": "y"},
        })
        updated = clear_custom_versions(repo)
        assert "__custom_version__" not in updated["1"]
        assert repo.load()["1"] == {"a.osu": "x"}
