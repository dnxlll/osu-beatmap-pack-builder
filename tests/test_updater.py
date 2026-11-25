import io
import json
from pathlib import Path

import pytest

from osu_pack_builder.infrastructure.updater import check_latest_release, download_release_asset


class _FakeResponse:
    def __init__(self, payload: bytes, headers: dict[str, str] | None = None) -> None:
        self._stream = io.BytesIO(payload)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None


class TestUpdater:
    def test_check_latest_release_returns_info_when_newer(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = json.dumps({
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/dnxlll/osu-beatmap-pack-builder/releases/tag/v1.2.0",
            "body": "Mejoras de rendimiento",
            "assets": [
                {
                    "name": "osu-beatmap-pack-builder.exe",
                    "browser_download_url": "https://github.com/dnxlll/osu-beatmap-pack-builder/releases/download/v1.2.0/osu-beatmap-pack-builder.exe",
                }
            ],
        }).encode("utf-8")

        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda req, timeout=8.0: _FakeResponse(payload),
        )

        info = check_latest_release(current_version="1.0.0")
        assert info is not None
        assert info.version == "1.2.0"
        assert info.download_url is not None
        assert info.download_url.endswith(".exe")

    def test_check_latest_release_returns_none_when_up_to_date(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = json.dumps({"tag_name": "v1.0.0", "assets": []}).encode("utf-8")
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda req, timeout=8.0: _FakeResponse(payload),
        )
        assert check_latest_release(current_version="1.0.0") is None

    def test_download_release_asset_writes_file_and_reports_progress(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        data = b"MZfakeexe" * 10
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda req, timeout=30.0: _FakeResponse(
                data, headers={"Content-Length": str(len(data))}
            ),
        )
        progress: list[tuple[int, int]] = []
        dest = tmp_path / "update.exe"
        download_release_asset(
            "https://example.com/app.exe",
            dest,
            on_progress=lambda d, t: progress.append((d, t)),
        )
        assert dest.read_bytes() == data
        assert progress[-1] == (len(data), len(data))
