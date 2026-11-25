"""Top header bar displaying the active osu! Songs directory."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from osu_pack_builder.ui.theme import COLOR_ACCENT_BLUE


class SongsHeader(QWidget):
    """Header bar with title, active Songs directory indicator, and folder picker button."""

    def __init__(
        self,
        songs_dir: Path,
        map_count: int,
        on_change_songs: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        title = QLabel("osu! BeatmapPack Builder")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        top_row.addWidget(title)
        top_row.addStretch()

        btn_change = QPushButton("Cambiar Songs...")
        btn_change.setObjectName("PrimaryBtn")
        btn_change.clicked.connect(on_change_songs)
        top_row.addWidget(btn_change)
        layout.addLayout(top_row)

        self.lbl_songs_dir = QLabel("")
        self.lbl_songs_dir.setStyleSheet(f"color: {COLOR_ACCENT_BLUE}; font-size: 12px;")
        layout.addWidget(self.lbl_songs_dir)
        self.update_songs_info(songs_dir, map_count)

    def update_songs_info(self, songs_dir: Path, map_count: int) -> None:
        """Refresh displayed Songs directory path and folder count."""
        self.lbl_songs_dir.setText(f"📁 Songs: {songs_dir} ({map_count} carpetas)")
